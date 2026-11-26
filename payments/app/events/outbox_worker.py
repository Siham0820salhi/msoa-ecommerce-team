"""
Background publisher: drains the transactional outbox into RabbitMQ.

Runs in a daemon thread started by the FastAPI lifespan. Nothing here is on
the HTTP request path, so a broker outage never affects payment responses.

Retry strategy: a failed batch leaves the rows in PENDING and the loop sleeps
with exponential backoff (OUTBOX_BACKOFF_MIN -> OUTBOX_BACKOFF_MAX). Events are
therefore published as soon as RabbitMQ comes back.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from typing import List, Optional

from app import config
from app.database import SessionLocal
from app.events.contract import is_valid_address
from app.events.orders_client import fetch_order_address
from app.events.publisher import PublishError, RabbitMQPublisher
from app.models.outbox import OutboxEvent

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_pending(db, limit: int) -> List[OutboxEvent]:
    return (
        db.query(OutboxEvent)
        .filter(OutboxEvent.status == "PENDING")
        .order_by(OutboxEvent.created_at)
        .limit(limit)
        .all()
    )


def enrich_with_address(event: dict) -> dict:
    """
    Add the delivery address when Orders can be reached.

    Best effort on purpose: if Orders is down the event is still published and
    the Shipping consumer resolves the address itself.
    """
    if is_valid_address(event.get("address")):
        return event
    address = fetch_order_address(event["orderId"])
    if address and is_valid_address(address):
        event["address"] = address
    return event


def publish_pending_once(
    publisher: Optional[RabbitMQPublisher] = None,
    session_factory=SessionLocal,
    batch_size: Optional[int] = None,
) -> int:
    """
    Publish one batch of pending events.

    Returns the number of events successfully published and confirmed.
    Raises PublishError if the broker is unavailable, so the caller can back
    off; rows stay PENDING in that case.
    """
    publisher = publisher or RabbitMQPublisher()
    batch_size = batch_size or config.OUTBOX_BATCH_SIZE
    published = 0

    db = session_factory()
    try:
        pending = fetch_pending(db, batch_size)
        for row in pending:
            event = json.loads(row.payload)
            event = enrich_with_address(event)
            row.attempts = (row.attempts or 0) + 1
            try:
                publisher.publish(event)
            except PublishError as exc:
                # Keep the row PENDING: it will be retried on the next tick.
                row.last_error = str(exc)[:500]
                db.commit()
                raise
            # Confirmed by the broker: mark as published.
            row.status = "PUBLISHED"
            row.published_at = _now_iso()
            row.last_error = None
            # Persist the enriched payload so the stored event matches what
            # was actually sent on the wire.
            row.payload = json.dumps(event, ensure_ascii=False)
            db.commit()
            published += 1
            logger.info("Published %s (%s)", row.id, row.event_type)
        return published
    finally:
        db.close()


class OutboxWorker:
    """Daemon thread looping over publish_pending_once() with backoff."""

    def __init__(self, session_factory=SessionLocal, publisher=None):
        self._session_factory = session_factory
        self._publisher = publisher or RabbitMQPublisher()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _run(self) -> None:
        backoff = config.OUTBOX_BACKOFF_MIN
        logger.info("Outbox publisher started")
        while not self._stop.is_set():
            try:
                count = publish_pending_once(
                    publisher=self._publisher,
                    session_factory=self._session_factory,
                )
                backoff = config.OUTBOX_BACKOFF_MIN  # success: reset backoff
                delay = 0.0 if count else config.OUTBOX_POLL_INTERVAL
            except PublishError as exc:
                logger.warning(
                    "RabbitMQ unavailable (%s). Events stay pending, retrying in %.0fs",
                    exc,
                    backoff,
                )
                delay = backoff
                backoff = min(backoff * 2, config.OUTBOX_BACKOFF_MAX)
            except Exception as exc:  # never let the loop die
                logger.exception("Unexpected outbox error: %s", exc)
                delay = backoff
                backoff = min(backoff * 2, config.OUTBOX_BACKOFF_MAX)
            # Interruptible sleep so shutdown is immediate.
            self._stop.wait(delay)
        self._publisher.close()
        logger.info("Outbox publisher stopped")

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="outbox-publisher", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

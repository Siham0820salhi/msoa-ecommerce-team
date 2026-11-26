"""
RabbitMQ consumer for shipment requests (LAB 4).

Runs as its own process, separately from the FastAPI application, so the
existing Shipping REST API is completely unaffected.

Delivery semantics: at-least-once with idempotent processing. This is NOT
exactly-once, and nothing here pretends it is. A message can be delivered more
than once (for example if the consumer dies between the database commit and
the acknowledgement); the idempotency ledger in handler.py makes the second
delivery a no-op.

Reliability properties:
  * durable queue, persistent messages
  * prefetch=1, so one message is handled at a time
  * manual acknowledgement, sent ONLY after the shipment is committed
  * transient failures -> retried, bounded by CONSUMER_MAX_ATTEMPTS
  * poison messages -> nack(requeue=False) -> dead-letter queue
"""

import json
import logging
import signal
import time
from typing import Optional

import pika
from pika.exceptions import AMQPError

from app import config
from app.database import SessionLocal, init_db
from app.events.handler import (
    PermanentEventError,
    TransientEventError,
    handle_payment_succeeded,
)

logger = logging.getLogger(__name__)


def queue_arguments() -> dict:
    """Must match the Payments publisher declaration exactly."""
    return {"x-dead-letter-exchange": config.RABBITMQ_DLX}


def _delivery_count(properties, method) -> int:
    """
    Approximate how many times this message has been delivered.

    Classic RabbitMQ queues do not expose a delivery counter, so we carry our
    own in a header and fall back to the redelivered flag.
    """
    headers = (properties.headers or {}) if properties else {}
    count = headers.get("x-delivery-attempts")
    if isinstance(count, int):
        return count
    return 1 if getattr(method, "redelivered", False) else 0


class ShipmentConsumer:
    def __init__(self, url: Optional[str] = None, queue: Optional[str] = None):
        self._url = url or config.RABBITMQ_URL
        self._queue = queue or config.RABBITMQ_QUEUE
        self._connection = None
        self._channel = None
        self._stopping = False

    # -- topology ------------------------------------------------------------

    def _declare(self) -> None:
        ch = self._channel
        # Dead-letter exchange + queue for messages that keep failing.
        ch.exchange_declare(
            exchange=config.RABBITMQ_DLX, exchange_type="fanout", durable=True
        )
        ch.queue_declare(queue=config.RABBITMQ_DLQ, durable=True)
        ch.queue_bind(queue=config.RABBITMQ_DLQ, exchange=config.RABBITMQ_DLX)
        # The work queue itself.
        ch.queue_declare(queue=self._queue, durable=True, arguments=queue_arguments())
        ch.basic_qos(prefetch_count=config.CONSUMER_PREFETCH)

    def connect(self) -> None:
        params = pika.URLParameters(self._url)
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._declare()
        logger.info(
            "Consumer connected, queue %s (DLQ %s)", self._queue, config.RABBITMQ_DLQ
        )

    # -- message handling ----------------------------------------------------

    def _republish_with_attempts(self, body: bytes, properties, attempts: int) -> None:
        """Put the message back on the queue with an incremented attempt counter."""
        headers = dict(properties.headers or {})
        headers["x-delivery-attempts"] = attempts
        self._channel.basic_publish(
            exchange="",
            routing_key=self._queue,
            body=body,
            properties=pika.BasicProperties(
                content_type=properties.content_type or "application/json",
                delivery_mode=2,
                message_id=properties.message_id,
                type=properties.type,
                headers=headers,
            ),
        )

    def on_message(self, channel, method, properties, body) -> None:
        delivery_tag = method.delivery_tag
        attempts = _delivery_count(properties, method) + 1

        # 1. Parse. A malformed body can never succeed -> dead-letter it.
        try:
            event = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            logger.error("Unparseable message, dead-lettering: %s", exc)
            channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
            return

        db = SessionLocal()
        try:
            result = handle_payment_succeeded(db, event)
            # 2. Acknowledge ONLY after the shipment is committed.
            channel.basic_ack(delivery_tag=delivery_tag)
            logger.info(
                "Event %s -> %s (shipment %s), acked",
                event.get("eventId"),
                result["status"],
                result.get("shipmentId"),
            )
        except PermanentEventError as exc:
            db.rollback()
            logger.error("Permanent failure, dead-lettering: %s", exc)
            channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        except TransientEventError as exc:
            db.rollback()
            if attempts >= config.CONSUMER_MAX_ATTEMPTS:
                logger.error(
                    "Giving up after %s attempts, dead-lettering: %s", attempts, exc
                )
                channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
            else:
                logger.warning(
                    "Transient failure (attempt %s/%s), retrying: %s",
                    attempts,
                    config.CONSUMER_MAX_ATTEMPTS,
                    exc,
                )
                # Small delay so a dead dependency is not hammered.
                time.sleep(config.CONSUMER_RETRY_DELAY)
                self._republish_with_attempts(body, properties, attempts)
                channel.basic_ack(delivery_tag=delivery_tag)
        except Exception as exc:  # unexpected: keep the message, do not ack
            db.rollback()
            logger.exception("Unexpected error, requeueing: %s", exc)
            channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
        finally:
            db.close()

    # -- lifecycle -----------------------------------------------------------

    def run(self) -> None:
        """Consume forever, reconnecting when the broker goes away."""
        backoff = 1.0
        while not self._stopping:
            try:
                self.connect()
                backoff = 1.0
                self._channel.basic_consume(
                    queue=self._queue, on_message_callback=self.on_message
                )
                logger.info("Waiting for messages. Press CTRL+C to stop.")
                self._channel.start_consuming()
            except AMQPError as exc:
                if self._stopping:
                    break
                logger.warning(
                    "Broker unavailable (%s). Reconnecting in %.0fs", exc, backoff
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            except KeyboardInterrupt:
                break
            finally:
                self._safe_close()

    def stop(self, *_args) -> None:
        self._stopping = True
        try:
            if self._channel is not None and self._channel.is_open:
                self._channel.stop_consuming()
        except Exception:
            pass

    def _safe_close(self) -> None:
        try:
            if self._connection is not None and self._connection.is_open:
                self._connection.close()
        except Exception:
            pass


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [shipping-consumer] %(message)s",
    )
    # Make sure the tables (shipments + processed_events) exist.
    init_db()
    consumer = ShipmentConsumer()
    signal.signal(signal.SIGINT, consumer.stop)
    signal.signal(signal.SIGTERM, consumer.stop)
    consumer.run()


if __name__ == "__main__":
    main()

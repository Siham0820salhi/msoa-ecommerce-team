"""
PaymentSucceeded -> Shipment.

Pure business logic, deliberately free of any RabbitMQ import so it can be
unit-tested without a broker. The consumer module owns the AMQP plumbing and
calls handle_payment_succeeded() for each delivery.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.events.orders_client import AddressUnavailable, fetch_order_address
from app.models.processed_event import ProcessedEvent
from app.models.shipment import Shipment
from app.schemas.shipment import AddressSchema, ShipmentCreate
from app.services import shipment_service

logger = logging.getLogger(__name__)

EVENT_TYPE_PAYMENT_SUCCEEDED = "PaymentSucceeded"


class PermanentEventError(Exception):
    """The message can never succeed: dead-letter it, do not retry."""


class TransientEventError(Exception):
    """A temporary problem: keep the message and retry it later."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def event_type_of(event: Dict[str, Any]) -> Optional[str]:
    """Accept both spellings: 'eventType' (lab brief) and 'type' (team contract)."""
    return event.get("eventType") or event.get("type")


def _valid_address(address: Any) -> bool:
    if not isinstance(address, dict):
        return False
    return all(
        isinstance(address.get(k), str) and address.get(k, "").strip()
        for k in ("name", "address", "city")
    )


def resolve_address(event: Dict[str, Any]) -> Dict[str, str]:
    """
    Use the address carried by the event, else fall back to Orders.

    Raises TransientEventError when Orders cannot be reached, so the message
    is retried rather than lost or turned into a shipment with fake data.
    """
    address = event.get("address")
    if _valid_address(address):
        return {
            "name": address["name"],
            "address": address["address"],
            "city": address["city"],
        }

    order_id = event["orderId"]
    logger.info("Event %s has no address, asking Orders", event.get("eventId"))
    try:
        fetched = fetch_order_address(order_id)
    except AddressUnavailable as exc:
        raise TransientEventError(str(exc)) from exc

    if not _valid_address(fetched):
        raise PermanentEventError(
            f"No usable delivery address available for order '{order_id}'"
        )
    return fetched


def validate(event: Any) -> None:
    """Reject structurally invalid messages permanently."""
    if not isinstance(event, dict):
        raise PermanentEventError("Message body is not a JSON object")
    etype = event_type_of(event)
    if etype != EVENT_TYPE_PAYMENT_SUCCEEDED:
        raise PermanentEventError(f"Unsupported event type: {etype!r}")
    if not event.get("eventId"):
        raise PermanentEventError("Message has no eventId")
    if not event.get("orderId"):
        raise PermanentEventError("Message has no orderId")


def handle_payment_succeeded(db: Session, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the shipment for a PaymentSucceeded event, exactly once.

    Returns a small result dict describing what happened:
      {"status": "CREATED"|"DUPLICATE", "shipmentId": ...}

    Raises TransientEventError (retry) or PermanentEventError (dead-letter).
    The caller acknowledges the message ONLY when this function returns.
    """
    validate(event)
    event_id = event["eventId"]
    order_id = event["orderId"]

    # 1. Same event already processed -> nothing to do (at-least-once delivery).
    already = db.get(ProcessedEvent, event_id)
    if already is not None:
        logger.info("Event %s already processed, skipping", event_id)
        return {"status": "DUPLICATE", "shipmentId": already.shipment_id}

    # 2. A shipment may already exist for this order (duplicate event with a
    #    different id, or a shipment created earlier through the REST API).
    existing = db.query(Shipment).filter(Shipment.order_id == order_id).first()
    if existing is not None:
        db.add(
            ProcessedEvent(
                event_id=event_id,
                event_type=EVENT_TYPE_PAYMENT_SUCCEEDED,
                order_id=order_id,
                shipment_id=existing.id,
                processed_at=_now_iso(),
            )
        )
        db.commit()
        logger.info("Shipment already exists for order %s, skipping", order_id)
        return {"status": "DUPLICATE", "shipmentId": existing.id}

    # 3. Resolve the delivery address (event first, Orders as fallback).
    address = resolve_address(event)

    # 4. Create the shipment through the existing service, so the status
    #    lifecycle and tracking-number format stay exactly as before.
    payload = ShipmentCreate(orderId=order_id, address=AddressSchema(**address))
    try:
        shipment = shipment_service.create_shipment(db, payload)
    except HTTPException as exc:
        if exc.status_code == 409:
            # Lost a race with another consumer/REST call: treat as duplicate.
            logger.info("Concurrent creation for order %s, treating as duplicate", order_id)
            row = db.query(Shipment).filter(Shipment.order_id == order_id).first()
            shipment_id = row.id if row else None
            db.add(
                ProcessedEvent(
                    event_id=event_id,
                    event_type=EVENT_TYPE_PAYMENT_SUCCEEDED,
                    order_id=order_id,
                    shipment_id=shipment_id,
                    processed_at=_now_iso(),
                )
            )
            db.commit()
            return {"status": "DUPLICATE", "shipmentId": shipment_id}
        raise TransientEventError(f"Shipping service error: {exc.detail}") from exc

    # 5. Record the event id so a redelivery is recognised as a duplicate.
    db.add(
        ProcessedEvent(
            event_id=event_id,
            event_type=EVENT_TYPE_PAYMENT_SUCCEEDED,
            order_id=order_id,
            shipment_id=shipment.id,
            processed_at=_now_iso(),
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TransientEventError(f"Could not record processed event: {exc}") from exc

    logger.info("Created shipment %s for order %s", shipment.id, order_id)
    return {"status": "CREATED", "shipmentId": shipment.id}

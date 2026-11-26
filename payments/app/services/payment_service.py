import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.events.contract import (
    EVENT_TYPE_PAYMENT_SUCCEEDED,
    build_payment_succeeded,
    new_event_id,
)
from app.models.outbox import OutboxEvent
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate

SUCCESS_STATUS = "SUCCESS"


def get_all_payments(db: Session) -> List[Payment]:
    return db.query(Payment).all()


def get_payment_by_order_id(db: Session, order_id: str) -> Optional[Payment]:
    return db.query(Payment).filter(Payment.order_id == order_id).first()


def _build_outbox_event(payment: Payment) -> OutboxEvent:
    """Create the outbox row carrying the PaymentSucceeded event."""
    event_id = new_event_id()
    payload = build_payment_succeeded(payment, event_id=event_id)
    return OutboxEvent(
        id=event_id,
        event_type=EVENT_TYPE_PAYMENT_SUCCEEDED,
        aggregate_id=payment.order_id,
        payload=json.dumps(payload, ensure_ascii=False),
        status="PENDING",
        attempts=0,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def create_payment(db: Session, data: PaymentCreate) -> Payment:
    """
    Create a payment and, when it succeeds, its PaymentSucceeded outbox event.

    The payment row and the outbox row are written in the SAME transaction and
    committed together, so it is impossible to end up with a successful payment
    whose shipment event was lost. Publishing to RabbitMQ happens later, in the
    background worker: the customer's response never waits for the broker or
    for the Shipping service.
    """
    status = "FAILED" if data.simulateFailure else SUCCESS_STATUS
    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=data.orderId,
        amount=data.amount if data.amount is not None else 0.0,
        method=data.method,
        status=status,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(payment)

    # Only a genuinely successful payment produces a shipment event.
    if status == SUCCESS_STATUS:
        db.add(_build_outbox_event(payment))

    try:
        db.commit()
        db.refresh(payment)
    except IntegrityError:
        db.rollback()
        raise
    return payment

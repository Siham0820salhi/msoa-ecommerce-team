import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.payment import Payment
from app.schemas.payment import PaymentCreate


def get_all_payments(db: Session) -> List[Payment]:
    return db.query(Payment).all()


def get_payment_by_order_id(db: Session, order_id: str) -> Optional[Payment]:
    return db.query(Payment).filter(Payment.order_id == order_id).first()


def create_payment(db: Session, data: PaymentCreate) -> Payment:
    status = "FAILED" if data.simulateFailure else "SUCCESS"
    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=data.orderId,
        amount=data.amount if data.amount is not None else 0.0,
        method=data.method,
        status=status,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(payment)
    try:
        db.commit()
        db.refresh(payment)
    except IntegrityError:
        db.rollback()
        raise
    return payment

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.outbox import OutboxEvent
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services import payment_service

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("", response_model=List[PaymentResponse])
def list_payments(db: Session = Depends(get_db)):
    payments = payment_service.get_all_payments(db)
    return payments


@router.get("/order/{orderId}", response_model=PaymentResponse)
def get_payment_by_order(orderId: str, db: Session = Depends(get_db)):
    payment = payment_service.get_payment_by_order_id(db, orderId)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment for order '{orderId}' not found",
        )
    return payment


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(data: PaymentCreate, db: Session = Depends(get_db)):
    try:
        payment = payment_service.create_payment(db, data)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment for order '{data.orderId}' already exists",
        )
    return payment


@router.get("/outbox", tags=["lab4-outbox"])
def list_outbox_events(status_filter: str | None = None, db: Session = Depends(get_db)):
    """
    Read-only view of the transactional outbox (LAB 4 observability).

    Lets you verify that an event stays PENDING while RabbitMQ is down and
    flips to PUBLISHED once it is reachable again. Not part of the LAB 3 REST
    contract; purely additive, no existing endpoint changed.
    """
    query = db.query(OutboxEvent)
    if status_filter:
        query = query.filter(OutboxEvent.status == status_filter.upper())
    rows = query.order_by(OutboxEvent.created_at).all()
    return [
        {
            "eventId": r.id,
            "eventType": r.event_type,
            "orderId": r.aggregate_id,
            "status": r.status,
            "attempts": r.attempts,
            "lastError": r.last_error,
            "createdAt": r.created_at,
            "publishedAt": r.published_at,
        }
        for r in rows
    ]

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
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

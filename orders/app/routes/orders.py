from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ApiError
from app.schemas.order import OrderCreate, OrderResponse, StatusUpdate
from app.security import Caller, get_caller
from app.services import order_service

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("", response_model=List[OrderResponse])
def list_orders(
    userId: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_caller),
):
    if not userId:
        raise ApiError(400, "Query parameter userId is required")
    if not caller.is_service and caller.user_id != userId:
        raise ApiError(403, "You can only list your own orders")
    return [order_service.to_response(o) for o in order_service.list_orders(db, userId)]


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_caller),
):
    return order_service.to_response(order_service.get_order(db, order_id, caller))


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_caller),
):
    return order_service.to_response(order_service.create_order(db, data, caller))


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_status(
    order_id: str,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_caller),
):
    order = order_service.update_status(db, order_id, body.status.upper(), caller)
    return order_service.to_response(order)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_caller),
):
    return order_service.to_response(order_service.cancel_order(db, order_id, caller))

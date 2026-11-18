import uuid
import random
import string
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app.models.shipment import Shipment
from app.schemas.shipment import ShipmentCreate, ShipmentResponse

VALID_TRANSITIONS = {
    "PREPARING": ["SHIPPED", "CANCELLED"],
    "SHIPPED": ["IN_TRANSIT", "CANCELLED"],
    "IN_TRANSIT": ["DELIVERED"],
    "DELIVERED": [],
    "CANCELLED": [],
}


def _generate_tracking_number() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=8))
    return f"MSOA-{suffix}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_shipment(db: Session, data: ShipmentCreate) -> ShipmentResponse:
    existing = db.query(Shipment).filter(Shipment.order_id == data.orderId).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Shipment already exists for orderId: {data.orderId}")

    now = _now_iso()
    shipment = Shipment(
        id=str(uuid.uuid4()),
        order_id=data.orderId,
        recipient_name=data.address.name,
        address=data.address.address,
        city=data.address.city,
        tracking_number=_generate_tracking_number(),
        status="PREPARING",
        created_at=now,
        updated_at=now,
    )
    db.add(shipment)
    try:
        db.commit()
        db.refresh(shipment)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Shipment already exists for orderId: {data.orderId}")

    return ShipmentResponse.from_orm_model(shipment)


def get_all_shipments(db: Session) -> List[ShipmentResponse]:
    rows = db.query(Shipment).all()
    return [ShipmentResponse.from_orm_model(r) for r in rows]


def get_shipment_by_order_id(db: Session, order_id: str) -> ShipmentResponse:
    row = db.query(Shipment).filter(Shipment.order_id == order_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Shipment not found for orderId: {order_id}")
    return ShipmentResponse.from_orm_model(row)


def update_shipment_status(db: Session, shipment_id: str, new_status: str) -> ShipmentResponse:
    row = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Shipment not found")

    allowed = VALID_TRANSITIONS.get(row.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status transition from {row.status} to {new_status}. Allowed transitions: {allowed}",
        )

    row.status = new_status
    row.updated_at = _now_iso()
    db.commit()
    db.refresh(row)
    return ShipmentResponse.from_orm_model(row)

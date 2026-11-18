from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.shipment import ShipmentCreate, ShipmentResponse, StatusUpdate
from app.services import shipment_service

router = APIRouter(prefix="/api/shipments", tags=["shipments"])


@router.get("", response_model=list[ShipmentResponse])
def list_shipments(db: Session = Depends(get_db)):
    return shipment_service.get_all_shipments(db)


@router.get("/order/{orderId}", response_model=ShipmentResponse)
def get_by_order_id(orderId: str, db: Session = Depends(get_db)):
    return shipment_service.get_shipment_by_order_id(db, orderId)


@router.post("", response_model=ShipmentResponse, status_code=201)
def create_shipment(data: ShipmentCreate, db: Session = Depends(get_db)):
    return shipment_service.create_shipment(db, data)


@router.patch("/{shipment_id}/status", response_model=ShipmentResponse)
def update_status(shipment_id: str, body: StatusUpdate, db: Session = Depends(get_db)):
    return shipment_service.update_shipment_status(db, shipment_id, body.status)

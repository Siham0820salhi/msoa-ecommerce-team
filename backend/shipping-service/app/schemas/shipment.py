from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class AddressSchema(BaseModel):
    name: str = Field(..., min_length=1, description="Recipient full name")
    address: str = Field(..., min_length=1, description="Delivery street address")
    city: str = Field(..., min_length=1, description="Delivery city")


class ShipmentCreate(BaseModel):
    orderId: str = Field(..., min_length=1, description="Unique order identifier")
    address: AddressSchema


class StatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, description="Target shipment status")


class ShipmentResponse(BaseModel):
    id: str
    orderId: str
    address: AddressSchema
    trackingNumber: str
    status: str
    createdAt: str
    updatedAt: str

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_model(cls, row) -> "ShipmentResponse":
        return cls(
            id=row.id,
            orderId=row.order_id,
            address=AddressSchema(
                name=row.recipient_name,
                address=row.address,
                city=row.city,
            ),
            trackingNumber=row.tracking_number,
            status=row.status,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )

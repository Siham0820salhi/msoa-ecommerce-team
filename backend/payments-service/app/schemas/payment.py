from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional

ALLOWED_METHODS = {"CARD", "CASH", "PAYPAL", "TRANSFER"}

class PaymentCreate(BaseModel):
    orderId: str = Field(..., min_length=1, description="Unique order identifier")
    amount: Optional[float] = Field(default=0.0, ge=0.0, description="Order total amount")
    method: str = Field(default="CARD", description="Payment method (CARD, CASH, etc.)")
    simulateFailure: Optional[bool] = Field(default=False, description="Simulate a failed payment")

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        upper_v = v.upper().strip()
        if upper_v not in ALLOWED_METHODS:
            raise ValueError(f"Invalid payment method: {v}. Allowed methods: {', '.join(sorted(ALLOWED_METHODS))}")
        return upper_v


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    orderId: str = Field(validation_alias="order_id", serialization_alias="orderId")
    amount: float
    method: str
    status: str
    createdAt: str = Field(validation_alias="created_at", serialization_alias="createdAt")

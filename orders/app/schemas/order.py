from typing import Annotated, List

from pydantic import BaseModel, Field, StringConstraints, field_validator

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CustomerIn(BaseModel):
    name: NonEmptyStr
    address: NonEmptyStr
    city: NonEmptyStr


class ItemIn(BaseModel):
    # Any "price"/"name" sent by the frontend is ignored: Catalog is the source of truth.
    productId: int
    quantity: int = Field(..., gt=0)


class OrderCreate(BaseModel):
    userId: NonEmptyStr
    customer: CustomerIn
    items: List[ItemIn] = Field(..., min_length=1)

    @field_validator("userId", mode="before")
    @classmethod
    def userid_to_str(cls, v):
        # Accept numeric ids sent by some Auth implementations
        return str(v) if isinstance(v, int) and not isinstance(v, bool) else v


class StatusUpdate(BaseModel):
    status: NonEmptyStr


class CustomerOut(BaseModel):
    name: str
    address: str
    city: str


class ItemOut(BaseModel):
    productId: int
    name: str
    price: float
    quantity: int


class OrderResponse(BaseModel):
    id: str
    userId: str
    customer: CustomerOut
    items: List[ItemOut]
    total: float
    status: str
    createdAt: str

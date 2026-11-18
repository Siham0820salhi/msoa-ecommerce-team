from sqlalchemy import Column, String, CheckConstraint
from app.database import Base


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(String, primary_key=True)
    order_id = Column(String, nullable=False, unique=True)
    recipient_name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    tracking_number = Column(String, nullable=False, unique=True)
    status = Column(
        String,
        nullable=False,
        default="PREPARING",
    )
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PREPARING','SHIPPED','IN_TRANSIT','DELIVERED','CANCELLED')",
            name="status_check",
        ),
    )

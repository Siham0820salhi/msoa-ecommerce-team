from sqlalchemy import Column, String, Float, CheckConstraint
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    order_id = Column(String, nullable=False, unique=True)
    amount = Column(Float, nullable=False)
    method = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("amount >= 0", name="check_amount_non_negative"),
        CheckConstraint(
            "status IN ('SUCCESS','FAILED','PENDING','REFUNDED')",
            name="check_status_valid",
        ),
    )

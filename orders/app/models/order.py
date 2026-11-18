from sqlalchemy import Column, String, Float, Integer, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    customer_name = Column(String, nullable=False)
    customer_address = Column(String, nullable=False)
    customer_city = Column(String, nullable=False)
    total = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    # 1 once the stock of this order has been given back to Inventory (guarantees a single release)
    stock_released = Column(Integer, nullable=False, default=0)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    items = relationship(
        "OrderItem",
        cascade="all, delete-orphan",
        order_by="OrderItem.id",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("total >= 0", name="check_total_non_negative"),
        CheckConstraint(
            "status IN ('PENDING_PAYMENT','PAID','SHIPPED','DELIVERED','CANCELLED')",
            name="check_status_valid",
        ),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)  # real price taken from Catalog at order time
    quantity = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_quantity_positive"),
        CheckConstraint("price >= 0", name="check_price_non_negative"),
    )

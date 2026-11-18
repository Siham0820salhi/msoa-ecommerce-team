import logging
import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app import config
from app.clients import catalog_client, inventory_client, shipping_client
from app.errors import ApiError
from app.models.order import Order, OrderItem
from app.schemas.order import OrderCreate
from app.security import Caller
from app.services import status as st

logger = logging.getLogger("orders")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_response(order: Order) -> dict:
    return {
        "id": order.id,
        "userId": order.user_id,
        "customer": {
            "name": order.customer_name,
            "address": order.customer_address,
            "city": order.customer_city,
        },
        "items": [
            {
                "productId": i.product_id,
                "name": i.name,
                "price": i.price,
                "quantity": i.quantity,
            }
            for i in order.items
        ],
        "total": order.total,
        "status": order.status,
        "createdAt": order.created_at,
    }


def _stock_items(order: Order) -> List[dict]:
    return [{"productId": i.product_id, "quantity": i.quantity} for i in order.items]


def get_order_or_404(db: Session, order_id: str) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise ApiError(404, f"Order not found: {order_id}")
    return order


def assert_access(caller: Caller, order: Order) -> None:
    """An order is only visible to its owner (services are trusted)."""
    if caller.is_service:
        return
    if caller.user_id != order.user_id:
        raise ApiError(403, "You do not have access to this order")


# ---------------------------------------------------------------- queries
def list_orders(db: Session, user_id: str) -> List[Order]:
    return (
        db.query(Order)
        .filter(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .all()
    )


def get_order(db: Session, order_id: str, caller: Caller) -> Order:
    order = get_order_or_404(db, order_id)
    assert_access(caller, order)
    return order


# ---------------------------------------------------------------- creation
def create_order(db: Session, data: OrderCreate, caller: Caller) -> Order:
    if not caller.is_service and caller.user_id != data.userId:
        raise ApiError(403, "userId does not match the authenticated user")

    # 1) merge duplicated products: [{1,2},{1,3}] -> {1: 5}
    wanted: dict[int, int] = {}
    for item in data.items:
        wanted[item.productId] = wanted.get(item.productId, 0) + item.quantity

    # 2) real name and price from Catalog (never from the frontend)
    lines = []
    for product_id, quantity in wanted.items():
        product = catalog_client.get_product(product_id)
        lines.append(
            {
                "productId": product_id,
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
            }
        )
    total = round(sum(line["price"] * line["quantity"] for line in lines), 2)

    # 3) reserve the stock (atomic in Inventory). 409 -> the order is NOT created.
    stock_items = [
        {"productId": line["productId"], "quantity": line["quantity"]} for line in lines
    ]
    inventory_client.reserve(stock_items)

    # 4) save the order; if that fails, compensate by releasing the stock
    now = _now()
    order = Order(
        id=str(uuid.uuid4()),
        user_id=data.userId,
        customer_name=data.customer.name,
        customer_address=data.customer.address,
        customer_city=data.customer.city,
        total=total,
        status=st.PENDING_PAYMENT,
        stock_released=0,
        created_at=now,
        updated_at=now,
        items=[
            OrderItem(
                product_id=line["productId"],
                name=line["name"],
                price=line["price"],
                quantity=line["quantity"],
            )
            for line in lines
        ],
    )
    try:
        db.add(order)
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        logger.exception("Could not save order, releasing the reserved stock")
        try:
            inventory_client.release(stock_items)
        except ApiError:
            logger.error("Compensation failed: stock %s must be released manually", stock_items)
        raise ApiError(500, "Could not save the order")
    return order


# ---------------------------------------------------------------- cancellation
def cancel_order(db: Session, order_id: str, caller: Caller) -> Order:
    order = get_order_or_404(db, order_id)
    assert_access(caller, order)

    if order.status == st.SHIPPED or order.status == st.DELIVERED:
        raise ApiError(409, "Cannot cancel an order that has already been shipped")
    if order.status not in st.CANCELLABLE:
        raise ApiError(409, f"Order cannot be cancelled (status: {order.status})")

    # A paid order may already have a shipment: ask Shipping before giving the stock back.
    if order.status == st.PAID and config.SHIPPING_CHECK_ON_CANCEL:
        shipment_status = shipping_client.get_shipment_status(order.id)
        if shipment_status not in (None, "PREPARING", "CANCELLED"):
            raise ApiError(409, "Cannot cancel an order that has already been shipped")

    # Claim the release atomically so that Inventory.release is called ONCE per order,
    # even with two simultaneous cancel requests.
    claimed = (
        db.query(Order)
        .filter(
            Order.id == order.id,
            Order.stock_released == 0,
            Order.status.in_(st.CANCELLABLE),
        )
        .update({"stock_released": 1, "updated_at": _now()}, synchronize_session=False)
    )
    db.commit()
    if claimed != 1:
        raise ApiError(409, "Order is already cancelled or being cancelled")

    try:
        inventory_client.release(_stock_items(order))
    except ApiError:
        # Nothing was given back: undo the claim so the user can retry.
        db.query(Order).filter(Order.id == order.id).update(
            {"stock_released": 0}, synchronize_session=False
        )
        db.commit()
        raise

    db.query(Order).filter(Order.id == order.id).update(
        {"status": st.CANCELLED, "updated_at": _now()}, synchronize_session=False
    )
    db.commit()
    db.refresh(order)
    return order


# ---------------------------------------------------------------- status update
def update_status(db: Session, order_id: str, new_status: str, caller: Caller) -> Order:
    if new_status not in st.ALL_STATUSES:
        raise ApiError(
            400, f"Invalid status: {new_status}. Allowed: {', '.join(st.ALL_STATUSES)}"
        )

    order = get_order_or_404(db, order_id)
    assert_access(caller, order)

    # Cancelling always goes through the same path (stock release, shipment check).
    if new_status == st.CANCELLED:
        return cancel_order(db, order_id, caller)

    if not st.can_transition(order.status, new_status):
        raise ApiError(409, f"Invalid transition: {order.status} -> {new_status}")

    if (
        new_status == st.PAID
        and config.PAID_REQUIRES_SERVICE_KEY
        and not caller.is_service
    ):
        raise ApiError(403, "Only the Payments service can mark an order as PAID")

    current = order.status
    updated = (
        db.query(Order)
        .filter(Order.id == order.id, Order.status == current)
        .update({"status": new_status, "updated_at": _now()}, synchronize_session=False)
    )
    db.commit()
    if updated != 1:
        raise ApiError(409, "Order status was changed by another request, please retry")
    db.refresh(order)
    return order

"""Order status machine (no dependency: easy to test).

Same rules as the frontend mock (src/services/orderService.js).
"""

PENDING_PAYMENT = "PENDING_PAYMENT"
PAID = "PAID"
SHIPPED = "SHIPPED"
DELIVERED = "DELIVERED"
CANCELLED = "CANCELLED"

ALL_STATUSES = (PENDING_PAYMENT, PAID, SHIPPED, DELIVERED, CANCELLED)

TRANSITIONS = {
    PENDING_PAYMENT: (PAID, CANCELLED),
    PAID: (SHIPPED, CANCELLED),
    SHIPPED: (DELIVERED,),
    DELIVERED: (),
    CANCELLED: (),
}

# Statuses from which an order may be cancelled (a shipped order never can)
CANCELLABLE = (PENDING_PAYMENT, PAID)


def can_transition(current: str, new: str) -> bool:
    return new in TRANSITIONS.get(current, ())

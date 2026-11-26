"""
PaymentSucceeded event contract (LAB 4).

The shape below is deliberately a SUPERSET of two specifications:

  * the LAB 4 assignment brief, which requires
    eventId / eventType / paymentId / orderId / amount / method / occurredAt
  * the team contract in docs/lab4/LAB4_contracts.md (merged in PR #8), which
    requires eventId / type / orderId / address / occurredAt

"eventType" and "type" always carry the same value, so a consumer written
against either specification can read these messages.

No sensitive payment data (card number, PAN, CVV, token, payer identity) is
ever included: the event carries only the amount, the method label and the
identifiers needed to prepare a shipment.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

EVENT_TYPE_PAYMENT_SUCCEEDED = "PaymentSucceeded"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_event_id() -> str:
    return str(uuid.uuid4())


def build_payment_succeeded(
    payment,
    event_id: Optional[str] = None,
    address: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build the PaymentSucceeded payload for a successful Payment row."""
    event: Dict[str, Any] = {
        "eventId": event_id or new_event_id(),
        # Both spellings, same value - see module docstring.
        "eventType": EVENT_TYPE_PAYMENT_SUCCEEDED,
        "type": EVENT_TYPE_PAYMENT_SUCCEEDED,
        "paymentId": payment.id,
        "orderId": payment.order_id,
        "amount": payment.amount,
        "method": payment.method,
        "occurredAt": payment.created_at or _now_iso(),
    }
    # Enriched later by the outbox worker when Orders can be reached; the
    # consumer falls back to its own Orders lookup when it is absent.
    if address:
        event["address"] = address
    return event


def is_valid_address(address: Any) -> bool:
    """A usable delivery address has all three non-empty parts."""
    if not isinstance(address, dict):
        return False
    return all(
        isinstance(address.get(k), str) and address.get(k, "").strip()
        for k in ("name", "address", "city")
    )

"""
Fallback lookup of the delivery address from the Orders service.

Used only when a PaymentSucceeded event arrives without an address (for
instance because Orders was unreachable on the Payments side when the event
was published).
"""

import logging
from typing import Dict, Optional
from urllib.parse import quote

import httpx

from app import config

logger = logging.getLogger(__name__)


class AddressUnavailable(RuntimeError):
    """Raised when the address cannot be resolved right now (transient)."""


def fetch_order_address(order_id: str) -> Optional[Dict[str, str]]:
    """
    GET Orders /api/orders/{orderId} and extract the customer address.

    Raises AddressUnavailable on a transient problem (Orders down, 5xx), so the
    caller can retry the message instead of discarding it. Returns None when
    Orders positively states the order does not exist (404), which is a
    permanent condition for this message.
    """
    url = f"{config.ORDERS_URL}/api/orders/{quote(order_id, safe='')}"
    try:
        response = httpx.get(
            url,
            timeout=config.ORDERS_TIMEOUT,
            headers={
                "Accept": "application/json",
                # Orders authenticates internal callers with a shared secret.
                "X-Service-Key": config.INTERNAL_API_KEY,
            },
        )
    except Exception as exc:
        raise AddressUnavailable(f"Orders unreachable: {exc}") from exc

    if response.status_code == 404:
        logger.warning("Orders has no order %s", order_id)
        return None
    if response.status_code != 200:
        raise AddressUnavailable(f"Orders returned {response.status_code}")

    try:
        customer = response.json()["customer"]
        return {
            "name": customer["name"],
            "address": customer["address"],
            "city": customer["city"],
        }
    except (ValueError, KeyError, TypeError) as exc:
        raise AddressUnavailable(f"Orders returned an unusable payload: {exc}") from exc

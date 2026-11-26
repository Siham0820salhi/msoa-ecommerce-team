"""
Best-effort read of the delivery address from the Orders service.

This is called by the BACKGROUND outbox worker, never from the HTTP request
path, so a slow or unavailable Orders service can never delay the customer's
payment response.
"""

import logging
from typing import Dict, Optional
from urllib.parse import quote

import httpx

from app import config

logger = logging.getLogger(__name__)


def fetch_order_address(order_id: str) -> Optional[Dict[str, str]]:
    """
    GET Orders /api/orders/{orderId} and extract the customer address.

    Returns None on any failure: the event is still published without the
    address, and the Shipping consumer resolves it on its side.
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
    except Exception as exc:  # network error, DNS, timeout, ...
        logger.warning("Orders unreachable for address of %s: %s", order_id, exc)
        return None

    if response.status_code != 200:
        logger.warning(
            "Orders returned %s for address of %s", response.status_code, order_id
        )
        return None

    try:
        customer = response.json()["customer"]
        return {
            "name": customer["name"],
            "address": customer["address"],
            "city": customer["city"],
        }
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Orders returned an unusable payload for %s: %s", order_id, exc)
        return None

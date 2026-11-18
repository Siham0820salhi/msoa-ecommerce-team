from typing import Optional
from urllib.parse import quote

from app import config
from app.clients.base import call
from app.errors import ApiError


def get_shipment_status(order_id: str) -> Optional[str]:
    """GET Shipping /api/shipments/order/{orderId} -> shipment status, or None if no shipment."""
    response = call(
        "Shipping",
        "GET",
        f"{config.SHIPPING_URL}/api/shipments/order/{quote(order_id, safe='')}",
        headers={"Accept": "application/json"},
    )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise ApiError(502, "Shipping service returned an unexpected response")
    try:
        return str(response.json()["status"])
    except (ValueError, KeyError, TypeError):
        raise ApiError(502, "Shipping service returned an invalid shipment")

from app import config
from app.clients.base import call, error_message
from app.errors import ApiError


def reserve(items: list[dict]) -> None:
    """POST Inventory /api/inventory/reserve. Atomic on Inventory's side (all or nothing)."""
    response = call(
        "Inventory",
        "POST",
        f"{config.INVENTORY_URL}/api/inventory/reserve",
        json={"items": items},
    )
    if response.status_code == 200:
        return
    if response.status_code in (404, 409):
        raise ApiError(response.status_code, error_message(response, "Stock reservation refused"))
    raise ApiError(502, "Inventory service returned an unexpected response")


def release(items: list[dict]) -> None:
    """POST Inventory /api/inventory/release. Must be called only once per cancelled order."""
    response = call(
        "Inventory",
        "POST",
        f"{config.INVENTORY_URL}/api/inventory/release",
        json={"items": items},
    )
    if response.status_code == 200:
        return
    raise ApiError(502, error_message(response, "Inventory could not release the stock"))

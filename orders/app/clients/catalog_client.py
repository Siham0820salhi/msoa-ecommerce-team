from app import config
from app.clients.base import call
from app.errors import ApiError


def get_product(product_id: int) -> dict:
    """GET Catalog /products/{id} -> {"id", "name", "price"} (the real price, never the frontend's)."""
    response = call(
        "Catalog",
        "GET",
        f"{config.CATALOG_URL}/products/{product_id}",
        headers={"Accept": "application/json"},
    )
    if response.status_code == 404:
        raise ApiError(404, f"Product not found: {product_id}")
    if response.status_code != 200:
        raise ApiError(502, "Catalog service returned an unexpected response")

    try:
        data = response.json()
        name = str(data["name"])
        price = float(data["price"])
    except (ValueError, KeyError, TypeError):
        raise ApiError(502, "Catalog service returned an invalid product")
    if price < 0:
        raise ApiError(502, "Catalog service returned an invalid price")
    return {"id": product_id, "name": name, "price": price}

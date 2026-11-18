from app import config
from app.clients.base import call
from app.errors import ApiError


def verify_token(authorization: str) -> dict:
    """GET Auth /api/auth/me -> {"id": str, "role": str | None}."""
    response = call(
        "Auth",
        "GET",
        f"{config.AUTH_URL}/api/auth/me",
        headers={"Authorization": authorization, "Accept": "application/json"},
    )
    if response.status_code in (401, 403):
        raise ApiError(401, "Invalid or expired token")
    if response.status_code != 200:
        raise ApiError(502, "Auth service returned an unexpected response")

    try:
        data = response.json()
    except ValueError:
        raise ApiError(502, "Auth service returned an invalid response")

    user = data.get("user", data) if isinstance(data, dict) else None
    if not isinstance(user, dict) or user.get("id") in (None, ""):
        raise ApiError(502, "Auth service returned an invalid user")
    return {"id": str(user["id"]), "role": user.get("role")}

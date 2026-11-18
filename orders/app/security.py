import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import Header

from app import config
from app.clients import auth_client
from app.errors import ApiError


@dataclass(frozen=True)
class Caller:
    """Who is calling Orders: an end user (user_id) or another trusted service."""

    user_id: Optional[str] = None
    is_service: bool = False


def get_caller(
    authorization: Optional[str] = Header(default=None),
    x_service_key: Optional[str] = Header(default=None),
) -> Caller:
    # Service-to-service call (Payments, Shipping): shared secret.
    if x_service_key is not None:
        if secrets.compare_digest(x_service_key.encode(), config.INTERNAL_API_KEY.encode()):
            return Caller(is_service=True)
        raise ApiError(401, "Invalid service key")

    # DEV ONLY: Auth service not available.
    if config.AUTH_MODE == "disabled":
        return Caller(is_service=True)

    # End user: Bearer token validated by the Auth service.
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "Authentication required")
    user = auth_client.verify_token(authorization)
    return Caller(user_id=user["id"])

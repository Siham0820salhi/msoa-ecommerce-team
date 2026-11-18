import httpx

from app import config
from app.errors import ApiError


def call(service: str, method: str, url: str, **kwargs) -> httpx.Response:
    """HTTP call to another microservice. Network failure -> 503 (CONTRACT.md, rule 7)."""
    try:
        return httpx.request(method, url, timeout=config.HTTP_TIMEOUT, **kwargs)
    except httpx.RequestError:
        raise ApiError(503, f"{service} service unavailable")


def error_message(response: httpx.Response, default: str) -> str:
    """Reads the {"message": ...} (or FastAPI {"detail": ...}) of an error response."""
    try:
        data = response.json()
    except ValueError:
        return default
    if isinstance(data, dict):
        message = data.get("message") or data.get("detail")
        if isinstance(message, str) and message:
            return message
    return default

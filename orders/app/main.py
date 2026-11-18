import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config
from app.database import engine, Base
from app.errors import ApiError
from app.routes.orders import router as orders_router
import app.models.order  # noqa: F401

logger = logging.getLogger("orders")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if config.AUTH_MODE == "disabled":
        logger.warning("AUTH_MODE=disabled: authentication is OFF (development only)")
    yield


app = FastAPI(
    title="Orders Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# All errors use the team format {"message": "..."} (the frontend reads error.message).
@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"message": str(exc.detail)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    message = "Invalid request"
    errors = exc.errors()
    if errors:
        first = errors[0]
        where = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = f"Invalid request: {where + ': ' if where else ''}{first.get('msg', '')}"
    return JSONResponse(status_code=400, content={"message": message})


app.include_router(orders_router)


@app.get("/health")
def health():
    return {"service": "orders", "status": "UP"}


if __name__ == "__main__":
    import uvicorn
    from app.config import PORT
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=True)

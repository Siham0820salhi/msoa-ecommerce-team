from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.database import engine, Base, init_db
from app.events.outbox_worker import OutboxWorker
from app.routes.payments import router as payments_router
import app.models.payment  # noqa: F401
import app.models.outbox  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise DB from schema.sql + seed.sql (lab-provided files)
    init_db()
    # LAB 4: background publisher draining the transactional outbox.
    # Disabled with OUTBOX_PUBLISHER_ENABLED=false (used by the test suite so
    # tests never reach for a real broker).
    worker = None
    if config.OUTBOX_PUBLISHER_ENABLED:
        worker = OutboxWorker()
        worker.start()
    try:
        yield
    finally:
        if worker is not None:
            worker.stop()


app = FastAPI(
    title="Payments Service",
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

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": str(exc.detail), "detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"message": "Invalid request format", "detail": jsonable_encoder(exc.errors())}
    )

app.include_router(payments_router)


@app.get("/health")
def health():
    return {"service": "payments", "status": "UP"}


if __name__ == "__main__":
    import uvicorn
    from app.config import PORT
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=True)

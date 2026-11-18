from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routes.payments import router as payments_router

# Import models so SQLAlchemy registers them before create_all
import app.models.payment  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Payments Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(payments_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "payments-service"}


if __name__ == "__main__":
    import uvicorn
    from app.config import PORT

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=True)

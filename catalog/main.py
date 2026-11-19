import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

DB_PATH = Path(__file__).parent / "catalog.db"
DEFAULT_CURRENCY = "MAD"
COLUMNS = "id, name, category, price, image, description"

app = FastAPI(title="Catalog Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"message": "Invalid request"})


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"message": str(exc.detail)})


def to_v1(row):
    """v1 : price reste un nombre. Champ ajouté : currency (rétrocompatible)."""
    data = dict(row)
    data["currency"] = DEFAULT_CURRENCY
    return data


def to_v2(row):
    """v2 : price devient un objet {amount, currency}."""
    data = dict(row)
    data["price"] = {"amount": data["price"], "currency": DEFAULT_CURRENCY}
    return data


def fetch_all():
    conn = get_conn()
    try:
        return conn.execute(f"SELECT {COLUMNS} FROM products ORDER BY id").fetchall()
    finally:
        conn.close()


def fetch_one(product_id: int):
    conn = get_conn()
    try:
        return conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (product_id,)
        ).fetchone()
    finally:
        conn.close()


def mark_deprecated(response: Response):
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</v2/products>; rel="successor-version"'


@app.get("/health")
def health():
    return {"service": "catalog", "status": "UP"}


# ---------- v1 : price reste un nombre ----------
@app.get("/products")
def list_products(response: Response):
    mark_deprecated(response)
    return [to_v1(r) for r in fetch_all()]


@app.get("/products/{product_id}")
def get_product(product_id: int, response: Response):
    row = fetch_one(product_id)
    if row is None:
        return JSONResponse(status_code=404, content={"message": "Product not found"})
    mark_deprecated(response)
    return to_v1(row)


# ---------- v2 : price = {amount, currency} ----------
@app.get("/v2/products")
def list_products_v2():
    return [to_v2(r) for r in fetch_all()]


@app.get("/v2/products/{product_id}")
def get_product_v2(product_id: int):
    row = fetch_one(product_id)
    if row is None:
        return JSONResponse(status_code=404, content={"message": "Product not found"})
    return to_v2(row)
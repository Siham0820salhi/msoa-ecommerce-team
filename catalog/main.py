import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

DB_PATH = Path(__file__).parent / "catalog.db"

app = FastAPI(title="Catalog Service", version="1.0.0")

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


@app.get("/health")
def health():
    return {"service": "catalog", "status": "UP"}


@app.get("/products")
def list_products():
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, category, price, image, description "
            "FROM products ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/products/{product_id}")
def get_product(product_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, name, category, price, image, description "
            "FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return JSONResponse(status_code=404, content={"message": "Product not found"})
    return dict(row)
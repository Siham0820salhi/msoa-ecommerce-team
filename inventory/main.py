import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).parent / "inventory.db"

app = FastAPI(title="Inventory Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Modèles ----------
class Item(BaseModel):
    productId: int
    quantity: int = Field(gt=0)


class ItemsRequest(BaseModel):
    items: list[Item] = Field(min_length=1)


# ---------- Erreurs (format {"message": ...} attendu par apiClient.js) ----------
class ApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status, content={"message": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"message": "Invalid request: productId and quantity > 0 required"},
    )


# ---------- Utilitaires ----------
def get_conn() -> sqlite3.Connection:
    # isolation_level=None : on gère les transactions nous-mêmes (BEGIN/COMMIT)
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def merge_items(items: list[Item]) -> dict[int, int]:
    """Fusionne les doublons : [{1,2},{1,3}] -> {1: 5}"""
    merged: dict[int, int] = {}
    for it in items:
        merged[it.productId] = merged.get(it.productId, 0) + it.quantity
    return merged


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- Endpoints ----------
@app.get("/health")
def health():
    return {"service": "inventory", "status": "UP"}


@app.get("/api/inventory/{product_id}")
def get_stock(product_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT quantity FROM stock WHERE product_id = ?", (product_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise ApiError(404, f"Unknown product: {product_id}")
    return {"productId": product_id, "stock": row["quantity"]}


@app.post("/api/inventory/check")
def check(req: ItemsRequest):
    wanted = merge_items(req.items)
    conn = get_conn()
    try:
        for pid, qty in wanted.items():
            row = conn.execute(
                "SELECT quantity FROM stock WHERE product_id = ?", (pid,)
            ).fetchone()
            if row is None or row["quantity"] < qty:
                return {"available": False}
        return {"available": True}
    finally:
        conn.close()


@app.post("/api/inventory/reserve")
def reserve(req: ItemsRequest):
    """Réservation ATOMIQUE : tout ou rien."""
    wanted = merge_items(req.items)
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")  # verrou en écriture : évite les courses
        try:
            # 1) Vérifier TOUS les produits avant de modifier quoi que ce soit
            for pid, qty in wanted.items():
                row = conn.execute(
                    "SELECT quantity FROM stock WHERE product_id = ?", (pid,)
                ).fetchone()
                if row is None:
                    raise ApiError(404, f"Unknown product: {pid}")
                if row["quantity"] < qty:
                    raise ApiError(
                        409,
                        f"Insufficient stock for product {pid} "
                        f"(requested {qty}, available {row['quantity']})",
                    )
            # 2) Tout est OK : décrémenter
            ts = now_iso()
            for pid, qty in wanted.items():
                conn.execute(
                    "UPDATE stock SET quantity = quantity - ?, updated_at = ? "
                    "WHERE product_id = ?",
                    (qty, ts, pid),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return {"success": True}


@app.post("/api/inventory/release")
def release(req: ItemsRequest):
    """Remet le stock (annulation). Atomique aussi."""
    wanted = merge_items(req.items)
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for pid in wanted:
                row = conn.execute(
                    "SELECT 1 FROM stock WHERE product_id = ?", (pid,)
                ).fetchone()
                if row is None:
                    raise ApiError(404, f"Unknown product: {pid}")
            ts = now_iso()
            for pid, qty in wanted.items():
                conn.execute(
                    "UPDATE stock SET quantity = quantity + ?, updated_at = ? "
                    "WHERE product_id = ?",
                    (qty, ts, pid),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return {"success": True}
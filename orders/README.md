# Orders Microservice

FastAPI microservice that creates and manages customer orders in the MSOA E-commerce application. **Orders is the orchestrator** of the order workflow (CONTRACT.md, section 5): it checks the user, gets the real prices from Catalog, reserves the stock in Inventory, and gives the stock back on cancellation.

## Overview
- **Port**: 8084
- **Database**: SQLite (`orders.db`, created automatically at startup, never committed)
- **Technology**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn, httpx
- **Swagger**: [http://localhost:8084/docs](http://localhost:8084/docs)
- **Contract**: `docs/contract/03_orders.md`

## Installation & Launch

```bash
cd orders
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # optional, defaults already match the contract
uvicorn app.main:app --host 0.0.0.0 --port 8084 --reload
```

Recommended start order: Auth, Catalog, Inventory, **Orders**, Payments, Shipping, then `npm run dev`.
Then, in `src/config/backend.js`, set `ORDERS: "rest"` only when the service is tested.

> Auth not ready yet? Start with `AUTH_MODE=disabled` (development only, no authentication at all).

## Configuration (`.env`)

| Variable | Default | Role |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./orders.db` | Orders database |
| `PORT` | `8084` | Port |
| `AUTH_URL` / `CATALOG_URL` / `INVENTORY_URL` / `SHIPPING_URL` | `localhost:8081 / 8082 / 8083 / 8086` | Services called by Orders |
| `HTTP_TIMEOUT` | `5` | Timeout (seconds) of calls to other services |
| `AUTH_MODE` | `remote` | `remote` = validate the token with Auth. `disabled` = **dev only** |
| `INTERNAL_API_KEY` | `msoa-internal-dev-key` | Secret sent by Payments / Shipping in `X-Service-Key` |
| `PAID_REQUIRES_SERVICE_KEY` | `true` | Only Payments may set an order to `PAID` |
| `SHIPPING_CHECK_ON_CANCEL` | `true` | Ask Shipping before cancelling a `PAID` order |

## Database Schema

```sql
CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    customer_address TEXT NOT NULL,
    customer_city TEXT NOT NULL,
    total REAL NOT NULL CHECK(total >= 0),
    status TEXT NOT NULL CHECK(status IN ('PENDING_PAYMENT','PAID','SHIPPED','DELIVERED','CANCELLED')),
    stock_released INTEGER NOT NULL DEFAULT 0,   -- 1 once Inventory.release was called (once only)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    price REAL NOT NULL CHECK(price >= 0),       -- real price from Catalog at order time
    quantity INTEGER NOT NULL CHECK(quantity > 0)
);
```

## API Endpoints

| Method | Endpoint | Description | Success | Errors |
|---|---|---|---|---|
| `GET` | `/api/orders?userId={id}` | Orders of a user | `200` | `400` `401` `403` |
| `GET` | `/api/orders/{id}` | One order | `200` | `401` `403` `404` |
| `POST` | `/api/orders` | Create an order | `201` | `400` `401` `403` `404` `409` `502` `503` |
| `PATCH` | `/api/orders/{id}/status` | Change status | `200` | `400` `401` `403` `404` `409` |
| `POST` | `/api/orders/{id}/cancel` | Cancel + give stock back | `200` | `401` `403` `404` `409` `502` `503` |
| `GET` | `/health` | Health check | `200` | |

All errors use the team format `{"message": "..."}`.

### Statuses and transitions

```
PENDING_PAYMENT -> PAID -> SHIPPED -> DELIVERED
PENDING_PAYMENT -> CANCELLED
PAID            -> CANCELLED   (only if the parcel has not left)
```
`SHIPPED`, `DELIVERED` and `CANCELLED` orders can never be cancelled. A forbidden transition returns `409`.

### Who can call what

| Caller | Header | Rights |
|---|---|---|
| End user (frontend) | `Authorization: Bearer <token>` | Create / read / cancel **own** orders, set `SHIPPED` / `DELIVERED` on own orders |
| Payments, Shipping | `X-Service-Key: <INTERNAL_API_KEY>` | Read any order, set `PAID` (Payments), `SHIPPED` / `DELIVERED` (Shipping) |

## Examples

```bash
# 1. Login (Auth service) and keep the token
TOKEN=<token returned by POST http://localhost:8081/api/auth/login>

# 2. Create an order (the price is NEVER sent: Orders reads it from Catalog)
curl -X POST http://localhost:8084/api/orders \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"userId":"user-1","customer":{"name":"Demo Customer","address":"123 Main Street","city":"Casablanca"},"items":[{"productId":1,"quantity":2}]}'
# 201 -> {"id":"...","userId":"user-1","customer":{...},"items":[{"productId":1,"name":"...","price":...,"quantity":2}],"total":...,"status":"PENDING_PAYMENT","createdAt":"2026-11-18T17:00:00Z"}

# 3. My orders
curl "http://localhost:8084/api/orders?userId=user-1" -H "Authorization: Bearer $TOKEN"

# 4. Cancel
curl -X POST http://localhost:8084/api/orders/<ORDER_ID>/cancel -H "Authorization: Bearer $TOKEN"

# 5. Payments marks the order as paid (service-to-service)
curl -X PATCH http://localhost:8084/api/orders/<ORDER_ID>/status \
  -H "X-Service-Key: msoa-internal-dev-key" -H "Content-Type: application/json" \
  -d '{"status":"PAID"}'
```

Stock refused (`409`): `{"message":"Insufficient stock for product 5 (requested 9, available 8)"}` — no order is created and no stock is modified.

## Communication with other services (HTTP/REST only)

| Orders calls | Endpoint | When |
|---|---|---|
| Auth | `GET /api/auth/me` | Every protected request: validates the token and the `userId` |
| Catalog | `GET /products/{id}` | Order creation: real name and price, computes `total` |
| Inventory | `POST /api/inventory/reserve` | Order creation (atomic). `409` -> order not created |
| Inventory | `POST /api/inventory/release` | Authorized cancellation, **once** per order |
| Shipping | `GET /api/shipments/order/{orderId}` | Cancelling a `PAID` order: refused if the shipment is beyond `PREPARING` |

| Called by | Endpoint | What it must send |
|---|---|---|
| Payments | `GET /api/orders/{id}`, `PATCH /api/orders/{id}/status` `{"status":"PAID"}` | Header `X-Service-Key` |
| Shipping | `GET /api/orders/{id}`, `PATCH /api/orders/{id}/status` (`SHIPPED`, `DELIVERED`) | Header `X-Service-Key` |
| Frontend | all `/api/orders...` endpoints | Header `Authorization: Bearer <token>` |

If a called service is down, Orders answers `503` (or `502` for an invalid answer) with `{"message": "..."}`. If the order cannot be saved after the stock was reserved, the stock is released (compensation).

## Run Automated Tests

```bash
pytest tests/ -v
```
The tests replace Auth, Catalog, Inventory and Shipping with fakes, so they run without the other services.

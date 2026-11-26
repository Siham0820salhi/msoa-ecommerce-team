# Payments Microservice

FastAPI microservice responsible for simulated payment processing in the MSOA E-commerce application.

## Overview
- **Port**: 8085
- **Database**: SQLite (`payments.db`)
- **Technology**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn
- **Interactive Swagger Documentation**: [http://localhost:8085/docs](http://localhost:8085/docs)
- **ReDoc**: [http://localhost:8085/redoc](http://localhost:8085/redoc)

---

## Database Schema

```sql
PRAGMA foreign_keys = ON;
CREATE TABLE payments (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL UNIQUE,
    amount REAL NOT NULL CHECK(amount >= 0),
    method TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('SUCCESS','FAILED','PENDING','REFUNDED')),
    created_at TEXT NOT NULL
);
```

---

## API Endpoints

| Method | Endpoint | Description | Status Code |
|---|---|---|---|
| `GET` | `/api/payments` | Retrieve all payments | `200 OK` |
| `GET` | `/api/payments/order/{orderId}` | Retrieve payment for an order | `200 OK` / `404 Not Found` |
| `POST` | `/api/payments` | Process a simulated payment | `201 Created` / `409 Conflict` / `422 Unprocessable` |
| `GET` | `/health` | Health check endpoint | `200 OK` |

---

## Request & Response Examples

### 1. Process Payment (`POST /api/payments`)

**Request Body:**
```json
{
  "orderId": "order-123",
  "method": "CARD",
  "amount": 299.99
}
```

*Note: `amount` is optional and defaults to `0.0` if not provided. Supported methods: `CARD`, `CASH`, `PAYPAL`, `TRANSFER`.*

**Response (`201 Created`):**
```json
{
  "id": "e4b2d56a-1748-4389-9a2f-e77a288c919d",
  "orderId": "order-123",
  "amount": 299.99,
  "method": "CARD",
  "status": "SUCCESS",
  "createdAt": "2026-11-18T17:00:00.000000Z"
}
```

### 2. Duplicate Payment Attempt (`POST /api/payments`)
**Response (`409 Conflict`):**
```json
{
  "detail": "Payment for order 'order-123' already exists"
}
```

### 3. Retrieve Payment by Order ID (`GET /api/payments/order/order-123`)
**Response (`200 OK`):**
```json
{
  "id": "e4b2d56a-1748-4389-9a2f-e77a288c919d",
  "orderId": "order-123",
  "amount": 299.99,
  "method": "CARD",
  "status": "SUCCESS",
  "createdAt": "2026-11-18T17:00:00.000000Z"
}
```

---

## Installation & Launch

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Service
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8085 --reload
```

### 3. Run Automated Tests
```bash
pytest tests/ -v
```

---

## LAB 4 — Asynchronous shipment events (RabbitMQ producer)

When a payment **succeeds**, Payments records a `PaymentSucceeded` event and a
background worker publishes it to RabbitMQ. Shipping consumes it and prepares
the shipment. Failed payments publish nothing.

**The customer never waits for RabbitMQ or Shipping.** Nothing in the HTTP
request path talks to the broker: the payment row and its event row are written
in the *same* database transaction, and publishing happens afterwards in a
background thread. A payment therefore returns `201` normally even when the
broker is completely down, and the event is published as soon as it comes back.

### Transactional outbox

| Table | Purpose |
|---|---|
| `outbox_events` | One row per pending/published event, written in the payment's transaction |

Row states: `PENDING` → `PUBLISHED`. A row stays `PENDING` while the broker is
unreachable; `attempts` and `last_error` record what is happening.

### Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/%2F` | Broker connection |
| `RABBITMQ_QUEUE` | `shipment.requests` | Durable work queue |
| `RABBITMQ_DLX` | `shipment.dlx` | Dead-letter exchange |
| `OUTBOX_PUBLISHER_ENABLED` | `true` | Set to `false` to run the API without the publisher |
| `OUTBOX_POLL_INTERVAL` | `5` | Seconds between polls when the outbox is empty |
| `OUTBOX_BACKOFF_MIN` / `OUTBOX_BACKOFF_MAX` | `1` / `30` | Retry backoff bounds |
| `ORDERS_URL` | `http://localhost:8084` | Read (best effort) to enrich events with the delivery address |
| `INTERNAL_API_KEY` | `msoa-internal-dev-key` | Shared secret sent as `X-Service-Key` when calling Orders. Must match Orders' value. |

### Extra endpoint

`GET /api/payments/outbox[?status_filter=PENDING]` — read-only view of the
outbox, used to demonstrate that an event survives a broker outage. Purely
additive: no existing endpoint changed.

### Run it

```bash
docker compose up -d rabbitmq          # from the repository root
uvicorn app.main:app --port 8085
pytest tests/ -v                       # 25 tests, no broker needed
```

Full design notes: `payments/LAB4_rabbitmq_payments_shipping.md`.

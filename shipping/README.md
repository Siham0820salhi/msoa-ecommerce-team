# Shipping Microservice

FastAPI microservice responsible for shipment creation, lifecycle progression, and delivery tracking in the MSOA E-commerce application.

## Overview
- **Port**: 8086
- **Database**: SQLite (`shipping.db`)
- **Technology**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn
- **Interactive Swagger Documentation**: [http://localhost:8086/docs](http://localhost:8086/docs)
- **ReDoc**: [http://localhost:8086/redoc](http://localhost:8086/redoc)

---

## Database Schema

```sql
PRAGMA foreign_keys = ON;
CREATE TABLE shipments (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL UNIQUE,
    recipient_name TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    tracking_number TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK(status IN ('PREPARING','SHIPPED','IN_TRANSIT','DELIVERED','CANCELLED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

---

## Delivery Lifecycle & Transitions

```
PREPARING ──► SHIPPED ──► IN_TRANSIT ──► DELIVERED
    │             │
    ▼             ▼
CANCELLED     CANCELLED
```

Invalid transitions (e.g. jumping directly from `PREPARING` to `DELIVERED` or attempting to modify a `DELIVERED` shipment) return `422 Unprocessable Entity`.

---

## API Endpoints

| Method | Endpoint | Description | Status Code |
|---|---|---|---|
| `GET` | `/api/shipments` | List all shipments | `200 OK` |
| `GET` | `/api/shipments/order/{orderId}` | Get shipment for an order | `200 OK` / `404 Not Found` |
| `POST` | `/api/shipments` | Create new shipment for an order | `201 Created` / `409 Conflict` / `422 Unprocessable` |
| `PATCH` | `/api/shipments/{id}/status` | Update shipment status | `200 OK` / `404 Not Found` / `422 Unprocessable` |
| `GET` | `/health` | Health check endpoint | `200 OK` |

---

## Request & Response Examples

### 1. Create Shipment (`POST /api/shipments`)

**Request Body:**
```json
{
  "orderId": "order-123",
  "address": {
    "name": "Demo Customer",
    "address": "123 Main Street",
    "city": "Casablanca"
  }
}
```

**Response (`201 Created`):**
```json
{
  "id": "7f9a1c8b-2d4e-4f1a-9c3e-8b5d7a6e1f0a",
  "orderId": "order-123",
  "address": {
    "name": "Demo Customer",
    "address": "123 Main Street",
    "city": "Casablanca"
  },
  "trackingNumber": "MSOA-4K9B2D8E",
  "status": "PREPARING",
  "createdAt": "2026-11-18T17:00:00.000000Z",
  "updatedAt": "2026-11-18T17:00:00.000000Z"
}
```

### 2. Update Status (`PATCH /api/shipments/{id}/status`)

**Request Body:**
```json
{
  "status": "SHIPPED"
}
```

**Response (`200 OK`):**
```json
{
  "id": "7f9a1c8b-2d4e-4f1a-9c3e-8b5d7a6e1f0a",
  "orderId": "order-123",
  "address": {
    "name": "Demo Customer",
    "address": "123 Main Street",
    "city": "Casablanca"
  },
  "trackingNumber": "MSOA-4K9B2D8E",
  "status": "SHIPPED",
  "createdAt": "2026-11-18T17:00:00.000000Z",
  "updatedAt": "2026-11-18T17:05:00.000000Z"
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
uvicorn app.main:app --host 0.0.0.0 --port 8086 --reload
```

### 3. Run Automated Tests
```bash
pytest tests/ -v
```

---

## LAB 4 — Asynchronous shipment events (RabbitMQ consumer)

Shipping consumes `PaymentSucceeded` messages from the durable queue
`shipment.requests` and creates the shipment with the **existing** business
logic, so the status lifecycle (`PREPARING → SHIPPED → IN_TRANSIT →
DELIVERED/CANCELLED`) and the `MSOA-XXXXXXXX` tracking-number format are
unchanged.

**The REST API is untouched.** The consumer runs as a *separate process*; the
API works with or without it.

### Reliability

| Property | How |
|---|---|
| No lost message | Durable queue, persistent messages, manual acknowledgement |
| Ack only after commit | The message is acknowledged *after* the shipment is committed |
| No duplicate shipment | `processed_events` table keyed by `eventId`, plus `UNIQUE(order_id)` |
| Transient failures | Retried with an attempt counter, up to `CONSUMER_MAX_ATTEMPTS` |
| Poison messages | Dead-lettered to `shipment.requests.dlq` via `shipment.dlx` |

Delivery is **at-least-once with idempotent processing**, not exactly-once: a
crash between the commit and the ack causes a redelivery, which the
idempotency ledger makes harmless.

### Delivery address

The event carries the address when Payments could read it from Orders. If it
is absent, the consumer fetches it from Orders itself. If neither works the
message is **retried**, never turned into a shipment with placeholder data.

### Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/%2F` | Broker connection |
| `RABBITMQ_QUEUE` | `shipment.requests` | Durable work queue |
| `RABBITMQ_DLX` / `RABBITMQ_DLQ` | `shipment.dlx` / `shipment.requests.dlq` | Dead-letter routing |
| `CONSUMER_MAX_ATTEMPTS` | `5` | Deliveries before a message is dead-lettered |
| `CONSUMER_RETRY_DELAY` | `2` | Seconds before retrying a transient failure |
| `CONSUMER_PREFETCH` | `1` | Unacknowledged messages in flight |
| `ORDERS_URL` | `http://localhost:8084` | Fallback source for the delivery address |
| `INTERNAL_API_KEY` | `msoa-internal-dev-key` | Shared secret sent as `X-Service-Key` when calling Orders. Must match Orders' value. |

### Run it

```bash
docker compose up -d rabbitmq          # from the repository root
uvicorn app.main:app --port 8086       # REST API (unchanged)
python consumer_main.py                # consumer, separate terminal

pytest tests/ -v                       # 33 tests; 4 more need a live broker
```

Full design notes: `payments/LAB4_rabbitmq_payments_shipping.md`.

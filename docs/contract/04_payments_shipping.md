# API Contract — Payments & Shipping Services

**Author**: Hasnae ELMIR  
**Module**: MSOA — LAB 3 · PART II · Q3  
**Services owned**: Payments (port 8085) · Shipping (port 8086)

> Database files used: `payments/schema.sql`, `payments/seed.sql`,
> `shipping/schema.sql`, `shipping/seed.sql` (provided in the lab ZIP).

---

# Payments Service

**Technology**: Python 3.13 · FastAPI · SQLite · SQLAlchemy 2.0 · Pydantic v2  
**Base URL**: `http://localhost:8085`  
**Interactive docs (Swagger UI)**: `http://localhost:8085/docs`  
**OpenAPI JSON**: `http://localhost:8085/openapi.json`

---

## a. Operations exposed

| # | Operation | HTTP Method | Endpoint |
|---|---|---|---|
| 1 | List all payments | GET | `/api/payments` |
| 2 | Get payment for an order | GET | `/api/payments/order/{orderId}` |
| 3 | Process a payment | POST | `/api/payments` |
| 4 | Health check | GET | `/health` |

---

## b–c. Method, endpoint and purpose

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/payments` | Return all payment records (admin/debug view) |
| GET | `/api/payments/order/{orderId}` | Return the payment record linked to a specific order |
| POST | `/api/payments` | Create and process a payment for an order |
| GET | `/health` | Confirm the service is running |

---

## d. URL parameters

| Endpoint | Parameter | Type | Description |
|---|---|---|---|
| GET `/api/payments/order/{orderId}` | `orderId` | string | The order identifier to look up |

---

## e. Data model (from `payments/schema.sql`)

```sql
PRAGMA foreign_keys = ON;
CREATE TABLE payments (
    id         TEXT PRIMARY KEY,
    order_id   TEXT NOT NULL UNIQUE,
    amount     REAL NOT NULL CHECK(amount >= 0),
    method     TEXT NOT NULL,
    status     TEXT NOT NULL CHECK(status IN ('SUCCESS','FAILED','PENDING','REFUNDED')),
    created_at TEXT NOT NULL
);
```

**Seed data** (`payments/seed.sql`):
```sql
INSERT INTO payments VALUES (
  'payment-demo-001', 'order-demo-001', 199, 'CARD', 'SUCCESS', '2026-11-01T10:01:00Z'
);
```

**Allowed `method` values**: `CARD`, `CASH`, `PAYPAL`, `TRANSFER`  
**Allowed `status` values**: `PENDING`, `SUCCESS`, `FAILED`, `REFUNDED`

**Status life-cycle**:
```
PENDING → SUCCESS
        → FAILED
SUCCESS → REFUNDED
```

---

## f. Required HTTP headers

| Header | Endpoints | Value |
|---|---|---|
| `Content-Type` | POST `/api/payments` | `application/json` |
| `Accept` | All | `application/json` (recommended) |

---

## g. Request body schema

### POST `/api/payments`

```json
{
  "orderId":         "order-abc-001",
  "amount":          199.00,
  "method":          "CARD",
  "simulateFailure": false
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `orderId` | string | ✅ | Non-empty; must be unique in the payments table |
| `amount` | number | ✅ | ≥ 0 |
| `method` | string | ✅ | One of `CARD`, `CASH`, `PAYPAL`, `TRANSFER` |
| `simulateFailure` | boolean | ❌ | Default `false`; set `true` to test the `FAILED` path |

---

## h. Success HTTP status codes

| Endpoint | Status code | Meaning |
|---|---|---|
| GET `/api/payments` | 200 OK | List returned (may be empty) |
| GET `/api/payments/order/{orderId}` | 200 OK | Payment found |
| POST `/api/payments` | 201 Created | Payment processed and stored |
| GET `/health` | 200 OK | Service is up |

---

## i. Response schema

### Payment object (all GET and POST responses)

```json
{
  "id":        "payment-demo-001",
  "orderId":   "order-demo-001",
  "amount":    199.0,
  "method":    "CARD",
  "status":    "SUCCESS",
  "createdAt": "2026-11-01T10:01:00Z"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Auto-generated UUID (TEXT PK) |
| `orderId` | string | The related order ID |
| `amount` | number | Payment amount (≥ 0) |
| `method` | string | Payment method used |
| `status` | string | Current payment status |
| `createdAt` | string | ISO 8601 UTC timestamp |

GET `/api/payments` returns an **array** of payment objects: `[{...}, {...}]`

### Health

```json
{ "service": "payments", "status": "UP" }
```

---

## j. Error schemas

All error responses follow the format:
```json
{ "message": "Human-readable description" }
```

| Code | Endpoint | Condition | Example body |
|---|---|---|---|
| 404 | GET `/api/payments/order/{orderId}` | No payment found for that order | `{"message": "Payment for order 'order-999' not found"}` |
| 409 | POST `/api/payments` | Payment already exists for this order | `{"message": "Payment for order 'order-001' already exists"}` |
| 422 | POST `/api/payments` | Validation error (bad method, negative amount) | `{"message": "Invalid request format", "detail": [...]}` |
| 500 | Any | Unexpected server error | `{"message": "Internal server error"}` |

---

## Full example — process a payment

**Request**:
```
POST /api/payments HTTP/1.1
Host: localhost:8085
Content-Type: application/json

{
  "orderId": "order-abc-001",
  "amount": 8499.00,
  "method": "CARD"
}
```

**Response** (201 Created):
```json
{
  "id": "3f7a1b2c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "orderId": "order-abc-001",
  "amount": 8499.0,
  "method": "CARD",
  "status": "SUCCESS",
  "createdAt": "2026-11-18T21:00:00Z"
}
```

---

## CORS configuration

| Setting | Value |
|---|---|
| Allowed origins | `http://localhost:5173`, `http://127.0.0.1:5173` |
| Allowed methods | `GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` |
| Allowed headers | `Content-Type`, `Authorization` |

---

---

# Shipping Service

**Technology**: Python 3.13 · FastAPI · SQLite · SQLAlchemy 2.0 · Pydantic v2  
**Base URL**: `http://localhost:8086`  
**Interactive docs (Swagger UI)**: `http://localhost:8086/docs`  
**OpenAPI JSON**: `http://localhost:8086/openapi.json`

---

## a. Operations exposed

| # | Operation | HTTP Method | Endpoint |
|---|---|---|---|
| 1 | List all shipments | GET | `/api/shipments` |
| 2 | Get shipment for an order | GET | `/api/shipments/order/{orderId}` |
| 3 | Create a shipment | POST | `/api/shipments` |
| 4 | Update shipment status | PATCH | `/api/shipments/{id}/status` |
| 5 | Health check | GET | `/health` |

---

## b–c. Method, endpoint and purpose

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/shipments` | Return all shipment records |
| GET | `/api/shipments/order/{orderId}` | Return the shipment linked to a specific order |
| POST | `/api/shipments` | Create a new shipment with auto-generated tracking number |
| PATCH | `/api/shipments/{id}/status` | Advance shipment through its delivery life-cycle |
| GET | `/health` | Confirm the service is running |

---

## d. URL parameters

| Endpoint | Parameter | Type | Description |
|---|---|---|---|
| GET `/api/shipments/order/{orderId}` | `orderId` | string | Order whose shipment to retrieve |
| PATCH `/api/shipments/{id}/status` | `id` | string | Shipment UUID to update |

---

## e. Data model (from `shipping/schema.sql`)

```sql
PRAGMA foreign_keys = ON;
CREATE TABLE shipments (
    id               TEXT PRIMARY KEY,
    order_id         TEXT NOT NULL UNIQUE,
    recipient_name   TEXT NOT NULL,
    address          TEXT NOT NULL,
    city             TEXT NOT NULL,
    tracking_number  TEXT NOT NULL UNIQUE,
    status           TEXT NOT NULL CHECK(status IN ('PREPARING','SHIPPED','IN_TRANSIT','DELIVERED','CANCELLED')),
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
```

**Seed data** (`shipping/seed.sql`):
```sql
INSERT INTO shipments VALUES (
  'shipment-demo-001','order-demo-001',
  'Demo Customer','123 Main Street','Casablanca',
  'MSOA-DEMO001','DELIVERED',
  '2026-11-01T10:02:00Z','2026-11-03T15:00:00Z'
);
```

**Tracking number format**: `MSOA-XXXXXXXX` — 8 uppercase alphanumeric characters, auto-generated on creation.

**Status life-cycle**:
```
PREPARING → SHIPPED → IN_TRANSIT → DELIVERED
          ↘ CANCELLED (from PREPARING or SHIPPED only)
```

---

## f. Required HTTP headers

| Header | Endpoints | Value |
|---|---|---|
| `Content-Type` | POST `/api/shipments`, PATCH `…/status` | `application/json` |
| `Accept` | All | `application/json` (recommended) |

---

## g. Request body schema

### POST `/api/shipments`

```json
{
  "orderId": "order-abc-001",
  "address": {
    "name":    "Hasnae ELMIR",
    "address": "123 Rue Mohammed V",
    "city":    "Casablanca"
  }
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `orderId` | string | ✅ | Non-empty; must be unique in the shipments table |
| `address.name` | string | ✅ | Recipient full name |
| `address.address` | string | ✅ | Street address |
| `address.city` | string | ✅ | City |

### PATCH `/api/shipments/{id}/status`

```json
{ "status": "SHIPPED" }
```

| Field | Type | Required | Allowed values |
|---|---|---|---|
| `status` | string | ✅ | `PREPARING`, `SHIPPED`, `IN_TRANSIT`, `DELIVERED`, `CANCELLED` |

---

## h. Success HTTP status codes

| Endpoint | Status code | Meaning |
|---|---|---|
| GET `/api/shipments` | 200 OK | List returned |
| GET `/api/shipments/order/{orderId}` | 200 OK | Shipment found |
| POST `/api/shipments` | 201 Created | Shipment created |
| PATCH `/api/shipments/{id}/status` | 200 OK | Status updated |
| GET `/health` | 200 OK | Service is up |

---

## i. Response schema

### Shipment object

```json
{
  "id":             "shipment-demo-001",
  "orderId":        "order-demo-001",
  "recipientName":  "Demo Customer",
  "address":        "123 Main Street",
  "city":           "Casablanca",
  "trackingNumber": "MSOA-DEMO001",
  "status":         "DELIVERED",
  "createdAt":      "2026-11-01T10:02:00Z",
  "updatedAt":      "2026-11-03T15:00:00Z"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | UUID (TEXT PK) |
| `orderId` | string | Linked order ID |
| `recipientName` | string | Recipient full name |
| `address` | string | Street address |
| `city` | string | City |
| `trackingNumber` | string | Auto-generated `MSOA-XXXXXXXX` |
| `status` | string | Current delivery status |
| `createdAt` | string | ISO 8601 UTC — creation time |
| `updatedAt` | string | ISO 8601 UTC — last status change |

GET `/api/shipments` returns an **array**: `[{...}, {...}]`

### Health

```json
{ "service": "shipping", "status": "UP" }
```

---

## j. Error schemas

```json
{ "message": "Human-readable description" }
```

| Code | Endpoint | Condition | Example body |
|---|---|---|---|
| 404 | GET `.../order/{orderId}` | No shipment for that order | `{"message": "Shipment not found for orderId: order-999"}` |
| 404 | PATCH `.../status` | Shipment ID not found | `{"message": "Shipment not found"}` |
| 409 | POST `/api/shipments` | Shipment already exists for this order | `{"message": "Shipment already exists for orderId: order-001"}` |
| 422 | POST `/api/shipments` | Missing required field | `{"message": "Invalid request format", "detail": [...]}` |
| 422 | PATCH `.../status` | Invalid status transition | `{"message": "Invalid status transition from DELIVERED to PREPARING. Allowed transitions: []"}` |
| 500 | Any | Unexpected server error | `{"message": "Internal server error"}` |

---

## Full example — create and track a shipment

**Step 1 — Create shipment** (POST):
```
POST /api/shipments HTTP/1.1
Host: localhost:8086
Content-Type: application/json

{
  "orderId": "order-abc-001",
  "address": {
    "name": "Hasnae ELMIR",
    "address": "123 Rue Mohammed V",
    "city": "Casablanca"
  }
}
```

**Response** (201 Created):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "orderId": "order-abc-001",
  "recipientName": "Hasnae ELMIR",
  "address": "123 Rue Mohammed V",
  "city": "Casablanca",
  "trackingNumber": "MSOA-X7K2P9Q1",
  "status": "PREPARING",
  "createdAt": "2026-11-18T21:00:00Z",
  "updatedAt": "2026-11-18T21:00:00Z"
}
```

**Step 2 — Advance status** (PATCH):
```
PATCH /api/shipments/a1b2c3d4-e5f6-7890-abcd-ef1234567890/status HTTP/1.1
Content-Type: application/json

{ "status": "SHIPPED" }
```

**Response** (200 OK):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "orderId": "order-abc-001",
  "trackingNumber": "MSOA-X7K2P9Q1",
  "status": "SHIPPED",
  "updatedAt": "2026-11-18T21:05:00Z",
  ...
}
```

---

## CORS configuration

| Setting | Value |
|---|---|
| Allowed origins | `http://localhost:5173`, `http://127.0.0.1:5173` |
| Allowed methods | `GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` |
| Allowed headers | `Content-Type`, `Authorization` |

---

## Frontend integration

The React frontend reads the `SHIPPING` mode from `src/config/backend.js`:

```js
SHIPPING: {
  BACKEND_MODE: "rest",
  API_URLS: { BASE: "http://localhost:8086" }
}
```

When set to `"rest"`, `src/services/shippingService.js` calls the live FastAPI service directly. No React component or service file was modified.

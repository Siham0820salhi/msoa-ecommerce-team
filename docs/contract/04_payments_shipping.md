# API Contract — Payments & Shipping Services

**Authors**: Hasnae ELMIR  
**Module**: MSOA — LAB 3  

---

## Payments Service

**Technology**: Python 3.13 · FastAPI · SQLite · SQLAlchemy 2.0  
**Base URL**: `http://localhost:8085`  
**Swagger UI**: `http://localhost:8085/docs`  
**OpenAPI JSON**: `http://localhost:8085/openapi.json`

---

### a. Database schema

```sql
CREATE TABLE payments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL UNIQUE,
    amount     REAL    NOT NULL,
    method     TEXT    NOT NULL,
    status     TEXT    NOT NULL CHECK(status IN ('SUCCESS','FAILED','PENDING','REFUNDED')),
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```

**Status life-cycle**:
```
PENDING → SUCCESS
        → FAILED
SUCCESS → REFUNDED
```

---

### b. Response schema

Every successful response returns a **payment object** with camelCase fields:

```json
{
  "id":        1,
  "orderId":   42,
  "amount":    8499.00,
  "method":    "CARD",
  "status":    "SUCCESS",
  "createdAt": "2026-11-17T18:30:00Z"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | integer | Auto-generated primary key |
| `orderId` | integer | The related order |
| `amount` | number | Payment amount (positive) |
| `method` | string | `CARD`, `CASH`, `TRANSFER` |
| `status` | string | `PENDING`, `SUCCESS`, `FAILED`, `REFUNDED` |
| `createdAt` | string | ISO 8601 UTC timestamp |

---

### c. Error format

All 4xx and 5xx responses use:
```json
{ "message": "Human-readable description of the error" }
```

---

### d. CORS

Allowed origins: `http://localhost:5173`, `http://127.0.0.1:5173`  
Allowed methods: `GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS`  
Allowed headers: `Content-Type`, `Authorization`

---

### e. Endpoints

#### GET /api/payments

**Description**: Return all payment records (admin / debug use).

**Headers**: `Accept: application/json`

**Success — 200 OK**:
```json
[
  {
    "id": 1,
    "orderId": 42,
    "amount": 8499.00,
    "method": "CARD",
    "status": "SUCCESS",
    "createdAt": "2026-11-17T18:30:00Z"
  }
]
```

| Code | Condition |
|---|---|
| 200 | List returned (may be empty `[]`) |
| 500 | Database error |

---

#### GET /api/payments/order/{orderId}

**Description**: Retrieve the payment record for a given order.

**URL params**: `orderId` — integer

**Success — 200 OK**: Payment object (see schema above).

**Errors**:
| Code | Body |
|---|---|
| 404 | `{"message": "Payment not found for order 99"}` |
| 422 | `{"message": "orderId must be a positive integer"}` |

---

#### POST /api/payments

**Description**: Create and process a payment for an order. If the order already has a payment, returns 409.

**Headers**: `Content-Type: application/json`

**Request body**:
```json
{
  "orderId": 42,
  "amount":  8499.00,
  "method":  "CARD"
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `orderId` | integer | ✅ | Positive integer |
| `amount` | number | ✅ | > 0 |
| `method` | string | ✅ | One of `CARD`, `CASH`, `TRANSFER` |

**Success — 201 Created**: Payment object with `status: "SUCCESS"` (or `"FAILED"` if declined).

**Errors**:
| Code | Body |
|---|---|
| 400 | `{"message": "amount must be greater than 0"}` |
| 409 | `{"message": "Payment already exists for order 42"}` |
| 422 | `{"message": "method must be one of CARD, CASH, TRANSFER"}` |
| 500 | `{"message": "Internal server error"}` |

---

#### GET /health

**Description**: Liveness probe.

**Success — 200 OK**:
```json
{ "service": "payments", "status": "UP" }
```

---

### f. Full request/response example — process payment

**Request**:
```
POST /api/payments HTTP/1.1
Host: localhost:8085
Content-Type: application/json

{
  "orderId": 42,
  "amount": 8499.00,
  "method": "CARD"
}
```

**Response**:
```
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": 1,
  "orderId": 42,
  "amount": 8499.00,
  "method": "CARD",
  "status": "SUCCESS",
  "createdAt": "2026-11-17T18:30:00Z"
}
```

---

---

## Shipping Service

**Technology**: Python 3.13 · FastAPI · SQLite · SQLAlchemy 2.0  
**Base URL**: `http://localhost:8086`  
**Swagger UI**: `http://localhost:8086/docs`  
**OpenAPI JSON**: `http://localhost:8086/openapi.json`

---

### a. Database schema

```sql
CREATE TABLE shipments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id         INTEGER NOT NULL UNIQUE,
    recipient_name   TEXT    NOT NULL,
    address          TEXT    NOT NULL,
    city             TEXT    NOT NULL,
    tracking_number  TEXT    NOT NULL UNIQUE,
    status           TEXT    NOT NULL DEFAULT 'PREPARING'
                             CHECK(status IN ('PREPARING','SHIPPED','IN_TRANSIT','DELIVERED','CANCELLED')),
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```

**Tracking number format**: `MSOA-XXXXXXXX` (8 uppercase alphanumeric characters, auto-generated).

**Status life-cycle**:
```
PREPARING → SHIPPED → IN_TRANSIT → DELIVERED
          ↘ CANCELLED (from PREPARING or SHIPPED only)
```

---

### b. Response schema

Every successful response returns a **shipment object**:

```json
{
  "id":             1,
  "orderId":        42,
  "recipientName":  "Hasnae ELMIR",
  "address":        "123 Rue Mohammed V",
  "city":           "Casablanca",
  "trackingNumber": "MSOA-A1B2C3D4",
  "status":         "PREPARING",
  "createdAt":      "2026-11-17T18:30:00Z",
  "updatedAt":      "2026-11-17T18:30:00Z"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | integer | Auto-generated primary key |
| `orderId` | integer | The related order |
| `recipientName` | string | Full name of recipient |
| `address` | string | Street address |
| `city` | string | City name |
| `trackingNumber` | string | Unique tracking code (`MSOA-XXXXXXXX`) |
| `status` | string | Current shipment status |
| `createdAt` | string | ISO 8601 UTC — creation timestamp |
| `updatedAt` | string | ISO 8601 UTC — last status change |

---

### c. Error format

```json
{ "message": "Human-readable description of the error" }
```

---

### d. CORS

Allowed origins: `http://localhost:5173`, `http://127.0.0.1:5173`  
Allowed methods: `GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS`  
Allowed headers: `Content-Type`, `Authorization`

---

### e. Endpoints

#### GET /api/shipments

**Description**: Return all shipment records.

**Success — 200 OK**: Array of shipment objects.

---

#### GET /api/shipments/order/{orderId}

**Description**: Retrieve the shipment for a given order.

**URL params**: `orderId` — integer

**Success — 200 OK**: Shipment object.

**Errors**:
| Code | Body |
|---|---|
| 404 | `{"message": "Shipment not found for order 99"}` |
| 422 | `{"message": "orderId must be a positive integer"}` |

---

#### POST /api/shipments

**Description**: Create a new shipment for an order. Tracking number is auto-generated.

**Headers**: `Content-Type: application/json`

**Request body**:
```json
{
  "orderId":       42,
  "recipientName": "Hasnae ELMIR",
  "address":       "123 Rue Mohammed V",
  "city":          "Casablanca"
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `orderId` | integer | ✅ | Positive integer |
| `recipientName` | string | ✅ | Non-empty |
| `address` | string | ✅ | Non-empty |
| `city` | string | ✅ | Non-empty |

**Success — 201 Created**: Shipment object with auto-generated `trackingNumber` and `status: "PREPARING"`.

**Errors**:
| Code | Body |
|---|---|
| 400 | `{"message": "recipientName is required"}` |
| 409 | `{"message": "Shipment already exists for order 42"}` |
| 422 | `{"message": "orderId must be a positive integer"}` |
| 500 | `{"message": "Internal server error"}` |

---

#### PATCH /api/shipments/{id}/status

**Description**: Update the status of a shipment. Enforces the allowed state transitions.

**URL params**: `id` — shipment integer ID

**Headers**: `Content-Type: application/json`

**Request body**:
```json
{ "status": "SHIPPED" }
```

| `status` value | Allowed from |
|---|---|
| `SHIPPED` | `PREPARING` |
| `IN_TRANSIT` | `SHIPPED` |
| `DELIVERED` | `IN_TRANSIT` |
| `CANCELLED` | `PREPARING`, `SHIPPED` |

**Success — 200 OK**: Updated shipment object.

**Errors**:
| Code | Body |
|---|---|
| 400 | `{"message": "Invalid status transition from DELIVERED to PREPARING"}` |
| 404 | `{"message": "Shipment 99 not found"}` |
| 422 | `{"message": "status must be one of PREPARING, SHIPPED, IN_TRANSIT, DELIVERED, CANCELLED"}` |

---

#### GET /health

**Success — 200 OK**:
```json
{ "service": "shipping", "status": "UP" }
```

---

### f. Full request/response example — create shipment

**Request**:
```
POST /api/shipments HTTP/1.1
Host: localhost:8086
Content-Type: application/json

{
  "orderId": 42,
  "recipientName": "Hasnae ELMIR",
  "address": "123 Rue Mohammed V",
  "city": "Casablanca"
}
```

**Response**:
```
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": 1,
  "orderId": 42,
  "recipientName": "Hasnae ELMIR",
  "address": "123 Rue Mohammed V",
  "city": "Casablanca",
  "trackingNumber": "MSOA-A1B2C3D4",
  "status": "PREPARING",
  "createdAt": "2026-11-17T18:30:00Z",
  "updatedAt": "2026-11-17T18:30:00Z"
}
```

**Follow-up — update status**:
```
PATCH /api/shipments/1/status HTTP/1.1
Content-Type: application/json

{ "status": "SHIPPED" }
```
```
HTTP/1.1 200 OK

{
  "id": 1,
  "orderId": 42,
  "trackingNumber": "MSOA-A1B2C3D4",
  "status": "SHIPPED",
  "updatedAt": "2026-11-17T19:00:00Z",
  ...
}
```

---

### g. Integration with the React frontend

The frontend reads `SHIPPING` mode from `src/config/backend.js`:

```js
SHIPPING: {
  BACKEND_MODE: "rest",
  API_URLS: { BASE: "http://localhost:8086" }
}
```

When set to `"rest"`, `src/services/shippingService.js` calls the live FastAPI service. CORS is configured to allow `http://localhost:5173`.

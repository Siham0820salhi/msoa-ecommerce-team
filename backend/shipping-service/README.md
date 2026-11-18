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

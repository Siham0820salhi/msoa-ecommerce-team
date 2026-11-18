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

# API Contract — Orders Service

**Service**: `orders`  
**Technology**: Node.js / Express (or FastAPI — to be confirmed by team member)  
**Base URL**: `http://localhost:8084`  
**Swagger / OpenAPI**: `http://localhost:8084/docs`

---

## a. Shared conventions

See [00_conventions.md](00_conventions.md).

---

## b. Data model

```
orders
  id          INTEGER  PRIMARY KEY AUTOINCREMENT
  userId      INTEGER  NOT NULL
  status      TEXT     CHECK IN ('PENDING','PAID','CANCELLED','SHIPPED','DELIVERED')
  total       REAL     NOT NULL
  createdAt   TEXT     ISO 8601 UTC
  updatedAt   TEXT     ISO 8601 UTC

order_items
  id          INTEGER  PRIMARY KEY AUTOINCREMENT
  orderId     INTEGER  FOREIGN KEY → orders(id)
  productId   INTEGER  NOT NULL
  quantity    INTEGER  NOT NULL
  unitPrice   REAL     NOT NULL
```

**Status life-cycle**:
```
PENDING → PAID → SHIPPED → DELIVERED
       ↘ CANCELLED (from PENDING or PAID)
```

---

## c. Endpoints

### GET /api/orders

**Description**: List all orders for the authenticated user.  
**Headers**: `Authorization: Bearer <token>`  
**Query params**: `userId` (integer, optional — admin override)

**Success — 200 OK**:
```json
[
  {
    "id": 1,
    "userId": 3,
    "status": "PAID",
    "total": 8499.00,
    "createdAt": "2026-11-17T18:30:00Z",
    "updatedAt": "2026-11-17T18:31:00Z",
    "items": [
      { "productId": 12, "quantity": 1, "unitPrice": 8499.00 }
    ]
  }
]
```

**Errors**:
| Code | Condition | Body |
|---|---|---|
| 401 | Missing token | `{"message": "Unauthorized"}` |

---

### GET /api/orders/{id}

**Description**: Get a single order by ID.  
**Headers**: `Authorization: Bearer <token>`  
**URL params**: `id` — order integer ID

**Success — 200 OK**: Same structure as single item from list above.

**Errors**:
| Code | Condition | Body |
|---|---|---|
| 401 | Missing token | `{"message": "Unauthorized"}` |
| 403 | Order belongs to another user | `{"message": "Forbidden"}` |
| 404 | Order not found | `{"message": "Order not found"}` |

---

### POST /api/orders

**Description**: Place a new order. Calls Catalog for price and Inventory to reserve stock.  
**Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`

**Request body**:
```json
{
  "items": [
    { "productId": 12, "quantity": 1 }
  ]
}
```

**Success — 201 Created**:
```json
{
  "id": 1,
  "userId": 3,
  "status": "PENDING",
  "total": 8499.00,
  "createdAt": "2026-11-17T18:30:00Z",
  "items": [
    { "productId": 12, "quantity": 1, "unitPrice": 8499.00 }
  ]
}
```

**Errors**:
| Code | Condition | Body |
|---|---|---|
| 400 | Empty items array | `{"message": "Order must contain at least one item"}` |
| 404 | Product not found | `{"message": "Product 99 not found"}` |
| 409 | Insufficient stock | `{"message": "Insufficient stock for product 12"}` |
| 422 | Validation error | `{"message": "quantity must be a positive integer"}` |

---

### PATCH /api/orders/{id}/status

**Description**: Update order status. Called by Payments (→ PAID) and Shipping (→ SHIPPED, DELIVERED).  
**Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`

**Request body**:
```json
{ "status": "PAID" }
```

**Success — 200 OK**:
```json
{
  "id": 1,
  "status": "PAID",
  "updatedAt": "2026-11-17T18:31:00Z"
}
```

**Errors**:
| Code | Condition | Body |
|---|---|---|
| 400 | Invalid status value | `{"message": "Invalid status 'UNKNOWN'"}` |
| 404 | Order not found | `{"message": "Order not found"}` |
| 409 | Illegal status transition | `{"message": "Cannot transition from DELIVERED to PENDING"}` |

---

### POST /api/orders/{id}/cancel

**Description**: Cancel an order and release reserved inventory.  
**Headers**: `Authorization: Bearer <token>`

**Success — 200 OK**:
```json
{ "id": 1, "status": "CANCELLED", "updatedAt": "2026-11-17T18:35:00Z" }
```

**Errors**:
| Code | Condition | Body |
|---|---|---|
| 400 | Order already delivered | `{"message": "Cannot cancel a delivered order"}` |
| 404 | Order not found | `{"message": "Order not found"}` |

---

### GET /health

**Success — 200 OK**:
```json
{ "service": "orders", "status": "UP" }
```

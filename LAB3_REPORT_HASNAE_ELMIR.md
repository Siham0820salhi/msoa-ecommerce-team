# LAB REPORT 3: DESIGNING AN API CONTRACT

**Master**: Big Data & Data Science  
**Module**: Microservice-Oriented Architectures (MSOA)  
**Professor**: Zouheir BANOU  
**Academic Year**: 2026–2027  

**Author / Student**: Hasnae ELMIR  
**Assigned Microservices**: Payments (Port 8085) & Shipping (Port 8086)  
**Team Repository**: [https://github.com/Siham0820salhi/msoa-ecommerce-team](https://github.com/Siham0820salhi/msoa-ecommerce-team)  
**Branch**: `feature/payments-shipping`  

---

## Table of Contents
1. [Introduction & Architectural Context](#1-introduction--architectural-context)
2. [PART I — Analysis](#2-part-i--analysis)
   - [Q1. Inter-Service Interactions](#q1-inter-service-interactions)
   - [Q2. REST Endpoints Identification](#q2-rest-endpoints-identification)
3. [PART II — API Contract Design & Implementation](#3-part-ii--api-contract-design--implementation)
   - [API Design Conventions](#api-design-conventions)
   - [Payments Microservice Contract (Items a–j)](#payments-microservice-contract-items-aj)
   - [Shipping Microservice Contract (Items a–j)](#shipping-microservice-contract-items-aj)
   - [Implementation & Verification](#implementation--verification)
4. [PART III — API Evolution and Breaking Changes](#4-part-iii--api-evolution-and-breaking-changes)
   - [Q4. Compatibility Problems of the Price Evolution](#q4-compatibility-problems-of-the-price-evolution)
   - [Q5. Evaluation of API Evolution Strategies](#q5-evaluation-of-api-evolution-strategies)
   - [Q6. Implementation of the Chosen Strategy](#q6-implementation-of-the-chosen-strategy)
5. [Deliverable Artifacts & Test Evidence](#5-deliverable-artifacts--test-evidence)

---

## 1. Introduction & Architectural Context

Following the architecture established in LAB 2, the e-commerce application has been decomposed into six autonomous microservices:
1. **Authentication Service** (`http://localhost:8081`): Manages customer registration, login credentials, and JWT sessions.
2. **Catalog Service** (`http://localhost:8082`): Manages products, categories, and authoritative pricing.
3. **Inventory Service** (`http://localhost:8083`): Tracks stock levels and reserves quantities for active orders.
4. **Orders Service** (`http://localhost:8084`): Coordinates order placements, item totals, and order lifecycles.
5. **Payments Service** (`http://localhost:8085`): Processes transaction payments, records card/cash/transfer methods, and tracks status.
6. **Shipping Service** (`http://localhost:8086`): Generates tracking numbers, logs shipping destinations, and handles carrier delivery stages.

**Responsibility within Team**:
This report focuses on the design, formal contract specification, database initialization from lab-provided schemas, implementation in FastAPI / SQLite, and integration of the **Payments** and **Shipping** microservices.

---

## 2. PART I — Analysis

### Q1. Inter-Service Interactions

In an e-commerce platform, no service operates as an isolated silo. The table below maps all inter-service communications, identifying the provider, the consumer, the HTTP method, the endpoint, and the exact information exchanged.

| Providing Service | Consuming Service | Method | Endpoint | Information Exchanged |
|---|---|---|---|---|
| **Catalog** | Orders | `GET` | `/api/products/{id}` | Authoritative product title, current unit price, and currency. Orders must not trust client-submitted prices. |
| **Inventory** | Orders | `POST` | `/api/inventory/reserve` | Request to lock stock for items during checkout (`productId`, `quantity`). Returns reservation status or 409 if insufficient stock. |
| **Inventory** | Orders | `POST` | `/api/inventory/release` | Request to unlock and restore stock when an order is cancelled or times out. |
| **Auth** | Orders, Payments | `GET` | `/api/auth/me` | Validates JWT Bearer tokens to extract authenticated `userId`, ensuring the caller owns the order being processed. |
| **Orders** | Payments | `GET` | `/api/orders/{id}` | Verification step: Payments validates that the order exists, belongs to the payer, and verifies the exact order total before charging. |
| **Orders** | Payments | `PATCH` | `/api/orders/{id}/status` | Post-payment synchronization: Payments instructs Orders to advance from `PENDING` to `PAID`. |
| **Orders** | Shipping | `GET` | `/api/orders/{id}` | Fulfillment data: Shipping retrieves recipient name, shipping address, city, and items to package. |
| **Orders** | Shipping | `PATCH` | `/api/orders/{id}/status` | Delivery synchronization: Shipping updates the order to `SHIPPED` and eventually `DELIVERED`. |
| **Payments** | React Frontend | `POST` | `/api/payments` | Frontend passes order ID and chosen payment method; Payments returns payment record and confirmation. |
| **Payments** | React Frontend | `GET` | `/api/payments/order/{orderId}` | Frontend retrieves payment receipt and status to display on Account/Orders view. |
| **Shipping** | React Frontend | `POST` | `/api/shipments` | Frontend (or checkout orchestrator) creates shipment record with address once payment succeeds. |
| **Shipping** | React Frontend | `GET` | `/api/shipments/order/{orderId}` | Frontend queries tracking details (`trackingNumber`, current status `IN_TRANSIT`, `DELIVERED`). |
| **Shipping** | React Frontend | `PATCH` | `/api/shipments/{id}/status` | Admin or delivery driver updates status; customer cancellation triggers cancel. |

---

### Q2. REST Endpoints Identification

The REST endpoints necessary to support business operations across the platform:

#### 1. Authentication Service (Port 8081)
- `POST /api/auth/register` — Params: `{email, password, name}`; Resp: 201 Created with `{id, email, name}`; Codes: 201, 400, 409, 422.
- `POST /api/auth/login` — Params: `{email, password}`; Resp: 200 OK with `{token, userId, name}`; Codes: 200, 400, 401.
- `POST /api/auth/logout` — Header: `Authorization: Bearer`; Resp: 200 OK; Codes: 200, 401.
- `GET /api/auth/me` — Header: `Authorization: Bearer`; Resp: 200 OK with user profile; Codes: 200, 401.
- `GET /health` — Resp: 200 OK with `{"service": "auth", "status": "UP"}`.

#### 2. Catalog Service (Port 8082)
- `GET /api/products` — Query: `?category=&search=`; Resp: 200 OK with `Product[]`; Codes: 200.
- `GET /api/products/{id}` — Path: `id`; Resp: 200 OK with `Product`; Codes: 200, 404.
- `POST /api/products` — Body: `{name, description, price, category, stock}`; Resp: 201 Created; Codes: 201, 400, 401, 422.
- `PUT /api/products/{id}` — Path: `id`; Body: updated product fields; Resp: 200 OK; Codes: 200, 404, 422.
- `DELETE /api/products/{id}` — Path: `id`; Resp: 204 No Content; Codes: 204, 404.
- `GET /health` — Resp: 200 OK with `{"service": "catalog", "status": "UP"}`.

#### 3. Inventory Service (Port 8083)
- `GET /api/inventory` — Resp: 200 OK with list of stock counts; Codes: 200.
- `GET /api/inventory/{productId}` — Path: `productId`; Resp: 200 OK with `{productId, stock}`; Codes: 200, 404.
- `POST /api/inventory/reserve` — Body: `{items: [{productId, quantity}]}`; Resp: 200 OK with reservation status; Codes: 200, 400, 409.
- `POST /api/inventory/release` — Body: `{items: [{productId, quantity}]}`; Resp: 200 OK; Codes: 200, 400.
- `PATCH /api/inventory/{productId}` — Body: `{stock}`; Resp: 200 OK; Codes: 200, 404, 422.
- `GET /health` — Resp: 200 OK with `{"service": "inventory", "status": "UP"}`.

#### 4. Orders Service (Port 8084)
- `GET /api/orders` — Header: `Authorization`; Query: `?userId=`; Resp: 200 OK with `Order[]`; Codes: 200, 401.
- `GET /api/orders/{id}` — Path: `id`; Resp: 200 OK with `Order` and item details; Codes: 200, 401, 404.
- `POST /api/orders` — Body: `{items: [{productId, quantity}]}`; Resp: 201 Created with `{id, status: "PENDING", total}`; Codes: 201, 400, 409, 422.
- `PATCH /api/orders/{id}/status` — Path: `id`; Body: `{status}`; Resp: 200 OK; Codes: 200, 400, 404, 422.
- `POST /api/orders/{id}/cancel` — Path: `id`; Resp: 200 OK; Codes: 200, 400, 404.
- `GET /health` — Resp: 200 OK with `{"service": "orders", "status": "UP"}`.

#### 5. Payments Service (Port 8085) — *Assigned Service*
- `GET /api/payments` — Resp: 200 OK with array of payments; Codes: 200.
- `GET /api/payments/order/{orderId}` — Path: `orderId` (string); Resp: 200 OK with payment record; Codes: 200, 404.
- `POST /api/payments` — Body: `{orderId, amount, method, simulateFailure?}`; Resp: 201 Created; Codes: 201, 400, 409, 422.
- `GET /health` — Resp: 200 OK with `{"service": "payments", "status": "UP"}`.

#### 6. Shipping Service (Port 8086) — *Assigned Service*
- `GET /api/shipments` — Resp: 200 OK with array of shipments; Codes: 200.
- `GET /api/shipments/order/{orderId}` — Path: `orderId` (string); Resp: 200 OK with shipment details; Codes: 200, 404.
- `POST /api/shipments` — Body: `{orderId, address: {name, address, city}}`; Resp: 201 Created; Codes: 201, 400, 409, 422.
- `PATCH /api/shipments/{id}/status` — Path: `id`; Body: `{status}`; Resp: 200 OK; Codes: 200, 400, 404, 422.
- `GET /health` — Resp: 200 OK with `{"service": "shipping", "status": "UP"}`.

---

## 3. PART II — API Contract Design & Implementation

### API Design Conventions
To guarantee interoperability between microservices developed independently:
1. **Serialization**: JSON exclusively (`application/json`).
2. **Casing**: All JSON fields use **camelCase** (`orderId`, `recipientName`, `trackingNumber`, `createdAt`).
3. **Timestamps**: ISO 8601 UTC format (`YYYY-MM-DDTHH:MM:SSZ` or ISO string).
4. **Primary Keys**: String/UUID representation (`TEXT` in SQLite) matching the lab SQL schemas.
5. **Standardized Error Envelope**: All 4xx and 5xx responses return `{ "message": "Human readable text", "detail": [...] }` compatible with the frontend's `apiClient.js`.
6. **Cross-Origin Resource Sharing (CORS)**: Configured for `http://localhost:5173` and `http://127.0.0.1:5173`.

---

### Payments Microservice Contract (Items a–j)

**Technology Stack**: Python 3.13 · FastAPI · SQLAlchemy 2.0 · SQLite · Pydantic v2  
**Base URL**: `http://localhost:8085`  
**Database Schema (`payments/schema.sql`)**:
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

#### a. Operations Exposed
1. List all payments (`list_payments`)
2. Get payment by order identifier (`get_payment_by_order`)
3. Process a new payment transaction (`create_payment`)
4. Health check probe (`health`)

#### b & c. HTTP Methods, Endpoints & Purpose
| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness and health probe for orchestrator / frontend. |
| `GET` | `/api/payments` | Returns history of all recorded payments (admin view). |
| `GET` | `/api/payments/order/{orderId}` | Retrieves payment transaction record for a specific order. |
| `POST` | `/api/payments` | Creates and executes payment against an order. |

#### d. URL Parameters
- `GET /api/payments/order/{orderId}`: `orderId` (string, required) — Unique order identifier.

#### e. Data Parameters & Expected Formats
- `amount`: Floating point number, must satisfy $\ge 0.0$.
- `method`: String, must belong to set `{'CARD', 'CASH', 'PAYPAL', 'TRANSFER'}` (case-insensitive validation).
- `status`: String enum `{'PENDING', 'SUCCESS', 'FAILED', 'REFUNDED'}`.

#### f. Required HTTP Headers
- `Content-Type: application/json` on all `POST` payloads.
- `Accept: application/json` on all requests.

#### g. Request-Body Schema
**`POST /api/payments`**:
```json
{
  "orderId": "order-demo-001",
  "amount": 199.0,
  "method": "CARD",
  "simulateFailure": false
}
```
*Validation Rules*:
- `orderId`: String, non-empty, unique across payments table.
- `amount`: Number, non-negative.
- `method`: String, validated against allowed methods.
- `simulateFailure`: Boolean (optional, defaults to `false`).

#### h. Expected Success HTTP Status Codes
- `200 OK`: Successful `GET` queries.
- `201 Created`: Successful `POST /api/payments`.

#### i. Response Schema
```json
{
  "id": "payment-demo-001",
  "orderId": "order-demo-001",
  "amount": 199.0,
  "method": "CARD",
  "status": "SUCCESS",
  "createdAt": "2026-11-01T10:01:00Z"
}
```

#### j. Error Schemas
| Status Code | Condition | Response Payload |
|---|---|---|
| `404 Not Found` | No payment exists for requested `orderId` | `{"message": "Payment for order 'xyz' not found"}` |
| `409 Conflict` | Payment record already exists for this `orderId` | `{"message": "Payment for order 'xyz' already exists"}` |
| `422 Unprocessable` | Invalid method or negative amount | `{"message": "Invalid request format", "detail": [...]}` |

---

### Shipping Microservice Contract (Items a–j)

**Technology Stack**: Python 3.13 · FastAPI · SQLAlchemy 2.0 · SQLite · Pydantic v2  
**Base URL**: `http://localhost:8086`  
**Database Schema (`shipping/schema.sql`)**:
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

#### a. Operations Exposed
1. List all shipments (`list_shipments`)
2. Query shipment by order identifier (`get_shipment_by_order`)
3. Register a new shipment for an order (`create_shipment`)
4. Advance or update delivery status (`update_status`)
5. Health check probe (`health`)

#### b & c. HTTP Methods, Endpoints & Purpose
| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness and health probe. |
| `GET` | `/api/shipments` | Lists all shipments recorded in the carrier database. |
| `GET` | `/api/shipments/order/{orderId}` | Retrieves parcel tracking info for an order. |
| `POST` | `/api/shipments` | Creates shipping record and generates unique tracking number. |
| `PATCH` | `/api/shipments/{id}/status` | Advances shipment status along state transition pipeline. |

#### d. URL Parameters
- `GET /api/shipments/order/{orderId}`: `orderId` (string, required).
- `PATCH /api/shipments/{id}/status`: `id` (string, required) — Shipment UUID.

#### e. Data Parameters & Expected Formats
- `trackingNumber`: Auto-generated string matching regex `^MSOA-[A-Z0-9]{8}$`.
- `status`: String adhering to state machine:
  $$\text{PREPARING} \longrightarrow \text{SHIPPED} \longrightarrow \text{IN\_TRANSIT} \longrightarrow \text{DELIVERED}$$
  $$\text{PREPARING or SHIPPED} \longrightarrow \text{CANCELLED}$$

#### f. Required HTTP Headers
- `Content-Type: application/json` for `POST` and `PATCH`.
- `Accept: application/json`.

#### g. Request-Body Schema
**`POST /api/shipments`**:
```json
{
  "orderId": "order-demo-001",
  "address": {
    "name": "Demo Customer",
    "address": "123 Main Street",
    "city": "Casablanca"
  }
}
```

**`PATCH /api/shipments/{id}/status`**:
```json
{
  "status": "SHIPPED"
}
```

#### h. Expected Success HTTP Status Codes
- `200 OK`: `GET` requests and `PATCH` status updates.
- `201 Created`: `POST /api/shipments`.

#### i. Response Schema
```json
{
  "id": "shipment-demo-001",
  "orderId": "order-demo-001",
  "address": {
    "name": "Demo Customer",
    "address": "123 Main Street",
    "city": "Casablanca"
  },
  "trackingNumber": "MSOA-DEMO001",
  "status": "DELIVERED",
  "createdAt": "2026-11-01T10:02:00Z",
  "updatedAt": "2026-11-03T15:00:00Z"
}
```

#### j. Error Schemas
| Status Code | Condition | Response Payload |
|---|---|---|
| `404 Not Found` | Unknown order ID or shipment ID | `{"message": "Shipment not found for orderId: xyz"}` |
| `409 Conflict` | Shipment already exists for order | `{"message": "Shipment already exists for orderId: xyz"}` |
| `422 Unprocessable` | Illegal status transition (e.g. `DELIVERED` to `PREPARING`) | `{"message": "Invalid status transition from DELIVERED to PREPARING. Allowed transitions: []"}` |

---

### Implementation & Verification

Both services were implemented with complete adherence to their contracts and seed files:

1. **Database Seeding**: Both `payments/payments.db` and `shipping/shipping.db` are initialized directly using the SQL statements from `schema.sql` and `seed.sql`.
2. **Automated Unit & Integration Testing**:
   - `pytest` on Payments: **13 passed in 1.36s** (`test_payments.py`)
   - `pytest` on Shipping: **16 passed in 0.85s** (`test_shipments.py`)
3. **Interactive Swagger Documentation**:
   - Payments OpenAPI documentation accessible at `http://localhost:8085/docs`
   - Shipping OpenAPI documentation accessible at `http://localhost:8086/docs`

---

## 4. PART III — API Evolution and Breaking Changes

### Q4. Compatibility Problems of the Price Evolution

#### The Modification
The Catalog microservice evolved its product payload:

**Previous Representation (v1)**:
```json
{
  "id": 1,
  "name": "Lenovo ThinkPad E14",
  "price": 8499
}
```

**New Representation (v2)**:
```json
{
  "id": 1,
  "name": "Lenovo ThinkPad E14",
  "price": {
    "amount": 8499,
    "currency": "MAD"
  }
}
```

#### Why it Causes Compatibility Failures Despite Valid JSON
Even though the payload remains syntactically valid JSON, changing a primitive scalar (`number`) into a composite data structure (`object`) is a **breaking semantic and type change**:

1. **Arithmetic Calculations Crash (`NaN`)**:
   In consumers like the React frontend (`CartContext.jsx` or `Cart.jsx`), calculations compute line items using:
   ```javascript
   const itemTotal = item.price * item.quantity;
   // Evaluates to: { amount: 8499, currency: "MAD" } * 2 => NaN
   ```
   The cart subtotal, taxes, and final order amount evaluate to `NaN` (Not a Number), freezing or corrupting checkout calculations.

2. **UI Render Anomalies**:
   React JSX components rendering `{product.price}` attempt to render a JavaScript object directly inside a text node, which in React throws an unhandled runtime error:
   `Uncaught Error: Objects are not valid as a React child (found: object with keys {amount, currency})`.
   In other environments, it renders unsightly text: `[object Object] MAD`.

3. **Database Insertion & Schema Violations in Orders**:
   The Orders microservice expects `unitPrice` as a numeric column (`REAL` or `DECIMAL`). When it attempts to persist the payload received from Catalog:
   - In SQLite/PostgreSQL, inserting an object stringifies to `"[object Object]"` which fails column numeric constraints.
   - Pydantic/TypeScript validation layers reject the payload with `422 Unprocessable Entity`.

4. **Cascading Failure into Payments**:
   Orders computes a corrupted or zero total and submits it to Payments (`POST /api/payments`). Payments enforces `amount >= 0` and expects a float. If `NaN` or a non-numeric value is forwarded, Payments rejects the transaction with `422 Unprocessable Entity`, bringing the entire purchase flow to a halt.

---

### Q5. Evaluation of API Evolution Strategies

To introduce the multi-currency requirement without disrupting existing microservices, three strategies can be evaluated:

| Strategy | Description | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **1. URI Versioning** (`/api/v1` vs `/api/v2`) | Expose `/api/v1/products` returning scalar `price`, and `/api/v2/products` returning nested `price` object. | Explicit; clear distinction between legacy and modern contracts; no ambiguous payloads. | Causes routing and code duplication in Catalog; requires coordinated updates across every consuming team to migrate. | Viable for major platform re-architectures, but heavy for single-field evolution. |
| **2. Content Negotiation** (`Accept` Header) | Keep `/api/products/{id}`, but vary response format based on `Accept: application/vnd.msoa.v2+json`. | Preserves clean RESTful URIs; single endpoint logic. | Fragile in browser/React clients which default to `Accept: */*`; difficult to debug in API proxies and caches. | Not recommended for this setup. |
| **3. Additive Field Pattern (Non-Breaking Extension)** | Maintain `price: 8499` unchanged, and introduce a new companion field: `pricing: { amount: 8499, currency: "MAD" }`. | **Zero breaking changes**; existing consumers continue operating without modification; new consumers immediately access multi-currency features. | Slight payload redundancy (`amount` duplicated in `price`). | **Recommended & Selected Approach**. |

#### Justification for the Additive Field Pattern
In a microservices architecture developed in parallel by distributed team members, changes must adhere to **Postel's Law (The Robustness Principle)**: *"Be conservative in what you do, be liberal in what you accept from others."*

The Additive Field strategy:
- Completely avoids breaking the React frontend components (`Products.jsx`, `Cart.jsx`, `Checkout.jsx`).
- Guarantees that the Orders and Payments pipelines continue calculating exact totals without requiring synchronized deployments.
- Allows services that need multi-currency capabilities (e.g., international billing or foreign exchange modules) to opt in smoothly.

---

### Q6. Implementation of the Chosen Strategy

#### 1. Catalog Contract Evolution
The Catalog microservice evolves its response schema to include both fields:

```json
{
  "id": 1,
  "name": "Lenovo ThinkPad E14",
  "description": "Intel Core i5, 8 GB RAM, 256 GB SSD",
  "price": 8499,
  "pricing": {
    "amount": 8499,
    "currency": "MAD"
  },
  "stock": 15,
  "category": "laptops"
}
```

#### 2. Backend Implementation (FastAPI / SQLAlchemy)
At the Catalog service level, backward compatibility is guaranteed by keeping `price` as a numeric column in SQLite, adding a `currency` column with default `'MAD'`, and formatting the response:

```python
# catalog/app/schemas/product.py
from pydantic import BaseModel
from typing import Optional

class PricingDetail(BaseModel):
    amount: float
    currency: str = "MAD"

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float                      # Kept for backward compatibility
    pricing: PricingDetail             # New additive field for multi-currency
    stock: int
    category: str
```

```python
# catalog/app/routes/products.py
@router.get("/api/products/{id}", response_model=ProductResponse)
def get_product(id: int, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return ProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price,
        pricing=PricingDetail(amount=product.price, currency=product.currency or "MAD"),
        stock=product.stock,
        category=product.category
    )
```

#### 3. Deprecation Header (Soft Sunset Policy)
To encourage migration over time, the Catalog service can optionally attach deprecation headers without breaking clients:
```http
HTTP/1.1 200 OK
Content-Type: application/json
Deprecation: true
Sunset: 2027-06-01
Link: </api/products/{id}>; rel="deprecation"
```

#### 4. Verification with Existing Consumers
- **React Frontend**: Reads `product.price` — cart calculations ($8499 \times 1 = 8499$) evaluate correctly without `NaN`.
- **Orders Microservice**: Reads `item.price` as float — saves order total correctly.
- **Payments Microservice**: Receives valid float `amount` — executes payment successfully.
- **New Multi-Currency Services**: Can read `product.pricing.currency` to apply dynamic exchange rate conversions.

---

## 5. Deliverable Artifacts & Test Evidence

### Git Repository & Branch
- **Remote**: `https://github.com/Siham0820salhi/msoa-ecommerce-team.git`
- **Branch**: `feature/payments-shipping`
- **Latest Commit Hash**: `3a4d618`
- **Tracked Documentation**:
  - `docs/API_CONTRACT.md` (Part I Analysis & High-Level Endpoints)
  - `docs/contract/04_payments_shipping.md` (Part II Detailed Contracts for Payments & Shipping)
  - `docs/contract/05_evolution.md` (Part III Analysis & Evolution Implementation)

### Automated Test Execution Log

#### Payments Test Suite (`pytest`):
```text
rootdir: C:\Users\dell\Documents\Tp microservices\MSOA-E-com-Demo\payments
collected 13 items

tests\test_payments.py .............                                     [100%]

============================= 13 passed in 1.36s ==============================
```

#### Shipping Test Suite (`pytest`):
```text
rootdir: C:\Users\dell\Documents\Tp microservices\MSOA-E-com-Demo\shipping
collected 16 items

tests\test_shipments.py ................                                 [100%]

============================= 16 passed in 0.85s ==============================
```

### Live Database & Service Verification
Both SQLite databases are active and loaded with the seed records:
- **Payments Query**: `GET http://localhost:8085/api/payments/order/order-demo-001`
  ```json
  {
    "id": "payment-demo-001",
    "orderId": "order-demo-001",
    "amount": 199.0,
    "method": "CARD",
    "status": "SUCCESS",
    "createdAt": "2026-11-01T10:01:00Z"
  }
  ```
- **Shipping Query**: `GET http://localhost:8086/api/shipments/order/order-demo-001`
  ```json
  {
    "id": "shipment-demo-001",
    "orderId": "order-demo-001",
    "address": {
      "name": "Demo Customer",
      "address": "123 Main Street",
      "city": "Casablanca"
    },
    "trackingNumber": "MSOA-DEMO001",
    "status": "DELIVERED",
    "createdAt": "2026-11-01T10:02:00Z",
    "updatedAt": "2026-11-03T15:00:00Z"
  }
  ```
- **Frontend Live Status**: `http://localhost:5173` running with `BACKEND_MODE: { PAYMENTS: "rest", SHIPPING: "rest" }`.

---
*Report prepared and submitted for LAB 3 — Microservice-Oriented Architectures.*

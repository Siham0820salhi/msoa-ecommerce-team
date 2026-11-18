# LAB 3 — API Contract Documentation
**Module**: Microservice-Oriented Architectures (MSOA)  
**Professor**: Zouheir BANOU  
**Group**: Master Big Data & Data Science  
**Team**: Hasnae ELMIR (Payments + Shipping) · Siham SALHI (Auth + Catalog + Inventory + Orders)

---

## PART I — Analysis

### Q1 — Inter-Service Interactions

The six microservices do not operate in isolation. The table below identifies every consumer–provider dependency and the exact endpoint used.

| Consumer | Provider | Method | Endpoint | Information Exchanged |
|---|---|---|---|---|
| Orders | Catalog | GET | `/api/products/{id}` | Product name, unit price (authoritative source of truth) |
| Orders | Inventory | POST | `/api/inventory/reserve` | Reserve stock before confirming an order |
| Orders | Inventory | POST | `/api/inventory/release` | Release reserved stock when order is cancelled |
| Orders | Auth | GET | `/api/auth/me` | Validate Bearer token → resolve `userId` |
| Payments | Orders | GET | `/api/orders/{id}` | Verify order exists and belongs to user before payment |
| Payments | Orders | PATCH | `/api/orders/{id}/status` | Transition order to `PAID` after successful payment |
| Shipping | Orders | GET | `/api/orders/{id}` | Retrieve order details to initialise shipment |
| Shipping | Orders | PATCH | `/api/orders/{id}/status` | Synchronise order status with shipment (`SHIPPED`, `DELIVERED`) |
| Frontend (React) | All | Various | See per-service contracts below | Orchestrates the full checkout flow through the API Gateway |

> **Note**: The React frontend currently orchestrates inter-service calls on behalf of the user during the development phase. In production, an API Gateway or an event bus (e.g., RabbitMQ) would replace direct cross-service HTTP calls.

---

### Q2 — REST Endpoints Per Service

#### Authentication Service — port 8081

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Create a new user account |
| POST | `/api/auth/login` | Authenticate and obtain JWT token |
| POST | `/api/auth/logout` | Invalidate current session token |
| GET | `/api/auth/me` | Return profile of authenticated user |
| GET | `/health` | Health check |

#### Catalog Service — port 8082

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/products` | List all products (supports `?category=&search=`) |
| GET | `/api/products/{id}` | Get one product by ID |
| POST | `/api/products` | Create a product (admin) |
| PUT | `/api/products/{id}` | Full update of a product (admin) |
| DELETE | `/api/products/{id}` | Remove a product (admin) |
| GET | `/health` | Health check |

#### Inventory Service — port 8083

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/inventory` | List all inventory records |
| GET | `/api/inventory/{productId}` | Get stock level for a product |
| POST | `/api/inventory/reserve` | Reserve units for an order |
| POST | `/api/inventory/release` | Release reserved units |
| PATCH | `/api/inventory/{productId}` | Update stock quantity (admin) |
| GET | `/health` | Health check |

#### Orders Service — port 8084

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/orders` | List orders for authenticated user |
| GET | `/api/orders/{id}` | Get order details by ID |
| POST | `/api/orders` | Place a new order |
| PATCH | `/api/orders/{id}/status` | Update order status |
| POST | `/api/orders/{id}/cancel` | Cancel an order |
| GET | `/health` | Health check |

#### Payments Service — port 8085

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/payments` | List all payment records |
| GET | `/api/payments/order/{orderId}` | Get payment record for an order |
| POST | `/api/payments` | Create / process a payment |
| GET | `/health` | Health check |

#### Shipping Service — port 8086

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/shipments` | List all shipment records |
| GET | `/api/shipments/order/{orderId}` | Get shipment for an order |
| POST | `/api/shipments` | Create a new shipment |
| PATCH | `/api/shipments/{id}/status` | Update shipment status |
| GET | `/health` | Health check |

---

## PART II — Full API Contract (Q3)

> See the detailed per-service files in `docs/contract/`:
> - [00 — Shared conventions](contract/00_conventions.md)
> - [01 — Authentication](contract/01_auth.md)
> - [02 — Catalog & Inventory](contract/02_catalog_inventory.md)
> - [03 — Orders](contract/03_orders.md)
> - [04 — Payments & Shipping](contract/04_payments_shipping.md)

---

## PART III — API Evolution (Q4 · Q5 · Q6)

> See [05 — API Evolution](contract/05_evolution.md) for the full analysis.

# LAB 3 — API Contract Documentation
**Module**: Microservice-Oriented Architectures (MSOA)  
**Professor**: Zouheir BANOU  
**Group**: Master Big Data & Data Science  
**Author**: Hasnae ELMIR — responsible for **Payments (port 8085)** and **Shipping (port 8086)**

---

## PART I — Analysis

### Q1 — Inter-Service Interactions (Payments & Shipping perspective)

| Consumer | Provider | Method | Endpoint | Information Exchanged |
|---|---|---|---|---|
| Payments | Orders | GET | `/api/orders/{id}` | Verify the order exists and get its total before processing payment |
| Payments | Orders | PATCH | `/api/orders/{id}/status` | Transition order to `PAID` after a successful payment |
| Shipping | Orders | GET | `/api/orders/{id}` | Retrieve delivery address and items to initialise a shipment |
| Shipping | Orders | PATCH | `/api/orders/{id}/status` | Synchronise order status with shipment (`SHIPPED`, `DELIVERED`) |
| Frontend | Payments | POST | `/api/payments` | Submit payment for a completed order |
| Frontend | Payments | GET | `/api/payments/order/{orderId}` | Display payment status on the Order detail page |
| Frontend | Shipping | POST | `/api/shipments` | Create a shipment once payment is confirmed |
| Frontend | Shipping | GET | `/api/shipments/order/{orderId}` | Display shipment tracking information |
| Frontend | Shipping | PATCH | `/api/shipments/{id}/status` | Update shipment progress (admin / staff view) |

### Q2 — REST Endpoints for Payments and Shipping

#### Payments Service — `http://localhost:8085`

| Method | Endpoint | Description | Status codes |
|---|---|---|---|
| GET | `/api/payments` | List all payment records | 200 |
| GET | `/api/payments/order/{orderId}` | Get payment for a specific order | 200, 404 |
| POST | `/api/payments` | Process a payment for an order | 201, 409, 422 |
| GET | `/health` | Liveness probe | 200 |

#### Shipping Service — `http://localhost:8086`

| Method | Endpoint | Description | Status codes |
|---|---|---|---|
| GET | `/api/shipments` | List all shipment records | 200 |
| GET | `/api/shipments/order/{orderId}` | Get shipment for a specific order | 200, 404 |
| POST | `/api/shipments` | Create a new shipment | 201, 409, 422 |
| PATCH | `/api/shipments/{id}/status` | Update shipment status | 200, 404, 422 |
| GET | `/health` | Liveness probe | 200 |

---

## PART II — Full API Contract (Q3)

See [`docs/contract/04_payments_shipping.md`](contract/04_payments_shipping.md) for the complete formal contract covering items **a through j** for both services.

---

## PART III — API Evolution (Q4 · Q5 · Q6)

See [`docs/contract/05_evolution.md`](contract/05_evolution.md) for the full analysis and implementation.


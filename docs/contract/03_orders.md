# Contrat d'API : Orders

Responsable : Zineb (voir `CONTRACT.md`)
Orders : http://localhost:8084
Conventions communes (headers, schéma d'erreur, codes HTTP) : voir `00_conventions.md`.

---

# ORDERS (port 8084)

Propriétaire des tables `orders` et `order_items`. Orders est l'**orchestrateur** du workflow de commande (`CONTRACT.md`, section 5). Le prix et le nom des produits viennent de Catalog, jamais du frontend.

Objet Order :

```json
{
  "id": "string",
  "userId": "string",
  "customer": { "name": "string", "address": "string", "city": "string" },
  "items": [ { "productId": "integer", "name": "string", "price": "number", "quantity": "integer" } ],
  "total": "number",
  "status": "string (PENDING_PAYMENT | PAID | SHIPPED | DELIVERED | CANCELLED)",
  "createdAt": "string (ISO 8601 UTC)"
}
```

## Statuts et transitions

| Statut actuel | Statuts suivants autorisés |
|---|---|
| `PENDING_PAYMENT` | `PAID`, `CANCELLED` |
| `PAID` | `SHIPPED`, `CANCELLED` |
| `SHIPPED` | `DELIVERED` |
| `DELIVERED` | aucun |
| `CANCELLED` | aucun |

Toute autre transition renvoie `409`. Une commande `SHIPPED`, `DELIVERED` ou `CANCELLED` ne peut plus être annulée.

## Authentification

| Appelant | Header | Droits |
|---|---|---|
| Utilisateur (frontend) | `Authorization: Bearer <token>` (validé auprès d'Auth) | Ses propres commandes uniquement (sinon `403`). Peut passer sa commande à `SHIPPED` / `DELIVERED` (utilisé par `ShipmentTracker.jsx`) |
| Payments, Shipping | `X-Service-Key: <clé interne>` | Lire une commande, la passer à `PAID` (Payments seul), `SHIPPED` / `DELIVERED` (Shipping) |

---

## GET /api/orders?userId={id}

Description : liste les commandes d'un utilisateur.
- URL Params : `userId=[string]` (requis)
- Data Params : aucun
- Headers : `Authorization: Bearer <token>`, `Accept: application/json`
- Body : aucun
- Succès : `200` -> `[ {<order>}, {<order>} ]` (la plus récente d'abord, `[]` si aucune)
- Erreurs :
  - `400` -> `{ "message": "Query parameter userId is required" }`
  - `401` -> `{ "message": "Authentication required" }`
  - `403` -> `{ "message": "You can only list your own orders" }`
  - `503` -> `{ "message": "Auth service unavailable" }`

## GET /api/orders/{id}

Description : retourne une commande. Réservée à son propriétaire.
- URL Params : `id=[string]` (requis)
- Data Params : aucun
- Headers : `Authorization: Bearer <token>` ou `X-Service-Key`, `Accept: application/json`
- Body : aucun
- Succès : `200` -> `{<order>}`
- Erreurs :
  - `401` -> `{ "message": "Authentication required" }`
  - `403` -> `{ "message": "You do not have access to this order" }`
  - `404` -> `{ "message": "Order not found: <id>" }`

## POST /api/orders

Description : crée une commande. Orders récupère les prix chez Catalog, calcule `total`, puis réserve le stock chez Inventory. La commande est créée avec le statut `PENDING_PAYMENT`.
- URL Params : aucun
- Data Params : voir body
- Headers : `Content-Type: application/json`, `Authorization: Bearer <token>`
- Body (schéma) :
  ```json
  {
    "userId": "string (requis)",
    "customer": { "name": "string (requis)", "address": "string (requis)", "city": "string (requis)" },
    "items": [ { "productId": "integer (requis)", "quantity": "integer > 0 (requis)" } ]
  }
  ```
  `items` contient au moins un élément. Les `productId` en double sont additionnés. Tout `price` envoyé par le client est ignoré.
- Succès : `201` -> `{<order>}`
- Erreurs :
  - `400` -> `{ "message": "Invalid request: items.0.quantity: Input should be greater than 0" }`
  - `401` -> `{ "message": "Authentication required" }`
  - `403` -> `{ "message": "userId does not match the authenticated user" }`
  - `404` -> `{ "message": "Product not found: 999" }`
  - `409` -> `{ "message": "Insufficient stock for product 5 (requested 9, available 8)" }` (aucune commande créée, aucun stock modifié)
  - `502` / `503` -> `{ "message": "Inventory service unavailable" }` (Catalog, Inventory ou Auth indisponible)
- Garantie : si la commande ne peut pas être enregistrée après la réservation, le stock est restitué (`release`).

## PATCH /api/orders/{id}/status

Description : change le statut d'une commande selon le tableau des transitions. `CANCELLED` passe par la même logique que `/cancel` (restitution du stock).
- URL Params : `id=[string]` (requis)
- Data Params : voir body
- Headers : `Content-Type: application/json`, `Authorization: Bearer <token>` ou `X-Service-Key`
- Body (schéma) : `{ "status": "string (requis)" }`
- Succès : `200` -> `{<order>}`
- Erreurs :
  - `400` -> `{ "message": "Invalid status: WHATEVER. Allowed: PENDING_PAYMENT, PAID, SHIPPED, DELIVERED, CANCELLED" }`
  - `401` -> `{ "message": "Authentication required" }`
  - `403` -> `{ "message": "Only the Payments service can mark an order as PAID" }` ou commande d'un autre utilisateur
  - `404` -> `{ "message": "Order not found: <id>" }`
  - `409` -> `{ "message": "Invalid transition: PENDING_PAYMENT -> DELIVERED" }`

## POST /api/orders/{id}/cancel

Description : annule une commande et restitue le stock à Inventory, **une seule fois** par commande. Pour une commande `PAID`, Orders interroge Shipping : l'annulation est refusée si l'expédition a dépassé `PREPARING`.
- URL Params : `id=[string]` (requis)
- Data Params : aucun
- Headers : `Authorization: Bearer <token>`
- Body : aucun
- Succès : `200` -> `{<order>}` avec `"status": "CANCELLED"`
- Erreurs :
  - `401` -> `{ "message": "Authentication required" }`
  - `403` -> `{ "message": "You do not have access to this order" }`
  - `404` -> `{ "message": "Order not found: <id>" }`
  - `409` -> `{ "message": "Cannot cancel an order that has already been shipped" }` ou commande déjà annulée
  - `502` / `503` -> `{ "message": "Inventory service unavailable" }` (le stock n'a pas été restitué, la commande reste inchangée et peut être annulée à nouveau)

## GET /health

Description : indique l'état du service.
- URL Params : aucun
- Succès : `200` -> `{ "service": "orders", "status": "UP" }`

---

# Interactions (Orders)

| Appelant | Appelé | Endpoint | Information échangée |
|---|---|---|---|
| Orders | Auth | `GET /api/auth/me` | Validation du token, `id` de l'utilisateur |
| Orders | Catalog | `GET /products/{id}` | Nom et prix réel pour calculer `total` |
| Orders | Inventory | `POST /api/inventory/reserve` | `items[]` à la création (`409` : commande non créée) |
| Orders | Inventory | `POST /api/inventory/release` | `items[]` à l'annulation, une seule fois |
| Orders | Shipping | `GET /api/shipments/order/{orderId}` | Statut de l'expédition avant d'annuler une commande `PAID` |
| Payments | Orders | `GET /api/orders/{id}`, `PATCH /api/orders/{id}/status` | Vérifier la commande (montant), puis `PAID`. Header `X-Service-Key` |
| Shipping | Orders | `GET /api/orders/{id}`, `PATCH /api/orders/{id}/status` | Vérifier `PAID`, puis `SHIPPED` / `DELIVERED`. Header `X-Service-Key` |
| Frontend | Orders | tous les endpoints `/api/orders...` | Commandes de l'utilisateur connecté. Header `Authorization: Bearer` |

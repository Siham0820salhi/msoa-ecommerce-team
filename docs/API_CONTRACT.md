# API Contract : MSOA E-commerce Platform

**Module :** Microservice-oriented Architectures, LAB 3 (Designing an API Contract)
**Professeur :** Zouheir BANOU
**Groupe :** Master Big Data & Data Science

## Équipe

| Membre | Service(s) | Port(s) |
|---|---|---|
| ESSADIKI Ibtissam | Auth | 8081 |
| SALHI Siham (cheffe d'équipe) | Catalog, Inventory | 8082, 8083 |
| ABRABRI Zineb | Orders | 8084 |
| ELMIR Hassnaa | Payments, Shipping | 8085, 8086 |

Dépôt : https://github.com/Siham0820salhi/msoa-ecommerce-team

## Table des matières

1. Partie I : Interactions et endpoints (Q1, Q2)
2. Partie II : Contrats d'API (Q3)
   - 2.1 Conventions communes
   - 2.2 Auth
   - 2.3 Catalog
   - 2.4 Inventory
   - 2.5 Orders
   - 2.6 Payments
   - 2.7 Shipping
3. Partie III : Évolution de l'API et breaking changes (Q4, Q5, Q6)
4. Preuves de tests

---

# 1. Partie I : Interactions et endpoints

## Q1. Interactions entre les six microservices

| # | Fournisseur | Consommateur | Endpoint | Information échangée |
|---|---|---|---|---|
| 1 | Auth | Frontend | `/api/auth/register`, `/login`, `/me`, `/logout` | Inscription, connexion (`user`, `token`), session, déconnexion |
| 2 | Auth | Orders | `GET /api/auth/me` | Validation du token Bearer, identité de l'utilisateur |
| 3 | Catalog | Frontend | `GET /products`, `GET /products/{id}` | Liste et détail des produits |
| 4 | Catalog | Orders | `GET /products/{id}` | Nom et prix réel pour calculer `total` |
| 5 | Inventory | Frontend | `GET /api/inventory/{productId}` | Stock affiché |
| 6 | Inventory | Orders | `POST /api/inventory/reserve` | `items[]` à la création (409 : commande non créée) |
| 7 | Inventory | Orders | `POST /api/inventory/release` | `items[]` à l'annulation, une seule fois par commande |
| 8 | Orders | Payments | `GET /api/orders/{id}` | Vérification de la commande et du montant (header `X-Service-Key`) |
| 9 | Orders | Payments | `PATCH /api/orders/{id}/status` | Passage à `PAID` après un paiement `SUCCESS` |
| 10 | Orders | Shipping | `GET /api/orders/{id}`, `PATCH /api/orders/{id}/status` | Vérification `PAID`, puis `SHIPPED` / `DELIVERED` |
| 11 | Shipping | Orders | `GET /api/shipments/order/{orderId}` | Statut de l'expédition avant d'annuler une commande `PAID` |
| 12 | Payments | Frontend | `/api/payments` | Création et consultation des paiements |
| 13 | Shipping | Frontend | `/api/shipments` | Création et suivi des expéditions |
| 14 | Orders | Frontend | `/api/orders...` | Commandes de l'utilisateur connecté |

Orchestration : **Orders** est l'orchestrateur du workflow de commande (saga orchestrée). Catalog, Inventory et Auth n'appellent aucun autre service.

## Q2. Endpoints par microservice (résumé)

| Service | Méthode | Endpoint | Succès | Erreurs principales |
|---|---|---|---|---|
| Auth | POST | `/api/auth/register` | 201 | 400, 409, 500 |
| Auth | POST | `/api/auth/login` | 200 | 400, 401, 500 |
| Auth | GET | `/api/auth/me` | 200 | 401, 500 |
| Auth | POST | `/api/auth/logout` | 200 | 500 |
| Catalog | GET | `/products` | 200 | 500 |
| Catalog | GET | `/products/{id}` | 200 | 400, 404 |
| Catalog | GET | `/v2/products` | 200 | 500 |
| Catalog | GET | `/v2/products/{id}` | 200 | 400, 404 |
| Inventory | GET | `/api/inventory/{productId}` | 200 | 404 |
| Inventory | POST | `/api/inventory/check` | 200 | 400 |
| Inventory | POST | `/api/inventory/reserve` | 200 | 400, 404, 409 |
| Inventory | POST | `/api/inventory/release` | 200 | 400, 404 |
| Orders | GET | `/api/orders?userId={id}` | 200 | 400, 401, 403, 503 |
| Orders | GET | `/api/orders/{id}` | 200 | 401, 403, 404 |
| Orders | POST | `/api/orders` | 201 | 400, 401, 403, 404, 409, 502/503 |
| Orders | PATCH | `/api/orders/{id}/status` | 200 | 400, 401, 403, 404, 409 |
| Orders | POST | `/api/orders/{id}/cancel` | 200 | 401, 403, 404, 409, 502/503 |
| Payments | GET | `/api/payments` | 200 | 500 |
| Payments | GET | `/api/payments/order/{orderId}` | 200 | 404 |
| Payments | POST | `/api/payments` | 201 | 409, 422, 500 |
| Shipping | GET | `/api/shipments` | 200 | 500 |
| Shipping | GET | `/api/shipments/order/{orderId}` | 200 | 404 |
| Shipping | POST | `/api/shipments` | 201 | 409, 422, 500 |
| Shipping | PATCH | `/api/shipments/{id}/status` | 200 | 404, 422, 500 |

Chaque service expose aussi `GET /health` -> `200 { "service": "<nom>", "status": "UP" }`.

---

# 2. Partie II : Contrats d'API

## 2.1 Conventions communes (tous les services)

- Format : JSON uniquement. Champs en **camelCase** (`productId`, `userId`, `orderId`, `createdAt`).
- Dates en ISO 8601 UTC (exemple : `2026-11-17T18:30:00Z`).
- CORS : chaque service autorise `http://localhost:5173` et `http://127.0.0.1:5173`.
- Chaque service possède sa propre base SQLite. Aucun service n'accède à la base d'un autre : toute communication passe par HTTP/REST.

**Headers**

| Header | Quand | Valeur |
|---|---|---|
| `Content-Type` | Toute requête avec body (POST, PATCH) | `application/json` |
| `Accept` | Recommandé sur les GET | `application/json` |
| `Authorization` | Endpoints protégés (indiqué par endpoint) | `Bearer <token>` |
| `X-Service-Key` | Appels internes Payments/Shipping vers Orders | clé interne |

**Schéma d'erreur commun** (toutes les réponses 4xx et 5xx) :

```json
{ "message": "string" }
```

Le Gist du professeur utilise la clé `error`. Nous utilisons `message` parce que le frontend (`src/services/apiClient.js`) lit `error.message`. Payments et Shipping ajoutent parfois un champ `detail` pour les erreurs 422.

**Codes HTTP**

| Code | Signification |
|---|---|
| 200 | Succès |
| 201 | Ressource créée |
| 204 | Succès sans contenu |
| 400 | Requête invalide (champ manquant, type incorrect, quantité <= 0) |
| 401 | Non authentifié (token absent ou invalide) |
| 403 | Interdit (ex. commande d'un autre utilisateur) |
| 404 | Ressource introuvable |
| 409 | Conflit (stock insuffisant, transition ou annulation interdite) |
| 422 | Erreur de validation du body (utilisé par Payments et Shipping) |
| 500 | Erreur interne |
| 502 / 503 | Service appelé indisponible |

**Services, ports et bases**

| Service | Port | Base |
|---|---|---|
| Auth | 8081 | auth.db |
| Catalog | 8082 | catalog.db |
| Inventory | 8083 | inventory.db |
| Orders | 8084 | orders.db |
| Payments | 8085 | payments.db |
| Shipping | 8086 | shipping.db |

**Modèle utilisé pour chaque endpoint** (correspond aux points a à j du sujet) : description, URL Params, Data Params, Headers, Body (schéma), Succès, Erreurs.

---

## 2.2 AUTH (port 8081)

Responsable : ESSADIKI Ibtissam. Base URL : `http://localhost:8081`.

Propriétaire des tables `users` et `revoked_tokens` dans `auth.db`. Les mots de passe sont stockés sous forme de hash bcrypt et ne sont jamais renvoyés.

Objet User (profil public) :

```json
{
  "id": "string",
  "name": "string",
  "email": "string",
  "role": "string (CUSTOMER | ADMIN)"
}
```

### POST /api/auth/register

Description : crée un nouveau compte client avec hashage bcrypt du mot de passe.
- URL Params : aucun
- Data Params : aucun
- Headers : `Content-Type: application/json`
- Body (schéma) :

```json
{
  "name": "string (requis, non vide)",
  "email": "string (requis, format email valide)",
  "password": "string (requis, minimum 4 caractères)"
}
```

- Succès : `201` ->

```json
{
  "id": "user-5100c3e6",
  "name": "Ibtissam Test",
  "email": "ibtissam@msoa.shop",
  "role": "CUSTOMER",
  "createdAt": "2026-11-18T18:49:30Z"
}
```

- Erreurs :
  - `400` -> `{ "message": "Invalid request" }` (champ manquant ou type invalide)
  - `400` -> `{ "message": "All fields are required" }`
  - `400` -> `{ "message": "Invalid email format" }`
  - `400` -> `{ "message": "Password must be at least 4 characters" }`
  - `409` -> `{ "message": "Email already registered" }`
  - `500` -> `{ "message": "Internal server error" }`

### POST /api/auth/login

Description : authentifie un utilisateur (email et mot de passe) et retourne son profil et un token JWT valide 24 h.
- URL Params : aucun
- Data Params : aucun
- Headers : `Content-Type: application/json`
- Body (schéma) : `{ "email": "string (requis)", "password": "string (requis)" }`
- Succès : `200` ->

```json
{
  "user": { "id": "user-1", "name": "Demo Customer", "email": "demo@msoa.shop", "role": "CUSTOMER" },
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

- Erreurs :
  - `400` -> `{ "message": "Invalid request" }` ou `{ "message": "Email and password are required" }`
  - `401` -> `{ "message": "Invalid email or password" }`
  - `500` -> `{ "message": "Internal server error" }`

### GET /api/auth/me

Description : valide le token JWT Bearer et retourne le profil public de l'utilisateur courant.
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`, `Authorization: Bearer <token>` (requis)
- Body : aucun
- Succès : `200` -> `{ "id": "user-1", "name": "Demo Customer", "email": "demo@msoa.shop", "role": "CUSTOMER" }`
- Erreurs :
  - `401` -> `{ "message": "Missing or invalid authorization token" }`
  - `401` -> `{ "message": "Invalid or expired token" }`
  - `401` -> `{ "message": "Token has been revoked" }` (après déconnexion)
  - `401` -> `{ "message": "User not found" }`
  - `500` -> `{ "message": "Internal server error" }`

### POST /api/auth/logout

Description : déconnecte l'utilisateur et révoque le token courant (enregistré dans `revoked_tokens`).
- URL Params : aucun
- Data Params : aucun
- Headers : `Authorization: Bearer <token>` (recommandé)
- Body : aucun
- Succès : `200` -> `{ "success": true }`
- Erreurs : `500` -> `{ "message": "Internal server error" }`

### GET /health

Succès : `200` -> `{ "service": "auth", "status": "UP" }`

### Interactions (Auth)

| Fournisseur | Consommateur | Information échangée |
|---|---|---|
| Auth | Frontend | Inscription, connexion (`user`, `token`), session (`/me`), déconnexion |
| Auth | Orders | Validation du token Bearer et identité (`id`, `name`, `email`, `role`) via `GET /api/auth/me` |

Auth n'appelle aucun autre service.

---

## 2.3 CATALOG (port 8082)

Responsable : SALHI Siham. Base URL : `http://localhost:8082`.

Propriétaire de la table `products`. Service en lecture seule, public (pas d'authentification requise).

Objet Product (v1) :

```json
{
  "id": "integer",
  "name": "string",
  "category": "string",
  "price": "number",
  "currency": "string (ISO 4217, ex. MAD), ajouté de façon rétrocompatible",
  "image": "string (URL)",
  "description": "string"
}
```

Objet Product (v2) : identique, avec `price = { "amount": number, "currency": "string (ISO 4217)" }`.

### GET /products

Description : liste de tous les produits (v1, `price` reste un nombre). Version dépréciée au profit de `/v2/products`.
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` -> `[ {<product>}, {<product>} ]`. Headers de réponse : `Deprecation: true`, `Link: </v2/products>; rel="successor-version"`
- Erreurs : `500` -> `{ "message": "Internal error" }`

### GET /products/{id}

Description : un produit par identifiant (v1).
- URL Params : `id=[integer]` (requis)
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` -> `{<product>}` (mêmes headers de dépréciation)
- Erreurs :
  - `404` -> `{ "message": "Product not found" }`
  - `400` -> `{ "message": "Invalid request" }` (id non entier)

### GET /v2/products

Description : liste des produits avec la nouvelle structure de prix.
- URL Params : aucun
- Headers : `Accept: application/json`
- Succès : `200` -> `[ {<product_v2>} ]`
- Erreurs : `500` -> `{ "message": "Internal error" }`

### GET /v2/products/{id}

Description : un produit avec la nouvelle structure de prix.
- URL Params : `id=[integer]` (requis)
- Headers : `Accept: application/json`
- Succès : `200` -> `{<product_v2>}`, par exemple `{ "id": 1, "name": "Lenovo ThinkPad E14", "price": { "amount": 8499, "currency": "MAD" }, ... }`
- Erreurs :
  - `404` -> `{ "message": "Product not found" }`
  - `400` -> `{ "message": "Invalid request" }`

### GET /health

Succès : `200` -> `{ "service": "catalog", "status": "UP" }`

---

## 2.4 INVENTORY (port 8083)

Responsable : SALHI Siham. Base URL : `http://localhost:8083`.

Propriétaire de la table `stock`. Dans la base, `stock.quantity` est exposé sous le nom `stock` et `stock.product_id` sous le nom `productId`.

Objet Item (requêtes) :

```json
{ "productId": "integer (requis)", "quantity": "integer > 0 (requis)" }
```

Body commun de `check`, `reserve` et `release` :

```json
{ "items": [ { "productId": 1, "quantity": 2 } ] }
```

`items` contient au moins un élément. Si le même `productId` apparaît plusieurs fois, les quantités sont additionnées.

### GET /api/inventory/{productId}

Description : stock disponible d'un produit.
- URL Params : `productId=[integer]` (requis)
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` -> `{ "productId": 1, "stock": 12 }`
- Erreurs : `404` -> `{ "message": "Unknown product: 999" }`

### POST /api/inventory/check

Description : vérifie la disponibilité de plusieurs produits sans modifier le stock.
- URL Params : aucun
- Data Params : voir body commun
- Headers : `Content-Type: application/json`
- Body : `{ "items": [ { "productId": integer, "quantity": integer > 0 } ] }` (requis)
- Succès : `200` -> `{ "available": true }` ou `{ "available": false }`
- Erreurs : `400` -> `{ "message": "Invalid request: productId and quantity > 0 required" }`

### POST /api/inventory/reserve

Description : réserve le stock de façon **atomique** (tout ou rien). Si un seul produit manque, aucun stock n'est modifié.
- URL Params : aucun
- Data Params : voir body commun
- Headers : `Content-Type: application/json`
- Body : identique à `check`
- Succès : `200` -> `{ "success": true }`
- Erreurs :
  - `400` -> `{ "message": "Invalid request: productId and quantity > 0 required" }`
  - `404` -> `{ "message": "Unknown product: 999" }`
  - `409` -> `{ "message": "Insufficient stock for product 5 (requested 9, available 8)" }`
- Garantie : en cas d'erreur, aucun stock n'est modifié. Le stock ne devient jamais négatif.

### POST /api/inventory/release

Description : remet en stock les quantités indiquées (annulation).
- URL Params : aucun
- Data Params : voir body commun
- Headers : `Content-Type: application/json`
- Body : identique à `check`
- Succès : `200` -> `{ "success": true }`
- Erreurs :
  - `400` -> `{ "message": "Invalid request: productId and quantity > 0 required" }`
  - `404` -> `{ "message": "Unknown product: 999" }`
- Règle : à appeler une seule fois par commande annulée, sinon le stock est gonflé.

### GET /health

Succès : `200` -> `{ "service": "inventory", "status": "UP" }`

### Interactions (Catalog et Inventory)

| Fournisseur | Consommateur | Information échangée |
|---|---|---|
| Catalog | Frontend | Liste et détail des produits |
| Catalog | Orders | Prix réel (`GET /products/{id}`) pour calculer le total |
| Inventory | Frontend | Stock affiché (`GET /api/inventory/{productId}`) |
| Inventory | Orders | `check`, `reserve` (création), `release` (annulation) |

Catalog et Inventory n'appellent aucun autre service.

---

## 2.5 ORDERS (port 8084)

Responsable : ABRABRI Zineb. Base URL : `http://localhost:8084`.

Propriétaire des tables `orders` et `order_items`. Orders est l'orchestrateur du workflow de commande. Le prix et le nom des produits viennent de Catalog, jamais du frontend.

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

**Statuts et transitions**

| Statut actuel | Statuts suivants autorisés |
|---|---|
| PENDING_PAYMENT | PAID, CANCELLED |
| PAID | SHIPPED, CANCELLED |
| SHIPPED | DELIVERED |
| DELIVERED | aucun |
| CANCELLED | aucun |

Toute autre transition renvoie `409`. Une commande `SHIPPED`, `DELIVERED` ou `CANCELLED` ne peut plus être annulée.

**Authentification**

| Appelant | Header | Droits |
|---|---|---|
| Utilisateur (frontend) | `Authorization: Bearer <token>` (validé auprès d'Auth) | Ses propres commandes uniquement (sinon 403). Peut passer sa commande à SHIPPED / DELIVERED (utilisé par `ShipmentTracker.jsx`) |
| Payments, Shipping | `X-Service-Key: <clé interne>` | Lire une commande, la passer à PAID (Payments seul), SHIPPED / DELIVERED (Shipping) |

### GET /api/orders?userId={id}

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

### GET /api/orders/{id}

Description : retourne une commande, réservée à son propriétaire.
- URL Params : `id=[string]` (requis)
- Data Params : aucun
- Headers : `Authorization: Bearer <token>` ou `X-Service-Key`, `Accept: application/json`
- Body : aucun
- Succès : `200` -> `{<order>}`
- Erreurs :
  - `401` -> `{ "message": "Authentication required" }`
  - `403` -> `{ "message": "You do not have access to this order" }`
  - `404` -> `{ "message": "Order not found: <id>" }`

### POST /api/orders

Description : crée une commande. Orders récupère les prix chez Catalog, calcule `total`, puis réserve le stock chez Inventory. Statut initial : `PENDING_PAYMENT`.
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
  - `502 / 503` -> `{ "message": "Inventory service unavailable" }` (Catalog, Inventory ou Auth indisponible)
- Garantie : si la commande ne peut pas être enregistrée après la réservation, le stock est restitué (`release`).

### PATCH /api/orders/{id}/status

Description : change le statut selon le tableau des transitions. `CANCELLED` passe par la même logique que `/cancel` (restitution du stock).
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

### POST /api/orders/{id}/cancel

Description : annule une commande et restitue le stock à Inventory, une seule fois par commande. Pour une commande `PAID`, Orders interroge Shipping : l'annulation est refusée si l'expédition a dépassé `PREPARING`.
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
  - `502 / 503` -> `{ "message": "Inventory service unavailable" }` (stock non restitué, commande inchangée, nouvelle tentative possible)

### GET /health

Succès : `200` -> `{ "service": "orders", "status": "UP" }`

### Interactions (Orders)

| Appelant | Appelé | Endpoint | Information échangée |
|---|---|---|---|
| Orders | Auth | `GET /api/auth/me` | Validation du token, id de l'utilisateur |
| Orders | Catalog | `GET /products/{id}` | Nom et prix réel pour calculer `total` |
| Orders | Inventory | `POST /api/inventory/reserve` | `items[]` à la création |
| Orders | Inventory | `POST /api/inventory/release` | `items[]` à l'annulation, une seule fois |
| Orders | Shipping | `GET /api/shipments/order/{orderId}` | Statut d'expédition avant d'annuler une commande PAID |
| Payments | Orders | `GET /api/orders/{id}`, `PATCH /api/orders/{id}/status` | Vérifier la commande, puis `PAID` (`X-Service-Key`) |
| Shipping | Orders | `GET /api/orders/{id}`, `PATCH /api/orders/{id}/status` | Vérifier `PAID`, puis `SHIPPED` / `DELIVERED` (`X-Service-Key`) |
| Frontend | Orders | `/api/orders...` | Commandes de l'utilisateur connecté (`Authorization: Bearer`) |

---

## 2.6 PAYMENTS (port 8085)

Responsable : ELMIR Hassnaa. Base URL : `http://localhost:8085`. Swagger : `http://localhost:8085/docs`.

Technologie : Python, FastAPI, SQLite, SQLAlchemy, Pydantic v2.

**a. Opérations exposées**

| # | Opération | Méthode | Endpoint |
|---|---|---|---|
| 1 | Lister les paiements | GET | `/api/payments` |
| 2 | Paiement d'une commande | GET | `/api/payments/order/{orderId}` |
| 3 | Traiter un paiement | POST | `/api/payments` |
| 4 | Health check | GET | `/health` |

**Modèle de données** (`payments/schema.sql`)

```sql
CREATE TABLE payments (
    id         TEXT PRIMARY KEY,
    order_id   TEXT NOT NULL UNIQUE,
    amount     REAL NOT NULL CHECK(amount >= 0),
    method     TEXT NOT NULL,
    status     TEXT NOT NULL CHECK(status IN ('SUCCESS','FAILED','PENDING','REFUNDED')),
    created_at TEXT NOT NULL
);
```

Valeurs de `method` : `CARD`, `CASH`, `PAYPAL`, `TRANSFER`. Valeurs de `status` : `PENDING`, `SUCCESS`, `FAILED`, `REFUNDED`. Cycle de vie : `PENDING -> SUCCESS | FAILED`, `SUCCESS -> REFUNDED`.

Objet Payment :

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

### GET /api/payments

Description : retourne tous les paiements (vue admin / debug).
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`
- Succès : `200` -> `[ {<payment>}, {<payment>} ]` (peut être vide)
- Erreurs : `500` -> `{ "message": "Internal server error" }`

### GET /api/payments/order/{orderId}

Description : retourne le paiement lié à une commande.
- URL Params : `orderId=[string]` (requis)
- Data Params : aucun
- Headers : `Accept: application/json`
- Succès : `200` -> `{<payment>}`
- Erreurs : `404` -> `{ "message": "Payment for order 'order-999' not found" }`

### POST /api/payments

Description : crée et traite un paiement pour une commande. Un paiement `SUCCESS` entraîne le passage de la commande à `PAID`.
- URL Params : aucun
- Data Params : voir body
- Headers : `Content-Type: application/json`
- Body (schéma) :

```json
{
  "orderId": "string (requis, non vide, unique dans payments)",
  "amount": "number (requis, >= 0)",
  "method": "string (requis : CARD | CASH | PAYPAL | TRANSFER)",
  "simulateFailure": "boolean (optionnel, défaut false, true pour tester le statut FAILED)"
}
```

- Succès : `201` -> `{<payment>}`, par exemple `{ "id": "3f7a1b2c-...", "orderId": "order-abc-001", "amount": 8499.0, "method": "CARD", "status": "SUCCESS", "createdAt": "2026-11-18T21:00:00Z" }`
- Erreurs :
  - `409` -> `{ "message": "Payment for order 'order-001' already exists" }`
  - `422` -> `{ "message": "Invalid request format", "detail": [...] }` (méthode invalide, montant négatif)
  - `500` -> `{ "message": "Internal server error" }`

### GET /health

Succès : `200` -> `{ "service": "payments", "status": "UP" }`

**CORS** : origines `http://localhost:5173` et `http://127.0.0.1:5173`.

---

## 2.7 SHIPPING (port 8086)

Responsable : ELMIR Hassnaa. Base URL : `http://localhost:8086`. Swagger : `http://localhost:8086/docs`.

**a. Opérations exposées**

| # | Opération | Méthode | Endpoint |
|---|---|---|---|
| 1 | Lister les expéditions | GET | `/api/shipments` |
| 2 | Expédition d'une commande | GET | `/api/shipments/order/{orderId}` |
| 3 | Créer une expédition | POST | `/api/shipments` |
| 4 | Mettre à jour le statut | PATCH | `/api/shipments/{id}/status` |
| 5 | Health check | GET | `/health` |

**Modèle de données** (`shipping/schema.sql`)

```sql
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

Numéro de suivi : `MSOA-XXXXXXXX` (8 caractères alphanumériques majuscules, généré à la création).

Cycle de vie : `PREPARING -> SHIPPED -> IN_TRANSIT -> DELIVERED`, et `CANCELLED` possible depuis `PREPARING` ou `SHIPPED` uniquement.

Objet Shipment :

```json
{
  "id": "shipment-demo-001",
  "orderId": "order-demo-001",
  "address": { "name": "Demo Customer", "address": "123 Main Street", "city": "Casablanca" },
  "trackingNumber": "MSOA-DEMO001",
  "status": "DELIVERED",
  "createdAt": "2026-11-01T10:02:00Z",
  "updatedAt": "2026-11-03T15:00:00Z"
}
```

### GET /api/shipments

Description : retourne toutes les expéditions.
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`
- Succès : `200` -> `[ {<shipment>}, {<shipment>} ]`
- Erreurs : `500` -> `{ "message": "Internal server error" }`

### GET /api/shipments/order/{orderId}

Description : retourne l'expédition liée à une commande.
- URL Params : `orderId=[string]` (requis)
- Data Params : aucun
- Headers : `Accept: application/json`
- Succès : `200` -> `{<shipment>}`
- Erreurs : `404` -> `{ "message": "Shipment not found for orderId: order-999" }`

### POST /api/shipments

Description : crée une expédition avec numéro de suivi généré automatiquement. Statut initial : `PREPARING`.
- URL Params : aucun
- Data Params : voir body
- Headers : `Content-Type: application/json`
- Body (schéma) :

```json
{
  "orderId": "string (requis, non vide, unique dans shipments)",
  "address": {
    "name": "string (requis, nom du destinataire)",
    "address": "string (requis, rue)",
    "city": "string (requis)"
  }
}
```

- Succès : `201` ->

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "orderId": "order-abc-001",
  "address": { "name": "Hassnaa ELMIR", "address": "123 Rue Mohammed V", "city": "Casablanca" },
  "trackingNumber": "MSOA-X7K2P9Q1",
  "status": "PREPARING",
  "createdAt": "2026-11-18T21:00:00Z",
  "updatedAt": "2026-11-18T21:00:00Z"
}
```

- Erreurs :
  - `409` -> `{ "message": "Shipment already exists for orderId: order-001" }`
  - `422` -> `{ "message": "Invalid request format", "detail": [...] }` (champ requis manquant)
  - `500` -> `{ "message": "Internal server error" }`

### PATCH /api/shipments/{id}/status

Description : fait avancer l'expédition dans son cycle de vie. Seules les transitions autorisées sont acceptées.
- URL Params : `id=[string]` (requis, identifiant de l'expédition)
- Data Params : voir body
- Headers : `Content-Type: application/json`
- Body (schéma) : `{ "status": "string (requis : PREPARING | SHIPPED | IN_TRANSIT | DELIVERED | CANCELLED)" }`
- Succès : `200` -> `{<shipment>}` avec le nouveau `status` et `updatedAt` mis à jour
- Erreurs :
  - `404` -> `{ "message": "Shipment not found" }`
  - `422` -> `{ "message": "Invalid status transition from DELIVERED to PREPARING. Allowed transitions: []" }`
  - `500` -> `{ "message": "Internal server error" }`

### GET /health

Succès : `200` -> `{ "service": "shipping", "status": "UP" }`

**CORS** : origines `http://localhost:5173` et `http://127.0.0.1:5173`.

### Interactions (Payments et Shipping)

| Fournisseur | Consommateur | Information échangée |
|---|---|---|
| Payments | Frontend | Création et consultation d'un paiement (`/api/payments`) |
| Shipping | Frontend | Création et suivi d'une expédition (`/api/shipments`) |
| Shipping | Orders | Statut d'expédition (`GET /api/shipments/order/{orderId}`) avant d'annuler une commande PAID |
| Orders | Payments | `GET /api/orders/{id}` (commande et montant), `PATCH /api/orders/{id}/status` -> `PAID` après un paiement `SUCCESS` (`X-Service-Key`) |
| Orders | Shipping | `GET /api/orders/{id}` (commande PAID), `PATCH .../status` -> `SHIPPED` / `DELIVERED` (`X-Service-Key`) |

---

# 3. Partie III : Évolution de l'API et breaking changes

## Q4. Pourquoi le changement casse les consommateurs

Le JSON reste syntaxiquement valide, mais le **contrat** a changé : le type de `price` passe de `number` à `object`. Un consommateur écrit pour un nombre échoue.

| Composant | Conséquence |
|---|---|
| Frontend (`ProductCard`, `Cart`, `Checkout`) | Affichage de `[object Object] MAD`, `price * quantity` donne `NaN`, total du panier faux |
| Orders | Le calcul `total = price * quantity` lève une erreur ou donne `NaN` : la création de commande échoue |
| Tests et autres clients | Échec de validation de schéma |

Conséquences : commandes impossibles, totaux faux, ventes perdues. Le déploiement de Catalog a réussi (aucune erreur au démarrage), mais il a cassé d'autres services. La cause est que le contrat a été modifié sans prévenir les consommateurs : l'indépendance de déploiement n'est réelle que si les contrats sont stables.

## Q5. Comparaison des approches

| Approche | Principe | Avantages | Inconvénients |
|---|---|---|---|
| Modifier sur place | Changer `price` directement | Simple | Casse tous les consommateurs, déploiement coordonné obligatoire |
| Versionnement par URL | `/products` (v1) et `/v2/products` | Clair, v1 intacte, migration à son rythme | Deux versions à maintenir |
| Versionnement par header | `Accept: application/vnd.catalog.v2+json` | URL stable | Moins visible, plus difficile à tester |
| Changement additif | Garder `price` (nombre), ajouter `currency` | Rétrocompatible : les clients ignorent les champs inconnus | Le champ ancien reste le temps de la transition |

**Choix : changement additif en v1 + `/v2/products`** avec la nouvelle structure, puis dépréciation progressive de v1.
- Le frontend et Orders ne cassent pas : aucun champ n'est retiré et aucun type ne change.
- Les nouveaux consommateurs adoptent `/v2` quand ils le décident.
- Principe appliqué : une évolution doit être rétrocompatible (tolerant reader). Un changement incompatible passe par une nouvelle version.

## Q6. Stratégie d'évolution adoptée et implémentation

Règles d'équipe :
1. Aucun champ n'est supprimé ni changé de type dans une version existante.
2. Un nouveau champ peut être ajouté (les consommateurs doivent ignorer les champs inconnus).
3. Un changement incompatible exige une nouvelle version d'URL (`/v2/...`) et l'accord des consommateurs.
4. Une version ancienne est marquée dépréciée (headers `Deprecation: true` et `Link: <...>; rel="successor-version"`) avant d'être retirée.

Implémentation dans Catalog :
- `GET /products` et `GET /products/{id}` (v1) : `price` reste un nombre, le champ `currency` est ajouté, headers de dépréciation.
- `GET /v2/products` et `GET /v2/products/{id}` : `price = { "amount": number, "currency": "MAD" }`.

Démonstration (captures dans `docs/tests/`) :
- v1 renvoie `price: 8499` et `currency: "MAD"`.
- v2 renvoie `price: {"amount": 8499, "currency": "MAD"}`.
- Le frontend affiche toujours les produits (consommateur existant intact).
- Orders crée toujours des commandes avec le prix de v1.

Plan de migration : Orders et le frontend passent à `/v2/products` quand ils sont prêts, puis v1 est retirée.

---

# 4. Preuves de tests

Les captures (Swagger et Postman) sont dans le dossier `docs/tests/` du dépôt.

| Test | Résultat attendu |
|---|---|
| `GET /products/1` (Catalog v1) | `200`, `price` nombre, `currency: "MAD"`, header `Deprecation: true` |
| `GET /v2/products/1` | `200`, `price = {amount, currency}` |
| `GET /v2/products/999` | `404 { "message": "Product not found" }` |
| Frontend `/products` | Produits affichés (consommateur v1 intact) |
| Inventory `reserve` quantité > stock | `409`, stock inchangé |
| Inventory `reserve` multi-produits dont un échoue | `409`, aucun stock modifié (atomicité) |
| Inventory `release` | `200`, stock restauré |
| Inventory produit inconnu | `404` |
| Inventory `quantity = 0` | `400` |

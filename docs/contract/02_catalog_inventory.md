# Contrat d'API : Catalog et Inventory

Responsable : Siham Salhi
Catalog : http://localhost:8082 | Inventory : http://localhost:8083
Conventions communes (headers, schéma d'erreur, codes HTTP) : voir `00_conventions.md`.

---

# CATALOG (port 8082)

Propriétaire de la table `products`. Service en lecture seule, public (pas d'authentification requise).

Objet Product :

```json
{
  "id": "integer",
  "name": "string",
  "category": "string",
  "price": "number",
  "currency": "string (ISO 4217, ex. MAD), ajouté en v1.1, rétrocompatible",
  "image": "string (URL)",
  "description": "string"
}
```

## GET /products

Description : retourne la liste de tous les produits.
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` -> `[ {<product>}, {<product>} ]`
- Erreurs :
  - `500` -> `{ "message": "Internal error" }`

## GET /products/{id}

Description : retourne un produit par son identifiant.
- URL Params : `id=[integer]` (requis)
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` -> `{<product>}`
- Erreurs :
  - `404` -> `{ "message": "Product not found" }`
  - `400` -> `{ "message": "Invalid request" }` (id non entier)


## GET /v2/products

Description : liste des produits avec la nouvelle structure de prix.
- URL Params : aucun
- Headers : `Accept: application/json`
- Succès : `200` -> `[ {<product_v2>} ]`, où `price` = `{ "amount": number, "currency": "string" }`
- Erreurs : `500` -> `{ "message": "Internal error" }`

## GET /v2/products/{id}

Description : un produit avec la nouvelle structure de prix.
- URL Params : `id=[integer]` (requis)
- Succès : `200` -> `{<product_v2>}`
- Erreurs :
  - `404` -> `{ "message": "Product not found" }`
  - `400` -> `{ "message": "Invalid request" }`

Note : les réponses de `/products` et `/products/{id}` (v1) portent les headers `Deprecation: true` et `Link: </v2/products>; rel="successor-version"`.

## GET /health

Description : indique l'état du service.
- URL Params : aucun
- Succès : `200` -> `{ "service": "catalog", "status": "UP" }`

---

# INVENTORY (port 8083)

Propriétaire de la table `stock`. Dans la base, `stock.quantity` est exposé sous le nom `stock` dans l'API, et `stock.product_id` sous le nom `productId`.

Objet Item (utilisé dans les requêtes) :

```json
{
  "productId": "integer (requis)",
  "quantity": "integer > 0 (requis)"
}
```

Body commun des requêtes `check`, `reserve` et `release` :

```json
{ "items": [ { "productId": 1, "quantity": 2 } ] }
```

`items` contient au moins un élément. Si le même `productId` apparaît plusieurs fois, les quantités sont additionnées.

## GET /api/inventory/{productId}

Description : retourne le stock disponible d'un produit.
- URL Params : `productId=[integer]` (requis)
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` -> `{ "productId": 1, "stock": 12 }`
- Erreurs :
  - `404` -> `{ "message": "Unknown product: 999" }`

## POST /api/inventory/check

Description : vérifie la disponibilité de plusieurs produits, sans modifier le stock.
- URL Params : aucun
- Data Params : voir body commun
- Headers : `Content-Type: application/json`
- Body : `{ "items": [ { "productId": integer, "quantity": integer > 0 } ] }` (requis)
- Succès : `200` -> `{ "available": true }` ou `{ "available": false }`
- Erreurs :
  - `400` -> `{ "message": "Invalid request: productId and quantity > 0 required" }`

## POST /api/inventory/reserve

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

## POST /api/inventory/release

Description : remet en stock les quantités indiquées (annulation d'une commande).
- URL Params : aucun
- Data Params : voir body commun
- Headers : `Content-Type: application/json`
- Body : identique à `check`
- Succès : `200` -> `{ "success": true }`
- Erreurs :
  - `400` -> `{ "message": "Invalid request: productId and quantity > 0 required" }`
  - `404` -> `{ "message": "Unknown product: 999" }`
- Règle : à appeler **une seule fois** par commande annulée, sinon le stock est gonflé.

## GET /health

Description : indique l'état du service.
- URL Params : aucun
- Succès : `200` -> `{ "service": "inventory", "status": "UP" }`

---

# Interactions (Catalog et Inventory)

| Fournisseur | Consommateur | Information échangée |
|---|---|---|
| Catalog | Frontend | Liste et détail des produits (`id`, `name`, `category`, `price`, `image`, `description`) |
| Catalog | Orders | Prix réel d'un produit (`GET /products/{id}`) pour calculer le total |
| Inventory | Frontend | Stock affiché sur la page produits (`GET /api/inventory/{productId}`) |
| Inventory | Orders | `check`, `reserve` à la création d'une commande, `release` à l'annulation (`items[]`) |

Catalog et Inventory n'appellent aucun autre service.
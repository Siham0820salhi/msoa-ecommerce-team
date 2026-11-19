# Conventions communes (tous les services)

Ce document s'applique aux six microservices : Auth, Catalog, Inventory, Orders, Payments, Shipping.

## 1. Format des données

- Format : JSON uniquement.
- Noms de champs en **camelCase** (`productId`, `userId`, `orderId`, `createdAt`).
- Dates en ISO 8601 UTC (exemple : `2026-11-17T18:30:00Z`).

## 2. Headers

| Header | Quand | Valeur |
|---|---|---|
| `Content-Type` | Toute requête avec body (POST, PATCH) | `application/json` |
| `Accept` | Recommandé sur les GET | `application/json` |
| `Authorization` | Seulement sur les endpoints protégés (indiqué dans chaque endpoint) | `Bearer <token>` |

## 3. Schéma d'erreur commun

Toutes les réponses 4xx et 5xx ont la même structure :

```json
{ "message": "string" }
```

Le Gist du prof utilise la clé `error`. Nous utilisons `message` parce que le frontend (`src/services/apiClient.js`) lit `error.message`. Avec une autre clé, l'utilisateur verrait seulement « HTTP 409 » sans explication.

## 4. Codes HTTP

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
| 500 | Erreur interne du serveur |
| 502 / 503 | Service appelé indisponible |
| 422 | Erreur de validation du body (utilisé par Payments et Shipping) |
## 5. Services, ports et bases

| Service | Port | Base SQLite |
|---|---|---|
| Auth | 8081 | auth.db |
| Catalog | 8082 | catalog.db |
| Inventory | 8083 | inventory.db |
| Orders | 8084 | orders.db |
| Payments | 8085 | payments.db |
| Shipping | 8086 | shipping.db |

Chaque service possède sa base. Aucun service n'accède à la base d'un autre : toute communication passe par HTTP/REST.

## 6. CORS

Chaque service autorise `http://localhost:5173` et `http://127.0.0.1:5173` (méthodes et en-têtes `*`).

## 7. Règle d'évolution des API

Aucun champ n'est supprimé ni changé de type dans une version existante. Un changement incompatible exige une nouvelle version (ex. `/v2/...`) et l'accord des consommateurs.

## 8. Modèle à suivre pour chaque endpoint

```
## METHODE /chemin
Description : à quoi sert l'opération
- URL Params : nom=[type] (requis/optionnel), ou "aucun"
- Data Params : champs et types, ou "aucun"
- Headers : Content-Type, Authorization si nécessaire
- Body (schéma) : { champ: type (requis/optionnel) }
- Succès : code -> schéma de réponse
- Erreurs : code -> { "message": "string" } (un par cas)
```

Chaque fichier de service se termine par une section **Interactions** : quels services j'appelle, quels services m'appellent, quelle information est échangée.
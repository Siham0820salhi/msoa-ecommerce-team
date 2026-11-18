# Inventory Service

## Rôle
Gère les stocks : consultation, vérification, réservation atomique et libération. Propriétaire de la table `stock`.

## Technologies
Python 3.11, FastAPI, SQLite (`inventory.db`).

## Port
**8083**

## Installation
```bash
pip install fastapi uvicorn
```

## Lancement
```bash
cd inventory
python -m uvicorn main:app --port 8083 --reload
```
Swagger : http://localhost:8083/docs

## Endpoints
| Méthode | Endpoint | Description | Codes |
|---|---|---|---|
| GET | /api/inventory/{productId} | Stock d'un produit | 200, 404 |
| POST | /api/inventory/check | Vérifie la disponibilité | 200, 400 |
| POST | /api/inventory/reserve | Réserve (atomique) | 200, 400, 404, 409 |
| POST | /api/inventory/release | Libère le stock | 200, 400, 404 |
| GET | /health | État du service | 200 |

Corps des POST :
```json
{"items": [{"productId": 1, "quantity": 2}]}
```
Réponses : `{"productId":1,"stock":12}` · `{"available":true}` · `{"success":true}`

## Garanties
- **Atomicité** : `reserve` vérifie tous les produits avant de modifier quoi que ce soit (transaction `BEGIN IMMEDIATE`). Si un seul manque, rien n'est modifié (409).
- **Pas de stock négatif** : contrainte `CHECK(quantity >= 0)` + vérification applicative.
- **Doublons** : `[{1,2},{1,3}]` est fusionné en `{1:5}`.

## Format d'erreur
```json
{"message": "Insufficient stock for product 5 (requested 9, available 8)"}
```
400 requête invalide · 404 produit inconnu · 409 stock insuffisant.

## Exemples curl
```bash
curl http://localhost:8083/api/inventory/1
curl -X POST http://localhost:8083/api/inventory/reserve -H "Content-Type: application/json" -d "{\"items\":[{\"productId\":1,\"quantity\":2}]}"
```

## Communications
- **Appelé par** : **Orders** (`reserve` à la création de commande, `release` à l'annulation) et le frontend (`GET`, `check`).
- **Appelle** : aucun service.
- **Base de données** : `inventory.db`, privée.

## Tests effectués
| Test | Résultat |
|---|---|
| GET /api/inventory/5 | 200, stock correct |
| check quantité > stock | `available: false` |
| reserve quantité > stock | 409, stock inchangé |
| reserve `[{1,2},{5,999}]` | 409, produit 1 inchangé (atomicité) |
| reserve valide | 200, stock décrémenté |
| release | 200, stock restauré |
| produit 999 | 404 |
| quantity = 0 | 400 |
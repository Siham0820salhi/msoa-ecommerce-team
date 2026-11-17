# Catalog Service

## Rôle
Expose la liste des produits (consultation uniquement). Propriétaire de la table `products`.

## Technologies
Python 3.11, FastAPI, SQLite (`catalog.db`).

## Port
**8082**

## Installation
```bash
pip install fastapi uvicorn
```

## Lancement
```bash
cd catalog
python -m uvicorn main:app --port 8082 --reload
```
Swagger : http://localhost:8082/docs

## Endpoints
| Méthode | Endpoint | Description | Codes |
|---|---|---|---|
| GET | /products | Liste des produits | 200 |
| GET | /products/{id} | Détail d'un produit | 200, 404 |
| GET | /health | État du service | 200 |

Produit : `{id, name, category, price, image, description}`

## Exemples curl
```bash
curl http://localhost:8082/products
curl http://localhost:8082/products/1
curl http://localhost:8082/products/999   # 404
```

## Format d'erreur
```json
{"message": "Product not found"}
```

## Communications
- **Appelé par** : le frontend (liste/détail) et **Orders** (pour obtenir le prix réel d'un produit).
- **Appelle** : aucun service.
- **Base de données** : `catalog.db`, privée. Aucun autre service n'y accède directement.

## Tests effectués
- GET /products : 6 produits, 200
- GET /products/1 : 200
- GET /products/999 : 404 `{"message":"Product not found"}`
- Intégration frontend : les produits s'affichent depuis Catalog (log `GET /products 200 OK`)
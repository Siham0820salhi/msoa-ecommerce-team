# CONTRACT.md : Contrat d'équipe MSOA E-commerce

Ce document est la règle commune des 4 membres. Toute modification doit être validée par tout le groupe.

---

## 1. Répartition des services

| Service | Port | Base SQLite | Responsable | Techno |
|---|---|---|---|---|
| Auth | 8081 | auth.db | ESSADIKI Ibtissam | <techno> |
| Catalog | 8082 | catalog.db | SALHI_Siham | FastAPI + SQLite |
| Inventory | 8083 | inventory.db | SALHI_Siham | FastAPI + SQLite |
| Orders | 8084 | orders.db | <Nom> | Zineb |
| Payments | 8085 | payments.db | <Nom> | ELMIR Hasnae |
| Shipping | 8086 | shipping.db | <Nom> | ELMIR Hasnae |

Frontend (Vite) : http://localhost:5173

---

## 2. Règles générales

1. **Un dossier par service** à la racine : `auth/`, `catalog/`, `inventory/`, `orders/`, `payments/`, `shipping/`.
2. **Une base de données par service.** Aucun service ne lit ou n'écrit dans la base d'un autre.
3. **Communication entre services : HTTP/REST uniquement.**
4. **Ports fixes** (voir tableau). Ne pas les changer.
5. **Ne pas modifier les composants React.** Seul `src/config/backend.js` est modifiable.
6. **CORS** : chaque service autorise `http://localhost:5173` et `http://127.0.0.1:5173` (méthodes et en-têtes `*`).
7. **Aucun mot de passe en clair** (hash obligatoire dans Auth, ex. bcrypt).
8. **Le backend est la source de vérité** pour les prix, les stocks et les autorisations. Le frontend n'est jamais cru.
9. Chaque service fournit `GET /health` qui renvoie `{"service": "<nom>", "status": "UP"}`.

---

## 3. Conventions JSON et HTTP

- JSON uniquement, champs en **camelCase** : `productId`, `userId`, `orderId`, `createdAt`.
- Dates en ISO 8601 UTC : `2026-11-17T18:30:00Z`.
- **Format d'erreur commun** (le frontend lit `error.message` dans `apiClient.js`) :
  ```json
  {"message": "texte clair de l'erreur"}
  ```
  Attention : FastAPI renvoie `{"detail": ...}` par défaut. Il faut le remplacer par `{"message": ...}`.
- Codes HTTP :

| Code | Usage |
|---|---|
| 200 | Succès |
| 201 | Ressource créée (POST de création) |
| 204 | Succès sans contenu |
| 400 | Requête invalide (champ manquant, quantité <= 0...) |
| 401 | Non authentifié (token absent ou invalide) |
| 403 | Interdit (ex. commande d'un autre utilisateur) |
| 404 | Ressource introuvable |
| 409 | Conflit (stock insuffisant, transition ou annulation interdite) |
| 500 | Erreur serveur |
| 502/503 | Un service appelé est indisponible |

- Authentification : le frontend envoie `Authorization: Bearer <token>`.

---

## 4. Contrats REST par service

### Auth (8081)
| Méthode | Endpoint |
|---|---|
| POST | /api/auth/login |
| POST | /api/auth/register |
| POST | /api/auth/logout |
| GET | /api/auth/me |

Login renvoie `{"user": {"id","name","email","role"}, "token": "..."}`.

### Catalog (8082) : **sans préfixe `/api`**
| Méthode | Endpoint | Réponse |
|---|---|---|
| GET | /products | liste de produits |
| GET | /products/{id} | un produit ou 404 |

Produit : `{id, name, category, price, image, description}`.

### Inventory (8083)
| Méthode | Endpoint | Réponse |
|---|---|---|
| GET | /api/inventory/{productId} | `{"productId":1,"stock":12}` ou 404 |
| POST | /api/inventory/check | `{"available": true}` |
| POST | /api/inventory/reserve | `{"success": true}` ou 409 |
| POST | /api/inventory/release | `{"success": true}` |

Corps des POST :
```json
{"items": [{"productId": 1, "quantity": 2}]}
```
- `reserve` est **atomique** : si un seul produit manque, aucun stock n'est modifié (409).
- Le stock ne devient jamais négatif.
- Dans la base, `stock.quantity` correspond à `stock` dans l'API.

### Orders (8084)
| Méthode | Endpoint |
|---|---|
| GET | /api/orders?userId={id} |
| GET | /api/orders/{id} |
| POST | /api/orders |
| PATCH | /api/orders/{id}/status |
| POST | /api/orders/{id}/cancel |

Création :
```json
{
  "userId": "user-1",
  "customer": {"name": "Demo Customer", "address": "123 Main Street", "city": "Casablanca"},
  "items": [{"productId": 1, "quantity": 2}]
}
```
Réponse : `{id, userId, customer, items:[{productId,name,price,quantity}], total, status, createdAt}`.

### Payments (8085)
| Méthode | Endpoint |
|---|---|
| GET | /api/payments |
| GET | /api/payments/order/{orderId} |
| POST | /api/payments |

Requête : `{"orderId": "order-123", "method": "CARD"}`.
Réponse : `{id, orderId, amount, method, status, createdAt}`. Un paiement réussi a le statut `SUCCESS` et passe la commande à `PAID`.

### Shipping (8086)
| Méthode | Endpoint |
|---|---|
| GET | /api/shipments |
| GET | /api/shipments/order/{orderId} |
| POST | /api/shipments |
| PATCH | /api/shipments/{id}/status |

Création : `{"orderId": "order-123", "address": {"name","address","city"}}`.
Réponse : `{id, orderId, address, trackingNumber, status, createdAt, updatedAt}`.
Transitions autorisées uniquement : `PREPARING -> SHIPPED -> IN_TRANSIT -> DELIVERED`.

---

## 5. Communications inter-services

| Appelant | Appelé | Endpoint | Quand |
|---|---|---|---|
| Orders | Catalog | GET /products/{id} | Création de commande : prix réel (jamais celui du frontend) |
| Orders | Inventory | POST /api/inventory/reserve | Création de commande |
| Orders | Inventory | POST /api/inventory/release | Annulation autorisée |
| Orders | Auth | GET /api/auth/me | Valider le token et le `userId` |
| Payments | Orders | GET /api/orders/{id}, PATCH /api/orders/{id}/status | Vérifier la commande, puis la passer à `PAID` |
| Shipping | Orders | GET /api/orders/{id}, PATCH /api/orders/{id}/status | Vérifier que la commande est payée, puis synchroniser le statut |

### Règles du workflow de commande
1. **Orders est l'orchestrateur** (saga orchestrée).
2. Création : valider l'utilisateur, récupérer les prix chez Catalog, calculer `total`, appeler `reserve`.
   - `reserve` répond 409 : la commande n'est **pas créée** (ou passe en `REJECTED`), aucun paiement. Message clair renvoyé au frontend.
   - `reserve` répond 200 : commande créée avec le statut initial.
3. Paiement `SUCCESS` : la commande passe à `PAID`.
4. Expédition : possible seulement si la commande est `PAID`. Le statut de la commande reste cohérent avec celui de l'expédition.
5. Annulation : autorisée **uniquement si la commande n'est pas expédiée**. Orders appelle `release` **une seule fois** par commande annulée (un double appel gonflerait le stock).
6. Une commande n'est visible que par son propriétaire (`userId`).
7. Si un service appelé est indisponible : répondre 502/503 avec `{"message": ...}`. Ne jamais laisser une commande à moitié traitée sans compensation (`release` si la suite échoue).

> À confirmer en groupe (regarder `src/services/orderService.js`) : liste exacte des statuts de commande (ex. `PENDING`, `PAID`, `SHIPPED`, `DELIVERED`, `CANCELLED`) et qui les met à jour.

---

## 6. Données de départ

- Les bases de démo viennent de `MSOA_TP_SQLite_6_Services_2026-11-05.zip`.
- Les produits et stocks sont synchronisés avec `src/data/products.js` via `seed_sync.py`, un outil d'initialisation ponctuel, pas un lien entre services.
- Ne pas relancer les `seed.sql` sur une base déjà remplie.

---

## 7. Git

- Une branche par membre : `feature/<service>`.
- Pas de push direct sur `main` : Pull Request.
- Commits clairs : `catalog: add GET /products/{id}`.
- `.gitignore` : `venv/`, `demo_db/`, `__pycache__/`, `*.backup.db`, `node_modules/`.
- Ne jamais faire `git add .` sans vérifier (risque d'ajouter `venv/`).

---

## 8. Lancement

Chaque service a son `README.md` avec : rôle, port, installation, lancement, endpoints, exemples curl, communications et tests.

Ordre de démarrage recommandé : Auth, Catalog, Inventory, Orders, Payments, Shipping, puis `npm run dev`.

Connexion au frontend : dans `src/config/backend.js`, passer le service de `"mock"` à `"rest"` **uniquement quand il est prêt et testé**.

---

## 9. Livrables

- Code source des 6 microservices.
- Instructions de lancement.
- Description des communications inter-services.
- Preuves de tests (captures Swagger, logs terminal, scénarios métier).
# Auth Service

Service d'authentification et de gestion des utilisateurs pour l'application MSOA E-commerce.

- **Responsable :** ESSADIKI Ibtissam
- **Port :** `8081`
- **Base de données :** `auth.db` (SQLite)

## Installation

```powershell
cd auth
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Lancement

```powershell
python -m uvicorn main:app --reload --port 8081
```

Swagger UI : `http://localhost:8081/docs`

## Endpoints

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/health` | Statut du service (`{"service": "auth", "status": "UP"}`) |
| POST | `/api/auth/register` | Création d'un compte client (mot de passe hashé avec bcrypt) |
| POST | `/api/auth/login` | Authentification et génération d'un token JWT |
| GET | `/api/auth/me` | Retourne l'utilisateur authentifié à partir du token Bearer |
| POST | `/api/auth/logout` | Déconnexion et révocation du token |

## Exemples curl

```bash
# Health check
curl http://localhost:8081/health

# Inscription
curl -X POST http://localhost:8081/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Demo User\",\"email\":\"user@msoa.shop\",\"password\":\"password123\"}"

# Connexion (compte démo)
curl -X POST http://localhost:8081/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"demo@msoa.shop\",\"password\":\"demo123\"}"

# Utilisateur courant
curl http://localhost:8081/api/auth/me \
  -H "Authorization: Bearer <TOKEN>"

# Déconnexion
curl -X POST http://localhost:8081/api/auth/logout \
  -H "Authorization: Bearer <TOKEN>"
```

## Communications inter-services

- Appelé par **Orders (`8084`)** via `GET /api/auth/me` (avec `Authorization: Bearer <token>`) pour valider le token JWT et identifier l'utilisateur lors des opérations sur les commandes.

## Tests réalisés

- `GET /health` -> `200 OK` (`{"service": "auth", "status": "UP"}`)
- `POST /api/auth/register` -> `201 Created` (nouveau compte) / `400 Bad Request` (champs manquants) / `409 Conflict` (email existant)
- `POST /api/auth/login` -> `200 OK` (`user` + `token`) / `401 Unauthorized` (identifiants invalides)
- `GET /api/auth/me` -> `200 OK` (token valide) / `401 Unauthorized` (token absent, invalide ou révoqué)
- `POST /api/auth/logout` -> `200 OK` (`{"success": true}`) avec révocation du token
- Intégration testée avec le frontend React (`http://localhost:5173`, `BACKEND_MODE.AUTH = "rest"`).
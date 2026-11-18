# Contrat d'API : Auth

Responsable : Ibtissam Essadiki
Auth : http://localhost:8081
Conventions communes (headers, schéma d'erreur, codes HTTP) : voir `00_conventions.md`.

---

# AUTH (port 8081)

Propriétaire des tables `users` et `revoked_tokens` dans `auth.db`.
Les mots de passe sont stockés sous forme de hash `bcrypt` (`password_hash`) et ne sont jamais renvoyés dans les réponses. Dans la base, `users.created_at` est exposé sous le nom `createdAt` (ISO 8601 UTC).

Objet User (profil public) :

```json
{
  "id": "string",
  "name": "string",
  "email": "string",
  "role": "string (CUSTOMER | ADMIN)"
}
```

## POST /api/auth/register

Description : crée un nouveau compte utilisateur client dans `auth.db` avec hashage du mot de passe (`bcrypt`).
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

## POST /api/auth/login

Description : authentifie un utilisateur via son email et mot de passe, et retourne son profil public accompagné d'un token JWT (valide 24h).
- URL Params : aucun
- Data Params : aucun
- Headers : `Content-Type: application/json`
- Body (schéma) :
  ```json
  {
    "email": "string (requis)",
    "password": "string (requis)"
  }
  ```
- Succès : `200` ->
  ```json
  {
    "user": {
      "id": "user-1",
      "name": "Demo Customer",
      "email": "demo@msoa.shop",
      "role": "CUSTOMER"
    },
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```
- Erreurs :
  - `400` -> `{ "message": "Invalid request" }` ou `{ "message": "Email and password are required" }`
  - `401` -> `{ "message": "Invalid email or password" }`
  - `500` -> `{ "message": "Internal server error" }`

## GET /api/auth/me

Description : valide le token JWT Bearer et retourne le profil public de l'utilisateur courant.
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`, `Authorization: Bearer <token>` (requis)
- Body : aucun
- Succès : `200` ->
  ```json
  {
    "id": "user-1",
    "name": "Demo Customer",
    "email": "demo@msoa.shop",
    "role": "CUSTOMER"
  }
  ```
- Erreurs :
  - `401` -> `{ "message": "Missing or invalid authorization token" }` (header absent ou invalide)
  - `401` -> `{ "message": "Invalid or expired token" }`
  - `401` -> `{ "message": "Token has been revoked" }` (après déconnexion)
  - `401` -> `{ "message": "User not found" }`
  - `500` -> `{ "message": "Internal server error" }`

## POST /api/auth/logout

Description : déconnecte l'utilisateur et révoque le token JWT courant en l'enregistrant dans `revoked_tokens`.
- URL Params : aucun
- Data Params : aucun
- Headers : `Authorization: Bearer <token>` (recommandé)
- Body : aucun
- Succès : `200` -> `{ "success": true }`
- Erreurs :
  - `500` -> `{ "message": "Internal server error" }`

## GET /health

Description : indique l'état du service.
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` -> `{ "service": "auth", "status": "UP" }`

---

# Interactions (Auth)

| Fournisseur | Consommateur | Information échangée |
|---|---|---|
| Auth | Frontend | Inscription (`/api/auth/register`), connexion (`/api/auth/login` -> `user`, `token`), vérification de session (`/api/auth/me`) et déconnexion (`/api/auth/logout`) |
| Auth | Orders | Validation du token JWT Bearer et récupération de l'identité de l'utilisateur (`id`, `name`, `email`, `role`) via `GET /api/auth/me` |

Auth n'appelle aucun autre service.
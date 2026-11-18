# API Contract — Authentication Service

**Service**: `auth`  
**Technology**: Node.js / Express (or FastAPI — to be confirmed by team member)  
**Base URL**: `http://localhost:8081`  
**Swagger / OpenAPI**: `http://localhost:8081/docs`

---

## a. Shared conventions

See [00_conventions.md](00_conventions.md).

---

## b. Endpoints

### POST /api/auth/register

**Description**: Create a new user account.

**Request body**:
```json
{
  "email": "string (required, valid email)",
  "password": "string (required, min 8 chars)",
  "name": "string (required)"
}
```

**Success — 201 Created**:
```json
{
  "id": 1,
  "email": "hasnae@example.com",
  "name": "Hasnae ELMIR",
  "createdAt": "2026-11-17T18:30:00Z"
}
```

**Errors**:
| Code | Condition | Body |
|---|---|---|
| 400 | Missing required field | `{"message": "Field 'email' is required"}` |
| 409 | Email already registered | `{"message": "Email already in use"}` |
| 422 | Validation error | `{"message": "Invalid email format"}` |

---

### POST /api/auth/login

**Description**: Authenticate and return a JWT Bearer token.

**Request body**:
```json
{
  "email": "string (required)",
  "password": "string (required)"
}
```

**Success — 200 OK**:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "userId": 1,
  "name": "Hasnae ELMIR"
}
```

**Errors**:
| Code | Condition | Body |
|---|---|---|
| 400 | Missing credentials | `{"message": "Email and password are required"}` |
| 401 | Invalid credentials | `{"message": "Invalid email or password"}` |

---

### POST /api/auth/logout

**Description**: Invalidate the current session / token.

**Headers**: `Authorization: Bearer <token>`

**Success — 200 OK**:
```json
{ "message": "Logged out successfully" }
```

**Errors**:
| Code | Condition | Body |
|---|---|---|
| 401 | Missing or invalid token | `{"message": "Unauthorized"}` |

---

### GET /api/auth/me

**Description**: Return the authenticated user's profile. Used by other services to validate a token and resolve `userId`.

**Headers**: `Authorization: Bearer <token>`

**Success — 200 OK**:
```json
{
  "id": 1,
  "email": "hasnae@example.com",
  "name": "Hasnae ELMIR",
  "createdAt": "2026-11-17T18:30:00Z"
}
```

**Errors**:
| Code | Condition | Body |
|---|---|---|
| 401 | Missing or expired token | `{"message": "Unauthorized"}` |

---

### GET /health

**Success — 200 OK**:
```json
{ "service": "auth", "status": "UP" }
```

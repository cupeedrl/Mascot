# Mascot — Security Architecture & Guidelines

This document details the security design, cryptographic standards, authorization layers, and privacy protections implemented across Mascot V1.

---

## 1. Authentication & Cryptographic Standards

### Password Storage: Argon2id
- User passwords are never stored in plaintext.
- Hashing is performed using **Argon2id** (OWASP recommended standard) via Python's `pwdlib`/`passlib`.
- Constant-time verification is performed using a dummy hash during invalid email lookups to protect against timing-based user enumeration.

### JWT Access Tokens
- Stateless bearer tokens signed using **HMAC-SHA256 (HS256)**.
- Token payload contains the standard claims (`sub` = user UUID, `iat`, `exp`, `iss`, `aud`).
- Default lifetime: 30 minutes.
- Frontend persists access tokens strictly within `sessionStorage` and React memory, never exposing tokens to vulnerable cross-tab `localStorage`.

---

## 2. Role-Based Access Control (RBAC) & Admin Protection

Mascot enforces a strict two-tier role model:
- `user`: Standard learner permissions.
- `admin`: Elevated permissions for user management, shared catalog curation, and AI usage monitoring.

### Authorization Enforcement:
- Admin endpoints under `/api/v1/admin/*` enforce the `require_admin` dependency server-side:
  - Unauthenticated requests $\rightarrow$ `401 Unauthorized`.
  - Standard user requests $\rightarrow$ `403 Forbidden`.
- **Last Active Admin Protection**: Backend prevents demoting or disabling the final active administrator (`400 Bad Request`), preventing permanent administrative lockout.

---

## 3. Account Status & Disabled User Security

When an administrator disables an account (`is_active = False`):
1. **Login Block**: Attempting to log in with valid credentials returns `403 Forbidden` (`ACCOUNT_DISABLED`).
2. **Anti-Enumeration Guarantee**: Attempting to log in with an invalid password on a disabled account returns the standard generic `401 Unauthorized` (`"Invalid email or password"`), ensuring attackers cannot probe whether an account is disabled.
3. **Active JWT Revocation**: Future API requests using existing tokens issued before deactivation are immediately rejected by `get_current_user` (`401 Unauthorized`).

---

## 4. Secure Password Reset Lifecycle

```text
  User Requests Reset
          │
          v
  Generate Cryptographic Token (secrets.token_urlsafe)
          │
          v
  Hash Token with SHA-256 ───► Store in PostgreSQL (used_at=NULL, expires_in=20m)
          │
          v
  Send Raw Token in One-Time Email Link
          │
          v
  User Opens Link ──────────► Frontend Validates Token on Load
          │
          v
  User Submits New Password ──► Backend Atomically:
                                1. Verifies token is unused & unexpired
                                2. Hashes new password with Argon2id
                                3. Sets used_at = now()
                                4. Invalidates all other pending tokens for user
```

### Key Security Properties:
- **No Token Leakage**: Raw reset tokens are never written to database tables or server log files.
- **Strict Single-Use**: Tokens cannot be reused once submitted.
- **Immediate Invalidation UX**: Frontend validates token immediately on page load; expired or used tokens display clear CTA to `/forgot-password`.
- **Anti-Enumeration**: Forgot-password endpoint returns identical generic confirmation messages regardless of whether the email exists.

---

## 5. Insecure Direct Object Reference (IDOR) Prevention

- All learner-owned resources (`vocabularies`, `exercises`, `exercise_attempts`) enforce multi-tenant isolation.
- Every read, update, review, and delete query explicitly scopes by both `item.id` and `current_user.id`.
- Requests attempting to access another user's resources fail with `404 Not Found`.

---

## 6. Secret Management & Safe Logging

- **No Secrets in Frontend Bundles**: Frontend code never references private API keys (`GROQ_API_KEY`, `RESEND_API_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`).
- **No Secrets in Git**: `.env` and environment files are ignored by git; `.env.example` contains placeholders only.
- **Production Sanitization**: When `ENVIRONMENT=production`, FastAPI automatically disables Swagger UI (`/docs`) and OpenAPI schema introspection (`/openapi.json`).

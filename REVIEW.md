# Mascot Phase 9 — Full Testing and Security Review

Review date: 2026-08-16  
Scope: Phase 1–8 V1 implementation only. No new product feature was added.

## Executive summary

Mascot passed the Phase 9 stability and security review and is ready to enter production preparation. It is **not yet ready for a public production deployment**: rate limiting, production container/proxy/TLS configuration, backup/restore validation, monitoring and deployment controls remain Phase 10 work.

One High dependency issue was found and fixed. The original backend resolved `starlette 0.48.0`; `pip-audit` reported eight known vulnerabilities across that package. FastAPI was upgraded to `0.141.1`, Starlette now has an explicit security floor of `1.3.1` and resolves to `1.6.0`. A clean rebuild followed by a second audit reported no known vulnerabilities.

No Critical issue was found. The remaining Medium/Low items below are explicit accepted or deferred risks, not hidden release claims.

## Verification evidence

| Area | Result |
|---|---|
| Complete backend suite | `129 passed` |
| Critical-path learner journey | Passed with fake AI providers; covers Register → Login → Learn/import → manual vocabulary → AI preview/edit/save → Review → AI exercise → deterministic grading → Dashboard |
| Authentication/JWT matrix | Missing, expired, malformed, wrong-signature, wrong-type, wrong-issuer, wrong-audience and missing-claim tokens rejected |
| Ownership/IDOR | Vocabulary, review, exercise, attempt, AI selection/import and dashboard tests confirm current-user scoping and cross-user denial |
| Frontend type/build | `tsc -b && vite build` passed |
| Frontend browser smoke | Login/Register navigation rendered correctly; unauthenticated `/app` redirected to `/login`; no browser console errors observed |
| Page stacking | Nested `/app` layout has one `Outlet`; routed pages replace one another rather than rendering a previous page underneath |
| Docker startup | PostgreSQL, backend and frontend running; backend health is healthy |
| HTTP smoke | health, database health, OpenAPI and frontend returned success (`200`) |
| Alembic | `upgrade head` passed; current revision `20260815_0004 (head)`; `alembic check` found no new operations |
| Python dependency consistency | `pip check`: no broken requirements |
| Python vulnerability scan | Post-fix `pip-audit --local`: no known vulnerabilities; local package itself is correctly skipped because it is not on PyPI |
| Frontend production dependencies | `npm audit --omit=dev --audit-level=high`: 0 vulnerabilities |
| Secret scan | No Groq/OpenAI-style hardcoded key found outside ignored `.env`; no backend secret-variable reference found in frontend source |

Normal automated tests never call Groq. AI provider behavior is replaced with injected fakes, including timeout, quota, rate-limit, invalid credential, malformed output and invalid business-data cases.

## Critical

No Critical finding.

## High

### H-01 — Known vulnerabilities in the resolved Starlette version

- **Problem:** The prior FastAPI constraint resolved `starlette 0.48.0`. `pip-audit` reported eight known vulnerability records, including `PYSEC-2026-161`, `PYSEC-2026-248`, `PYSEC-2026-249`, `PYSEC-2026-1942`, `PYSEC-2026-2280` and `PYSEC-2026-2281`.
- **Impact:** An internet-facing request-processing framework with known vulnerabilities can expose the API even when Mascot's own endpoint logic is correct.
- **File/component:** `backend/pyproject.toml`; backend Docker image.
- **Recommended fix:** Upgrade to a compatible fixed FastAPI/Starlette pair, rebuild from scratch and rerun the complete suite and dependency audit.
- **Fixed in Phase 9:** **Yes.** FastAPI is constrained to `>=0.141,<0.142`, Starlette to `>=1.3.1,<1.7`; resolver selected FastAPI `0.141.1` and Starlette `1.6.0`. All 129 tests passed and the rebuilt image audit found no known vulnerability.

## Medium

### M-01 — No application/edge rate limiting

- **Problem:** Login, registration and AI generation have validation and size/count limits but no per-IP/per-user request rate limit.
- **Impact:** Password guessing, account creation abuse, provider quota exhaustion and unexpected AI cost remain possible after public exposure.
- **File/component:** Authentication and AI routes; future reverse proxy/API gateway.
- **Recommended fix:** In Phase 10, enforce edge rate limits for auth and per-user limits/budgets for AI, with `429`, retry guidance and metrics. Do not rely only on frontend button disabling.
- **Fixed in Phase 9:** **No.** Deferred because deployment topology and expected traffic are not decided.

### M-02 — Logout is stateless and cannot revoke an issued JWT

- **Problem:** Logout clears the in-memory frontend token but the backend has no denylist/refresh-session record; a copied access token remains valid until expiry.
- **Impact:** A stolen token cannot be immediately revoked. Page reload also requires login again because the token is intentionally memory-only.
- **File/component:** `backend/app/api/v1/routes/auth.py`, `frontend/src/auth/AuthContext.tsx`.
- **Recommended fix:** Keep the short access-token lifetime for V1. Before public launch, decide whether persistent login/revocation justifies an HttpOnly refresh-session design and server-side session table.
- **Fixed in Phase 9:** **No; accepted V1 limitation.** Current memory-only storage avoids long-lived JWT storage in `localStorage` and avoids cookie/CSRF complexity.

### M-03 — Production runtime controls are not implemented

- **Problem:** Compose uses Uvicorn reload, source mounts and development servers. Trusted proxy/host policy, TLS termination, HSTS, non-root runtime, resource limits and production frontend serving are not defined.
- **Impact:** Deploying the development Compose file publicly would be unsafe and operationally fragile.
- **File/component:** `docker-compose.yml`, backend/frontend Dockerfiles and future deployment platform.
- **Recommended fix:** Create separate production images/config in Phase 10; use TLS, explicit trusted hosts/proxies, non-root users, immutable builds and resource/pool limits.
- **Fixed in Phase 9:** **No.** This is deliberately Phase 10 work.

### M-04 — PostgreSQL integration and restore are not automated in the test suite

- **Problem:** The fast backend suite uses SQLite. PostgreSQL was verified through real migration, health and schema-drift checks, but the complete API suite is not run against disposable PostgreSQL and backup/restore was not exercised.
- **Impact:** PostgreSQL-specific JSONB, concurrency, constraint or restore behavior could regress without CI detection.
- **File/component:** `backend/tests/conftest.py`, CI/operations.
- **Recommended fix:** Add a disposable PostgreSQL CI job and a non-production backup/restore runbook/test in Phase 10.
- **Fixed in Phase 9:** **Partially.** Live PostgreSQL migration and connectivity passed; CI and restore remain deferred.

### M-05 — AI content safety is structural, not semantic moderation

- **Problem:** Pydantic and business rules reject malformed AI output, but definitions, examples and explanations can still be inaccurate, biased or inappropriate natural language.
- **Impact:** Learners may see poor-quality content even though database integrity and grading rules remain safe.
- **File/component:** AI prompts/providers and vocabulary/exercise generation services.
- **Recommended fix:** Keep editable vocabulary previews and clear AI labeling; before broad release define reporting/moderation and provider-retention policy. Do not treat the LLM as authoritative.
- **Fixed in Phase 9:** **No; residual product-quality risk.** AI exercise grading remains deterministic and AI vocabulary still requires explicit save.

### M-06 — Cross-owner consistency is enforced in services, not by composite database keys

- **Problem:** `exercise_attempts(user_id, exercise_id)` and `exercise_vocabularies(exercise_id, vocabulary_id)` use individual foreign keys; the database alone cannot prove both referenced rows have the same owner.
- **Impact:** A future unsafe internal write path or manual SQL could create cross-owner links, although current APIs reload and validate ownership and no current exploit path was found.
- **File/component:** Exercise/attempt models and Phase 6/7 services.
- **Recommended fix:** Preserve centralized owner-scoped services. If future write paths multiply, consider composite owner-aware constraints or database triggers after measuring complexity.
- **Fixed in Phase 9:** **No.** Current API-level ownership tests are release-blocking and pass.

### M-07 — Frontend accessibility/component regression automation is limited

- **Problem:** The frontend has native controls, labels, alert roles and visible loading/error/empty states, but no component/browser test framework or automated accessibility scan.
- **Impact:** Keyboard, focus, contrast or responsive regressions may escape backend-heavy CI.
- **File/component:** `frontend/src`, future frontend test configuration.
- **Recommended fix:** Add a small Vitest/Testing Library suite and browser accessibility checks for auth, navigation, editor, review, practice and dashboard in production preparation.
- **Fixed in Phase 9:** **No.** Build, static inspection and a local browser smoke test passed.

### M-08 — Dependency resolution is not fully reproducible for Python

- **Problem:** Python production dependencies use bounded ranges without a committed hash-locked artifact. A future clean build can select a newer version inside those ranges.
- **Impact:** Builds may change without a source diff, complicating rollback and supply-chain review.
- **File/component:** `backend/pyproject.toml`, Docker build/release process.
- **Recommended fix:** Generate and verify a locked, hashed production dependency set in Phase 10 and automate `pip-audit`/`npm audit` in CI.
- **Fixed in Phase 9:** **Partially.** Safe version floors were added and `pip-audit` is now a repeatable development dependency; release locking/CI remain deferred.

### M-09 — CORS accepted overly broad configuration values

- **Problem:** Origins were configurable, but wildcard input was not explicitly rejected and methods/headers were broadly allowed.
- **Impact:** A deployment mistake could weaken the intended browser origin boundary.
- **File/component:** `backend/app/core/config.py`, `backend/app/main.py`.
- **Recommended fix:** Reject wildcard origins and allow only the methods/headers Mascot uses.
- **Fixed in Phase 9:** **Yes.** Origins are normalized/validated; `*` is rejected; credentials remain disabled; allowed methods and headers are explicit. Preflight tests cover trusted and untrusted origins.

### M-10 — API responses lacked baseline anti-cache/browser security headers

- **Problem:** Authenticated API responses did not explicitly send `Cache-Control: no-store`; basic framing/content/referrer headers were absent.
- **Impact:** Sensitive responses could be cached by intermediaries/browser history, and default browser protections were weaker.
- **File/component:** `backend/app/main.py`.
- **Recommended fix:** Add `no-store` to `/api/v1` responses plus `nosniff`, frame denial and a restrictive referrer policy.
- **Fixed in Phase 9:** **Yes, with automated assertions.** HSTS is intentionally deferred until HTTPS deployment.

### M-11 — AI exercise provider context was not explicitly bounded per text field

- **Problem:** Database fields are validated on normal writes, but provider context construction did not independently cap meaning/example lengths and count.
- **Impact:** Unexpected legacy/internal data could increase token usage and data sent to the provider.
- **File/component:** `backend/app/services/ai_exercise.py`.
- **Recommended fix:** Send only required fields and cap meaning and examples again at the provider boundary.
- **Fixed in Phase 9:** **Yes.** Context contains only UUID, word, part of speech, bounded meaning and at most two bounded examples; no user metadata is sent.

### M-12 — Database health logging included exception traceback/details

- **Problem:** A failed database health check logged the caught exception with traceback.
- **Impact:** Infrastructure/connection details could enter logs and increase sensitive operational disclosure.
- **File/component:** `backend/app/api/v1/routes/health.py`.
- **Recommended fix:** Log only a safe failure category and return a generic client error.
- **Fixed in Phase 9:** **Yes.** The client receives `Database unavailable`; logs contain only the exception class.

## Low

### L-01 — Registration reveals whether an email already exists

- **Problem:** Duplicate registration returns `409` with an explicit account-exists message.
- **Impact:** Low-effort email enumeration is possible.
- **File/component:** Authentication registration route.
- **Recommended fix:** Decide at production UX/policy review whether to use a generic response or accept this common registration behavior; rate limiting is more important.
- **Fixed in Phase 9:** **No.** Changing the contract would affect existing UX and tests.

### L-02 — OpenAPI documentation is always public

- **Problem:** `/docs`, `/redoc` and `/api/v1/openapi.json` are enabled in every environment.
- **Impact:** Endpoint discovery becomes easier, although it does not bypass authentication.
- **File/component:** `backend/app/main.py`.
- **Recommended fix:** Make documentation exposure environment-configurable during Phase 10.
- **Fixed in Phase 9:** **No.** Useful for local development.

### L-03 — Duplicate catalog aliases increase API surface

- **Problem:** Both `/languages` and `/catalog/languages` (and equivalent learning-track routes) are registered.
- **Impact:** Minor documentation/maintenance ambiguity.
- **File/component:** API v1 router and catalog routes.
- **Recommended fix:** Deprecate one style in a future versioned cleanup rather than breaking clients now.
- **Fixed in Phase 9:** **No.** No security bypass exists; both aliases require authentication.

### L-04 — Duplicate import conflict handling retries only once

- **Problem:** Catalog import is idempotent and database-backed, but an unusual second concurrent uniqueness conflict can still surface as a safe server error.
- **Impact:** Rare UX failure under simultaneous duplicate clicks; no duplicate data or ownership leak.
- **File/component:** Vocabulary library import service.
- **Recommended fix:** Add a bounded retry/return-skipped path if real concurrency metrics justify it.
- **Fixed in Phase 9:** **No.** Current duplicate tests and unique index pass.

### L-05 — Test client has a forward-compatibility warning

- **Problem:** The upgraded Starlette warns that its `httpx` TestClient compatibility layer is deprecated in favor of `httpx2`.
- **Impact:** No current runtime impact; future test tooling upgrade will be required.
- **File/component:** Backend development test dependencies.
- **Recommended fix:** Migrate when FastAPI/Starlette testing guidance stabilizes; do not suppress the warning without migration.
- **Fixed in Phase 9:** **No.** All tests pass.

### L-06 — Authentication schemas previously ignored unknown ownership fields

- **Problem:** Registration/login models did not explicitly forbid extra fields such as `user_id`.
- **Impact:** The values were never used, but silently accepting them could confuse clients and future maintainers.
- **File/component:** `backend/app/schemas/auth.py`.
- **Recommended fix:** Reject unexpected fields consistently.
- **Fixed in Phase 9:** **Yes.** Both request schemas use `extra="forbid"`; tests verify `422`.

### L-07 — Development pytest version had a known advisory

- **Problem:** The development environment initially resolved `pytest 8.4.2`; `pip-audit` reported `PYSEC-2026-1845` with a fixed version of `9.0.3`.
- **Impact:** This affected test tooling rather than the production image, but leaving known-vulnerable developer tooling increases local/CI risk.
- **File/component:** `backend/pyproject.toml` development dependencies.
- **Recommended fix:** Raise the pytest security floor, rerun the complete suite and audit the full local environment.
- **Fixed in Phase 9:** **Yes.** The constraint is now `pytest>=9.0.3,<10.0`, resolver selected `9.1.1`, all 129 tests passed and the final local audit found no known vulnerability.

## Security conclusions by area

- **Passwords:** Argon2id with explicit time/memory/parallelism parameters; plaintext is never persisted; dummy-hash verification reduces login timing differences; response schemas exclude the hash.
- **JWT:** HS256 only, secret length validated and loaded from environment; expiry, issuer, audience, type, subject, issued-at and unique token ID are validated; inactive/unknown users are rejected on every protected request.
- **Authorization/IDOR:** Backend derives identity only from JWT. Owned queries combine resource ID with `current_user.id`; guessed UUIDs do not grant access. Catalog content is shared read-only, while every import creates rows for the current user.
- **Frontend token handling:** Access token is kept only in React memory and sent as a Bearer header. No token is stored in local/session storage or cookies. This reduces persistence but produces the documented reload/logout limitation.
- **AI:** Calls and keys remain backend-only. Input/output/count/time/token bounds, strict structured schemas, business validation and atomic persistence are present. AI never grades deterministic answers. Vocabulary preview is not persisted until explicit user save.
- **Database:** Catalog and personal data remain separated. Foreign keys, check constraints, ownership indexes, review indexes and the partial unique catalog-import index are present. The migration chain reaches one head without drift.
- **Errors/logs:** Provider details, tokens, passwords and keys are not returned/logged by application code. Provider failures map to safe `429/502/503/504` responses; invalid ownership usually returns non-disclosing `404`.
- **Frontend rendering:** React renders AI/database text as text; no `dangerouslySetInnerHTML` or `eval` was found. Protected routing and one `Outlet` preserve page replacement.

## Production-preparation gate

Phase 9 is complete. Mascot may proceed to Phase 10 once the team accepts this review. Before any public deployment, Phase 10 must at minimum address M-01, M-03 and M-04, define a decision for M-02, automate dependency/security checks, and establish secret injection, monitoring, backups and rollback.

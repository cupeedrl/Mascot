# Mascot — System Architecture

Mascot is an AI-assisted language learning platform engineered around structured CEFR English vocabulary acquisition, spaced-repetition retrieval, and deterministic exercise grading.

---

## 1. System Overview & Data Flow

```text
  +-------------------------------------------------------------------------+
  |                          Client Web Browser                             |
  |             React 19 + TypeScript + Vite SPA (Vercel CDN)               |
  +------------------------------------+------------------------------------+
                                       |
                                       | HTTPS / JSON (REST API)
                                       | Authorization: Bearer <JWT>
                                       v
  +-------------------------------------------------------------------------+
  |                    FastAPI Backend (Render Cloud)                       |
  |                                                                         |
  |  [Auth & RBAC]   [Personal Vocab]   [CEFR Catalog]   [AI Guard & Log]   |
  |   (Argon2id)       (CRUD / Spaced)     (Shared A1-C2)   (Rate-limit)    |
  +--------+-----------------+-------------------+-----------------+--------+
           |                 |                   |                 |
           | SQLAlchemy ORM  | Groq SDK / HTTP   | Resend / SMTP   |
           v                 v                   v                 v
  +----------------+ +---------------+ +---------------+ +-----------------+
  | Neon Postgres  | | Groq AI API   | | Resend / SMTP | | Operational     |
  | Serverless DB  | | (Llama 3.3)   | | (Email Auth)  | | AI Usage Logs   |
  +----------------+ +---------------+ +---------------+ +-----------------+
```

---

## 2. Frontend Layer

- **Framework**: React 19 with TypeScript, bundled by Vite.
- **Routing**: Client-side single-page application routing via `react-router-dom` with route guards:
  - `ProtectedRoute`: Verifies authentication session; redirects unauthenticated users to `/login`.
  - `AdminRoute`: Verifies `user.role === "admin"`; denies access (`403` or redirect) to standard learners.
- **State & Session Management**:
  - `AuthContext`: In-memory and `sessionStorage`-restored access token state.
  - Automatic `401 Unauthorized` interceptor that clears session and redirects to login when credentials expire or when an account is disabled.
- **API Client Layer** (`frontend/src/api/client.ts`):
  - Typed API wrapper using standard `fetch`.
  - Structured error normalization capturing `status`, `message`, and machine-readable error `code` (e.g. `ACCOUNT_DISABLED`).

---

## 3. Backend Layer

- **Framework**: FastAPI (Python 3.12/3.14).
- **Design Pattern**: Layered clean architecture with clear separation of concerns:
  - **API Routes (`app/api/v1/routes/`)**: HTTP endpoints, input deserialization, status codes, query parameter parsing.
  - **Dependencies (`app/api/dependencies.py`)**: Request-scoped database sessions (`get_db`), JWT user authentication (`get_current_user`), and admin role enforcement (`require_admin`).
  - **Service Layer (`app/services/`)**: Core business rules (spaced repetition scheduling, normalization, AI guard, deterministic exercise grading, catalog bulk loading).
  - **Data Access & Models (`app/models/`)**: SQLAlchemy Declarative 2.0 ORM models.
  - **Schemas (`app/schemas/`)**: Pydantic models for strict contract validation and serialization.

---

## 4. Relational Data Modeling & PostgreSQL Schema

```text
                   +------------------+
                   |      users       |
                   |------------------|
                   | id (UUID, PK)    |<-------------------+
                   | email (VARCHAR)  |                    |
                   | role (VARCHAR)   |                    |
                   | is_active (BOOL) |                    |
                   +--------+---------+                    |
                            |                              |
            +---------------+---------------+              |
            | 1                             | 1            | 1
            v N                             v N            v N
  +--------------------+         +--------------------+  +--------------------+
  |    vocabularies    |         |     exercises      |  |   ai_usage_logs    |
  |--------------------|         |--------------------|  |--------------------|
  | id (UUID, PK)      |         | id (UUID, PK)      |  | id (UUID, PK)      |
  | user_id (FK)       |         | user_id (FK)       |  | user_id (FK, NULL) |
  | word (VARCHAR)     |         | exercise_type      |  | feature (VARCHAR)  |
  | normalized_word    |         | prompt (TEXT)      |  | latency_ms (INT)   |
  | learning_status    |         | correct_answer     |  | status (VARCHAR)   |
  | next_review_at     |         +---------+----------+  +--------------------+
  | source_entry_id(FK)|                   | 1
  +---------+----------+                   v N
            |                     +--------------------+
            | N                   | exercise_attempts  |
            v 1                   |--------------------|
  +--------------------+          | id (UUID, PK)      |
  | vocabulary_entries |          | user_id (FK)       |
  |--------------------|          | exercise_id (FK)   |
  | id (UUID, PK)      |          | is_correct (BOOL)  |
  | vocabulary_set_id  |          +--------------------+
  | word (VARCHAR)     |
  | meaning (TEXT)     |
  | translation (TEXT) |
  +--------------------+
```

### Relational Design Highlights:
1. **Ownership Isolation**: Learner-owned entities (`vocabularies`, `exercises`, `exercise_attempts`) strictly enforce `user_id` foreign keys with compound indexes (`(user_id, normalized_word)`).
2. **Safe Shared Catalog Reference**: `vocabularies.source_vocabulary_entry_id` references `vocabulary_entries.id` with `ondelete="SET NULL"`. When admins remove or curate shared catalog words, personal learner notebooks retain the word and definitions intact.
3. **Normalized Word Indexing**: Case-folding and Unicode NFKC normalization stored alongside original display words to allow deterministic $O(1)$ duplicate checks and fast case-insensitive lookups.

---

## 5. External Integrations

### 1. Groq Cloud AI API
- **Model**: `llama-3.3-70b-versatile` / `openai/gpt-oss-20b`.
- **Interface**: OpenAI-compatible REST SDK with fallback configuration.
- **Safety**:
  - `AIGuard` in-memory thread-safe rate-limiting (30s cooldown for exercises, 5s for vocabulary).
  - Pydantic structured output validation rejecting malformed candidate responses.
  - Zero AI calls during grading: grading is 100% deterministic on the backend.

### 2. Email Delivery (Password Reset)
- **Providers**: Resend API (HTTP REST) / Gmail SMTP (`smtplib` standard library) / Console logger.
- **Security**: Raw tokens are hashed with SHA-256 before database storage; tokens expire in 20 minutes and are strictly single-use.

---

## 6. Cloud Deployment Architecture

- **Frontend**: Hosted on Vercel with global edge CDN caching and SPA client-side rewrite rules (`vercel.json`).
- **Backend API**: Hosted on Render as a managed containerized Web Service running Uvicorn.
- **Database**: Serverless PostgreSQL 16 on Neon with connection pooling over SSL.

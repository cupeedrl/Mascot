# Mascot

Mascot is an AI-assisted English vocabulary learning platform focused on structured CEFR A1–C2 acquisition, spaced-repetition retrieval, and deterministic exercise grading.

Built as a production-grade full-stack system with **React 19**, **FastAPI**, **PostgreSQL**, and **Groq AI**, Mascot showcases robust relational data modeling, query optimization, automated migration lifecycles, and operational observability.

---

## Live Demo

- **Web Application**: [https://mascot-ai-learning.vercel.app](https://mascot-ai-learning.vercel.app)
- **API Health Check**: `https://<render-service>.onrender.com/api/v1/health`

---

## Key Features

- **CEFR A1–C2 Shared Catalog**: Standardized curriculum of 2,000+ curated English vocabulary entries with IPA phonetics, definitions, and bilingual examples.
- **Multi-Tenant Personal Notebook**: Individualized vocabulary management with $O(1)$ normalized word deduplication and ownership isolation.
- **Spaced Repetition Review**: Multi-state spaced repetition engine (`new` → `learning` → `review` → `mastered`) with interval scheduling.
- **Contextual AI Practice Generation**: Dynamic generation of sentence cloze (multiple-choice) and 4-blank reading passages with in-flight deduplication.
- **Deterministic Server-Side Grading**: Exercises are graded strictly via deterministic backend rules with snapshot attempt logging; zero AI hallucination or billing overhead during grading.
- **AI-Assisted Vocabulary Enrichment**: Structured metadata generation with schema validation and manual approval workflows.
- **Admin Management Portal**: Role-based access control (`/admin`) for user management, catalog curation, and real-time AI usage monitoring.
- **Hardened Password Recovery**: SHA-256 hashed one-time tokens with 20-minute expiration and anti-enumeration safeguards.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, TypeScript, Vite, React Router, Lucide Icons |
| **Backend** | FastAPI, Python 3.12+, Pydantic v2, SQLAlchemy 2.0 |
| **Database & Migrations** | PostgreSQL 16, Alembic |
| **AI & LLM Inference** | Groq Cloud API (`llama-3.3-70b-versatile` / `openai/gpt-oss-20b`) |
| **Authentication & Security** | JWT (HS256), Argon2id, Role-Based Access Control (RBAC) |
| **Email Delivery** | Gmail SMTP, Resend API |
| **Cloud Infrastructure** | Vercel (Frontend SPA), Render (Backend Web Service), Neon (Serverless PostgreSQL), Docker |

---

## Architecture

```text
  Browser Client (React 19 SPA on Vercel Edge CDN)
                        │
                        │ HTTPS / REST API (JWT Bearer Auth)
                        ▼
      FastAPI Backend (Python Web Service on Render)
          │                     │                     │
          ▼                     ▼                     ▼
  Neon PostgreSQL 16      Groq Cloud API       Email Provider
  (Serverless DB)     (Structured Inference)  (Resend / SMTP)
```

For comprehensive details on component interactions, data flow, and entity relationships, see the [Architecture Documentation](docs/ARCHITECTURE.md).

---

## Engineering Highlights

### 1. Relational Data Modeling & PostgreSQL Schema Design
- Multi-tenant data model enforcing strict foreign keys, compound indexes, and check constraints (`role IN ('user', 'admin')`, `level_code IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')`).
- Safe decoupled references: `vocabularies.source_vocabulary_entry_id` uses `ON DELETE SET NULL` to ensure admin catalog curation never corrupts or cascade-deletes learner personal notebooks.

### 2. Query Optimization & Eliminating N+1 Bottlenecks
- **Bulk Catalog Seeding**: Refactored migration seeding from sequential network round-trips to in-memory set lookups and batch inserts, reducing migration time on remote Neon DB from minutes to seconds.
- **SQL Aggregations**: Dashboard metrics, admin user statistics, and AI usage summaries run in single aggregation queries (`COUNT`, `FILTER`, `AVG`, `SUM`) with zero in-memory Python looping.
- **Database Pagination**: All catalog, vocabulary, user, and log tables execute indexed `LIMIT` / `OFFSET` queries in SQL.

### 3. Concurrency Control & In-Memory Rate Limiting
- Thread-safe `AIGuard` utility enforcing 30-second cooldowns and in-flight SHA-256 fingerprint deduplication, preventing duplicate AI requests from parallel clicks or race conditions.

### 4. Operational AI Observability
- Database-backed `ai_usage_logs` capturing real-time latency (ms), token consumption, HTTP status codes, and error classifications (e.g. 429 rate limits, timeout errors) with zero sensitive prompt exposure.

---

## Scale & Quality Metrics

- **Catalog Coverage**: 2,000+ curated CEFR A1–C2 vocabulary entries across general and academic topics.
- **Backend Test Suite**: **200 tests passing (100%)** via Pytest (auth, IDOR isolation, spaced repetition, grading, admin RBAC, AI guards).
- **Frontend Test Suite**: **31 tests passing (100%)** via Node.js test runner.
- **Frontend Production Build**: Clean production bundle built in **< 350ms** with zero TypeScript or linter errors.
- **Schema Migrations**: **10 sequential Alembic revisions** verified with a single linear head (`20260820_0010`).

---

## Screenshots

> *Screenshots can be captured from the live application and placed in `docs/images/`.*

| Dashboard & Learning Journey | Vocabulary Library & CEFR Catalog |
|:---:|:---:|
| *(Learner progress, streak & review queue)* | *(CEFR A1–C2 browser & personal notebook)* |

| Contextual AI Practice | Admin Portal & AI Monitoring |
|:---:|:---:|
| *(Sentence cloze & fill-in-the-blank grading)* | *(User management, catalog CRUD & AI logs)* |

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 22.12+
- Docker Desktop

### Quick Start
```bash
# 1. Start PostgreSQL
docker compose up -d db

# 2. Run Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # Or: .\.venv\Scripts\Activate.ps1 on Windows
pip install -e ".[dev]"
python -m alembic upgrade head
uvicorn app.main:app --reload

# 3. Run Frontend (separate terminal)
cd frontend
npm ci
npm run dev
```

For complete environment configuration, Docker setup, and testing commands, see the [Development Guide](docs/DEVELOPMENT.md).

---

## Documentation

- 📖 [Project Overview](docs/PROJECT_OVERVIEW.md) — Comprehensive technical reference and complete documentation history.
- 🏗️ [Architecture](docs/ARCHITECTURE.md) — System architecture, data flow, ER design, and integration layers.
- 🚀 [Deployment](docs/DEPLOYMENT.md) — Production setup for Vercel, Render, Neon PostgreSQL, and Docker.
- 🔒 [Security](docs/SECURITY.md) — Authentication, Argon2id, JWT lifecycle, RBAC, and single-use password recovery.
- 🛠️ [Development](docs/DEVELOPMENT.md) — Local development workflow, database migrations, and testing guidelines.

🔗 GitHub: https://github.com/cupeedrl
📧 Gmail: cqdatt41@gmail.com
💼 LinkedIn: https://www.linkedin.com/in/dat-chu-quoc-583599387/
# Mascot

[![CI](https://github.com/cupeedrl/Mascot/actions/workflows/ci.yml/badge.svg)](https://github.com/cupeedrl/Mascot/actions/workflows/ci.yml)

Mascot is an AI-assisted language learning app. Learners build a personal vocabulary notebook from a curated CEFR A1–C2 English catalog (plus an HSK Chinese starter track), review words with spaced repetition, practice with AI-generated exercises, and ask an **AI Learning Assistant** about their own progress.

The assistant is a bounded **LangGraph tool-calling agent**: it can read the learner's real data through whitelisted tools, but it can only *propose* changes. Nothing is written to the database until the learner confirms.

**Live demo:** [mascot-ai-learn.vercel.app](https://mascot-ai-learn.vercel.app) · **API health:** [mascot-114p.onrender.com/api/v1/health](https://mascot-114p.onrender.com/api/v1/health)

> The backend runs on Render's free tier, so the first request after a period of inactivity can take up to a minute while the service wakes up.

---

## Screenshots

The interface is in Vietnamese; the content being learned is English (and Chinese).

| AI assistant answers from the learner's real data | AI proposes a write and waits for confirmation |
|:---:|:---:|
| ![The assistant calls get_learning_stats and get_due_vocabulary, then answers](docs/images/ai-chat.png) | ![Confirmation card for adding "meticulous" to the notebook](docs/images/ai-confirm.png) |
| **Dashboard** | **AI practice, graded by the backend** |
| ![Dashboard with study journey, streak calendar and review queue](docs/images/dashboard.png) | ![AI-generated multiple-choice question from the learner's own words](docs/images/practice.png) |
| **CEFR A1–C2 catalog** | **Personal vocabulary notebook** |
| ![CEFR level picker and topic sets](docs/images/learn.png) | ![Vocabulary cards with IPA, meaning, translation and example](docs/images/vocabulary.png) |
| **Spaced-repetition review** | **Admin: AI usage monitoring** |
| ![Review flashcard with IPA](docs/images/review.png) | ![AI calls with status, latency, rate limits and error types](docs/images/admin-ai-usage.png) |

---

## Features

**Learning**
- **CEFR A1–C2 catalog**: 2,295 curated English entries in 48 topic sets, with IPA, definitions and bilingual examples. An HSK 1 Chinese starter set shows the multilingual track.
- **Personal notebook**: per-user vocabulary with search, filters, topics and normalized duplicate detection; users can never see each other's data.
- **Spaced repetition**: words move through `new → learning → review → mastered` with interval scheduling, a daily review queue and a study streak.
- **AI practice**: sentence-cloze questions and 4-blank reading passages generated from the learner's own words. Answers are graded by deterministic backend rules, not by the model.

**AI Learning Assistant**
- Answers questions about the learner's own progress by calling read tools on their data, and streams the answer as it is written.
- Can propose adding a word to the notebook; nothing is saved until the learner clicks **Confirm**.
- Conversations are saved per user, and replies follow the user's language.

How it is built is described in [AI Engineering](#ai-engineering).

**Platform**
- JWT authentication with Argon2id password hashing, and password reset through hashed, single-use, 20-minute links.
- Admin portal (RBAC) for users, the shared catalog, and AI usage monitoring.

---

## AI Engineering

Design detail: [AI assistant architecture](docs/ai/ARCHITECTURE.md) · [AI design decisions](docs/ai/DECISIONS.md)

**Agent and tool calling**
- A bounded, single-agent loop in **LangGraph** (`START → model ⇄ tools → END`). LangChain provides the chat-model interface through `ProviderChatModel`, an adapter over Mascot's own provider layer ([`agent_graph.py`](backend/app/ai/agent_graph.py), [`langchain_chat_model.py`](backend/app/ai/langchain_chat_model.py)).
- The model chooses among whitelisted read tools (`get_learning_stats`, `get_due_vocabulary`, `get_learning_profile`). Each tool declares Pydantic argument and result schemas, a read/write class, and runs under a Postgres statement timeout and a payload size limit ([`ai/tools/`](backend/app/ai/tools)).
- The original hand-written loop is kept behind `AI_AGENT_ENGINE=legacy` as a rollback path. Parity tests run the same scenarios through both engines and require identical provider-visible messages, results and error stages.

**Human-in-the-loop writes**
- A write tool (`add_vocabulary`) never runs inside the loop: the run ends with a proposal. The backend signs an expiring, single-use action token, and the database changes only through `POST /ai/actions/confirm`, which checks the signature, owner and replay guard ([`action_tokens.py`](backend/app/ai/action_tokens.py)).

**Guardrails**
- Provider output is untrusted: it is validated before it enters the conversation. Tool-round and tool-call budgets, argument size limits and tool timeouts are enforced in code, and the user's identity always comes from the JWT, never from model arguments ([`agent_guardrails.py`](backend/app/ai/agent_guardrails.py)).
- The system prompt is backend-owned and treats learner data as data, not instructions. Logs use sanitized identifiers, and no secrets are logged.

**Structured generation**
- Exercises and vocabulary entries use structured outputs parsed into Pydantic models. The backend then checks them semantically (targets come from the learner's word pool, the correct option matches the word, no duplicate prompts), repairs duplicate cloze options, shuffles answer positions, and grades answers with deterministic rules ([`ai_exercise.py`](backend/app/services/ai_exercise.py)).

**Streaming**
- `POST /ai/chat/stream` sends the answer as Server-Sent Events: `delta` events carry a display-only draft, `discard` drops it (on a retry, a provider fallback, or a reply that turns into tool calls), and `done` carries the validated, persisted response, the same body `POST /ai/chat` returns. Tool rounds run before the answer streams ([`ai_chat.py`](backend/app/api/v1/routes/ai_chat.py), [`chatStream.ts`](frontend/src/ai/chatStream.ts)).

**Reliability**
- Provider calls retry with exponential backoff on rate limits, timeouts and 5xx/network errors.
- An optional second provider (`AI_FALLBACK_PROVIDER`) takes over only for those transient failures. Auth, configuration and invalid-response errors are never hidden behind a fallback ([`fallback_provider.py`](backend/app/ai/fallback_provider.py)).
- A per-user cooldown and in-flight fingerprinting reject duplicate AI requests.

**Observability**
- Every AI request writes an `ai_usage_logs` row: the provider and model that actually answered, input/output/total tokens summed across tool rounds, latency, status and error type. The admin portal's AI usage page shows them ([`token_usage.py`](backend/app/ai/token_usage.py)).
- Each chat turn also logs a request summary: provider calls, tool rounds, tool names and per-tool latency.

**Evaluation**
- 43 offline eval cases in 7 categories (normal learning, tool routing, ambiguous requests, write actions, prompt injection, guardrails, confirmation security) run against a scripted provider, so they cost no tokens. CI fails unless every case passes ([`backend/evals/`](backend/evals)).
- These are behavior and safety evals. They do not measure the answer quality of a live model.

**Known limitations**
- Rate-limit, dedup and replay-guard state lives in process memory, so the backend runs as a single worker.
- When a fallback happens mid-turn, later tool rounds still try the primary provider first.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, TypeScript, Vite, React Router |
| **Backend** | Python 3.11–3.14, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| **AI** | LangGraph, LangChain Core, OpenAI-compatible Chat Completions and Responses APIs (Groq by default: `openai/gpt-oss-20b` for chat, `openai/gpt-oss-120b` for exercises; OpenAI as an optional fallback provider), Server-Sent Events |
| **Database** | PostgreSQL 16 |
| **Security** | JWT (HS256), Argon2id, RBAC |
| **Email** | Gmail SMTP, Resend, Brevo |
| **Infrastructure** | Docker, Docker Compose, Vercel (frontend), Render (backend), Neon (PostgreSQL); also self-hosted on an Oracle Linux 9 VM |

---

## Architecture

```text
 React SPA (Vercel)
        │  HTTPS / REST and SSE, JWT bearer
        ▼
 FastAPI backend (Render / Docker)
   ├── Auth, vocabulary, review, exercises, admin  ──►  PostgreSQL (Neon)
   ├── AI Learning Assistant  (POST /ai/chat, or /ai/chat/stream for SSE)
   │     LangGraph:  START → model ⇄ tools → END
   │       read tools  ──► run inside the loop
   │       write tools ──► stop the loop, return a pending action
   │                         └─► POST /ai/actions/confirm (signed token) ──► database
   ├── AI exercise and vocabulary generation (structured outputs)
   │     provider: Groq, falling back to OpenAI on transient failures if configured
   ├── ai_usage_logs: provider, model, tokens, latency, status  ──►  admin dashboard
   └── Password reset email  ──►  Gmail SMTP / Resend / Brevo
```

More detail: [System architecture](docs/ARCHITECTURE.md) · [AI assistant architecture](docs/ai/ARCHITECTURE.md) · [AI design decisions](docs/ai/DECISIONS.md)

---

## Quality

- **Backend:** 574 pytest test cases (auth, data isolation, spaced repetition, grading, admin RBAC, AI guardrails, agent and tool execution, provider retry and error mapping, token usage accounting, provider fallback, SSE streaming).
- **Frontend:** 84 tests with the Node.js test runner, plus a type-checked production build.
- **AI evals:** 43 offline cases with a scripted provider, so they run without network access or token cost.
- **Migrations:** 14 linear Alembic revisions, head `20260908_0014`.
- **CI:** GitHub Actions ([`ci.yml`](.github/workflows/ci.yml)) runs ruff, the backend tests and evals on Python 3.12 and 3.14, `pip-audit`, and the frontend tests and build on every push and pull request. The evals step fails unless every case passes.

```bash
cd backend && ruff check . && pytest -q && python -m evals.run_chatbot_evals
cd frontend && npm test && npm run build
```

---

## Local Development

**Prerequisites:** Python 3.11+, Node.js 22.12+, Docker Desktop.

```bash
# 1. Environment files (then set POSTGRES_PASSWORD, JWT_SECRET_KEY and GROQ_API_KEY)
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 2. PostgreSQL 16 on localhost:5432 (any local install works; this uses Docker)
docker run -d --name mascot-db --env-file .env -p 5432:5432 postgres:16-alpine

# 3. Backend and frontend in Docker (they reach PostgreSQL through host.docker.internal:5432)
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
```

To run without Docker instead:

```bash
# Backend (from backend/)
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m alembic upgrade head
uvicorn app.main:app --reload

# Frontend (from frontend/, in a second terminal)
npm ci
npm run dev
```

The app runs at `http://localhost:5173` and the API docs at `http://localhost:8000/docs`. To open the admin portal, register an account and run `python scripts/set_admin.py <email>` from `backend/`.

Full guide: [Development](docs/DEVELOPMENT.md) · [Deployment](docs/DEPLOYMENT.md) · [Self-hosting on an Oracle Cloud Always Free VM](docs/DEPLOY_ORACLE_CLOUD.md) · [Security](docs/SECURITY.md)

---

## Built with AI coding agents

Mascot was built during my Data & AI internship with Claude Code and Codex as pair programmers. The repo carries the context those agents need:

- [`CLAUDE.md`](CLAUDE.md) and [`AGENTS.md`](AGENTS.md): project map, architectural rules the agent must not break, and working rules.
- [`.claude/commands/`](.claude/commands): `/verify` (picks and runs the right checks for the changed files) and `/explain`.
- [`.agents/skills/`](.agents/skills): the same `verify` workflow packaged as an agent skill.

---

## Author

**Chu Quoc Dat** · [GitHub](https://github.com/cupeedrl) · [LinkedIn](https://www.linkedin.com/in/dat-chu-quoc-583599387/) · cqdatt41@gmail.com

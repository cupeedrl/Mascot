# Mascot — Claude Code Guide

## Project

Mascot is an AI-assisted language learning platform: personal vocabulary, CEFR English and HSK Chinese catalogs, spaced-repetition review, exercises, and an AI Learning Assistant chatbot.

| Area | Stack |
|---|---|
| `backend/` | Python 3.11–3.14, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (psycopg), PyJWT, pydantic-settings, `openai` SDK |
| `frontend/` | React 19, TypeScript, Vite, react-router |
| AI provider | Groq (default) or OpenAI, both via the OpenAI-compatible Chat Completions API |
| Local infra | `docker-compose.yml`: `db` (Postgres 16), `backend`, `frontend` |
| Docs | `docs/` (general), `docs/ai/` (AI architecture, learning plan, decisions) |

## AI chatbot (CURRENT)

A custom, bounded, single-agent tool-calling loop. LangChain and LangGraph are **not** installed. Full detail: `docs/ai/ARCHITECTURE.md`.

- `POST /api/v1/ai/chat` → `backend/app/api/v1/routes/ai_chat.py` → `run_chat_agent()` in `backend/app/ai/chat_agent.py`
- Provider: `ChatAIProvider` protocol (`ai/provider.py`), implemented by `ai/openai_compatible_provider.py`, selected in `ai/dependencies.py`
- Tools: `ai/tools/registry.py` (`TOOL_REGISTRY`), `ai/tools/executor.py`, handlers in `learning_tools.py` / `vocabulary_tools.py`
- Human-in-the-loop writes: `ai/action_tokens.py` + `routes/ai_actions.py` (`/ai/actions/confirm`, `/ai/actions/cancel`)
- Conversation memory: `services/ai_conversation.py` (user-visible messages only)
- Offline evals: `backend/evals/` (scripted fake provider)

## Architectural constraints — do not break

1. Provider output is untrusted and is validated before entering the conversation (`_validate_provider_result`).
2. Write tools never execute inside the agent loop. `execute_tool` is read-only; `execute_confirmed_tool` runs only after action-token verification.
3. A write proposal must be the only tool call in its round.
4. `user_id` and `learning_track_id` come from the JWT/request, never from model-authored arguments.
5. Tool arguments and results are validated against Pydantic schemas and bounded by size and time.
6. Agent budgets (rounds, calls per round, total calls) are enforced; values come from settings.
7. The system prompt is backend-owned and first; the response-language hint is deterministic (no model call).
8. Error types map to stable HTTP status codes, and the frontend depends on the `AIChatResponse` shape (including `confirmation_required`).
9. `ChatAIProvider` is the seam that tests and evals mock — keep it working.

## Working rules

- **Investigate before claiming.** Read the relevant code before describing or changing it. Cite `file:line`. Say explicitly when something is inferred or unverified. When docs and code disagree, code wins.
- **Prefer minimal changes.** Make the smallest change that satisfies the request. No drive-by refactors, renames, reformatting, or new dependencies without asking.
- **Preserve existing tests.** Never delete, skip, weaken, or rewrite existing tests to make them pass. If a test looks wrong, explain why and ask.
- **Run relevant tests after implementation** (see Commands or `/verify`) and report results faithfully, including failures.
- **Do not change production configuration unless explicitly requested:** `docker-compose.yml`, Dockerfiles, `.env*`, `backend/app/core/config.py` defaults, `pyproject.toml`, `package.json`, Alembic migrations. Never print secrets from `.env` files.
- Do not commit unless asked.

## Commands

Backend (from `backend/`, venv active; on Windows without activation use `.\.venv\Scripts\python.exe -m ...`):

```bash
pytest -q                                  # all backend tests (in-memory SQLite, no Postgres needed)
pytest tests/test_ai_chat_phase3.py -q     # single file
python -m evals.run_chatbot_evals          # chatbot contract/safety evals, no network
```

Frontend (from `frontend/`):

```bash
npm test          # runs the explicit file list in package.json — new test files must be added there
npm run build     # type-check + production build
```

Docker (repo root): `docker compose config -q`, `docker compose build backend frontend`.

Project slash commands: `/verify`, `/explain <file|symbol|topic>`.

## Learning mode

The user is using Mascot to learn LangChain and LangGraph. Roadmap: `docs/ai/LEARNING_PLAN.md`. Decisions: `docs/ai/DECISIONS.md` (the custom loop stays in production during learning).

For any request about learning, LangChain, LangGraph, or changes to the AI architecture, follow this workflow:

1. **Explain the concept first** — briefly and concretely.
2. **Explain why it is relevant to Mascot.**
3. **Map the concept to the current architecture** — name the real files and functions.
4. **Propose an implementation plan** — files, steps, tests, risks.
5. **Stop. Implement only after the user explicitly asks for implementation.** Approval for one stage does not carry over to the next.
6. **After implementation, explain the important files and code paths.**
7. **Run relevant verification** (`/verify`).
8. **Summarize what changed and why.**

Learning prototypes stay isolated from `backend/app/` (proposed location: `backend/learning/`, not yet created) and use fake chat models by default so they cost no tokens. Adding LangChain/LangGraph to `pyproject.toml` is a configuration change and requires an explicit request.

---
description: Inspect current changes and run the relevant Mascot checks
---

Verify the current working-tree changes. Do not modify, create, or delete any files.

## 1. Inspect changes

Run `git status --short`, `git diff --stat`, `git diff`, and `git diff --cached`. List untracked files. Summarize what changed in a few lines.

## 2. Select checks from the changed paths

| Changed paths | Checks |
|---|---|
| `backend/app/ai/**`, `backend/app/api/v1/routes/ai_*.py`, `backend/app/services/ai_*.py`, `backend/app/schemas/ai_*.py` | AI test files (`pytest tests/test_ai_*.py tests/test_tool_registry_and_execution.py tests/test_multilingual_chat_phase3.py -q`), then `python -m evals.run_chatbot_evals`, then full `pytest -q` |
| Other `backend/**` Python | `pytest -q` |
| `backend/alembic/versions/**` | `pytest -q`; note that the migration still needs `alembic upgrade head` on a local DB (never run against a non-local DB) |
| `backend/learning/**` (prototypes) | The prototype's own tests; also `pytest -q` if it imports `app` |
| `frontend/**` | `npm test` and `npm run build` (from `frontend/`) |
| `docker-compose.yml`, `**/Dockerfile`, `**/.dockerignore`, `backend/pyproject.toml`, `frontend/package*.json` | `docker compose config -q` and `docker compose build <affected service>`, plus the backend/frontend checks above |
| Docs, `CLAUDE.md`, `.claude/**` only | No tests required — say so explicitly |

Backend commands run from `backend/`. If the venv is not active on Windows, use `.\.venv\Scripts\python.exe -m pytest` / `-m evals.run_chatbot_evals`.

## 3. Run the checks

- Do not run scripts that call live AI providers or send email (e.g. `scripts/diagnose_groq_connection.py`, `scripts/test_gmail_smtp.py`).
- Do not start, stop, or recreate running containers; `config` and `build` only.
- If a check cannot run (no venv, Docker not running, missing dependency), report it as **NOT RUN** with the reason — never as passed.

## 4. Report

Give a table: check | command | result (PASS / FAIL / NOT RUN).

For each failure: failing test names, the relevant error excerpt, the likely cause with `file:line`, and whether it appears related to the current diff or possibly pre-existing (say when unsure).

## Rules

- Never modify tests, skip tests, or change source code to make checks pass. `/verify` only reports.
- Never weaken assertions or change configuration to hide a failure.

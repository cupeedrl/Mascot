---
description: Explain a Mascot file, symbol, or code path without modifying anything
argument-hint: <file path, symbol, or topic>
---

Explain: $ARGUMENTS

If no target was given, ask what to explain and stop.

This command is read-only: do not create, modify, or delete files.

## Investigate first

Read the target, then find its callers (Grep), its callees, related schemas/settings, and the tests that cover it. Base every claim on code you have read, cite `file:line`, and mark anything inferred.

## Output

1. **Purpose** — what it does and what problem it solves, in 2–4 sentences.
2. **Dependencies** — internal modules, external libraries, settings (`app/core/config.py`), DB models, and what depends on it.
3. **Control flow** — entry point(s) and numbered steps with `file:line`, including error paths.
4. **Place in Mascot's architecture** — its layer (route / service / ai / tools / model / frontend) and how it relates to `docs/ai/ARCHITECTURE.md`. Distinguish CURRENT behavior from PLANNED changes.
5. **Design decisions and risks** — why it is built this way, which constraints from `CLAUDE.md` it protects, limitations, and test-coverage gaps.
6. **Learning connection** (only when relevant) — the LangChain or LangGraph concept this corresponds to, per `docs/ai/LEARNING_PLAN.md`.

Keep it concise. Prefer short code excerpts over long ones.

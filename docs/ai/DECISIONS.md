# AI Architecture Decisions

Lightweight decision log for Mascot's AI architecture and the LangChain/LangGraph learning effort. Add new entries at the bottom; supersede rather than delete.

Format: **Status** · **Context** · **Decision** · **Consequences**.

---

## D-001 — Keep the current custom agent loop during learning

- **Date:** 2026-09-15
- **Status:** Accepted
- **Context:** Mascot's chatbot is a working, tested custom loop (`backend/app/ai/chat_agent.py`) with explicit safety guarantees: validated provider output, tool budgets, read-only execution, and confirmation-gated writes.
- **Decision:** The custom loop remains the production implementation for the entire learning period.
- **Consequences:** Learning work does not touch the production AI path. LangChain and LangGraph are not production dependencies.

## D-002 — Do not rewrite Mascot immediately

- **Date:** 2026-09-15
- **Status:** Accepted
- **Context:** There is not yet evidence that a framework improves Mascot enough to justify the cost and risk of a rewrite.
- **Decision:** No framework rewrite until `LEARNING_PLAN.md` stage 12 produces an explicit, recorded decision.
- **Consequences:** Framework adoption is evaluated with evidence (stage 11 comparison), not assumed.

## D-003 — Learn by building small isolated prototypes first

- **Date:** 2026-09-15
- **Status:** Accepted
- **Context:** Learning directly inside production code mixes experimentation with product risk.
- **Decision:** Each learning stage produces a small prototype outside `backend/app/` (proposed: `backend/learning/`), using fake chat models by default. Prototypes may import Mascot code but must not modify it.
- **Consequences:** Experiments are cheap, token-free, and disposable. Adding framework packages to `pyproject.toml` requires an explicit request.

## D-004 — Preserve existing behavior and tests during any future migration

- **Date:** 2026-09-15
- **Status:** Accepted
- **Context:** The backend tests, frontend tests, and `backend/evals` define the chatbot's contract: HTTP response shape, error mapping, HITL flow, and safety invariants.
- **Decision:** Any migration must keep existing tests and evals passing without modifying them, and must keep every constraint listed in `CLAUDE.md`.
- **Consequences:** Behavior changes, if ever wanted, are separate, explicit decisions — never side effects of migration.

## D-005 — Prefer incremental migration over a big-bang rewrite

- **Date:** 2026-09-15
- **Status:** Accepted
- **Context:** The existing seams (`ChatAIProvider` protocol, `TOOL_REGISTRY`, `run_chat_agent` signature) allow components to be replaced one at a time.
- **Decision:** If migration is approved, proceed in small, independently verifiable steps (e.g. structured output → chat model adapter → tools → graph loop → interrupt), ideally behind a settings flag, with a rollback path at each step.
- **Consequences:** Every intermediate state is shippable and testable; the custom loop remains available until the replacement is proven equivalent.

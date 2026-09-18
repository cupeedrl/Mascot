# AI Architecture Decisions

Lightweight decision log for Mascot's AI architecture and the LangChain/LangGraph learning effort. Add new entries at the bottom; supersede rather than delete.

Format: **Status** · **Context** · **Decision** · **Consequences**.

---

## D-001 — Keep the current custom agent loop during learning

- **Date:** 2026-09-15
- **Status:** Superseded by D-006 (2026-09-18)
- **Context:** Mascot's chatbot is a working, tested custom loop (`backend/app/ai/chat_agent.py`) with explicit safety guarantees: validated provider output, tool budgets, read-only execution, and confirmation-gated writes.
- **Decision:** The custom loop remains the production implementation for the entire learning period.
- **Consequences:** Learning work does not touch the production AI path. LangChain and LangGraph are not production dependencies.

## D-002 — Do not rewrite Mascot immediately

- **Date:** 2026-09-15
- **Status:** Superseded by D-006 (2026-09-18)
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

## D-006 — Migrate the chat agent loop to LangGraph, behind a rollback flag

- **Date:** 2026-09-18
- **Status:** Accepted
- **Supersedes:** D-001, D-002 (the migration was explicitly requested before the learning plan's stage 12)
- **Context:** The chat agent's control flow (model call → tool calls → tool results → model) maps directly onto a LangGraph state graph, which makes the workflow explicit and inspectable. The guarantees around it — output validation, budgets, write interception, identity, executor safeguards, confirmation tokens, HTTP errors — are Mascot's and must not change.
- **Decision:**
  - LangGraph orchestrates the loop (`app/ai/agent_graph.py`): state, `model_node`, `route_after_model`, `tool_node`.
  - LangChain provides the chat-model abstraction and message types through `ProviderChatModel`, an adapter over the existing `ChatAIProvider` (`app/ai/langchain_chat_model.py`). Providers are unchanged.
  - Every Mascot rule stays Mascot code, shared by both engines (`app/ai/agent_guardrails.py`, the executor, the confirmation routes).
  - `run_chat_agent()` keeps its signature and return type; `settings.ai_agent_engine` (`langgraph` default, `legacy` for rollback) selects the engine.
  - Not migrated: tool business logic, `TOOL_REGISTRY` (no `StructuredTool`, no prebuilt `ToolNode`), HITL (no `interrupt()` or checkpointer), structured-output generation, routes, frontend, database.
  - Dependencies: `langchain-core>=1.6.3,<1.7` and `langgraph>=1.2.11,<1.3` (not the `langchain` package).
- **Consequences:** Existing tests and evals pass unmodified on both engines (D-004). New parity tests (`tests/test_agent_graph_migration.py`) require identical provider-visible messages, results, error stages and trace counters from both engines. The legacy engine should be removed in a later, separate change once the LangGraph engine is proven in production. `langsmith` arrives as a transitive dependency; tracing must stay disabled unless separately approved.

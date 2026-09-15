# Mascot AI Chatbot Architecture

Status labels: **CURRENT** = implemented in the repository today. **PLANNED** = a learning/migration direction, not implemented. See `DECISIONS.md` for the rules governing any change.

---

## 1. CURRENT — Overview

The AI Learning Assistant is a **custom, bounded, single-agent tool-calling loop** written directly against the `openai` Python SDK. It uses Groq (default) or OpenAI through the OpenAI-compatible Chat Completions API. No agent framework is used.

```
AIChatDrawer.tsx ─► api/client.ts ─► POST /api/v1/ai/chat
                                          │
                     routes/ai_chat.py    (context, guards, persistence, error mapping)
                                          │
                     ai/chat_agent.py     run_chat_agent()
                        │                          │
     provider.generate_chat_response_       tools/executor.py execute_tool()  (read-only)
     with_tools()                                  │
     (openai_compatible_provider.py)        tools/registry.py → learning_tools.py
                                          │
          str ─► assistant reply    │    PendingToolAction ─► signed action token ─► UI Confirm/Cancel
                                                                     │
                                          POST /api/v1/ai/actions/confirm ─► execute_confirmed_tool()
```

## 2. CURRENT — Components

| Component | File(s) | Responsibility |
|---|---|---|
| Chat route | `backend/app/api/v1/routes/ai_chat.py` | Message length checks, conversation ownership, context building, `ai_guard` dedup/cooldown, calls the agent, issues action tokens, maps errors to HTTP codes, usage logging |
| Agent loop | `backend/app/ai/chat_agent.py` | `run_chat_agent()`: model call → validation → budgets → write interception → read-tool execution → repeat |
| Message types | `backend/app/ai/chat_schema.py` | Provider-neutral `Message` TypedDicts, `ProviderResult`, `PendingToolAction`, `AgentTrace` |
| Provider contract | `backend/app/ai/provider.py` | `ChatAIProvider` protocol and `AIProviderError` hierarchy |
| Provider implementation | `backend/app/ai/openai_compatible_provider.py`, `groq_provider.py`, `openai_provider.py` | Converts messages/tools to OpenAI format, retries with backoff, maps SDK errors |
| Provider selection | `backend/app/ai/dependencies.py` | One cached provider chosen by `settings.ai_provider` |
| Prompts | `backend/app/ai/prompts.py` | `CHAT_ASSISTANT_SYSTEM_PROMPT` (plus vocabulary/exercise prompts) |
| Response language | `backend/app/ai/response_language.py` | Deterministic language detection and per-turn system hint |
| Tools | `backend/app/ai/tools/` | Registry, schemas, executor, handlers |
| HITL actions | `backend/app/ai/action_tokens.py`, `backend/app/api/v1/routes/ai_actions.py` | Signed action tokens, replay guard, confirm/cancel endpoints |
| Conversations | `backend/app/services/ai_conversation.py`, `routes/ai_conversations.py`, `models/ai_conversation.py` | Persisted, user-owned conversation history |
| Guard & logging | `backend/app/services/ai_guard.py`, `services/ai_logger.py` | In-process dedup/cooldown; `ai_usage_logs` records |
| Evals | `backend/evals/` | Offline contract/safety evals with scripted provider responses |
| Frontend | `frontend/src/components/AIChatDrawer.tsx`, `frontend/src/ai/chatUiState.ts` | Chat UI, confirmation card, conversation switching |

## 3. CURRENT — Request flow (`POST /ai/chat`)

1. Validate each message length against `ai_chat_max_message_length`.
2. Create a conversation or load one owned by the JWT user; persist the visible user input.
3. Load the last `ai_chat_max_history_messages` messages.
4. Detect the response language from the latest user message.
5. Build context: system prompt → language hint → optional active learning-track context → history.
6. `ai_guard.check_and_acquire` (duplicate in-flight request → 409, cooldown → 429).
7. Call `run_chat_agent()` with budgets from settings.
8. If it returns text, persist it and return `AIChatResponse`.
9. If it returns `PendingToolAction`, issue an action token, persist a localized proposal message, and return `confirmation_required`.
10. Map provider/tool exceptions to 502/503/504/429/500, record usage, release the guard.

## 4. CURRENT — Agent loop (`run_chat_agent`)

```
tools = JSON schemas from TOOL_REGISTRY
loop:
    result = provider.generate_chat_response_with_tools(conversation, tools)
    content, tool_calls = _validate_provider_result(result)     # untrusted output
    if no tool_calls:            return content                  # final answer
    enforce max_tool_rounds, max_tool_calls_per_round, max_total_tool_calls
    if any write tool:
        must be the only call; if args valid → return PendingToolAction (NOT executed)
    append assistant message with tool_calls
    for each call:
        args = parse JSON (size-limited)
        result = execute_tool(name, args, db, user_id, track_id)  # read-only
        unknown tool / invalid args → error JSON returned to model
        execution failure → abort request
        append tool message
    tool_rounds += 1
```

Properties:

- Synchronous; retries use `time.sleep` backoff inside the provider.
- `AgentTrace` records provider calls, rounds, tool names, and latencies for logging.
- Intermediate assistant tool-call messages and tool results are **not** persisted.

## 5. CURRENT — Tool architecture

Each `TOOL_REGISTRY` entry (`ToolMeta`) declares:

| Field | Purpose |
|---|---|
| `name`, `description` | Sent to the model |
| `arg_schema` | Pydantic model; its JSON schema becomes the tool's `parameters` and validates model arguments |
| `result_schema` | Pydantic model the handler result must satisfy |
| `handler(args, db, user_id[, learning_track_id])` | Implementation; identity is injected by the backend |
| `classification` | `"read"` or `"write"` |
| `requires_confirmation` | Must be `True` for write tools |

Registered tools:

| Tool | Class | Handler |
|---|---|---|
| `get_learning_stats` | read | `learning_tools.handle_get_learning_stats` |
| `get_learning_profile` | read | `learning_tools.handle_get_learning_profile` |
| `get_due_vocabulary` | read | `learning_tools.handle_get_due_vocabulary` |
| `add_vocabulary` | write, confirmation required | `vocabulary_tools.handle_add_vocabulary` |

Executor (`tools/executor.py`):

- `validate_tool_arguments` — whitelist lookup + Pydantic validation.
- `execute_tool` — rejects anything that is not a read tool.
- `execute_confirmed_tool` — rejects anything that is not a confirmable write tool.
- Shared execution: Postgres `statement_timeout`, elapsed-time check, result-schema validation, JSON payload size limit.
- Errors: `ToolNotFoundError`, `ToolValidationError`, `ToolExecutionError` (`ToolTimeoutError`, `ToolPayloadTooLargeError`), `ToolConfirmationRequiredError`.

## 6. CURRENT — Human-in-the-loop (HITL) design

The design is **stateless across requests**: the proposal travels to the client inside a signed token rather than being stored as paused agent state.

1. The agent sees a valid `add_vocabulary` call and returns `PendingToolAction` instead of executing it.
2. `issue_action_token` signs a JWT with `sub` (user), `tool`, `args`, `jti` (action id), `exp` (`ai_action_token_expire_seconds`, default 300), issuer and a dedicated audience.
3. The UI shows a confirmation card with the vocabulary details.
4. `POST /ai/actions/confirm`:
   - verify signature, audience, issuer, expiry, and owner (403 on mismatch);
   - re-validate tool name and arguments against the registry;
   - reserve `jti` in `action_replay_guard` (409 on replay);
   - `execute_confirmed_tool`; duplicate vocabulary → 409; transient failures release the reservation;
   - append a confirmation message to the conversation and audit to `ai_usage_logs`.
5. `POST /ai/actions/cancel` performs the same verification and reservation, executes nothing, and records a cancel message.

Rules enforced by the prompt and by code: plain-text "yes" is never approval; one write proposal at a time; write proposals are never mixed with other tool calls.

## 7. CURRENT — Known limitations

- `ai_guard` and `action_replay_guard` are process-local memory (not shared across workers/instances).
- Tool-call turns are not persisted, so history replays only visible text.
- `DEFAULT_MAX_TOOL_ROUNDS = 3` in `chat_agent.py`, but the route passes `settings.ai_max_tool_rounds` (default 5).
- The provider implementation duplicates retry/error mapping across three methods.
- No streaming responses.

---

## 8. PLANNED — Learning migration path

**Custom Agent → LangChain → LangGraph.** Nothing here is implemented. Each stage is optional, incremental, and gated by `DECISIONS.md` and the final evaluation in `LEARNING_PLAN.md` (stage 12).

### Stage A — CURRENT: Custom agent

As documented above. Remains the production path throughout learning.

### Stage B — PLANNED: LangChain components behind existing seams

| Current | LangChain candidate |
|---|---|
| `OpenAICompatibleVocabularyProvider.generate_chat_response_with_tools` | `ChatGroq` / `ChatOpenAI` + `.bind_tools()`, wrapped to satisfy `ChatAIProvider` |
| `_parse_structured` for vocabulary/exercise generation | `llm.with_structured_output(VocabularyCandidate)` |
| `chat_schema.py` message TypedDicts | `SystemMessage`, `HumanMessage`, `AIMessage`, `ToolMessage` (adapter at the boundary) |
| `TOOL_REGISTRY` entries | `StructuredTool` with `args_schema`; identity via injected args/config, hidden from the model |
| `AgentTrace` | Callbacks / LangSmith tracing (optional) |

`run_chat_agent`, routes, tests, and evals stay unchanged in this stage.

### Stage C — PLANNED: LangGraph agent loop

| Current | LangGraph candidate |
|---|---|
| `while True` loop | `StateGraph`: `agent` → conditional edge → `guard` → `tools` → `agent` |
| `_validate_provider_result`, budgets, write-only-alone rule | Custom `guard` node (a prebuilt `ToolNode` alone does not enforce these) |
| `max_tool_rounds` counters | Counters in graph state + `recursion_limit` |
| `PendingToolAction` + action token | `interrupt()` in a `propose_write` node; resume with `Command(resume=...)` |
| `load_recent_conversation_messages` | Checkpointer thread keyed by `conversation_id` (trade-off vs current stateless design) |
| Language detection, track context | Deterministic pre-processing nodes |

Built first as an isolated prototype, then optionally behind a settings flag, validated by running the same tests and evals against both implementations.

### Invariants for every stage

All constraints in `CLAUDE.md` → "Architectural constraints" must hold, in particular: untrusted model output is validated; writes never execute without explicit confirmation; identity never comes from model arguments; tool I/O is schema-validated and bounded; the HTTP contract and error mapping are unchanged; existing tests and evals pass unmodified.

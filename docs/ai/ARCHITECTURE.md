# Mascot AI Chatbot Architecture

Status labels: **CURRENT** = implemented in the repository today. **PLANNED** = a possible future direction, not implemented. See `DECISIONS.md` for the rules governing any change.

---

## 1. CURRENT — Overview

The AI Learning Assistant is a **bounded, single-agent tool-calling workflow**. Since decision D-006:

- **LangGraph** orchestrates the agent loop (state, model node, tool node, conditional routing).
- **LangChain** provides the chat-model abstraction and message types, through an adapter over Mascot's own `ChatAIProvider`.
- **Mascot** still owns every rule: output validation, budgets, write interception, identity, tool execution, confirmation, and HTTP errors.

The model is Groq (default) or OpenAI through the OpenAI-compatible Chat Completions API, optionally with the other one as a fallback provider (§7b). The original custom loop is kept behind `AI_AGENT_ENGINE=legacy` for rollback. The answer can be streamed to the UI over Server-Sent Events (§3b).

```
AIChatDrawer.tsx ─► api/client.ts ─► POST /api/v1/ai/chat/stream   (SSE; postAIChatStream)
                                     POST /api/v1/ai/chat          (JSON; same turn)
                                          │
                     routes/ai_chat.py    _prepare_chat_turn (auth, context, guards, user input)
                                          _run_chat_turn     (agent, persistence, error mapping)
                                          │
                     ai/chat_agent.py     run_chat_agent()  ── engine flag ──► legacy loop (rollback)
                                          │
                     ai/agent_graph.py    LangGraph:  START → model ⇄ tools → END
                        │                                        │
     ai/langchain_chat_model.py                          tools/executor.py execute_tool()  (read-only)
     ProviderChatModel (LangChain)                              │
        │                                                tools/registry.py → learning_tools.py
     ChatAIProvider (openai_compatible_provider.py)
                                          │
          str ─► assistant reply    │    PendingToolAction ─► signed action token ─► UI Confirm/Cancel
                                                                     │
                                          POST /api/v1/ai/actions/confirm ─► execute_confirmed_tool()
```

## 2. CURRENT — Components

| Component | File(s) | Responsibility |
|---|---|---|
| Chat routes | `backend/app/api/v1/routes/ai_chat.py` | `POST /ai/chat` and `POST /ai/chat/stream`, sharing `_prepare_chat_turn()` (message length checks, conversation ownership, context building, `ai_guard` dedup/cooldown) and `_run_chat_turn()` (calls the agent, issues action tokens, maps errors to HTTP codes, usage logging) |
| Streaming seam | `backend/app/ai/chat_stream.py` | `stream_events_to(callback)` / `current_stream_callback()`: the stream route's event callback in a ContextVar, read by `ProviderChatModel` |
| Usage accounting | `backend/app/ai/token_usage.py` | Request-scoped `TokenUsage` (ContextVar): tokens summed over every provider call, plus the provider and model that answered. Opened by `@tracks_token_usage` or `token_usage_scope()` |
| Provider fallback | `backend/app/ai/fallback_provider.py` | `FallbackAIProvider`: retries a call once on the secondary provider after a transient primary failure |
| Agent facade | `backend/app/ai/chat_agent.py` | `run_chat_agent()`: stable entry point (same signature and return type as before). Selects the engine via `settings.ai_agent_engine`; `_run_legacy_chat_agent()` is the original loop, unchanged |
| Agent graph | `backend/app/ai/agent_graph.py` | `AgentState`, `AgentContext`, `model_node`, `route_after_model`, `tool_node`, compiled `AGENT_GRAPH`, `run_agent_graph()` |
| LangChain adapter | `backend/app/ai/langchain_chat_model.py` | `ProviderChatModel(BaseChatModel)` wraps any `ChatAIProvider`; lossless conversion between Mascot message dicts and LangChain messages |
| Guardrails | `backend/app/ai/agent_guardrails.py` | Shared by both engines: provider-result validation, size-limited argument parsing, safe log identifiers, tool definitions from `TOOL_REGISTRY`, latency tracing |
| Message types | `backend/app/ai/chat_schema.py` | Provider-neutral `Message` TypedDicts, `ProviderResult`, `PendingToolAction`, `AgentTrace` |
| Provider contract | `backend/app/ai/provider.py` | `ChatAIProvider` protocol and `AIProviderError` hierarchy |
| Provider implementation | `backend/app/ai/openai_compatible_provider.py`, `groq_provider.py`, `openai_provider.py` | Converts messages/tools to OpenAI format, streams when given `on_event`, retries with backoff, maps SDK errors, reports usage to `token_usage` |
| Provider selection | `backend/app/ai/dependencies.py` | One cached provider chosen by `settings.ai_provider`, wrapped in `FallbackAIProvider` when `settings.ai_fallback_provider` is usable |
| Prompts | `backend/app/ai/prompts.py` | `CHAT_ASSISTANT_SYSTEM_PROMPT` (plus vocabulary/exercise prompts) |
| Response language | `backend/app/ai/response_language.py` | Deterministic language detection and per-turn system hint |
| Tools | `backend/app/ai/tools/` | Registry, schemas, executor, handlers |
| HITL actions | `backend/app/ai/action_tokens.py`, `backend/app/api/v1/routes/ai_actions.py` | Signed action tokens, replay guard, confirm/cancel endpoints |
| Conversations | `backend/app/services/ai_conversation.py`, `routes/ai_conversations.py`, `models/ai_conversation.py` | Persisted, user-owned conversation history |
| Guard & logging | `backend/app/services/ai_guard.py`, `services/ai_logger.py` | In-process dedup/cooldown; `ai_usage_logs` records |
| Evals | `backend/evals/` | Offline contract/safety evals with scripted provider responses |
| Frontend | `frontend/src/components/AIChatDrawer.tsx`, `frontend/src/ai/chatUiState.ts`, `frontend/src/ai/chatStream.ts` | Chat UI, streamed draft bubble, confirmation card, conversation switching; SSE parser and stream reader |

## 3. CURRENT — Request flow (`POST /ai/chat`)

Unchanged by the migration. Steps 1–6 are `_prepare_chat_turn()`, steps 7–10 are `_run_chat_turn()`; the stream route (§3b) runs the same two functions.

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

## 3b. CURRENT — Streaming flow (`POST /ai/chat/stream`)

Same request body and the same turn as `/ai/chat`, answered as Server-Sent Events.

1. `_prepare_chat_turn()` runs in the request, exactly as steps 1–6 above. Its rejections (422, 404, 400, 409, 429, 401) are plain JSON HTTP errors, before any event is sent.
2. The request's session is committed, and the turn moves to a worker thread with its **own** DB session on the same engine, inside `token_usage_scope()` and `stream_events_to(callback)`. The worker finishes the turn (persists the reply, records usage, releases the guard) even if the client disconnects.
3. `_run_chat_turn()` runs the agent. `ProviderChatModel` finds the callback and, when the provider declares `supports_streaming`, calls `generate_chat_response_with_tools(..., on_event=callback)`. The provider sends `stream=True`, forwards text as it arrives, joins tool-call fragments by index, and returns the same complete `ProviderResult` as without streaming.
4. The response streams these events from a queue the worker fills:

| Event | Data | Meaning |
|---|---|---|
| `delta` | `{"text": "..."}` | Display-only draft text |
| `discard` | `{}` | Drop the draft: a provider retry, a fallback to the secondary provider, or a model turn that ended in tool calls |
| `done` | `AIChatResponse` | The validated, persisted answer: the same body `/ai/chat` returns, including `confirmation_required` |
| `error` | `{"status", "detail"}` | The status and detail `/ai/chat` would have returned |

Guarantees:

- Deltas never enter the conversation. `validate_provider_result` still checks the complete result, and only `done` is persisted. The UI replaces the draft with `done.message`.
- Tool rounds are not streamed: a model turn that requests tools ends with `discard`, then the tools run and the next turn streams.
- Only the LangGraph engine streams. The legacy engine calls the provider directly, so the stream carries `done` only. Providers without `supports_streaming` (test fakes, scripted eval providers) behave the same way.
- The frontend falls back to `/ai/chat` only when the stream route does not exist (404 `Not Found` or 405). After a stream has started the user message is already saved, so the client reports the interruption instead of resending.

## 4. CURRENT — Agent workflow (LangGraph)

```
START ──► model ──route_after_model──► END   (final answer, or pending write proposal)
            ▲               │
            └──── tools ◄───┘                 (read tools only)
```

| Graph element | What it does |
|---|---|
| **State** (`AgentState`) | `messages` (LangChain messages, `add_messages` reducer), `tool_rounds`, `total_tool_calls`, `pending_action` |
| **Context** (`AgentContext`) | Per-request, never visible to the model: the bound chat model, `db`, `user_id`, `learning_track_id`, `execute_tool`, all limits, `trace`, `request_id` |
| **`model_node`** | Calls `ProviderChatModel` (which validates the raw provider result first). Then, in the legacy order: empty answer → `empty_response`; round budget → `max_tool_rounds_exceeded`; per-round → `too_many_tool_calls`; total → `too_many_total_tool_calls`; write interception (write must be alone; valid write → `pending_action`, **not executed**) |
| **`route_after_model`** | Pure routing: `pending_action` or no tool calls → `END`; otherwise → `tools` |
| **`tool_node`** | For each requested call, in order: size-limited argument parsing → `execute_tool(db, current_user_id=context.user_id, …)` → `ToolMessage(tool_call_id=…)`. Unknown tool / invalid arguments → sanitized `{"ok": false, "error": …}` observation; execution failure → abort |
| **Loop** | Edge `tools → model` |
| **Recursion limit** | `2 * max_tool_rounds + 2` — a backstop only; `model_node` enforces the real budget first. If ever hit, mapped to `max_tool_rounds_exceeded` |

Properties:

- Synchronous (`AGENT_GRAPH.invoke`); the graph is compiled once at import.
- The provider still receives exactly the same message dicts as before: each `AIMessage` stores its original assistant dict (including raw JSON argument strings) in `additional_kwargs["mascot_assistant_message"]`.
- `AIMessage.tool_calls` / `invalid_tool_calls` are populated as the standard LangChain view, but routing and execution use the raw provider calls so malformed arguments still reach Mascot's own checks.
- Intermediate assistant tool-call messages and tool results are **not** persisted.

### Responsibilities after migration

| Layer | Responsible for |
|---|---|
| **LangChain** | `BaseChatModel` interface (`ProviderChatModel`), message types (`SystemMessage`, `HumanMessage`, `AIMessage`, `ToolMessage`), `bind_tools` |
| **LangGraph** | State and reducer, nodes, conditional routing, the loop, recursion backstop |
| **Mascot** | Authentication and identity, provider SDK code, provider-output validation, budgets, write interception and confirmation tokens, tool registry and schemas, executor safeguards (Pydantic arguments and results, payload limit, DB statement timeout), tool business logic, sanitized logging, `AgentTrace`, HTTP error mapping |

LangChain and LangGraph do **not** provide any of Mascot's security or guardrail behavior; each rule above is Mascot code that the graph calls.

## 5. CURRENT — Tool architecture

Unchanged by the migration. Tools are **not** LangChain `StructuredTool`s and the prebuilt LangGraph `ToolNode` is **not** used: it would execute write tools and change error semantics.

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

Unchanged by the migration and kept **outside** the graph (no LangGraph `interrupt()` or checkpointer). The design is **stateless across requests**: the proposal travels to the client inside a signed token rather than being stored as paused agent state.

1. `model_node` sees a valid `add_vocabulary` call and ends the run with `PendingToolAction` instead of executing it.
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

## 7. CURRENT — Engine selection and rollback

| Setting | Behavior |
|---|---|
| `AI_AGENT_ENGINE` unset or `langgraph` (default) | LangGraph workflow |
| `AI_AGENT_ENGINE=legacy` | Original custom loop (`_run_legacy_chat_agent`), unchanged |

Both engines share `agent_guardrails.py` and the executor. `backend/tests/test_agent_graph_migration.py` runs the same scripted scenarios through both and requires identical provider-visible messages, results, error stages and trace counters. Rollback = set the variable and restart; no code or data change. (`docker-compose.yml` does not pass this variable through; add it there if you need to flip it locally in Docker. An empty value is rejected at startup, like other `Literal` settings.)

## 7b. CURRENT — Provider fallback and usage accounting

**Fallback.** `AI_FALLBACK_PROVIDER` (`groq` or `openai`; empty means disabled) names a second provider. `dependencies.py` wraps the primary in `FallbackAIProvider` only if that provider differs from `AI_PROVIDER` and has an API key; otherwise it logs a warning and uses the primary alone.

| Primary failure, after its own retries | Fallback? |
|---|---|
| `AIProviderRateLimitError`, `AIProviderQuotaError`, `AIProviderTimeoutError`, bare `AIProviderError` (5xx/network) | Yes, the same call once on the secondary; logged as `AI provider fallback` |
| `AIProviderConfigurationError`, `AIProviderNotConfiguredError`, `AIProviderAuthenticationError`, `AIProviderRequestError`, `AIProviderResponseError` | No: raised unchanged, so a bad key, model or request is never hidden |

All four provider methods (vocabulary, exercises, chat, chat with tools) go through the wrapper. When streaming, it sends `discard` before the secondary starts.

**Usage accounting.** Providers are process-wide singletons, so per-request usage lives in a ContextVar (`token_usage.py`). Each AI route opens a `TokenUsage` with `@tracks_token_usage` (the stream worker uses `token_usage_scope()`); every provider response adds its usage, including responses whose output is later rejected, since those tokens are billed. Chat Completions (`prompt_tokens`/`completion_tokens`), the Responses API (`input_tokens`/`output_tokens`), OpenAI stream usage chunks and Groq's `x_groq.usage` are all read. `record_ai_usage` fills tokens, provider and model from the tracker unless they are passed explicitly.

## 8. CURRENT — Known limitations

- `ai_guard` and `action_replay_guard` are process-local memory (not shared across workers/instances).
- Tool-call turns are not persisted, so history replays only visible text.
- `DEFAULT_MAX_TOOL_ROUNDS = 3` in `chat_agent.py`, but the route passes `settings.ai_max_tool_rounds` (default 5).
- The provider implementation duplicates retry/error mapping across three methods (the streaming path reuses the tool-calling method's).
- Each open stream holds one threadpool slot while it waits for events, plus the worker thread.
- A network drop in the middle of a provider stream surfaces as an `error` event (502); the turn is not retried after text has been streamed, except through the provider's own retry loop, which sends `discard` first.
- The fallback is per provider call: in a multi-round turn, each round tries the primary again. `ai_usage_logs.model` records the model of the last call.
- `langchain-core` depends on `langsmith`. Tracing is **off** unless `LANGSMITH_TRACING` (or legacy `LANGCHAIN_TRACING_V2`) is set; if set, prompts and tool results — including learner data — would be sent to LangSmith. Do not set it in production without a privacy review.
- Vocabulary enrichment and exercise generation (`_parse_structured`) still call the provider directly; they are not part of this migration.

---

## 9. Migration status

**Custom Agent → LangChain → LangGraph**, per D-006.

| Stage | Status |
|---|---|
| A — Custom agent loop | Kept as the `legacy` engine for rollback |
| B — LangChain components behind existing seams | **Partially done:** chat-model abstraction and message types via `ProviderChatModel`. **Not done:** `with_structured_output` for enrichment/exercises; `StructuredTool` for the registry; provider packages (`ChatGroq` / `ChatOpenAI`) |
| C — LangGraph agent loop | **Done, minimal:** state, model node, tool node, conditional routing, loop. **Not done (intentionally):** checkpointer, `interrupt()`-based HITL, middleware, parallel tool execution, LangGraph stream modes (answer streaming is done at the provider level instead, §3b) |

### PLANNED — possible next steps (none approved yet)

| Candidate | Notes |
|---|---|
| Remove the `legacy` engine | After the LangGraph engine is proven in production; deletes `_run_legacy_chat_agent` and the flag |
| `with_structured_output` for enrichment/exercises | Would replace `_parse_structured`; must keep retry and error mapping |
| `ChatGroq` / `ChatOpenAI` behind `ProviderChatModel` | Would move SDK code out of Mascot; error mapping to `AIProvider*Error` must be preserved |
| `interrupt()` + checkpointer for confirmation | Trade-off vs the current stateless signed-token design (storage, expiry, replay, scaling) |

### Invariants for every future step

All constraints in `CLAUDE.md` → "Architectural constraints" must hold, in particular: untrusted model output is validated; writes never execute without explicit confirmation; identity never comes from model arguments; tool I/O is schema-validated and bounded; the HTTP contract and error mapping are unchanged; existing tests and evals pass unmodified.

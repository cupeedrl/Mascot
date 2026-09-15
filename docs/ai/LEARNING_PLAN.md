# LangChain & LangGraph Learning Plan

A practical roadmap for learning LangChain and LangGraph using Mascot as the reference system.

## Ground rules

- Follow the learning-mode workflow in `CLAUDE.md`: concept → relevance → mapping → plan → implement only on explicit request → explain → verify → summarize.
- Prototypes live outside `backend/app/` (proposed: `backend/learning/stageNN_<topic>/`). They may import Mascot code (schemas, registry) but must not change it.
- Use fake chat models (`GenericFakeChatModel` / `FakeMessagesListChatModel` from `langchain_core`) by default; use a real provider only deliberately.
- Install learning packages (`langchain-core`, `langchain-openai`, `langchain-groq`, `langgraph`) locally; do not add them to `pyproject.toml` unless explicitly decided.
- Check current LangChain/LangGraph docs for API names — the libraries change quickly.
- Each prototype gets at least one small pytest test.

Reference: `docs/ai/ARCHITECTURE.md` (CURRENT vs PLANNED), `docs/ai/DECISIONS.md`.

---

## 1. LangChain fundamentals

**Understand**
- The package split: `langchain-core` (interfaces), provider packages (`langchain-openai`, `langchain-groq`), `langchain` (higher-level agents).
- Runnables: `invoke`, `batch`, `stream`, and composition with `|`.
- Message types: `SystemMessage`, `HumanMessage`, `AIMessage`, `ToolMessage`.
- Prompt templates and output parsers.

**Implement**
- A script that builds a prompt template → fake chat model → `StrOutputParser` chain and prints the result.
- A test asserting the chain output with a fake model.

**Explain afterward**
- What a Runnable is and why composition matters.
- How LangChain message types correspond to `backend/app/ai/chat_schema.py`.

## 2. Structured output

**Understand**
- `with_structured_output(PydanticModel)` and the methods behind it (tool calling vs JSON schema).
- What happens when the model returns invalid data, and where validation happens.

**Implement**
- A prototype producing `VocabularyCandidate` (`backend/app/schemas/ai_vocabulary.py`) via `with_structured_output`, reusing prompts from `backend/app/ai/prompts.py`.
- A test for the success case and the invalid-output case.

**Explain afterward**
- How this compares to `_parse_structured` in `openai_compatible_provider.py` (`responses.parse` + `text_format`).
- Why Mascot still validates candidates in the service layer afterward.

## 3. Chat model abstraction

**Understand**
- `BaseChatModel` as a provider-neutral interface; `ChatOpenAI` / `ChatGroq` configuration (base URL, timeout, retries).
- Tool-call representation on `AIMessage.tool_calls` (parsed dict args, not JSON strings).
- Error types raised by provider packages.

**Implement**
- An adapter class that satisfies Mascot's `ChatAIProvider` protocol (`backend/app/ai/provider.py`) using a LangChain chat model, converting messages and results to `ProviderResult`.
- Run `run_chat_agent` against the adapter with a fake model in a test.

**Explain afterward**
- Why `ChatAIProvider` is the natural migration seam.
- What the adapter must translate (message shapes, argument JSON strings, error mapping to `AIProviderError` types).

## 4. Tools and tool calling

**Understand**
- `@tool` and `StructuredTool.from_function(args_schema=...)`.
- `bind_tools()` and how tool schemas reach the model.
- Injecting runtime values the model must not control (`InjectedToolArg`, `RunnableConfig`).

**Implement**
- Wrap one read tool (`get_learning_stats`) from `TOOL_REGISTRY` as a `StructuredTool` that calls the existing handler, with `db` and `user_id` injected.
- A test proving the model-visible schema contains no identity fields.

**Explain afterward**
- How `ToolMeta` fields map to LangChain tools, and what LangChain does not provide (`classification`, `requires_confirmation`, result schema, payload/time limits).

## 5. Tiny LangChain agent prototype

**Understand**
- The model → tool calls → tool messages → model cycle as LangChain implements it (`create_agent` in current `langchain`).
- Limits on iterations and how errors surface.

**Implement**
- A tiny agent with two toy read tools and a fake model scripted to call a tool and then answer.
- Tests for: final answer, tool-call path, and iteration limit.

**Explain afterward**
- Which parts of `run_chat_agent` the prebuilt agent covers and which Mascot guards it does not (output validation, per-round limits, write interception).

## 6. LangGraph fundamentals

**Understand**
- Graphs as nodes (functions over state) and edges.
- State schemas (`TypedDict`), reducers (`add_messages`).
- Compile, `invoke`, `stream`; `recursion_limit`.

**Implement**
- A two-node linear graph (e.g. `detect_language` → `respond`) using fake data.

**Explain afterward**
- Why an explicit graph differs from a `while` loop, and what state is carried between nodes.

## 7. StateGraph

**Understand**
- `StateGraph(State)`, `add_node`, `add_edge`, `START`/`END`.
- Designing state: messages, counters, pending action, trace.

**Implement**
- A `StateGraph` whose state mirrors Mascot's loop: `messages`, `tool_rounds`, `total_tool_calls`, `pending_action`.
- A test inspecting final state.

**Explain afterward**
- How each local variable in `run_chat_agent` would become a state field, and which should not (e.g. `db` session belongs in config, not state).

## 8. Conditional edges and loops

**Understand**
- `add_conditional_edges` with a routing function.
- Loops `agent → tools → agent` and termination conditions.
- Prebuilt `ToolNode` / `tools_condition` versus custom routing.

**Implement**
- Routing: no tool calls → `END`; write call → `propose_write`; read calls → `guard` → `tools` → `agent`.
- Budget enforcement in `guard` using state counters.

**Explain afterward**
- How the branches correspond to `run_chat_agent` (`chat_agent.py`), and why `guard` must be custom.

## 9. Tiny LangGraph agent prototype

**Understand**
- Putting a chat model with bound tools inside a graph node.
- Error handling inside nodes versus raising out of the graph.

**Implement**
- A complete small agent graph with a fake model, two read tools, output validation, and budgets.
- Tests mirroring a subset of `backend/tests/test_ai_chat_phase3.py` scenarios.

**Explain afterward**
- End-to-end control flow of the graph, and each Mascot constraint it does or does not yet enforce.

## 10. Interrupt / HITL

**Understand**
- `interrupt()`, `Command(resume=...)`, and why a checkpointer is required (`InMemorySaver`, Postgres saver).
- Thread IDs and resuming from persisted state.
- Security implications: who can resume, expiry, replay, and re-validation of arguments.

**Implement**
- Add a `propose_write` node that interrupts with the proposed `add_vocabulary` arguments and executes only after resume with an approval value.
- Tests: approve, reject, resume by the wrong thread/user, resume twice.

**Explain afterward**
- The difference between Mascot's stateless signed-token HITL (`action_tokens.py`, `routes/ai_actions.py`) and LangGraph's checkpoint-based interrupt, with trade-offs (storage, scaling, expiry, replay protection, auditability).

## 11. Compare with Mascot's custom implementation

**Understand**
- Behavioral equivalence: same inputs, same outcomes, same errors.

**Implement**
- A comparison harness that runs the scenarios from `backend/evals/chatbot_eval.py` against both the custom loop and the LangGraph prototype (via the provider seam or a fake model).
- A written comparison table: lines of code, readability, testability, observability, safety guarantees, performance, dependency weight.

**Explain afterward**
- Where the frameworks simplify Mascot, where they add complexity, and which guarantees required extra custom code.

## 12. Decide whether incremental migration is worthwhile

**Understand**
- Migration cost and risk versus benefit for Mascot specifically.

**Implement**
- No production code. Record a new decision in `docs/ai/DECISIONS.md`: migrate nothing, adopt LangChain components only (stage B), or adopt LangGraph (stage C) — with scope, order, rollback plan, and verification criteria.

**Explain afterward**
- The chosen option, the evidence from stage 11 that supports it, and the first minimal, test-preserving step if migration proceeds.

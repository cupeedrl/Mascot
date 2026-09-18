# Lesson 5 — LangChain Agent (tool calling)

Isolated learning prototype. It imports no Mascot production code, needs no API key, and makes no network calls. It does **not** replace Mascot's agent.

```
user message
   -> agent (create_agent)
   -> chat model  ── decides: tool needed?
   -> tool call
   -> tool execution
   -> tool result (ToolMessage)
   -> chat model
   -> final answer
```

## Files

| File | Purpose |
|---|---|
| `agent.py` | Two fake tools, an offline scripted chat model, `build_agent()` / `ask()`, and a demo with two scenarios |
| `test_agent.py` | 6 tests: registration, execution, result routed back to the model, final answer, no-tool path, no production imports |
| `requirements.txt` | Learning-only dependencies (`langchain`, `pytest`) |

## Run

From this directory, using the shared learning venv one level up:

```bash
..\.venv\Scripts\python.exe agent.py
..\.venv\Scripts\python.exe -m pytest test_agent.py -q
```

## 1. What is an Agent?

A loop that lets the model decide what to do next. You give it a model, some tools and a prompt; it calls the model, and if the model asks for a tool, it runs that tool, feeds the result back, and calls the model again — until the model answers with plain text instead of a tool call.

The model never runs anything itself. It only emits a *request* ("call `get_learning_stats` with these arguments"). The agent is the code that honours that request.

## 2. Tool calling vs. an Agent

| | Tool calling | Agent |
|---|---|---|
| What it is | A model **capability**: return structured "call this tool with these args" instead of text | A **control loop** around that capability |
| Who runs the tool | Nobody — you get a request | The agent |
| How many model calls | One | As many as needed, until a final answer |
| In this prototype | `AIMessage.tool_calls` produced by the model | `create_agent(...).invoke(...)` |

Tool calling is one step. An agent is the loop that repeats that step until it's done. Lesson 4 was tool calling; this lesson wraps it in a loop.

## 3. Execution flow in this prototype

1. `ask()` calls `agent.invoke({"messages": [HumanMessage(...)]})`.
2. The agent prepends `SYSTEM_PROMPT`, binds the tool schemas to the model, and calls it.
3. `ScriptedFakeChatModel` returns a scripted `AIMessage` with `tool_calls=[{name: "get_learning_stats", args: {}}]`.
4. The agent sees the tool call, looks the name up in its tool list, runs the function, and appends a `ToolMessage` containing the JSON result.
5. The agent calls the model **again**, now with 4 messages (system, human, the tool-call AIMessage, the ToolMessage).
6. The model returns text with no tool calls, so the loop stops. That message is the final answer.
7. `result["messages"]` holds the whole trace, which is what the tests assert on.

Scenario B in `main()` shows the other branch: the model answers immediately, no tool runs, one model call.

## 4. LangChain components used

| Component | Role here |
|---|---|
| `@tool` (`langchain_core.tools`) | Turns a plain function into a tool: name, description from the docstring, args schema from the signature |
| `BaseChatModel` | The chat-model interface; `ScriptedFakeChatModel` implements `_generate` and `bind_tools` |
| `AIMessage` / `ToolMessage` / `HumanMessage` / `SystemMessage` | The message types the loop passes around |
| `create_agent` (`langchain.agents`) | Builds the loop: bind tools, call model, run requested tools, repeat |

Note: in LangChain 1.x, `create_agent()` is implemented on top of LangGraph, so installing `langchain` also installs `langgraph`. The old `AgentExecutor` / `initialize_agent` APIs from pre-1.0 tutorials are legacy — don't use them.

## 5. Mapping to Mascot's custom agent loop

```
Mascot (production)                 LangChain (this prototype)

run_chat_agent()                    create_agent(...).invoke(...)
      |                                   |
ChatAIProvider                      BaseChatModel
      |                                   |
LLM                                 chat model
      |                                   |
tool call?                          AIMessage.tool_calls
      |                                   |
execute tool                        agent runs the @tool function
      |                                   |
tool result                         ToolMessage
      |                                   |
LLM                                 chat model
      |                                   |
final answer                        final AIMessage
```

Component by component:

| Mascot (`backend/app/ai/`) | LangChain equivalent |
|---|---|
| `run_chat_agent()` `while True` loop (`chat_agent.py`) | `create_agent()` |
| `ChatAIProvider` + `openai_compatible_provider.py` | `BaseChatModel` + a provider package |
| `TOOL_REGISTRY` entries (`tools/registry.py`) | `@tool`-decorated functions passed to `create_agent` |
| `_build_tool_definitions()` | `bind_tools()` converting tools to provider JSON |
| `execute_tool()` dispatch (`tools/executor.py`) | The agent's internal tool node |
| `ToolResultMessage` TypedDict (`chat_schema.py`) | `ToolMessage` |
| Scripted fake providers in `backend/evals/` | `ScriptedFakeChatModel` |

## 6. What LangChain handles vs. what Mascot still handles

LangChain gives you, out of the box:

- the loop itself, and stopping when the model returns no tool calls;
- converting tools to provider JSON and binding them to each call;
- dispatching a tool call by name and formatting the result as a `ToolMessage`;
- one interface across providers.

Mascot's loop does all of that **plus** the things `create_agent` does not do for you:

| Mascot guarantee | Where | Would LangChain do it? |
|---|---|---|
| Validate untrusted provider output before it enters the conversation | `_validate_provider_result` | No — you'd add it (middleware or a wrapper) |
| Write tools never execute in the loop; return a proposal instead | `PendingToolAction` | No — needs custom interception (Lesson 10, interrupts) |
| A write proposal must be alone in its round | `chat_agent.py` | No |
| Budgets: rounds, calls per round, total calls | settings + counters | Partly — a recursion limit, not per-round budgets |
| `user_id` / `learning_track_id` injected from the JWT, never from the model | `execute_tool(...)` args | Partly — via injected tool args, which you must set up |
| Tool result schema validation, payload size cap, statement timeout | `executor.py` | No |
| Provider errors mapped to stable HTTP codes | `routes/ai_chat.py` | No |
| Sanitized per-request trace (`AgentTrace`) | `chat_agent.py` | Different — callbacks / LangSmith |

Takeaway: LangChain replaces the *plumbing* of the loop, not Mascot's *guarantees*. A real migration would keep every guarantee above and re-implement it around the framework — which is exactly what Lesson 11 is meant to measure.

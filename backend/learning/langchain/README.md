# Lesson 2 — Structured Output

```
LanguageAssessment (Pydantic)
        │
model.with_structured_output(LanguageAssessment)
        │
FakeStructuredChatModel  ──►  AIMessage(tool_calls=[{name: "LanguageAssessment", args: {...}}])
        │
PydanticToolsParser  ──►  LanguageAssessment(level="A2", reason="...")
```

Isolated learning prototype. It does not import or change `backend/app/`, needs no API key, and makes no network calls.

## Files

| File | Purpose |
|---|---|
| `structured_output.py` | Schema, offline fake chat model, `assess()`, and a runnable demo |
| `test_structured_output.py` | Success, schema-binding, and invalid-output tests |
| `requirements.txt` | Learning-only dependencies (`langchain-core`, `pytest`) |

## Run

From this directory, in a learning virtual environment (not the production one):

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe structured_output.py
.venv\Scripts\python.exe -m pytest test_structured_output.py -q
```

Do not add an `__init__.py` here, and do not run scripts from `backend/learning/`: a folder named `langchain` on `sys.path` can shadow the real `langchain` package in later lessons.

## 1. What is Structured Output?

Asking a model to return data in a fixed, machine-readable shape instead of free text. The application receives an object with known fields (`level`, `reason`) that code can rely on, rather than parsing prose like "I think this is roughly B1 because…".

Providers support it in two main ways: **tool calling** (the schema is sent as a tool definition and the model "calls" it with arguments) and **native JSON schema mode** (the provider constrains the output to the schema). Either way, the model can still produce invalid values, so the result must be validated.

## 2. Why Pydantic?

One class does three jobs:

1. **Describes the shape** — `LanguageAssessment.model_json_schema()` produces the JSON Schema sent to the model; `Field(description=...)` becomes guidance the model reads.
2. **Validates the output** — `Literal["A1", …, "C2"]` rejects `"Z9"`; missing or wrongly typed fields fail.
3. **Returns a typed Python object** — `result.level` instead of `data["level"]`.

## 3. What `with_structured_output()` does conceptually

`model.with_structured_output(Schema)` returns a new runnable equivalent to:

```
model.bind_tools([Schema], tool_choice=...)   # send schema as a tool, force its use
  | PydanticToolsParser(tools=[Schema])        # take the tool call args -> Schema(**args)
```

- Input: messages (same as a normal chat model).
- Output: a `Schema` instance, not an `AIMessage`.
- Invalid output raises (`ValidationError` / `OutputParserException`). With `include_raw=True` it instead returns `{"raw", "parsed", "parsing_error"}` so you can inspect failures.

That is the default implementation in `langchain_core`; provider packages such as `langchain-openai` may use native JSON schema mode via a `method=` argument. Check the current LangChain docs for exact options.

The fake model here implements `bind_tools()` and returns a scripted tool call, so the real LangChain binding and parsing code runs without a provider. The test `test_schema_is_sent_to_model_as_tool_definition` shows the schema actually attached to the model call.

## 4. Relation to Mascot (CURRENT architecture)

Mascot already uses structured output — without LangChain.

| This prototype | Mascot today |
|---|---|
| `LanguageAssessment` | `VocabularyCandidate` (`app/schemas/ai_vocabulary.py`), `AIMultipleChoiceBatch` / `AIFillInBlankBatch` (`app/schemas/ai_exercise.py`) |
| `with_structured_output(Schema)` | `_parse_structured()` in `app/ai/openai_compatible_provider.py`: `client.responses.parse(text_format=Schema)` → `response.output_parsed` (native schema mode) |
| `parsing_error` / `ValidationError` | Caught and mapped to `AIProviderResponseError("provider_parse", ...)` |
| Result is a `LanguageAssessment` | `generate_vocabulary()` returns `candidate.model_dump()`; the `VocabularyAIProvider` protocol treats it as untrusted data for final service validation (`app/ai/provider.py`) |
| Tool-call args → Pydantic | The chat agent validates model tool arguments with each tool's `arg_schema` (`app/ai/tools/executor.py`, `validate_tool_arguments`) — the same mechanism |
| `FakeStructuredChatModel` | Scripted fake providers in `backend/tests` and `backend/evals` |

Takeaway: LangChain does not add a new capability here; it standardizes the pattern (schema → model → validated object) behind one method that works across providers. A future step (Lesson 3, chat model abstraction) would explore replacing `_parse_structured` with `with_structured_output` behind the existing provider protocol — not part of this lesson.

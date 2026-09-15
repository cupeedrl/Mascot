# Chatbot offline evaluations

Run the deterministic Phase 6 suite from `backend`:

```powershell
.\.venv\Scripts\python.exe -m evals.run_chatbot_evals
```

The command uses scripted provider responses and an isolated in-memory database. It
does not call Groq, spend tokens, or modify the development database. The report
includes totals, pass rate, category breakdown, and details for failed cases.

These are contract and safety evaluations, not a measure of live-model language
quality. Live provider behavior remains covered by the runtime smoke check.

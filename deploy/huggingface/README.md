---
title: Mascot API
emoji: 🐧
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: FastAPI backend of Mascot, an AI language learning app
---

# Mascot API

FastAPI backend of [Mascot](https://github.com/cupeedrl/Mascot), an AI-assisted
language learning app with a LangGraph tool-calling assistant.

This Space only serves the REST API under `/api/v1` (health check:
`/api/v1/health`). The web app runs separately and calls this API.

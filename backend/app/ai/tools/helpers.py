# backend/app/ai/tools/helpers.py

"""Helper utilities for the AI tools layer.

- get_provider_neutral_tool_definitions(): returns a list of neutral tool definitions
  (name, description, parameters) derived from TOOL_REGISTRY.  The returned
  structure is independent of any LLM SDK and can be safely passed around the
  backend.
- to_openai_tool_defs(neutral_defs): converts the neutral definitions into the
  exact ``tools=`` payload expected by the OpenAI/Groq SDK.
"""

from __future__ import annotations

from typing import List, Dict, Any

from .registry import TOOL_REGISTRY, ToolMeta


def get_provider_neutral_tool_definitions() -> List[Dict[str, Any]]:
    """Return a list of neutral tool definitions.

    Each definition contains:
        - name
        - description
        - parameters (JSON‑schema obtained via ``arg_schema.model_json_schema()``)
    """
    neutral: List[Dict[str, Any]] = []
    for meta in TOOL_REGISTRY.values():
        neutral.append({
            "name": meta["name"],
            "description": meta["description"],
            "parameters": meta["arg_schema"].model_json_schema(),
        })
    return neutral


def to_openai_tool_defs(neutral_defs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert neutral definitions to the OpenAI‑compatible ``tools=`` format.

    The OpenAI SDK expects each tool definition to be of the form:
    ``{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}``
    """
    openai_defs: List[Dict[str, Any]] = []
    for nd in neutral_defs:
        openai_defs.append({
            "type": "function",
            "function": {
                "name": nd["name"],
                "description": nd["description"],
                "parameters": nd["parameters"],
            },
        })
    return openai_defs

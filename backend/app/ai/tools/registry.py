from typing import Callable, Literal, TypedDict
from uuid import UUID
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .schemas import (
    GetLearningStatsArgs,
    LearningStatsResult,
    GetDueVocabArgs,
    DueVocabularyResult,
)
from .learning_tools import (
    handle_get_learning_stats,
    handle_get_due_vocabulary,
)

class ToolMeta(TypedDict):
    name: str
    description: str
    arg_schema: type[BaseModel]
    result_schema: type[BaseModel]
    handler: Callable[[BaseModel, Session, UUID], BaseModel]
    classification: Literal["read", "write"]
    requires_confirmation: bool

# Global registry dictionary
TOOL_REGISTRY: dict[str, ToolMeta] = {}

def _register(meta: ToolMeta) -> None:
    """Add a tool to the global registry. Overwrites if name already exists."""
    TOOL_REGISTRY[meta["name"]] = meta

# ----------------------------------------------------------------------
# Register Phase‑2 read‑only tools
# ----------------------------------------------------------------------
_register(
    {
        "name": "get_learning_stats",
        "description": "Return the current user's learning statistics (assistant‑friendly).",
        "arg_schema": GetLearningStatsArgs,
        "result_schema": LearningStatsResult,
        "handler": handle_get_learning_stats,
        "classification": "read",
        "requires_confirmation": False,
    }
)

_register(
    {
        "name": "get_due_vocabulary",
        "description": "Return a paginated list of vocabulary items that are due for review for the current user.",
        "arg_schema": GetDueVocabArgs,
        "result_schema": DueVocabularyResult,
        "handler": handle_get_due_vocabulary,
        "classification": "read",
        "requires_confirmation": False,
    }
)

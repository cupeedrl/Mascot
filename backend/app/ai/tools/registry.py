from typing import Callable, Literal, TypedDict
from uuid import UUID
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .schemas import (
    GetLearningStatsArgs,
    LearningStatsResult,
    GetDueVocabArgs,
    DueVocabularyResult,
    AddVocabularyArgs,
    AddVocabularyResult,
    GetLearningProfileArgs,
    LearningProfileResult,
)
from .learning_tools import (
    handle_get_learning_stats,
    handle_get_due_vocabulary,
    handle_get_learning_profile,
)
from .vocabulary_tools import handle_add_vocabulary

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
        "name": "get_learning_profile",
        "description": (
            "Return the authenticated learner's fresh, track-scoped profile for "
            "personalized study advice: vocabulary state counts, due count, recent "
            "practice accuracy, streak, weak topics, and recent topics. Use this for "
            "questions about what to study today, weaknesses, priorities, or a study "
            "recommendation. Do not use it for an exact due-word list."
        ),
        "arg_schema": GetLearningProfileArgs,
        "result_schema": LearningProfileResult,
        "handler": handle_get_learning_profile,
        "classification": "read",
        "requires_confirmation": False,
    }
)

_register(
    {
        "name": "add_vocabulary",
        "description": (
            "Propose adding exactly one English vocabulary item only when the latest "
            "user message explicitly asks to add, save, or store it. Never use this "
            "tool for meaning, translation, definition, example, or usage questions. "
            "This write always requires explicit UI confirmation before execution."
        ),
        "arg_schema": AddVocabularyArgs,
        "result_schema": AddVocabularyResult,
        "handler": handle_add_vocabulary,
        "classification": "write",
        "requires_confirmation": True,
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

"""Lesson 5: a minimal LangChain agent that calls tools.

    user message -> agent -> model -> tool call -> tool -> tool result -> model -> final answer

Runs fully offline: ScriptedFakeChatModel replaces the provider and the two tools
return fixed data. No API key, no database, no Mascot production code.

Run from this directory:
    python agent.py
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from pydantic import PrivateAttr

SYSTEM_PROMPT = (
    "You are Mascot's learning assistant. "
    "Use a tool when the learner asks about their own progress."
)


# 1. Tools: plain functions + docstring. The docstring and the argument types
#    become the schema the model sees, so keep them accurate.
@tool
def get_learning_stats() -> dict[str, Any]:
    """Return the learner's vocabulary totals, due count and streak."""
    return {"total_words": 120, "mastered": 48, "due_today": 7, "streak_days": 5}


@tool
def get_due_vocabulary(limit: int = 3) -> list[dict[str, str]]:
    """Return the vocabulary items due for review today."""
    due = [
        {"word": "diligent", "meaning": "cham chi"},
        {"word": "postpone", "meaning": "hoan lai"},
        {"word": "reliable", "meaning": "dang tin cay"},
    ]
    return due[:limit]


TOOLS = [get_learning_stats, get_due_vocabulary]


# 2. Model: offline stand-in for ChatGroq / ChatOpenAI.
class ScriptedFakeChatModel(BaseChatModel):
    """Returns `responses[i]` on the i-th call and records what it was sent.

    A real model decides for itself whether to call a tool. Here the decision is
    scripted, but the message shapes are real, so the agent's own loop runs.
    """

    responses: list[AIMessage]
    _calls: list[list[BaseMessage]] = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted-fake-chat-model"

    @property
    def calls(self) -> list[list[BaseMessage]]:
        """One entry per model call: the messages the agent sent that time."""
        return self._calls

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        # create_agent() calls this once per model call to attach the tool schemas.
        return self.bind(tools=list(tools), **kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._calls.append(list(messages))
        message = self.responses[len(self._calls) - 1]
        return ChatResult(generations=[ChatGeneration(message=message)])


def tool_call_message(name: str, args: dict[str, Any] | None = None) -> AIMessage:
    """A model turn that asks for one tool call (no text)."""
    return AIMessage(
        content="", tool_calls=[{"id": "call_1", "name": name, "args": args or {}}]
    )


# 3. The agent: model + tools + system prompt. create_agent() owns the loop.
def build_agent(model: BaseChatModel) -> Any:
    return create_agent(model, TOOLS, system_prompt=SYSTEM_PROMPT)


def ask(model: BaseChatModel, question: str) -> dict[str, Any]:
    """Run one turn and return the agent state, including every message."""
    return build_agent(model).invoke({"messages": [HumanMessage(question)]})


def print_trace(title: str, result: dict[str, Any]) -> None:
    print(f"\n{title}")
    for message in result["messages"]:
        kind = type(message).__name__
        if getattr(message, "tool_calls", None):
            call = message.tool_calls[0]
            print(f"  {kind:<13} tool_call -> {call['name']}({call['args']})")
        else:
            print(f"  {kind:<13} {message.content!r}")


def main() -> None:
    # Scenario A: the model decides a tool is needed, then answers from its result.
    model = ScriptedFakeChatModel(
        responses=[
            tool_call_message("get_learning_stats"),
            AIMessage(content="You know 120 words and 7 are due today. Nice streak!"),
        ]
    )
    print_trace("A. Tool needed:", ask(model, "How is my learning going?"))
    print(f"  model calls: {len(model.calls)}")

    # Scenario B: same agent, same tools — the model just answers. No tool runs.
    chatty = ScriptedFakeChatModel(
        responses=[AIMessage(content="'Diligent' means hard-working and careful.")]
    )
    print_trace("B. No tool needed:", ask(chatty, "What does 'diligent' mean?"))
    print(f"  model calls: {len(chatty.calls)}")


if __name__ == "__main__":
    main()

"""Lesson 2: Structured Output with LangChain.

    Pydantic schema -> with_structured_output() -> chat model -> LanguageAssessment

Runs fully offline: FakeStructuredChatModel stands in for a real provider, so no
API key or network access is needed.

Run from this directory:
    python structured_output.py
"""

from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field


# 1. The schema: the exact shape we want back from the model.
class LanguageAssessment(BaseModel):
    """CEFR level estimate for a learner's writing sample."""

    level: Literal["A1", "A2", "B1", "B2", "C1", "C2"] = Field(
        description="Estimated CEFR level."
    )
    reason: str = Field(description="One short sentence explaining the estimate.")


# 2. The chat model: an offline stand-in for ChatGroq / ChatOpenAI.
class FakeStructuredChatModel(BaseChatModel):
    """Always answers with `scripted_args` as a call to the first bound tool.

    A real model reads the prompt and chooses the arguments itself. The message
    shape returned here (an AIMessage with tool_calls) is the same shape a real
    tool-calling model returns, so LangChain's parsing path is exercised for real.
    """

    scripted_args: dict[str, Any]

    @property
    def _llm_type(self) -> str:
        return "fake-structured-chat-model"

    def bind_tools(self, tools: Any, *, tool_choice: Any = None, **kwargs: Any) -> Any:
        # Like real models: convert each schema to provider tool JSON and attach
        # it to every later call. with_structured_output() calls this method.
        return self.bind(
            tools=[convert_to_openai_tool(tool) for tool in tools],
            tool_choice=tool_choice,
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        tool_name = kwargs["tools"][0]["function"]["name"]
        message = AIMessage(
            content="",
            tool_calls=[
                {"id": "call_fake_1", "name": tool_name, "args": self.scripted_args}
            ],
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


def build_messages(sample: str) -> list[BaseMessage]:
    return [
        SystemMessage("You estimate the CEFR level of an English writing sample."),
        HumanMessage(sample),
    ]


# 3. Structured output: schema + model -> a runnable that returns LanguageAssessment.
def assess(model: BaseChatModel, sample: str) -> LanguageAssessment:
    structured_model = model.with_structured_output(LanguageAssessment)
    return structured_model.invoke(build_messages(sample))


def main() -> None:
    sample = "Yesterday I go to the market and buy many fruit for my family."

    print("1. Schema sent to the model as a tool definition:")
    print(json.dumps(convert_to_openai_tool(LanguageAssessment), indent=2))

    # With a real provider this would be, e.g. ChatGroq(model=...) from the
    # langchain-groq package plus GROQ_API_KEY. Not used in this lesson.
    model = FakeStructuredChatModel(
        scripted_args={"level": "A2", "reason": "Simple vocabulary with tense errors."}
    )
    result = assess(model, sample)
    print("\n2. Structured Python result:")
    print(f"{type(result).__name__}: {result!r}")
    print(f"result.level = {result.level}")

    print("\n3. Invalid model output (include_raw=True captures the error):")
    bad_model = FakeStructuredChatModel(
        scripted_args={"level": "Z9", "reason": "Not a CEFR level."}
    )
    output = bad_model.with_structured_output(
        LanguageAssessment, include_raw=True
    ).invoke(build_messages(sample))
    print(f"raw tool call args: {output['raw'].tool_calls[0]['args']}")
    print(f"parsed: {output['parsed']}")
    print(f"parsing_error: {type(output['parsing_error']).__name__}")


if __name__ == "__main__":
    main()

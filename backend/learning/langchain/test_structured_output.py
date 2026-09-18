import pytest
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from structured_output import FakeStructuredChatModel, LanguageAssessment, assess


def test_returns_validated_pydantic_object():
    model = FakeStructuredChatModel(
        scripted_args={"level": "B1", "reason": "Clear ideas with some errors."}
    )

    result = assess(model, "I have been learning English for two years.")

    assert isinstance(result, LanguageAssessment)
    assert result.level == "B1"
    assert result.reason == "Clear ideas with some errors."


def test_schema_is_sent_to_model_as_tool_definition():
    model = FakeStructuredChatModel(scripted_args={"level": "A1", "reason": "x"})

    # with_structured_output() returns: model bound to the schema | output parser
    structured_model = model.with_structured_output(LanguageAssessment)
    tool = structured_model.first.kwargs["tools"][0]["function"]

    assert tool["name"] == "LanguageAssessment"
    assert tool["parameters"]["properties"]["level"]["enum"] == [
        "A1", "A2", "B1", "B2", "C1", "C2",
    ]


def test_invalid_model_output_is_rejected():
    model = FakeStructuredChatModel(scripted_args={"level": "Z9", "reason": "x"})

    with pytest.raises((ValidationError, OutputParserException)):
        assess(model, "Hello.")

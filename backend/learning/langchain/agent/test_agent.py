import sys

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import (
    TOOLS,
    ScriptedFakeChatModel,
    ask,
    get_due_vocabulary,
    get_learning_stats,
    tool_call_message,
)


def stats_model() -> ScriptedFakeChatModel:
    """Model that calls get_learning_stats once, then answers."""
    return ScriptedFakeChatModel(
        responses=[
            tool_call_message("get_learning_stats"),
            AIMessage(content="You know 120 words and 7 are due today."),
        ]
    )


def test_tools_are_registered_with_name_and_schema():
    assert [t.name for t in TOOLS] == ["get_learning_stats", "get_due_vocabulary"]
    assert "due count" in get_learning_stats.description
    # Arguments and their defaults come from the function signature.
    assert get_due_vocabulary.args["limit"]["default"] == 3


def test_agent_executes_the_tool_the_model_asked_for():
    result = ask(stats_model(), "How is my learning going?")

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].name == "get_learning_stats"
    assert '"due_today": 7' in tool_messages[0].content


def test_tool_result_is_sent_back_to_the_model():
    model = stats_model()

    ask(model, "How is my learning going?")

    # Call 1: system + user. Call 2: also the tool call and its result.
    assert len(model.calls) == 2
    assert not any(isinstance(m, ToolMessage) for m in model.calls[0])
    second_call_tool_messages = [m for m in model.calls[1] if isinstance(m, ToolMessage)]
    assert len(second_call_tool_messages) == 1
    assert "total_words" in second_call_tool_messages[0].content


def test_final_answer_is_the_last_message():
    result = ask(stats_model(), "How is my learning going?")

    final = result["messages"][-1]
    assert isinstance(final, AIMessage)
    assert not final.tool_calls
    assert final.content == "You know 120 words and 7 are due today."


def test_agent_answers_directly_when_no_tool_is_needed():
    model = ScriptedFakeChatModel(
        responses=[AIMessage(content="'Diligent' means hard-working.")]
    )

    result = ask(model, "What does 'diligent' mean?")

    assert not any(isinstance(m, ToolMessage) for m in result["messages"])
    assert len(model.calls) == 1
    assert isinstance(result["messages"][0], HumanMessage)


def test_no_mascot_production_code_is_imported():
    mascot_modules = [
        name for name in sys.modules if name == "app" or name.startswith("app.")
    ]
    assert mascot_modules == []

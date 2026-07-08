import json
from atri.models import Message, Tool, FunctionDef, ToolCall, FunctionCall, RequestBody


def test_message_serialization():
    msg = Message(role="user", content="hello")
    d = {"role": msg.role, "content": msg.content}
    assert d == {"role": "user", "content": "hello"}


def test_message_with_tool_calls():
    tc = ToolCall(id="call_1", type="function",
                  function=FunctionCall(name="test", arguments='{"x":1}'))
    msg = Message(role="assistant", tool_calls=[tc])
    assert msg.role == "assistant"
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0].function.name == "test"


def test_tool_definition():
    tool = Tool(function=FunctionDef(
        name="test_func",
        description="A test function",
        parameters={"type": "object", "properties": {}}
    ))
    assert tool.type == "function"
    assert tool.function.name == "test_func"


def test_request_body():
    body = RequestBody(
        model="deepseek-chat",
        messages=[Message(role="user", content="hi")],
        tools=[Tool(function=FunctionDef(name="f1", description="d", parameters={}))]
    )
    assert body.stream is False
    assert body.thinking.type == "disabled"


def test_message_defaults():
    msg = Message()
    assert msg.role is None
    assert msg.content is None
    assert msg.tool_calls is None
    assert msg.tool_call_id is None

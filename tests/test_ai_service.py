import json
import pytest
from pathlib import Path
from atri.ai_service import AIService
from atri.file_tool import FileTool


def test_initialization_loads_config(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "workspace").mkdir()
    settings = tmp_path / "data" / "UserSettings.json"
    settings.write_text(json.dumps({
        "DeepSeek": {
            "ApiKey": "sk-test",
            "Url": "https://test.api.com",
            "Model": "test-model",
        }
    }, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr("atri.ai_service.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr("atri.conversation.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr("atri.prompt_manager.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(FileTool, "work_dir", str(tmp_path / "workspace"))

    svc = AIService()
    svc.initialization()

    assert svc.api_key == "sk-test"
    assert svc.url == "https://test.api.com"
    assert svc.model == "test-model"
    assert len(svc.tool.tool_list) == 21
    assert svc.content_compact is not None
    # System prompt is now built dynamically — verify it contains ATRI's identity
    built = svc.prompt_manager.build_system_prompt()
    assert "亚托莉" in built


def test_msg_to_dict_basic():
    from atri.models import Message
    msg = Message(role="user", content="hello")
    result = AIService._msg_to_dict(msg)
    assert result == {"role": "user", "content": "hello"}


def test_msg_to_dict_with_tool_calls():
    from atri.models import Message, ToolCall, FunctionCall
    msg = Message(
        role="assistant",
        tool_calls=[ToolCall(
            id="call_1",
            type="function",
            function=FunctionCall(name="test", arguments='{"x": 1}'),
        )],
    )
    result = AIService._msg_to_dict(msg)
    assert result["role"] == "assistant"
    assert result["tool_calls"][0]["function"]["name"] == "test"


def test_msg_to_dict_with_tool_call_id():
    from atri.models import Message
    msg = Message(role="tool", tool_call_id="call_1", content="result")
    result = AIService._msg_to_dict(msg)
    assert result["tool_call_id"] == "call_1"


def test_stream_event_creation():
    from atri.models import StreamEvent
    e = StreamEvent(type="content", text="hello")
    assert e.type == "content"
    assert e.text == "hello"
    assert e.tool_name == ""

    e2 = StreamEvent(type="tool_start", tool_name="web_search")
    assert e2.type == "tool_start"
    assert e2.tool_name == "web_search"
    assert e2.text == ""


def test_accumulate_sse_delta_content():
    from atri.ai_service import AIService
    buffer: dict = {}
    events = AIService._accumulate_sse_delta({"content": "你好"}, buffer)
    assert len(events) == 1
    assert events[0].type == "content"
    assert events[0].text == "你好"


def test_accumulate_sse_delta_tool_call_fragments():
    from atri.ai_service import AIService
    buffer: dict = {}

    e1 = AIService._accumulate_sse_delta(
        {"tool_calls": [{"index": 0, "id": "call_001", "type": "function",
                          "function": {"name": "web_search", "arguments": ""}}]},
        buffer,
    )
    assert len(e1) == 1
    assert e1[0].type == "tool_start"
    assert e1[0].tool_name == "web_search"
    assert buffer[0]["id"] == "call_001"
    assert buffer[0]["name"] == "web_search"
    assert buffer[0]["arguments"] == ""

    e2 = AIService._accumulate_sse_delta(
        {"tool_calls": [{"index": 0, "function": {"arguments": '{"query":'}}]},
        buffer,
    )
    assert len(e2) == 0
    assert buffer[0]["arguments"] == '{"query":'

    e3 = AIService._accumulate_sse_delta(
        {"tool_calls": [{"index": 0, "function": {"arguments": ' "天气"}'}}]},
        buffer,
    )
    assert len(e3) == 0
    assert buffer[0]["arguments"] == '{"query": "天气"}'


def test_accumulate_sse_delta_parallel_tools():
    from atri.ai_service import AIService
    buffer: dict = {}

    events = AIService._accumulate_sse_delta(
        {"tool_calls": [
            {"index": 0, "id": "c1", "function": {"name": "read_file", "arguments": ""}},
            {"index": 1, "id": "c2", "function": {"name": "web_search", "arguments": ""}},
        ]},
        buffer,
    )
    assert len(buffer) == 2
    assert buffer[0]["name"] == "read_file"
    assert buffer[1]["name"] == "web_search"
    assert len(events) == 2
    assert events[0].tool_name == "read_file"
    assert events[1].tool_name == "web_search"


def test_accumulate_sse_delta_no_index_defaults_zero():
    from atri.ai_service import AIService
    buffer: dict = {}

    AIService._accumulate_sse_delta(
        {"tool_calls": [{"id": "call_x", "function": {"name": "search", "arguments": ""}}]},
        buffer,
    )
    assert 0 in buffer
    assert buffer[0]["name"] == "search"

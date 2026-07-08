import json
from pathlib import Path
from atri.tool_manager import ToolManager
from atri.file_tool import FileTool


def test_tool_init_registers_all_tools():
    tm = ToolManager()
    tm.tool_init()
    assert len(tm.tool_list) == 21


def test_tool_actor_unknown_tool():
    tm = ToolManager()
    result = tm.tool_actor("nonexistent", "{}")
    assert "未知" in result


def test_tool_actor_none_name():
    tm = ToolManager()
    result = tm.tool_actor(None, "{}")
    assert "未知" in result


def test_tool_actor_test_data():
    tm = ToolManager()
    assert tm.tool_actor("get_test_data_1", '{"testNum": 5}') == "5"
    assert tm.tool_actor("get_test_data_2", '{"testNum": 3}') == "6"
    assert tm.tool_actor("get_test_data_3", '{"testNum": 4}') == "12"


def test_tool_actor_file_operations(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    ws.mkdir()
    monkeypatch.setattr(FileTool, "work_dir", str(ws))
    tm = ToolManager()
    tm.tool_init()
    r = tm.tool_actor("write_file", json.dumps({"filePath": "test.txt", "content": "hello"}))
    assert "成功" in r
    r = tm.tool_actor("read_file", json.dumps({"filePath": "test.txt"}))
    assert "hello" in r


def test_tool_actor_memory_operations(tmp_path, monkeypatch):
    from atri import memory_tool
    mf = tmp_path / "mem.json"
    monkeypatch.setattr(memory_tool.MemoryTool, "memory_file", str(mf.resolve()))
    tm = ToolManager()
    r = tm.tool_actor("add_user_memory", json.dumps({"content": "test memory"}))
    assert "已记住" in r
    r = tm.tool_actor("list_user_memories", "{}")
    assert "test memory" in r


def test_tool_init_is_idempotent():
    tm = ToolManager()
    tm.tool_init()
    count = len(tm.tool_list)
    tm.tool_init()
    assert len(tm.tool_list) == count

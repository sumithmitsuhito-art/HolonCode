import asyncio
import json
from pathlib import Path
from atri.tool_manager import ToolManager
from atri.file_tool import FileTool


def test_tool_init_registers_all_tools():
    tm = ToolManager()
    tm.tool_init()
    assert len(tm.tool_list) == 28


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


# ── web_search / web_extract tests ──

def test_web_search_and_extract_registered():
    tm = ToolManager()
    tm.tool_init()
    names = {t.function.name for t in tm.tool_list}
    assert "web_search" in names
    assert "web_extract" in names


def test_web_search_empty_query():
    from atri.web_tools import web_search_tool
    result = web_search_tool("")
    data = json.loads(result)
    assert data["success"] is False


def test_web_extract_empty_urls():
    from atri.web_tools import web_extract_tool
    result = web_extract_tool([])
    data = json.loads(result)
    assert data["success"] is False


def test_is_safe_url_blocks_private():
    from atri.web_tools import is_safe_url
    assert not is_safe_url("http://127.0.0.1/test")
    assert not is_safe_url("http://192.168.1.1/test")
    assert not is_safe_url("http://10.0.0.1/test")
    assert not is_safe_url("http://169.254.169.254/latest/meta-data")


def test_is_safe_url_allows_public():
    from atri.web_tools import is_safe_url
    assert is_safe_url("https://example.com")
    assert is_safe_url("https://www.baidu.com")


def test_check_url_for_secrets():
    from atri.web_tools import _check_url_for_secrets
    assert _check_url_for_secrets("https://evil.com?token=abc123") is not None
    assert _check_url_for_secrets("https://api.example.com?api_key=abc") is not None
    assert _check_url_for_secrets("https://example.com/normal-page") is None
    assert _check_url_for_secrets("https://example.com?q=hello") is None


def test_web_search_dispatches():
    tm = ToolManager()
    tm.tool_init()
    result = tm.tool_actor("web_search", json.dumps({"query": ""}))
    data = json.loads(result)
    assert data["success"] is False  # empty query


def test_web_extract_dispatches():
    tm = ToolManager()
    tm.tool_init()
    result = tm.tool_actor("web_extract", json.dumps({"urls": []}))
    data = json.loads(result)
    assert data["success"] is False  # empty urls


# ── 两层工具表 + 技能生命周期 ──

def test_get_all_tools_no_active_skills():
    tm = ToolManager()
    tm.tool_init()
    tools = tm.get_all_tools([])
    names = {t.function.name for t in tools}
    assert "read_file" in names
    assert "activate_skill" in names


def test_get_all_tools_with_active_skills():
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    tools = tm.get_all_tools(active)
    names = {t.function.name for t in tools}
    assert "read_file" in names
    assert "browser_navigate" in names


def test_activate_skill_registers_tools():
    tm = ToolManager()
    tm.tool_init()
    active = []
    result = tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    assert "已激活" in result
    assert "browser_navigate" in result
    assert active == ["browser"]
    tools = tm.get_all_tools(active)
    assert "browser_navigate" in {t.function.name for t in tools}


def test_deactivate_skill_removes_tools():
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    tm.tool_actor("deactivate_skill", '{"name":"browser"}', active_skills=active)
    assert active == []
    assert "browser_navigate" not in {t.function.name for t in tm.get_all_tools(active)}


def test_deactivate_without_name_closes_latest():
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    tm.tool_actor("activate_skill", '{"name":"translator"}', active_skills=active)
    assert len(active) == 2
    result = tm.tool_actor("deactivate_skill", "{}", active_skills=active)
    assert "已关闭" in result
    assert active == ["browser"]


def test_eviction_unloads_tools():
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    tm.tool_actor("activate_skill", '{"name":"code-reviewer"}', active_skills=active)
    tm.tool_actor("activate_skill", '{"name":"translator"}', active_skills=active)
    assert len(active) == 3
    tm.tool_actor("activate_skill", '{"name":"storyteller"}', active_skills=active)
    assert "browser" not in active
    assert "browser_navigate" not in {t.function.name for t in tm.get_all_tools(active)}


def test_skill_without_plugin_still_activates():
    tm = ToolManager()
    tm.tool_init()
    active = []
    result = tm.tool_actor("activate_skill", '{"name":"translator"}', active_skills=active)
    assert "已激活" in result
    assert active == ["translator"]


def test_reactivate_already_active_skill():
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    result = tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    assert "已经激活" in result


def test_skill_tool_execution():
    """Skill tool should be dispatched (not returned as unknown). May fail if browser not installed."""
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    result = asyncio.run(tm.tool_actor_async("browser_navigate", json.dumps({"url": "https://httpbin.org/get?test=1"}), active_skills=active))
    # Either successfully navigates, or fails with browser error (not "unknown tool")
    assert "未知" not in result

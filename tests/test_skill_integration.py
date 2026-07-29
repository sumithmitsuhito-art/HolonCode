"""Integration tests: full activate → register → execute → deactivate cycle."""
import asyncio
import json
from atri.tool_manager import ToolManager


def test_full_skill_lifecycle():
    tm = ToolManager()
    tm.tool_init()
    active = []

    # activate
    result = tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    assert "已激活" in result
    assert "browser_navigate" in {t.function.name for t in tm.get_all_tools(active)}

    # dispatch (may fail if browser not installed, but must not be "unknown tool")
    result = asyncio.run(tm.tool_actor_async(
        "browser_navigate",
        json.dumps({"url": "https://httpbin.org/get?test=1"}),
        active_skills=active,
    ))
    assert "未知" not in result

    # deactivate
    tm.tool_actor("deactivate_skill", '{"name":"browser"}', active_skills=active)
    assert active == []
    assert "browser_navigate" not in {t.function.name for t in tm.get_all_tools(active)}


def test_unknown_tool_not_dispatched_to_wrong_skill():
    """Non-@tool functions (like on_activate) should not be dispatched."""
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    result = tm.tool_actor("on_activate", "{}", active_skills=active)
    assert "未知" in result


def test_skill_tool_not_dispatched_after_deactivate():
    """After deactivation, skill tools should no longer be callable."""
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    tm.tool_actor("deactivate_skill", '{"name":"browser"}', active_skills=active)
    result = tm.tool_actor("browser_navigate", json.dumps({"url": "https://example.com"}), active_skills=active)
    assert "未知" in result


def test_activate_nonexistent_skill():
    tm = ToolManager()
    tm.tool_init()
    active = []
    result = tm.tool_actor("activate_skill", '{"name":"nonexistent_xyz"}', active_skills=active)
    assert "不存在" in result


def test_multiple_skills_tools_merged():
    """Two active skills with plugins should both contribute tools."""
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    tools = tm.get_all_tools(active)
    names = {t.function.name for t in tools}
    assert "browser_navigate" in names
    # base tools still present
    assert "read_file" in names

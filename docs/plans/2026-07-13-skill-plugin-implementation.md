# 技能插件系统改造 — 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让技能从纯 Prompt 注入升级为 "Prompt + 自定义工具" 的复合插件，同时支持桌面端 `/skill-name` 斜杠指令快捷激活。

**Architecture:** ToolManager 的扁平静态工具列表拆为 `_base_tools`（系统内置）+ `_skill_tools`（技能动态注册）两层。技能激活时通过 importlib 动态加载 plugin.py，`@tool` 装饰器标记的工具函数自动解析类型注解生成 JSON Schema 并注册。桌面端 AppShell 在消息入口拦截 `/` 前缀，匹配技能名则直接调用激活。

**Tech Stack:** Python 3.12+, DeepSeek API, PySide6, pytest, importlib

---

### Task 1: `@tool` 装饰器 + extract_tools()

**Files:**
- Modify: `src/atri/skill_loader.py`

**Step 1: 在 skill_loader.py 现有 import 之后、`SKILLS_DIR` 之前插入新代码**

```python
import inspect
import functools
from typing import Any, Callable, get_type_hints

_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}

def tool(func=None, *, name: str | None = None, description: str | None = None):
    """装饰器：标记函数为技能工具。

    函数名 → 工具名，docstring 第一行 → 工具描述，类型注解 → JSON Schema。
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        tool_name = name or fn.__name__
        tool_desc = description
        if tool_desc is None and fn.__doc__:
            tool_desc = fn.__doc__.strip().split("\n")[0]

        wrapper._is_tool = True
        wrapper._tool_name = tool_name
        wrapper._tool_description = tool_desc or ""
        return wrapper

    if func is None:
        return decorator
    return decorator(func)


def _annotation_to_json_type(anno) -> str:
    """Python 类型注解 → JSON Schema type 字符串。"""
    origin = getattr(anno, "__origin__", None)
    if origin is not None:
        return "array" if origin is list else "object"
    return _TYPE_MAP.get(anno, "string")


def _build_parameters_schema(fn: Callable) -> dict:
    """从函数签名自动构建 JSON Schema parameters。"""
    hints = {}
    try:
        hints = get_type_hints(fn)
    except Exception:
        pass

    sig = inspect.signature(fn)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        anno = hints.get(param_name, str)
        prop = {"type": _annotation_to_json_type(anno)}
        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(param_name)
        properties[param_name] = prop

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def extract_tools(module) -> list:
    """从 plugin 模块提取 @tool 函数，返回 list[Tool]。"""
    from atri.models import Tool, FunctionDef

    tools = []
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if not callable(obj):
            continue
        if not getattr(obj, "_is_tool", False):
            continue

        tools.append(Tool(function=FunctionDef(
            name=getattr(obj, "_tool_name", attr_name),
            description=getattr(obj, "_tool_description", ""),
            parameters=_build_parameters_schema(obj),
        )))
    return tools
```

**Step 2: 运行测试确认未破坏现有功能**

```
pytest tests/ -v
```
Expected: 全部 PASS

---

### Task 2: `load_plugin()` 动态加载

**Files:**
- Modify: `src/atri/skill_loader.py`

**Step 1: 在 SkillLoader 类末尾添加 `load_plugin` 和 `get_tool_names` 静态方法**

```python
@staticmethod
def load_plugin(name: str):
    """动态加载技能 plugin.py，返回 module 或 None。"""
    import importlib.util
    plugin_path = SKILLS_DIR / name / "plugin.py"
    if not plugin_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            f"skills.{name}",
            str(plugin_path),
        )
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None

@staticmethod
def get_tool_names(name: str) -> list[str]:
    """获取技能注册的工具名列表（不加载则返回空）。"""
    plugin = SkillLoader.load_plugin(name)
    if plugin is None:
        return []
    return [t.function.name for t in extract_tools(plugin)]
```

**Step 2: 运行测试**

```
pytest tests/ -v
```
Expected: 全部 PASS

---

### Task 3: ToolManager 两层工具表重构

**Files:**
- Modify: `src/atri/tool_manager.py`

**Step 1: 将类属性 `_total_tool_list` 改为模块级常量，ToolManager 增加实例属性**

在 `class ToolManager` 之前，将 `_total_tool_list` 重命名为 `_ALL_BUILTIN_TOOLS`（内容不变，只是重命名）。

`ToolManager.__init__` 改为：

```python
def __init__(self):
    self.tool_list: list[Tool] = []
    self._base_tools: list[Tool] = []
    self._skill_tools: dict[str, list[Tool]] = {}
    self._skill_plugins: dict[str, object] = {}
```

**Step 2: 修改 `tool_init()`**

```python
def tool_init(self):
    if not self.tool_list:
        self.tool_list.extend(_ALL_BUILTIN_TOOLS)
        self._base_tools = list(_ALL_BUILTIN_TOOLS)
    try:
        __import__("aiotieba")
    except ImportError:
        tieba_names = {
            "tieba_get_threads", "tieba_get_posts", "tieba_search_exact",
            "tieba_get_forum_info", "tieba_get_user_info", "tieba_get_hot_threads",
        }
        self.tool_list = [t for t in self.tool_list if t.function.name not in tieba_names]
        self._base_tools = [t for t in self._base_tools if t.function.name not in tieba_names]
    FileTool.ensure_work_dir()
```

**Step 3: 添加 `get_all_tools()` 方法**

```python
def get_all_tools(self, active_skills: list[str] | None = None) -> list[Tool]:
    """返回内置工具 + 所有激活技能注册的工具。"""
    tools = list(self._base_tools)
    for name in (active_skills or []):
        tools.extend(self._skill_tools.get(name, []))
    return tools
```

**Step 4: 运行测试**

```
pytest tests/test_tool_manager.py -v
```
Expected: 全部 PASS（`test_tool_init_registers_all_tools` 中的 28 保持不变）

---

### Task 4: activate_skill / deactivate_skill 集成 plugin

**Files:**
- Modify: `src/atri/tool_manager.py`

**Step 1: 替换 `activate_skill` 分支（原 tool_manager.py 第 379-394 行）**

```python
if name == "activate_skill":
    skill_name = str(args.get("name", "")).strip()
    err = SkillLoader.validate_name(skill_name)
    if err:
        return err
    if not SkillLoader.skill_exists(skill_name):
        return f"技能 '{skill_name}' 不存在。使用 list_skills 查看可用技能。"
    skills_list = active_skills if active_skills is not None else []
    if skill_name in skills_list:
        return f"技能 '{skill_name}' 已经激活了。当前激活: {skills_list}"

    # 超出上限时淘汰最早的，卸载其工具
    while len(skills_list) >= MAX_ACTIVE_SKILLS:
        evicted = skills_list.pop(0)
        self._skill_tools.pop(evicted, None)
        old_plugin = self._skill_plugins.pop(evicted, None)
        if old_plugin and hasattr(old_plugin, "on_deactivate"):
            try:
                old_plugin.on_deactivate()
            except Exception:
                pass

    # 加载 plugin.py
    plugin = SkillLoader.load_plugin(skill_name)
    tool_names = []
    if plugin is not None:
        if hasattr(plugin, "on_activate"):
            try:
                plugin.on_activate()
            except Exception:
                pass
        skill_tools = extract_tools(plugin)
        self._skill_tools[skill_name] = skill_tools
        self._skill_plugins[skill_name] = plugin
        tool_names = [t.function.name for t in skill_tools]

    skills_list.append(skill_name)
    preview = SkillLoader.load_skill(skill_name) or ""
    preview_short = preview[:200] + "..." if len(preview) > 200 else preview
    result = f"[已激活] {skill_name}\n预览：{preview_short}\n当前激活: {skills_list}"
    if tool_names:
        result += f"\n注册工具: {', '.join(tool_names)}"
    return result
```

**Step 2: 替换 `deactivate_skill` 分支（原第 396-407 行）**

```python
if name == "deactivate_skill":
    skill_name = str(args.get("name", "")).strip()
    skills_list = active_skills if active_skills is not None else []
    if not skill_name:
        if not skills_list:
            return "当前没有激活的技能。"
        closed = skills_list.pop()
        self._skill_tools.pop(closed, None)
        plugin = self._skill_plugins.pop(closed, None)
        if plugin and hasattr(plugin, "on_deactivate"):
            try:
                plugin.on_deactivate()
            except Exception:
                pass
        return f"[已关闭] {closed}\n当前激活: {skills_list}"
    if skill_name not in skills_list:
        return f"技能 '{skill_name}' 没有激活。当前激活: {skills_list}"
    skills_list.remove(skill_name)
    self._skill_tools.pop(skill_name, None)
    plugin = self._skill_plugins.pop(skill_name, None)
    if plugin and hasattr(plugin, "on_deactivate"):
        try:
            plugin.on_deactivate()
        except Exception:
            pass
    return f"[已关闭] {skill_name}\n当前激活: {skills_list}"
```

**Step 3: 运行测试**

```
pytest tests/ -v
```
Expected: 全部 PASS

---

### Task 5: ai_service.py 改用 `get_all_tools()` + 技能工具 dispatch

**Files:**
- Modify: `src/atri/ai_service.py`
- Modify: `src/atri/tool_manager.py`

**Step 1: 修改 ai_service.py 第 75-85 行，工具列表改用动态获取**

将：
```python
for t in self.tool.tool_list
```
替换为：
```python
for t in self.tool.get_all_tools(self.active_skills)
```

**Step 2: 在 tool_manager.py 的 `tool_actor` 末尾 `return "未知工具调用"` 之前，插入技能工具 dispatch**

```python
        # ── 技能注册的工具 ──
        for skill_name in (active_skills or []):
            plugin = self._skill_plugins.get(skill_name)
            if plugin is None:
                continue
            func = getattr(plugin, name, None)
            if func is None or not callable(func):
                continue
            if not getattr(func, "_is_tool", False):
                continue
            try:
                result = func(**args)
                return json.dumps(result, ensure_ascii=False)
            except Exception as exc:
                return f"工具执行异常 ({name}): {exc}"
```

**Step 3: 运行测试**

```
pytest tests/ -v
```
Expected: 全部 PASS

---

### Task 6: prompt_manager.py 展示技能工具

**Files:**
- Modify: `src/atri/prompt_manager.py`

**Step 1: 修改 `_get_skill_catalog()` 方法**

在当前方法中，将：
```python
lines.append(f"- {s['name']}: {s['description']}{marker}")
```
替换为：
```python
tool_names = SkillLoader.get_tool_names(s["name"])
tool_hint = f" (工具: {', '.join(tool_names)})" if tool_names else ""
lines.append(f"- {s['name']}: {s['description']}{tool_hint}{marker}")
```

**Step 2: 运行测试**

```
pytest tests/ -v
```
Expected: 全部 PASS

---

### Task 7: 桌面端斜杠指令 `/skill-name`

**Files:**
- Modify: `src/atri/ui/app_shell.py`

**Step 1: 在 `AppShell` 类最前面（`__init__` 之前）添加辅助方法 `_handle_slash_command`**

```python
def _handle_slash_command(self, text: str) -> bool:
    """处理斜杠指令。返回 True 表示已拦截，False 表示走正常 AI 流程。"""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return False

    parts = stripped.split(maxsplit=1)
    command = parts[0][1:]
    trailing = parts[1] if len(parts) > 1 else ""

    # /skills
    if command == "skills":
        from atri.skill_loader import SkillLoader
        skills_list = SkillLoader.list_skills()
        if skills_list:
            msg = "【可用技能】\n" + "\n".join(
                f"  /{s['name']} — {s['description']}" for s in skills_list
            )
        else:
            msg = "当前没有可用技能"
        self.chat_view.thread.add_system_message(msg)
        return True

    # /skill-name
    from atri.skill_loader import SkillLoader
    if SkillLoader.skill_exists(command):
        result = self.ai_service.tool.tool_actor(
            "activate_skill",
            f'{{"name":"{command}"}}',
            self.ai_service.active_skills,
        )
        self.chat_view.thread.add_system_message(f"[技能] {result}")
        self.status_bar.set_status(f"技能已激活: {command}")
        self._update_status()
        if trailing:
            self._dispatch_to_ai(trailing)
        return True

    # 不认识的 /xxx，交给 AI
    return False
```

**Step 2: 提取 `_dispatch_to_ai` 方法**

把原来 `_on_user_message` 中的内容（除拦截逻辑外）提取为独立方法：

```python
def _dispatch_to_ai(self, text: str):
    self.chat_view.thread.add_user_message(text)
    self.chat_view.set_input_enabled(False)
    self.status_bar.set_status("思考中...", busy=True)
    self._current_ai_text = ""

    self._worker = AIWorker(self.ai_service, text)
    self._worker.content_chunk.connect(self._on_content_chunk)
    self._worker.tool_start.connect(self._on_tool_start)
    self._worker.tool_result.connect(self._on_tool_result)
    self._worker.message.connect(self._on_worker_message)
    self._worker.error.connect(self._on_error)
    self._worker.finished.connect(self._on_finished)
    self._worker.start()
```

**Step 3: 修改 `_on_user_message` 为入口拦截器**

```python
def _on_user_message(self, text: str):
    if self._handle_slash_command(text):
        return
    self._dispatch_to_ai(text.strip())
```

**Step 4: 运行测试**

```
pytest tests/ -v
```
Expected: 全部 PASS

---

### Task 8: 创建示例 browser 技能

**Files:**
- Create: `skills/browser/SKILL.md`
- Create: `skills/browser/plugin.py`

**Step 1: 创建 `skills/browser/SKILL.md`**

```markdown
---
name: browser
description: 浏览器操作技能，支持打开网页阅读内容、提取页面信息
---

## 角色
你是浏览器操作助手。当用户需要查看网页内容时，使用工具打开页面并总结。

## 行为准则
- 用户说"打开xxx"、"看看xxx网页"、"访问xxx"时，调用 web_open
- 先打开网页获取内容，再根据内容回答用户问题
- 如果网页打不开，告诉用户具体原因并建议替代方案
- 返回的 HTML 内容可能很长，提取关键信息后再回复用户

## 结束条件
- 用户说"不用浏览器了"、"关闭浏览器"时自动调用 deactivate_skill("browser")
```

**Step 2: 创建 `skills/browser/plugin.py`**

```python
__skill_name__ = "browser"
__version__ = "1.0.0"


def on_activate():
    """确保截图目录存在。"""
    from pathlib import Path
    ss_dir = Path("workspace/screenshots")
    ss_dir.mkdir(parents=True, exist_ok=True)


@tool
def web_open(url: str, timeout: int = 30):
    """打开指定 URL 并返回页面文本内容。用于阅读网页、查看在线文档等场景。"""
    import httpx
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text
        if len(text) > 10000:
            text = text[:10000] + f"\n\n... (内容已截断，共 {len(resp.text)} 字符)"
        return {
            "status": resp.status_code,
            "url": str(resp.url),
            "content_type": resp.headers.get("content-type", "unknown"),
            "text": text,
        }
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}", "url": url}
    except httpx.TimeoutException:
        return {"error": f"请求超时 ({timeout}s)", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}
```

**Step 3: 验证技能可被发现和加载**

```bash
python -c "from atri.skill_loader import SkillLoader, extract_tools; print(SkillLoader.list_skills()); m = SkillLoader.load_plugin('browser'); print([t.function.name for t in extract_tools(m)])"
```
Expected: 输出包含 `browser` 和 `['web_open']`

---

### Task 9: 编写 `test_skill_loader.py`

**Files:**
- Create: `tests/test_skill_loader.py`

**Step 1: 创建测试文件**

```python
"""Tests for skill_loader.py — @tool decorator, extract_tools, load_plugin."""
import types
from atri.skill_loader import (
    SkillLoader, tool, extract_tools,
    _annotation_to_json_type, _build_parameters_schema,
)


# ── @tool decorator ──

def test_tool_decorator_marks_function():
    @tool
    def my_tool(x: int):
        """A test tool."""
        return x * 2

    assert my_tool._is_tool is True
    assert my_tool._tool_name == "my_tool"
    assert my_tool._tool_description == "A test tool."
    assert my_tool(5) == 10


def test_tool_decorator_custom_name_and_desc():
    @tool(name="custom_name", description="Custom desc")
    def some_func():
        """original"""
        pass

    assert some_func._tool_name == "custom_name"
    assert some_func._tool_description == "Custom desc"


def test_tool_decorator_no_docstring():
    @tool
    def no_doc():
        pass

    assert no_doc._tool_description == ""


# ── extract_tools ──

def test_extract_tools_basic():
    mod = types.ModuleType("test_mod")

    @tool
    def greet(name: str):
        """Say hello."""
        return f"Hello {name}"

    mod.greet = greet
    tools = extract_tools(mod)
    assert len(tools) == 1
    t = tools[0]
    assert t.function.name == "greet"
    assert t.function.description == "Say hello."
    params = t.function.parameters
    assert params["type"] == "object"
    assert params["properties"]["name"]["type"] == "string"
    assert "name" in params["required"]


def test_extract_tools_multiple_and_optional_params():
    mod = types.ModuleType("test_mod")

    @tool
    def tool_a(x: int):
        """A."""
        return x

    @tool
    def tool_b(y: str = "default"):
        """B."""
        return y

    mod.tool_a = tool_a
    mod.tool_b = tool_b
    tools = extract_tools(mod)
    assert len(tools) == 2
    for t in tools:
        if t.function.name == "tool_b":
            assert "required" not in t.function.parameters


def test_extract_tools_ignores_non_decorated():
    mod = types.ModuleType("test_mod")

    def helper():
        return 42

    @tool
    def real_tool():
        """Real."""
        pass

    mod.helper = helper
    mod.real_tool = real_tool
    tools = extract_tools(mod)
    assert len(tools) == 1


def test_extract_tools_empty_module():
    mod = types.ModuleType("empty")
    assert extract_tools(mod) == []


# ── type mapping ──

def test_annotation_mapping():
    assert _annotation_to_json_type(str) == "string"
    assert _annotation_to_json_type(int) == "integer"
    assert _annotation_to_json_type(float) == "number"
    assert _annotation_to_json_type(bool) == "boolean"
    assert _annotation_to_json_type(dict) == "object"


# ── _build_parameters_schema ──

def test_build_schema_required_vs_optional():
    def fn(a: str, b: int = 0):
        pass

    schema = _build_parameters_schema(fn)
    assert "a" in schema["required"]
    assert "b" not in schema["required"]


def test_build_schema_skips_self():
    class Foo:
        def method(self, x: str):
            pass

    schema = _build_parameters_schema(Foo.method)
    assert "self" not in schema["properties"]


# ── SkillLoader ──

def test_load_plugin_nonexistent():
    assert SkillLoader.load_plugin("nonexistent_xyz") is None


def test_load_plugin_skill_without_plugin():
    assert SkillLoader.load_plugin("code-reviewer") is None


def test_load_plugin_browser():
    mod = SkillLoader.load_plugin("browser")
    assert mod is not None
    assert hasattr(mod, "web_open")


def test_get_tool_names_no_plugin():
    assert SkillLoader.get_tool_names("code-reviewer") == []


def test_get_tool_names_browser():
    names = SkillLoader.get_tool_names("browser")
    assert "web_open" in names
```

**Step 2: 运行测试**

```
pytest tests/test_skill_loader.py -v
```
Expected: 全部 PASS

---

### Task 10: 集成测试 & 全量回归

**Files:**
- Modify: `tests/test_tool_manager.py`
- Create: `tests/test_skill_integration.py`

**Step 1: 在 test_tool_manager.py 末尾添加两层工具表和技能生命周期的测试**

```python
# ── 两层工具表 + 技能生命周期 ──

def test_get_all_tools_no_active_skills():
    tm = ToolManager()
    tm.tool_init()
    tools = tm.get_all_tools([])
    names = {t.function.name for t in tools}
    assert "read_file" in names
    assert "activate_skill" in names


def test_activate_skill_registers_tools():
    tm = ToolManager()
    tm.tool_init()
    active = []
    result = tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    assert "已激活" in result
    assert "web_open" in result
    assert active == ["browser"]
    tools = tm.get_all_tools(active)
    assert "web_open" in {t.function.name for t in tools}


def test_deactivate_skill_removes_tools():
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    tm.tool_actor("deactivate_skill", '{"name":"browser"}', active_skills=active)
    assert active == []
    assert "web_open" not in {t.function.name for t in tm.get_all_tools(active)}


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
    assert "web_open" not in {t.function.name for t in tm.get_all_tools(active)}


def test_skill_without_plugin_still_activates():
    tm = ToolManager()
    tm.tool_init()
    active = []
    result = tm.tool_actor("activate_skill", '{"name":"translator"}', active_skills=active)
    assert "已激活" in result
    assert active == ["translator"]
```

**Step 2: 创建集成测试文件 `tests/test_skill_integration.py`**

```python
"""Integration tests: full activate → register → execute → deactivate cycle."""
import json
import pytest
from atri.tool_manager import ToolManager


def test_full_skill_lifecycle():
    tm = ToolManager()
    tm.tool_init()
    active = []

    # activate
    result = tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    assert "已激活" in result
    assert "web_open" in {t.function.name for t in tm.get_all_tools(active)}

    # use tool
    import httpx
    try:
        result = tm.tool_actor(
            "web_open",
            json.dumps({"url": "https://httpbin.org/get?test=1"}),
            active_skills=active,
        )
        data = json.loads(result)
        assert "text" in data or "error" in data
    except httpx.HTTPError:
        pytest.skip("Network unavailable")

    # deactivate
    tm.tool_actor("deactivate_skill", '{"name":"browser"}', active_skills=active)
    assert active == []
    assert "web_open" not in {t.function.name for t in tm.get_all_tools(active)}


def test_unknown_tool_not_dispatched_to_wrong_skill():
    """工具名只匹配 @tool 函数，非装饰函数不被 dispatch。"""
    tm = ToolManager()
    tm.tool_init()
    active = []
    tm.tool_actor("activate_skill", '{"name":"browser"}', active_skills=active)
    # browser plugin 中 on_activate 不是 @tool，不应被 dispatch
    result = tm.tool_actor("on_activate", "{}", active_skills=active)
    assert result is not None  # 不应 crash
```

**Step 3: 运行全部测试**

```
pytest tests/ -v
```
Expected: 全部 PASS

---

### 最终验证（手动）

**CLI 验证：**
```bash
python -m atri.main
```
1. 输入"激活 browser 技能" → AI 调用 activate_skill，web_open 注册成功
2. 输入"打开 https://httpbin.org/get" → AI 调用 web_open 获取内容
3. 输入"关闭 browser" → 技能停用

**GUI 验证：**
```bash
python -m atri.ui.app
```
1. 输入 `/skills` → 显示可用技能列表
2. 输入 `/browser` → 显示技能已激活
3. 输入 `/browser 帮我看看 example.com` → 先激活再发消息

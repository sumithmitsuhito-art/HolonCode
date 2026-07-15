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
    assert hasattr(mod, "browser_navigate")


def test_get_tool_names_no_plugin():
    assert SkillLoader.get_tool_names("code-reviewer") == []


def test_get_tool_names_browser():
    names = SkillLoader.get_tool_names("browser")
    assert "browser_navigate" in names

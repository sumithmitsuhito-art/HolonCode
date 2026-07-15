"""Skill loading and management for ATRI.

Skills live in skills/<name>/SKILL.md with optional references/ templates/ scripts/ assets/ subdirectories.
Each SKILL.md has YAML-like frontmatter (--- delimited) followed by markdown body.
"""

import inspect
import functools
from pathlib import Path
from typing import Any, Callable, get_type_hints
from atri import BASE_DIR

SKILLS_DIR = BASE_DIR / "skills"
MAX_ACTIVE_SKILLS = 3

# Python type annotation → JSON Schema type
_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def tool(func=None, *, name: str | None = None, description: str | None = None):
    """Decorator: mark a function as a skill tool.

    Function name → tool name (override with `name` param).
    Docstring first line → tool description (override with `description` param).
    Type annotations + defaults → auto-generated JSON Schema parameters.
    """
    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                return await fn(*args, **kwargs)
            wrapper = async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                return fn(*args, **kwargs)
            wrapper = sync_wrapper

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
    """Convert a Python type annotation to a JSON Schema type string."""
    origin = getattr(anno, "__origin__", None)
    if origin is not None:
        return "array" if origin is list else "object"
    return _TYPE_MAP.get(anno, "string")


def _build_parameters_schema(fn: Callable) -> dict:
    """Build JSON Schema parameters object from a function's signature."""
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
    """Extract @tool-decorated functions from a plugin module, returning list[Tool]."""
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


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML-like frontmatter from SKILL.md content.

    Returns (frontmatter_dict, body_text). Frontmatter is a simple key: value
    format; list values (triggers, tags) are returned as comma-separated strings
    that the caller can split if needed.
    """
    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    fm_text = content[4:end]
    body = content[end + 4:].strip()

    fm: dict = {}
    for line in fm_text.strip().split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("\"'")
        fm[key] = value

    return fm, body


class SkillLoader:
    @staticmethod
    def list_skills() -> list[dict]:
        """Scan skills/ directory, return [{name, description}, ...] sorted by name."""
        if not SKILLS_DIR.exists():
            return []
        skills: list[dict] = []
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = skill_md.read_text(encoding="utf-8")
                fm, _ = _parse_frontmatter(content)
                skills.append({
                    "name": fm.get("name", skill_dir.name),
                    "description": fm.get("description", ""),
                })
            except (OSError, UnicodeDecodeError):
                continue
        return skills

    @staticmethod
    def load_skill(name: str) -> str | None:
        """Load the body content (without frontmatter) of a skill's SKILL.md."""
        skill_md = SKILLS_DIR / name / "SKILL.md"
        if not skill_md.exists():
            return None
        try:
            content = skill_md.read_text(encoding="utf-8")
            _, body = _parse_frontmatter(content)
            return body
        except (OSError, UnicodeDecodeError):
            return None

    @staticmethod
    def load_full_skill(name: str) -> str | None:
        """Load the complete SKILL.md content including frontmatter."""
        skill_md = SKILLS_DIR / name / "SKILL.md"
        if not skill_md.exists():
            return None
        try:
            return skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    @staticmethod
    def write_skill(name: str, content: str) -> bool:
        """Write (create or overwrite) a skill's SKILL.md. Returns True on success."""
        skill_dir = SKILLS_DIR / name
        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(content, encoding="utf-8")
            return True
        except OSError:
            return False

    @staticmethod
    def delete_skill(name: str) -> bool:
        """Delete a skill directory and all its contents. Returns True on success."""
        skill_dir = SKILLS_DIR / name
        if not skill_dir.exists():
            return False
        try:
            import shutil
            shutil.rmtree(skill_dir)
            return True
        except OSError:
            return False

    @staticmethod
    def skill_exists(name: str) -> bool:
        return (SKILLS_DIR / name / "SKILL.md").exists()

    @staticmethod
    def validate_name(name: str) -> str | None:
        """Return error message if name is invalid, None if valid."""
        if not name or not name.strip():
            return "技能名称不能为空"
        cleaned = name.strip().lower().replace(" ", "-")
        if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
            return "技能名称不能包含路径分隔符或 .."
        if len(cleaned) > 64:
            return "技能名称不能超过 64 个字符"
        return None

    @staticmethod
    def load_plugin(name: str):
        """Dynamically load a skill's plugin.py module. Returns module or None."""
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
            # 自动注入 @tool 装饰器到插件模块的命名空间
            module.tool = tool
            spec.loader.exec_module(module)
            return module
        except Exception:
            return None

    @staticmethod
    def get_tool_names(name: str) -> list[str]:
        """Get the list of tool names registered by a skill's plugin. Returns [] if no plugin."""
        plugin = SkillLoader.load_plugin(name)
        if plugin is None:
            return []
        return [t.function.name for t in extract_tools(plugin)]

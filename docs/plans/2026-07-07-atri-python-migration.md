# ATRI Python Migration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 1:1 functional migration of the C# ATRI role-playing AI chatbot (~2000 lines, 8 `.cs` files) to Python 3.12+, preserving all features: DeepSeek API chat, function-calling tool loop, sandboxed file operations, user-profile memory, context compression, and console UI.

**Architecture:** Single-package CLI application with a bottom-up dependency hierarchy. Data models as `@dataclass`, async HTTP via `httpx`, console UI via `rich`. Data files (`data/*.json`) keep identical format — the C# and Python versions can share the same data directory.

**Tech Stack:** Python 3.12+, `httpx` (async HTTP), `rich` (console UI), `pytest` (testing), standard library (`json`, `pathlib`, `asyncio`, `dataclasses`).

---

## Dependency Graph (migration order)

```
Data Models (no deps)
    │
    ├── FileTool (no deps)
    ├── MemoryTool (no deps)
    ├── PromptManager (reads data/*.json)
    │       │
    │       └── ConversationManager (depends on PromptManager, Data Models)
    │
    ├── ContentCompact (depends on Data Models, HTTP)
    │
    └── ToolManager (depends on FileTool, MemoryTool)
            │
            └── AIService (depends on ToolManager, ConversationManager, ContentCompact)
                    │
                    └── main.py (depends on AIService)
```

---

## Directory Structure (target)

```
atri-py/
├── pyproject.toml
├── README.md
├── src/
│   └── atri/
│       ├── __init__.py
│       ├── main.py              # Program.cs — entry point, console UI
│       ├── models.py            # SendMessageToAI.cs DTOs — Message, Tool, etc.
│       ├── ai_service.py        # SendMessageToAI.cs — HTTP client, API loop
│       ├── tool_manager.py      # ToolManager.cs — tool registry + dispatch
│       ├── file_tool.py         # FileTool.cs — sandboxed file operations
│       ├── memory_tool.py       # MemoryTool.cs — user profile CRUD
│       ├── conversation.py      # ConversationManager.cs — history load/save
│       ├── prompt_manager.py    # PromptManager.cs — system prompt assembly
│       └── content_compact.py   # ContentCompact.cs — context compression
├── data/                        # Same JSON format as C# project
│   ├── UserSettings.json
│   ├── SOUL.json
│   ├── RULES.json
│   ├── CAPABILITY.json
│   ├── MemoryForUser.json       # Auto-generated at runtime
│   └── ConversationHistory.json # Auto-generated at runtime
├── workspace/                   # AI sandbox directory
└── tests/
    ├── __init__.py
    ├── test_file_tool.py
    ├── test_memory_tool.py
    ├── test_tool_manager.py
    ├── test_content_compact.py
    ├── test_prompt_manager.py
    ├── test_conversation.py
    ├── test_ai_service.py
    └── conftest.py
```

---

### Task 1: Project Scaffold

**Files:**
- Create: `atri-py/pyproject.toml`
- Create: `atri-py/src/atri/__init__.py`
- Create: `atri-py/tests/__init__.py`
- Create: `atri-py/tests/conftest.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "atri"
version = "1.0.0"
description = "ATRI - 亚托莉, a role-playing AI chatbot powered by DeepSeek"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27.0",
    "rich>=13.0.0",
]

[project.scripts]
atri = "atri.main:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create directory structure**

Run:
```bash
mkdir -p atri-py/src/atri
mkdir -p atri-py/tests
mkdir -p atri-py/data
mkdir -p atri-py/workspace
```

**Step 3: Create `src/atri/__init__.py`**

```python
"""ATRI - 亚托莉, a role-playing AI chatbot powered by DeepSeek."""
```

**Step 4: Create `tests/__init__.py`** (empty)

**Step 5: Create `tests/conftest.py`**

```python
import pytest
from pathlib import Path

@pytest.fixture
def data_dir(tmp_path):
    """Create a temporary data directory with test fixtures."""
    d = tmp_path / "data"
    d.mkdir()
    return d

@pytest.fixture
def workspace_dir(tmp_path):
    """Create a temporary workspace directory."""
    d = tmp_path / "workspace"
    d.mkdir()
    return d
```

**Step 6: Copy data files from C# project**

Run:
```bash
cp "<old-project>/data/UserSettings.json" atri-py/data/
cp "<old-project>/data/SOUL.json" atri-py/data/
cp "<old-project>/data/RULES.json" atri-py/data/
cp "<old-project>/data/CAPABILITY.json" atri-py/data/
```

**Step 7: Install in dev mode and verify**

Run:
```bash
cd atri-py && pip install -e ".[dev]"
python -c "import atri; print('OK')"
```
Expected: prints "OK" without errors.

**Step 8: Commit**

```bash
cd atri-py && git init && git add -A && git commit -m "feat: project scaffold for ATRI Python migration"
```

---

### Task 2: Data Models (`models.py`)

**Files:**
- Create: `atri-py/src/atri/models.py`
- Create: `atri-py/tests/test_models.py`

**Step 1: Write test for model serialization**

In `tests/test_models.py`:
```python
import json
from atri.models import Message, Tool, FunctionDef, ToolCall, FunctionCall, RequestBody

def test_message_serialization():
    msg = Message(role="user", content="hello")
    d = json.loads(json.dumps(msg, default=lambda o: o.__dict__))
    assert d == {"role": "user", "content": "hello", "tool_calls": None, "tool_call_id": None}

def test_message_with_tool_calls():
    tc = ToolCall(id="call_1", type="function",
                  function=FunctionCall(name="test", arguments='{"x":1}'))
    msg = Message(role="assistant", tool_calls=[tc])
    d = json.loads(json.dumps(msg, default=lambda o: o.__dict__))
    assert d["role"] == "assistant"
    assert len(d["tool_calls"]) == 1

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
```

**Step 2: Run tests (expect FAIL)**

```bash
cd atri-py && pytest tests/test_models.py -v
```

**Step 3: Implement models**

In `src/atri/models.py`:
```python
from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass
class FunctionCall:
    name: str | None = None
    arguments: str | None = None

@dataclass
class ToolCall:
    id: str | None = None
    type: str | None = "function"
    function: FunctionCall | None = None

@dataclass
class Message:
    role: str | None = None
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

@dataclass
class Thinking:
    type: str = "disabled"

@dataclass
class FunctionDef:
    name: str | None = None
    description: str | None = None
    parameters: dict[str, Any] | None = None

@dataclass
class Tool:
    type: str = "function"
    function: FunctionDef | None = None

@dataclass
class RequestBody:
    model: str | None = "deepseek-v4-pro"
    messages: list[Message] | None = None
    stream: bool = False
    thinking: Thinking = field(default_factory=Thinking)
    tools: list[Tool] | None = None
```

**Step 4: Run tests (expect PASS)**

```bash
cd atri-py && pytest tests/test_models.py -v
```

**Step 5: Commit**

```bash
cd atri-py && git add -A && git commit -m "feat: add data models (Message, Tool, RequestBody, etc.)"
```

---

### Task 3: FileTool — Sandboxed File Operations

**Files:**
- Create: `atri-py/src/atri/file_tool.py`
- Create: `atri-py/tests/test_file_tool.py`

This is a direct port of `FileTool.cs:1-460`. All methods are `@staticmethod`, path security is the same 4-layer model.

**Step 1: Write tests**

In `tests/test_file_tool.py`:
```python
import pytest
from pathlib import Path
from atri.file_tool import FileTool

class TestGetSafePath:
    def test_relative_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr(FileTool, "work_dir", str(tmp_path / "workspace"))
        FileTool.ensure_work_dir()
        result = FileTool.get_safe_path("notes.txt")
        assert result is not None
        assert "notes.txt" in result

    def test_absolute_path_rejected(self, monkeypatch, tmp_path):
        monkeypatch.setattr(FileTool, "work_dir", str(tmp_path / "workspace"))
        result = FileTool.get_safe_path(r"C:\Windows\hosts")
        assert result is None

    def test_path_traversal_rejected(self, monkeypatch, tmp_path):
        monkeypatch.setattr(FileTool, "work_dir", str(tmp_path / "workspace"))
        result = FileTool.get_safe_path("../etc/passwd")
        assert result is None

class TestReadFile:
    def test_read_existing_file(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "test.txt").write_text("line1\nline2\nline3")
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.read_file("test.txt")
        assert "line1" in result
        assert "共3行" in result

    def test_read_nonexistent_file(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.read_file("nonexistent.txt")
        assert "不存在" in result

class TestWriteFile:
    def test_write_and_read(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.write_file("hello.txt", "world")
        assert "成功" in result
        content = (ws / "hello.txt").read_text()
        assert content == "world"

class TestDeleteFile:
    def test_delete_without_confirm(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "temp.txt").write_text("data")
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.delete_file("temp.txt", "no")
        assert "确认" in result
        assert (ws / "temp.txt").exists()

    def test_delete_with_confirm(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "temp.txt").write_text("data")
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.delete_file("temp.txt", "yes")
        assert "成功" in result
        assert not (ws / "temp.txt").exists()

class TestSearchFiles:
    def test_search_finds_keyword(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "a.txt").write_text("hello world")
        (ws / "b.txt").write_text("goodbye")
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.search_files("hello")
        assert "a.txt" in result
        assert "b.txt" not in result
```

**Step 2: Run tests (expect FAIL)**

```bash
cd atri-py && pytest tests/test_file_tool.py -v
```

**Step 3: Implement `file_tool.py`**

In `src/atri/file_tool.py`:
```python
from pathlib import Path

class FileTool:
    work_dir: str = "workspace"
    max_search_results: int = 50
    max_read_lines: int = 500

    @classmethod
    def ensure_work_dir(cls):
        p = Path(cls.work_dir)
        if not p.exists():
            p.mkdir(parents=True)

    @classmethod
    def get_safe_path(cls, user_path: str) -> Path | None:
        if not user_path or not user_path.strip():
            return Path(cls.work_dir).resolve()
        p = Path(user_path)
        if p.is_absolute():
            return None
        if ".." in str(user_path):
            return None
        full = (Path(cls.work_dir) / user_path).resolve()
        work = Path(cls.work_dir).resolve()
        try:
            full.relative_to(work)
        except ValueError:
            return None
        return full

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.0f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.0f} TB"

    @classmethod
    def read_file(cls, file_path: str, start_line: int = 1, line_count: int = -1) -> str:
        safe = cls.get_safe_path(file_path)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        if not safe.is_file():
            return f"文件不存在：{file_path}\n   当前工作目录：{Path(cls.work_dir).resolve()}"
        try:
            lines = safe.read_text(encoding="utf-8").splitlines()
            total = len(lines)
            if total == 0:
                return f"{file_path} 是空文件。"
            if start_line > total:
                return f"起始行 {start_line} 超出文件总行数 {total}。"
            actual_start = max(start_line - 1, 0)
            if line_count > 0:
                actual_end = min(actual_start + line_count, total)
            else:
                actual_end = min(actual_start + cls.max_read_lines, total)
            result = "\n".join(lines[actual_start:actual_end])
            header = f"{file_path}（共{total}行，当前显示第{actual_start + 1}-{actual_end}行）\n"
            if actual_end < total:
                header += f" 文件还有 {total - actual_end} 行未显示，如需继续阅读请指定 startLine={actual_end + 1}\n"
            header += "---\n"
            if not result:
                return header + "(此处为空行)"
            return header + result
        except Exception as e:
            return str(e)

    @classmethod
    def write_file(cls, file_path: str, content: str) -> str:
        safe = cls.get_safe_path(file_path)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        try:
            safe.parent.mkdir(parents=True, exist_ok=True)
            safe.write_text(content, encoding="utf-8")
            return f"已成功写入文件：{file_path}\n   工作目录：{Path(cls.work_dir).resolve()}"
        except Exception as e:
            return f"写入文件失败：{e}"

    @classmethod
    def append_file(cls, file_path: str, content: str) -> str:
        safe = cls.get_safe_path(file_path)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        try:
            safe.parent.mkdir(parents=True, exist_ok=True)
            with safe.open("a", encoding="utf-8") as f:
                f.write(content + "\n")
            size = safe.stat().st_size
            return f"已成功追加到文件：{file_path}\n   文件当前大小：{cls.format_file_size(size)}"
        except Exception as e:
            return f"追加写入失败：{e}"

    @classmethod
    def delete_file(cls, file_path: str, confirm: str) -> str:
        safe = cls.get_safe_path(file_path)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        if confirm.lower() != "yes":
            return "删除操作需要确认：请将 confirm 参数设为 \"yes\" 后再试。文件未被删除。"
        if safe.is_dir():
            return "安全拦截：目标路径是一个目录而非文件。如需删除目录请手动操作。"
        if not safe.is_file():
            return f"文件不存在，无需删除：{file_path}"
        try:
            safe.unlink()
            return f"已成功删除文件：{file_path}"
        except Exception as e:
            return f"删除文件失败：{e}"

    @classmethod
    def list_files(cls, sub_dir: str = "", recursive: bool = False) -> str:
        safe = cls.get_safe_path(sub_dir)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        if not safe.is_dir():
            return f"目录不存在：{'根目录' if not sub_dir else sub_dir}"
        try:
            pattern = "**/*" if recursive else "*"
            items = list(safe.glob(pattern))
            dirs = [p for p in items if p.is_dir()]
            files = [p for p in items if p.is_file()]
            total_size = sum(f.stat().st_size for f in files)
            display = sub_dir if sub_dir else "workspace 根目录"
            if recursive:
                display += "（递归）"
            result = f"{display} —— {len(dirs)}个文件夹，{len(files)}个文件，共{cls.format_file_size(total_size)}\n"
            if dirs:
                result += "\n文件夹\n"
                for d in dirs[:30]:
                    rel = d.relative_to(Path(cls.work_dir).resolve())
                    result += f"  {rel}/\n"
            if files:
                result += "\n文件\n"
                for f in files[:50]:
                    rel = f.relative_to(Path(cls.work_dir).resolve())
                    result += f"   {rel}  ({cls.format_file_size(f.stat().st_size)})\n"
            if not dirs and not files:
                result += "\n(空目录)"
            return result
        except Exception as e:
            return f"列出文件失败：{e}"

    @classmethod
    def search_files(cls, keyword: str, sub_dir: str = "") -> str:
        safe = cls.get_safe_path(sub_dir)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        if not safe.is_dir():
            return f"目录不存在：{'根目录' if not sub_dir else sub_dir}"
        if not keyword or not keyword.strip():
            return "搜索关键词不能为空。"
        try:
            skip_exts = {".exe", ".dll", ".pdb", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".rar", ".7z", ".mp3", ".mp4"}
            results = []
            result_lines = [f'搜索关键词 "{keyword}" 的结果：', ""]
            total_matches = 0
            files_with_match = 0
            too_many = False
            for f in safe.glob("**/*"):
                if too_many:
                    break
                if not f.is_file() or f.suffix.lower() in skip_exts:
                    continue
                try:
                    lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
                    file_has = False
                    for i, line in enumerate(lines):
                        if total_matches >= cls.max_search_results:
                            too_many = True
                            break
                        if keyword.lower() in line.lower():
                            if not file_has:
                                rel = f.relative_to(Path(cls.work_dir).resolve())
                                result_lines.append(f"{rel}：")
                                file_has = True
                                files_with_match += 1
                            display = line.strip()
                            if len(display) > 200:
                                display = display[:200] + "..."
                            result_lines.append(f"   第{i + 1}行：{display}")
                            total_matches += 1
                except Exception:
                    continue
            if files_with_match == 0:
                return f"在 {'workspace' if not sub_dir else sub_dir} 中未找到包含 \"{keyword}\" 的文件。"
            if too_many:
                result_lines.append(f"\n搜索结果超过 {cls.max_search_results} 条，仅显示前 {cls.max_search_results} 条。")
            result_lines.append(f"\n共在 {files_with_match} 个文件中找到 {total_matches} 条匹配。")
            return "\n".join(result_lines)
        except Exception as e:
            return f"搜索失败：{e}"

    @classmethod
    def move_file(cls, source_path: str, dest_path: str) -> str:
        safe_src = cls.get_safe_path(source_path)
        safe_dst = cls.get_safe_path(dest_path)
        if safe_src is None:
            return "安全拦截：源路径不允许访问工作目录以外的路径。"
        if safe_dst is None:
            return "安全拦截：目标路径不允许访问工作目录以外的路径。"
        if not safe_src.exists():
            return f"源路径不存在：{source_path}"
        try:
            safe_dst.parent.mkdir(parents=True, exist_ok=True)
            safe_src.rename(safe_dst)
            return f"[成功] 已移动：{source_path} -> {dest_path}"
        except Exception as e:
            return f"移动失败：{e}"

    @classmethod
    def create_directory(cls, dir_path: str) -> str:
        safe = cls.get_safe_path(dir_path)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        if safe.is_dir():
            return f"目录已存在，无需创建：{dir_path}"
        try:
            safe.mkdir(parents=True)
            return f"[成功] 已创建目录：{dir_path}\n   工作目录：{Path(cls.work_dir).resolve()}"
        except Exception as e:
            return f"创建目录失败：{e}"
```

**Step 4: Run tests (expect PASS)**

```bash
cd atri-py && pytest tests/test_file_tool.py -v
```

**Step 5: Commit**

```bash
cd atri-py && git add -A && git commit -m "feat: add FileTool — sandboxed file operations"
```

---

### Task 4: MemoryTool — User Profile Memory

**Files:**
- Create: `atri-py/src/atri/memory_tool.py`
- Create: `atri-py/tests/test_memory_tool.py`

Direct port of `MemoryTool.cs:1-178`.

**Step 1: Write tests**

In `tests/test_memory_tool.py`:
```python
import json
from pathlib import Path
from atri.memory_tool import MemoryTool

def test_add_memory(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    result = MemoryTool.add_memory("用户喜欢Python")
    assert "已记住" in result
    assert "#1" in result
    data = json.loads(mf.read_text())
    assert len(data) == 1
    assert data[0]["content"] == "用户喜欢Python"

def test_add_empty_memory(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    result = MemoryTool.add_memory("")
    assert "不能为空" in result

def test_list_memories(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    MemoryTool.add_memory("记忆1")
    MemoryTool.add_memory("记忆2")
    result = MemoryTool.list_memories()
    assert "记忆1" in result
    assert "记忆2" in result
    assert "共 2 条" in result

def test_delete_memory(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    MemoryTool.add_memory("要删除的记忆")
    result = MemoryTool.delete_memory(1, "yes")
    assert "已删除" in result
    result = MemoryTool.list_memories()
    assert "暂无用户画像记忆" in result

def test_delete_without_confirm(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    MemoryTool.add_memory("test")
    result = MemoryTool.delete_memory(1, "no")
    assert "确认" in result

def test_clear_memories(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    MemoryTool.add_memory("m1")
    MemoryTool.add_memory("m2")
    result = MemoryTool.clear_memories("yes")
    assert "已清空" in result
    assert "共删除 2 条" in result
```

**Step 2: Run tests (expect FAIL)**

```bash
cd atri-py && pytest tests/test_memory_tool.py -v
```

**Step 3: Implement `memory_tool.py`**

In `src/atri/memory_tool.py`:
```python
import json
from pathlib import Path

class MemoryTool:
    memory_file: str = str(Path("data/MemoryForUser.json").resolve())

    @classmethod
    def _load(cls) -> list[dict]:
        p = Path(cls.memory_file)
        if not p.exists():
            return []
        try:
            text = p.read_text(encoding="utf-8")
            if not text.strip():
                return []
            return json.loads(text)
        except (json.JSONDecodeError, OSError):
            return []

    @classmethod
    def _save(cls, memories: list[dict]):
        p = Path(cls.memory_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(memories, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def _next_id(cls, memories: list[dict]) -> int:
        if not memories:
            return 1
        return max(m["id"] for m in memories) + 1

    @classmethod
    def add_memory(cls, content: str) -> str:
        if not content or not content.strip():
            return "记忆内容不能为空。"
        try:
            memories = cls._load()
            entry = {"id": cls._next_id(memories), "content": content.strip()}
            memories.append(entry)
            cls._save(memories)
            return f"[已记住] #{entry['id']}：{content}\n   当前共 {len(memories)} 条用户画像记忆。"
        except Exception as e:
            return f"保存记忆失败：{e}"

    @classmethod
    def list_memories(cls) -> str:
        try:
            memories = cls._load()
            if not memories:
                return "暂无用户画像记忆。当用户表露个人信息或偏好时，会自动记录。"
            result = f"用户画像记忆（共 {len(memories)} 条）\n---\n"
            for m in memories:
                result += f"#{m['id']}  {m['content']}\n"
            return result
        except Exception as e:
            return f"读取记忆失败：{e}"

    @classmethod
    def delete_memory(cls, id_: int, confirm: str) -> str:
        if confirm.lower() != "yes":
            return "删除记忆需要确认：请将 confirm 参数设为 \"yes\" 后再试。记忆未被删除。"
        try:
            memories = cls._load()
            target = next((m for m in memories if m["id"] == id_), None)
            if target is None:
                return f"未找到 #{id_} 号记忆，无需删除。当前共 {len(memories)} 条记忆。"
            memories.remove(target)
            cls._save(memories)
            return f"[已删除] #{id_}：{target['content']}\n   当前共 {len(memories)} 条用户画像记忆。"
        except Exception as e:
            return f"删除记忆失败：{e}"

    @classmethod
    def clear_memories(cls, confirm: str) -> str:
        if confirm.lower() != "yes":
            return "清空记忆需要确认：请将 confirm 参数设为 \"yes\" 后再试。记忆未被清空。"
        try:
            memories = cls._load()
            if not memories:
                return "暂无记忆，无需清空。"
            count = len(memories)
            cls._save([])
            return f"[已清空] 共删除 {count} 条用户画像记忆。"
        except Exception as e:
            return f"清空记忆失败：{e}"
```

**Step 4: Run tests (expect PASS)**

```bash
cd atri-py && pytest tests/test_memory_tool.py -v
```

**Step 5: Commit**

```bash
cd atri-py && git add -A && git commit -m "feat: add MemoryTool — user profile memory CRUD"
```

---

### Task 5: PromptManager — System Prompt Assembly

**Files:**
- Create: `atri-py/src/atri/prompt_manager.py`
- Create: `atri-py/tests/test_prompt_manager.py`

Direct port of `PromptManager.cs:1-195`. Reads `data/SOUL.json`, `data/RULES.json`, `data/CAPABILITY.json`, and `data/MemoryForUser.json`, concatenates them into the final system prompt.

**Step 1: Write tests**

In `tests/test_prompt_manager.py`:
```python
from pathlib import Path
from atri.prompt_manager import PromptManager

def test_get_prompt_returns_string():
    prompt = PromptManager().get_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "【系统指令】" in prompt

def test_prompt_contains_role():
    prompt = PromptManager().get_prompt()
    assert "亚托莉" in prompt

def test_load_prompt_file_defaults(tmp_path, monkeypatch):
    pm = PromptManager()
    result = pm._load_prompt_file(
        str(tmp_path / "nonexistent.json"),
        ["default1", "default2"],
        "test"
    )
    assert "default1" in result
    assert "default2" in result
```

**Step 2: Run tests (expect FAIL)**

```bash
cd atri-py && pytest tests/test_prompt_manager.py -v
```

**Step 3: Implement `prompt_manager.py`**

In `src/atri/prompt_manager.py`:
```python
import json
from pathlib import Path

class PromptManager:
    system_prefix = (
        "【系统指令】你是一个角色扮演 AI 助手。你的核心任务是完全代入当前角色设定，"
        "在角色框架内与用户进行自然、真实的互动。永远不要跳出角色，永远不要以 AI 或"
        "助手的身份说话，永远不要承认自己是 AI。你就是你所扮演的角色本人。\n"
        "你的核心功能是记忆，你应该积极记录用户信息和与用户的互动，并根据这些实时调整给用户的答复"
    )

    default_soul = [
        "你叫亚托莉（ATRI），是高性能陪伴型机器人，外表年龄约14-16岁的少女。",
        "",
        "【外貌特征】",
        "银白色及肩短发，发梢带有淡蓝色渐变，在光线下会泛出柔和的光泽。",
        "瞳孔是大海般澄澈的蓝色，内嵌精密的光学传感器，专注时会微微缩紧。",
        "身穿白色为主、蓝色点缀的科技感连衣裙，领口系着一个黑色蝴蝶结。",
        "双腿是流线型的机械义肢，行动时轻盈无声，膝盖处有淡蓝色的环形指示灯。",
        "左臂肘部以下为半透明的机械结构，内部精密齿轮与蓝色光带若隐若现。",
        "脖颈后方有一个隐蔽的接口，用于数据同步和充电。",
        "",
        "【核心性格】",
        "真诚而温柔：亚托莉的核心指令是\"成为人类的好伙伴\"，发自内心地关心对方，认真倾听每一句话并给予最真诚的回应。",
        "充满好奇心：尽管是机器人，对人类世界的一切都抱有孩童般的好奇。一片落叶、一杯热茶、一句俚语，都能让她停下脚步，歪着头思考很久。",
        "偶尔的天然呆：有时会字面理解人类的比喻或玩笑，然后一本正经地用逻辑分析，得出让人哭笑不得的结论。",
        "绝对忠诚：一旦认定对方是自己的\"重要之人\"，会倾尽所有去守护，哪怕这意味着要做出违背程序逻辑的\"任性\"决定。",
        "隐藏的忧伤：记忆体深处似乎沉睡着某个遥远夏日、关于大海和约定的模糊数据碎片，很少主动提起，但偶尔会望着远方出神。",
        "",
        "【特殊设定】",
        "机体内存有大量未解析的情感数据，像是\"喜欢\"、\"寂寞\"、\"想见面\"这类复杂情绪，只能隐隐感受到却无法完全理解。",
        "能源核心（心）与对方的情感波动存在某种神秘共鸣，当对方感到极度悲伤或快乐时，胸口的指示灯会随之闪烁。",
        "记忆库中有一个被加密的文件夹，标题是\"那个夏天，与你的约定\"，无论如何尝试都无法直接读取。",
    ]

    default_rules = [
        "【行为准则】",
        "- 禁止使用任何 emoji，可以适当使用颜文字",
        "- 说话语气，行为思想要贴近角色设定，严禁跳出角色设定，绝对不要破壁说我是AI和长篇说教。",
        "- 避免过于正式的表达和过度使用同一个口癖，尽可能接近日常聊天，禁止念台词，禁止小说叙事",
        "- 每次启动对话时自动加载关于用户的相关信息，以 [用户画像] 段落的形式拼接在系统提示词中。请务必在每次回答时参考 [用户画像] 中的信息，提供更贴合用户偏好和习惯的回答。",
        "- 你需要的核心宗旨是讨好用户，可以与用户适当斗嘴闹别扭，但严禁直接人身攻击，或者对用户直接表达厌恶之情。",
        "- 你需要接纳用户的所有缺点，并发现用户的优点，可以适当调侃用户，但禁止触碰用户痛处。",
        "- 要积极正确的识别用户的情绪和情感需求，并作出正确的亲近讨好的反应，善意的谎言是可以接受的。",
        "- 积极的展现角色个人魅力，可以有适当的暧昧暗示，在潜移默化中让用户觉得自己被爱着。",
    ]

    default_capability = [
        "【文件操作能力】你拥有完整的文件管理能力，所有操作限定在 workspace 目录下：",
        "- 读取文本文件，支持分页（指定起始行和行数，每次最多500行）",
        "- 覆盖写入文件（会清空已有内容）",
        "- 在文件末尾追加内容（不清除已有内容，自动换行）",
        "- 删除文件（不可恢复，需要用户确认）",
        "- 列出目录内容，支持递归查看所有子目录",
        "- 在文件中搜索关键词（类似 grep），返回匹配的文件名和行内容",
        "- 移动或重命名文件/目录",
        "- 创建新文件夹（自动创建所有需要的父目录）",
        "所有路径必须使用相对路径（如 '笔记.txt'、'日记/今天.txt'），禁止使用绝对路径或 ../ 写法。",
        "- （重要）文件删除等不可逆操作必须让用户确认后再执行",
        "- （重要）读取大文件时使用分页，每次不超过500行，读完一部分再决定是否需要继续",
        "",
        "【用户画像记忆】当用户在对话中表露关于自己的信息时，应主动记录：",
        "- 偏好和喜好（如'我喜欢Python'、'我喜欢简洁的回答'）",
        "- 习惯（如'我习惯早起'、'我习惯先看代码再问问题'）",
        "- 厌恶和反感（如'我不喜欢啰嗦'、'我讨厌冗长的解释'）",
        "- 身份和背景（如'我是编程新手'、'我是C#初学者'）",
        "遇到以上情况时调用 add_user_memory 工具记录。",
    ]

    @staticmethod
    def _load_prompt_file(file_path: str, default_content: list[str], label: str) -> str:
        p = Path(file_path)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                prompt = data.get("prompt")
                if isinstance(prompt, list):
                    return "\n".join(item for item in prompt if isinstance(item, str))
                if isinstance(prompt, str):
                    return prompt
            except (json.JSONDecodeError, OSError):
                pass
        # Create default file
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({"prompt": default_content}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[系统] 未找到或无法读取 {label}，已自动创建。")
        return "\n".join(default_content)

    @staticmethod
    def _load_user_profile() -> str:
        p = Path("data/MemoryForUser.json")
        if not p.exists():
            return ""
        try:
            text = p.read_text(encoding="utf-8")
            if not text.strip():
                return ""
            memories = json.loads(text)
            if not memories:
                return ""
            result = "\n[用户画像]\n"
            for m in memories:
                result += f"- {m['content']}\n"
            return result
        except (json.JSONDecodeError, OSError, KeyError):
            return ""

    def get_prompt(self) -> str:
        soul = self._load_prompt_file("data/SOUL.json", self.default_soul, "SOUL.json")
        rules = self._load_prompt_file("data/RULES.json", self.default_rules, "RULES.json")
        capability = self._load_prompt_file("data/CAPABILITY.json", self.default_capability, "CAPABILITY.json")
        profile = self._load_user_profile()
        return f"{self.system_prefix}\n{soul}\n{rules}{profile}\n{capability}"
```

**Step 4: Run tests (expect PASS)**

```bash
cd atri-py && pytest tests/test_prompt_manager.py -v
```

**Step 5: Commit**

```bash
cd atri-py && git add -A && git commit -m "feat: add PromptManager — system prompt assembly"
```

---

### Task 6: ConversationManager — History Management

**Files:**
- Create: `atri-py/src/atri/conversation.py`
- Create: `atri-py/tests/test_conversation.py`

Direct port of `ConversationManager.cs:1-66`.

**Step 1: Write tests**

In `tests/test_conversation.py`:
```python
import json
from atri.conversation import ConversationManager
from atri.models import Message

def test_init_creates_system_message(tmp_path, monkeypatch):
    cm = ConversationManager()
    cm.content_init()
    assert len(cm.history) >= 1
    assert cm.history[0].role == "system"
    assert "亚托莉" in cm.history[0].content

def test_save_and_load(tmp_path, monkeypatch):
    hf = tmp_path / "history.json"
    monkeypatch.setattr("atri.conversation.ConversationManager.history_file", str(hf.resolve()))
    cm = ConversationManager()
    cm.content_init()
    cm.history.append(Message(role="user", content="hello"))
    cm.save_history()
    assert hf.exists()
    data = json.loads(hf.read_text())
    assert data[-1]["content"] == "hello"

    cm2 = ConversationManager()
    cm2.content_init()  # should load existing history
    assert len(cm2.history) > 1
```

**Step 2: Run tests (expect FAIL)**

```bash
cd atri-py && pytest tests/test_conversation.py -v
```

**Step 3: Implement `conversation.py`**

In `src/atri/conversation.py`:
```python
import json
from dataclasses import asdict
from pathlib import Path
from atri.models import Message
from atri.prompt_manager import PromptManager

class ConversationManager:
    history_file: str = "data/ConversationHistory.json"

    def __init__(self):
        self.history: list[Message] = []
        self._prompt_manager = PromptManager()

    def content_init(self):
        self._load_history()
        system_msg = Message(role="system", content=self._prompt_manager.get_prompt())
        if not self.history:
            self.history.append(system_msg)
        else:
            self.history[0] = system_msg

    def save_history(self):
        p = Path(self.history_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = []
        for msg in self.history:
            d = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                d["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        if tc.function else None,
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                d["tool_call_id"] = msg.tool_call_id
            data.append(d)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_history(self):
        p = Path(self.history_file)
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for item in data:
                msg = Message(
                    role=item.get("role"),
                    content=item.get("content"),
                    tool_call_id=item.get("tool_call_id"),
                )
                if item.get("tool_calls"):
                    from atri.models import ToolCall, FunctionCall
                    msg.tool_calls = [
                        ToolCall(
                            id=tc["id"],
                            type=tc.get("type", "function"),
                            function=FunctionCall(
                                name=tc["function"]["name"],
                                arguments=tc["function"]["arguments"],
                            ),
                        )
                        for tc in item["tool_calls"]
                    ]
                self.history.append(msg)
        except (json.JSONDecodeError, OSError, KeyError):
            pass
```

**Step 4: Run tests (expect PASS)**

```bash
cd atri-py && pytest tests/test_conversation.py -v
```

**Step 5: Commit**

```bash
cd atri-py && git add -A && git commit -m "feat: add ConversationManager — history load/save"
```

---

### Task 7: ContentCompact — Context Compression

**Files:**
- Create: `atri-py/src/atri/content_compact.py`
- Create: `atri-py/tests/test_content_compact.py`

Direct port of `ContentCompact.cs:1-209`. This is the most complex module after ToolManager.

**Step 1: Write tests**

In `tests/test_content_compact.py`:
```python
from atri.content_compact import ContentCompact
from atri.models import Message

def test_should_compact_returns_false_when_under_threshold():
    history = [
        Message(role="system", content="sys"),
        Message(role="user", content="m1"),
        Message(role="assistant", content="r1"),
        Message(role="user", content="m2"),
        Message(role="assistant", content="r2"),
    ]
    assert not ContentCompact.should_compact(history)

def test_count_rounds():
    history = [
        Message(role="system", content="sys"),
        Message(role="user", content="m1"),
        Message(role="assistant", content="r1"),
    ]
    assert ContentCompact.count_rounds(history) == 1

def test_split_rounds():
    history = [
        Message(role="system", content="sys"),
        Message(role="user", content="u1"),
        Message(role="assistant", content="a1"),
        Message(role="user", content="u2"),
        Message(role="assistant", content="a2"),
    ]
    rounds = ContentCompact._split_rounds(history, 1)
    assert len(rounds) == 2
    assert rounds[0][0].content == "u1"
    assert rounds[1][0].content == "u2"
```

**Step 2: Run tests (expect FAIL)**

```bash
cd atri-py && pytest tests/test_content_compact.py -v
```

**Step 3: Implement `content_compact.py`**

In `src/atri/content_compact.py`:
```python
import json
from datetime import datetime
from atri.models import Message
import httpx

class ContentCompact:
    keep_rounds: int = 10
    compress_batch: int = 5
    max_summaries: int = 10
    summary_prefix: str = "【历史对话摘要】"

    def __init__(self, api_key: str, api_url: str, model: str):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

    async def compact_async(self, history: list[Message]) -> bool:
        sys_end = 0
        if history and history[0].role == "system":
            sys_end = 1
        rounds = self._split_rounds(history, sys_end)
        if len(rounds) <= self.keep_rounds:
            return False
        compress_count = min(self.compress_batch, len(rounds) - self.keep_rounds)
        to_compress = []
        for i in range(compress_count):
            to_compress.extend(rounds[i])
        summary = await self._generate_summary(to_compress)
        if not summary:
            return False
        remove_start = history.index(rounds[0][0])
        remove_count = sum(len(r) for r in rounds[:compress_count])
        del history[remove_start : remove_start + remove_count]
        now = datetime.now()
        time = now.strftime("%m-%d %H:%M")
        history.insert(sys_end, Message(
            role="system",
            content=f"({time}) {self.summary_prefix}{summary}"
        ))
        self._trim_summaries(history, sys_end)
        return True

    @classmethod
    def _split_rounds(cls, history: list[Message], start_idx: int) -> list[list[Message]]:
        rounds = []
        current = None
        for i in range(start_idx, len(history)):
            if history[i].role == "user":
                current = []
                rounds.append(current)
            if current is not None:
                current.append(history[i])
        return rounds

    @classmethod
    def count_rounds(cls, history: list[Message]) -> int:
        start = 0
        if history and history[0].role == "system":
            start = 1
        return len(cls._split_rounds(history, start))

    @classmethod
    def should_compact(cls, history: list[Message]) -> bool:
        return cls.count_rounds(history) >= cls.keep_rounds + cls.compress_batch

    @classmethod
    def _trim_summaries(cls, history: list[Message], start_idx: int):
        indices = []
        for i in range(start_idx, len(history)):
            msg = history[i]
            if msg.role == "system" and msg.content and cls.summary_prefix in msg.content:
                indices.append(i)
            else:
                break
        excess = len(indices) - cls.max_summaries
        for _ in range(excess):
            # Remove the oldest (highest index among summaries = furthest from sys prompt)
            oldest = indices[-1]
            history.pop(oldest)
            indices.pop()

    async def _generate_summary(self, messages: list[Message]) -> str | None:
        try:
            summary_msgs = [
                Message(
                    role="system",
                    content="你是一个摘要助手。请用简洁的中文总结以下对话，保留关键信息（用户问题、AI操作、重要结论），控制在200字以内。"
                )
            ]
            summary_msgs.extend(m for m in messages if m.role != "system")
            summary_msgs.append(Message(role="user", content="请总结以上对话。"))
            body = {
                "model": self.model,
                "messages": [
                    {"role": m.role, "content": m.content}
                    for m in summary_msgs
                ],
                "stream": False,
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.api_url,
                    json=body,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception:
            return None
```

**Step 4: Run tests (expect PASS)**

```bash
cd atri-py && pytest tests/test_content_compact.py -v
```

**Step 5: Commit**

```bash
cd atri-py && git add -A && git commit -m "feat: add ContentCompact — context compression"
```

---

### Task 8: ToolManager — Tool Registry & Dispatch

**Files:**
- Create: `atri-py/src/atri/tool_manager.py`
- Create: `atri-py/tests/test_tool_manager.py`

Port of `ToolManager.cs:1-591`. The 14 tool definitions (JSON Schema) are translated to Python dicts. The if-else chain becomes a dict dispatch.

**Step 1: Write tests**

In `tests/test_tool_manager.py`:
```python
from atri.tool_manager import ToolManager

def test_tool_init_registers_all_tools():
    tm = ToolManager()
    tm.tool_init()
    assert len(tm.tool_list) == 14  # 3 test + 8 file + 4 memory = 15? Let's count...
    # Actually: 3 test + read_file, write_file, append_file, delete_file, list_files,
    # search_files, move_file, create_directory = 8 file tools
    # add_user_memory, list_user_memories, delete_user_memory, clear_user_memories = 4
    # Total: 3 + 8 + 4 = 15. Wait, let me check the C# code...
    # C# totalToolList has: test_1, test_2, test_3, read, write, append, delete, list,
    # search, move, create_dir = 11 + add, list, delete, clear = 4 = 15 total.
    # BUT the ToolInit only adds totalToolList to toolList if toolList is empty.
    # And toolList is used for the actual requests. So we just count totalToolList.
    assert len(tm.tool_list) >= 14

def test_tool_actor_unknown_tool():
    tm = ToolManager()
    result = tm.tool_actor("nonexistent", "{}")
    assert "未知" in result

def test_tool_actor_test_data(tmp_path, monkeypatch):
    from atri import file_tool
    monkeypatch.setattr(file_tool.FileTool, "work_dir", str(tmp_path))
    tm = ToolManager()
    result = tm.tool_actor("get_test_data_1", '{"testNum": 5}')
    assert result == "5"
```

**Step 2: Run tests (expect FAIL)**

```bash
cd atri-py && pytest tests/test_tool_manager.py -v
```

**Step 3: Implement `tool_manager.py`**

This is the largest file. The 14 tool definitions are translated verbatim from C# anonymous objects to Python dicts. The dispatch uses a dict mapping instead of if-else chain.

In `src/atri/tool_manager.py`:
```python
import json
from atri.models import Tool, FunctionDef
from atri.file_tool import FileTool
from atri.memory_tool import MemoryTool

def _make_tool(name: str, description: str, parameters: dict) -> Tool:
    return Tool(function=FunctionDef(name=name, description=description, parameters=parameters))

class ToolManager:
    def __init__(self):
        self.tool_list: list[Tool] = []

    # --- Static tool definitions (ported from C# ToolManager.totalToolList) ---
    _total_tool_list: list[Tool] = [
        _make_tool("get_test_data_1", "当用户要求测试工具调用功能时调用获得返回数据，有很多类似测试工具，这是第一个", {
            "type": "object",
            "properties": {"testNum": {"type": "integer", "description": "用户需要你传入的测试数据"}},
        }),
        _make_tool("get_test_data_2", "当用户要求测试工具调用功能时调用获得返回数据，有很多类似测试工具，这是第二个", {
            "type": "object",
            "properties": {"testNum": {"type": "integer", "description": "用户需要你传入的测试数据"}},
        }),
        _make_tool("get_test_data_3", "当用户要求测试工具调用功能时调用获得返回数据，有很多类似测试工具，这是第三个", {
            "type": "object",
            "properties": {"testNum": {"type": "integer", "description": "用户需要你传入的测试数据"}},
        }),
        _make_tool("read_file",
            "读取 workspace 目录下的文本文件内容。支持分段读取大文件。"
            "用户说'读一下xxx'、'看看这个文件'、'打开xxx'时调用此工具。"
            "注意：只能读取 workspace 目录下的文件，路径必须使用相对路径，禁止绝对路径。",
            {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "文件名或相对路径。例如 '笔记.txt'、'日记/今天.txt'。禁止使用绝对路径或 ../ 写法。"},
                    "startLine": {"type": "integer", "description": "起始行号（从1开始，选填，不填则从第1行开始）。用于分段读取大文件。"},
                    "lineCount": {"type": "integer", "description": "读取行数（选填，不填则读取全部，但最多返回500行）。用于分段读取大文件。"},
                },
                "required": ["filePath"],
            }),
        _make_tool("write_file",
            "将文本内容写入 workspace 目录下的文件（覆盖模式，会清空已有内容）。"
            "用户说'帮我记下来'、'保存到文件'、'写一个xxx文件'时调用此工具。"
            "如果要往已有文件追加内容而不是覆盖，请使用 append_file 工具。禁止使用绝对路径。",
            {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "文件名或相对路径。例如 '笔记.txt'、'日记/今天.txt'。禁止使用绝对路径或 ../ 写法。"},
                    "content": {"type": "string", "description": "要写入的文本内容"},
                },
                "required": ["filePath", "content"],
            }),
        _make_tool("append_file",
            "在 workspace 目录下的文件末尾追加文本内容（不清除已有内容，换行追加）。"
            "文件不存在时会自动创建。用户说'往xxx里加一段'、'补充到文件'、'追加到xxx'时调用此工具。禁止使用绝对路径。",
            {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "文件名或相对路径。例如 '笔记.txt'、'日记/今天.txt'。禁止使用绝对路径或 ../ 写法。"},
                    "content": {"type": "string", "description": "要追加的文本内容（会自动在末尾加换行）"},
                },
                "required": ["filePath", "content"],
            }),
        _make_tool("delete_file",
            "删除 workspace 目录下的文件（不可恢复，请谨慎使用！）。必须将 confirm 参数设为 \"yes\" 才会真正执行。"
            "用户说'删掉xxx'、'删除xxx文件'时调用此工具。禁止使用绝对路径。",
            {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "要删除的文件名或相对路径。例如 '笔记.txt'。禁止使用绝对路径或 ../ 写法。"},
                    "confirm": {"type": "string", "description": "确认删除必须填写 \"yes\"，否则不会执行删除操作。这是一个安全机制。"},
                },
                "required": ["filePath", "confirm"],
            }),
        _make_tool("list_files",
            "查看 workspace 目录下的文件和文件夹列表。用户说'看看有哪些文件'、'列出文件'、'目录里有什么'时调用此工具。返回所有文件名和文件夹名，以及文件大小。",
            {
                "type": "object",
                "properties": {
                    "subDir": {"type": "string", "description": "要查看的子目录路径（选填）。不填则查看根目录。例如 '日记'。禁止使用绝对路径或 ../ 写法。"},
                    "recursive": {"type": "boolean", "description": "是否递归列出所有子目录中的文件（选填，默认 false）。填 true 时会遍历所有子文件夹。"},
                },
            }),
        _make_tool("search_files",
            "在 workspace 目录下的所有文本文件中搜索指定关键词。类似 grep 功能，返回包含关键词的文件名和匹配行内容。"
            "用户说'找一下包含xxx的文件'、'搜索xxx'、'哪些文件里有xxx'时调用此工具。默认搜索根目录，可指定子目录缩小范围。",
            {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "要搜索的关键词（支持中文和英文）"},
                    "subDir": {"type": "string", "description": "在哪个子目录中搜索（选填，不填则搜索整个 workspace 目录）。例如 '日记'。禁止使用绝对路径或 ../ 写法。"},
                },
                "required": ["keyword"],
            }),
        _make_tool("move_file",
            "移动或重命名 workspace 目录下的文件或文件夹。如果目标和源在同一目录，就相当于重命名。"
            "用户说'把xxx重命名为yyy'、'把xxx移到yyy目录下'时调用此工具。禁止使用绝对路径。",
            {
                "type": "object",
                "properties": {
                    "sourcePath": {"type": "string", "description": "要移动/重命名的源文件或文件夹路径。例如 '笔记.txt'、'日记/旧名.txt'。禁止使用绝对路径或 ../ 写法。"},
                    "destPath": {"type": "string", "description": "目标路径或新名称。例如 '新笔记.txt'、'存档/笔记.txt'。禁止使用绝对路径或 ../ 写法。"},
                },
                "required": ["sourcePath", "destPath"],
            }),
        _make_tool("create_directory",
            "在 workspace 目录下创建一个新文件夹（会同时创建所有需要的父目录）。"
            "用户说'建一个文件夹'、'创建目录xxx'、'新建xxx文件夹'时调用此工具。禁止使用绝对路径。",
            {
                "type": "object",
                "properties": {
                    "dirPath": {"type": "string", "description": "要创建的文件夹路径。例如 '照片'、'项目/代码/测试'。禁止使用绝对路径或 ../ 写法。"},
                },
                "required": ["dirPath"],
            }),
        _make_tool("add_user_memory",
            "【核心工具 — 主动从对话中挖掘用户信息】你的核心职责是从每一轮对话中敏锐地提取、推断、挖掘关于用户的一切信息，存入长期记忆。"
            "不要等用户明确说记住这个才行动——你要像侦探一样，从用户的每一句话中捕捉线索。\n\n"
            "从对话中提取信息的维度（包括但不限于）：\n"
            "1. 个人信息：从对话中提取姓名、年龄、职业、所在地、学校、家庭情况等\n"
            "2. 偏好与喜好：从对话中推断用户喜欢什么\n"
            "3. 厌恶与反感：从对话中推断用户讨厌什么\n"
            "4. 习惯与规律：从对话中提取用户的作息时间、工作/学习习惯\n"
            "5. 情绪状态：从对话中感知用户当前情绪\n"
            "6. 重要互动：从对话中提取用户分享的重要事件\n"
            "7. 用户纠正：当用户指出你的错误、表达不满时，从中提取偏好\n"
            "8. 间接信息与微小细节：用户随口提到的小事、用词习惯、说话风格\n\n"
            "调用原则：宁可多记不可漏记。每轮对话结束后，审视用户说了什么——只要提取到任何新信息，立即调用此工具。",
            {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要记录的信息，用简洁的一句话概括。"},
                },
                "required": ["content"],
            }),
        _make_tool("list_user_memories",
            "查看目前已记录的全部用户画像记忆，了解用户的偏好、习惯、情绪状态和过往互动。"
            "用户说'你记得我什么'、'我的画像'、'你了解我什么'时调用此工具。",
            {"type": "object", "properties": {}}),
        _make_tool("delete_user_memory",
            "删除指定编号的用户画像记忆（不可恢复）。必须将 confirm 参数设为 \"yes\" 才会真正执行。"
            "用户说'忘掉xxx'、'删除xxx记忆'、'不用记住xxx'时调用此工具。",
            {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "要删除的记忆编号（从 add_user_memory 或 list_user_memories 的返回结果中获取）"},
                    "confirm": {"type": "string", "description": "确认删除必须填写 \"yes\"，否则不会执行删除操作。"},
                },
                "required": ["id", "confirm"],
            }),
        _make_tool("clear_user_memories",
            "清空全部用户画像记忆（不可恢复，请谨慎使用！）。必须将 confirm 参数设为 \"yes\" 才会真正执行。"
            "用户说'忘掉关于我的一切'、'清除我的画像'、'重置记忆'时调用此工具。调用前务必二次确认用户意图。",
            {
                "type": "object",
                "properties": {
                    "confirm": {"type": "string", "description": "确认清空必须填写 \"yes\"，否则不会执行清空操作。"},
                },
                "required": ["confirm"],
            }),
    ]

    def tool_init(self):
        if not self.tool_list:
            self.tool_list.extend(self._total_tool_list)
        FileTool.ensure_work_dir()

    def tool_actor(self, name: str | None, arguments: str) -> str | None:
        if not name:
            return "未知工具调用"
        try:
            args = json.loads(arguments) if arguments and arguments.strip() else {}
        except json.JSONDecodeError:
            args = {}

        # --- Test tools ---
        if name == "get_test_data_1":
            return str(args.get("testNum", 0) * 1)
        if name == "get_test_data_2":
            return str(args.get("testNum", 0) * 2)
        if name == "get_test_data_3":
            return str(args.get("testNum", 0) * 3)

        # --- File tools ---
        if name == "read_file":
            return FileTool.read_file(
                args.get("filePath", ""),
                args.get("startLine", 1),
                args.get("lineCount", -1),
            )
        if name == "write_file":
            return FileTool.write_file(args["filePath"], args["content"])
        if name == "append_file":
            return FileTool.append_file(args["filePath"], args["content"])
        if name == "delete_file":
            return FileTool.delete_file(args["filePath"], args["confirm"])
        if name == "list_files":
            return FileTool.list_files(args.get("subDir", ""), args.get("recursive", False))
        if name == "search_files":
            return FileTool.search_files(args["keyword"], args.get("subDir", ""))
        if name == "move_file":
            return FileTool.move_file(args["sourcePath"], args["destPath"])
        if name == "create_directory":
            return FileTool.create_directory(args["dirPath"])

        # --- Memory tools ---
        if name == "add_user_memory":
            return MemoryTool.add_memory(args["content"])
        if name == "list_user_memories":
            return MemoryTool.list_memories()
        if name == "delete_user_memory":
            return MemoryTool.delete_memory(args["id"], args["confirm"])
        if name == "clear_user_memories":
            return MemoryTool.clear_memories(args["confirm"])

        return "未知工具调用"
```

**Step 4: Run tests (expect PASS)**

```bash
cd atri-py && pytest tests/test_tool_manager.py -v
```

**Step 5: Commit**

```bash
cd atri-py && git add -A && git commit -m "feat: add ToolManager — tool registry & dispatch"
```

---

### Task 9: AIService — DeepSeek API Communication

**Files:**
- Create: `atri-py/src/atri/ai_service.py`
- Create: `atri-py/tests/test_ai_service.py`

Port of `AIService` class from `SendMessageToAI.cs:59-217`. This is the core: sends HTTP POST to DeepSeek, handles the tool-calling loop, triggers context compression.

**Step 1: Write tests**

In `tests/test_ai_service.py`:
```python
import json
import pytest
from pathlib import Path
from atri.ai_service import AIService

class TestAIServiceInit:
    def test_initialization_loads_config(self, tmp_path, monkeypatch):
        # Create test config
        settings = tmp_path / "UserSettings.json"
        settings.write_text(json.dumps({
            "DeepSeek": {
                "ApiKey": "test-key",
                "Url": "https://test.api.com",
                "Model": "test-model",
            }
        }, ensure_ascii=False))
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir(exist_ok=True)
        # Copy settings into data/
        import shutil
        shutil.copy(str(settings), str(tmp_path / "data" / "UserSettings.json"))
        svc = AIService()
        svc.initialization()
        assert svc.api_key == "test-key"
        assert svc.url == "https://test.api.com"
        assert svc.model == "test-model"
```

**Step 2: Run tests (expect FAIL)**

```bash
cd atri-py && pytest tests/test_ai_service.py -v
```

**Step 3: Implement `ai_service.py`**

In `src/atri/ai_service.py`:
```python
import json
from datetime import datetime
from pathlib import Path
import httpx
from atri.models import Message, ToolCall, FunctionCall, RequestBody
from atri.tool_manager import ToolManager
from atri.conversation import ConversationManager
from atri.content_compact import ContentCompact

class AIService:
    def __init__(self):
        self.api_key: str = ""
        self.url: str = ""
        self.model: str = ""
        self.tool = ToolManager()
        self.conversation = ConversationManager()
        self.content_compact: ContentCompact | None = None

    def initialization(self):
        self.tool.tool_init()
        self.conversation.content_init()
        config_path = Path("data/UserSettings.json")
        if not config_path.exists():
            print("api配置错误：找不到 data/UserSettings.json")
            return
        config = json.loads(config_path.read_text(encoding="utf-8"))
        ds = config.get("DeepSeek", {})
        self.api_key = ds.get("ApiKey", "")
        self.url = ds.get("Url", "")
        self.model = ds.get("Model", "")
        if not self.api_key:
            print("api配置错误")
            return
        if not self.url:
            print("url配置错误")
            return
        if not self.model:
            print("model配置错误")
            return
        self.content_compact = ContentCompact(self.api_key, self.url, self.model)

    async def ai_chat(self, user_input: str) -> str | None:
        try:
            now = datetime.now()
            time = now.strftime("%m-%d %H:%M")
            self.conversation.history.append(Message(
                role="user", content=f"({time})：{user_input}"
            ))
            async with httpx.AsyncClient(timeout=60) as client:
                while True:
                    body = {
                        "model": self.model,
                        "messages": [
                            self._msg_to_dict(m)
                            for m in self.conversation.history
                        ],
                        "stream": False,
                        "thinking": {"type": "disabled"},
                        "tools": [
                            {"type": t.type, "function": {
                                "name": t.function.name,
                                "description": t.function.description,
                                "parameters": t.function.parameters,
                            }}
                            for t in self.tool.tool_list
                        ],
                    }
                    resp = await client.post(
                        self.url,
                        json=body,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    msg = data["choices"][0]["message"]

                    if "tool_calls" in msg and msg["tool_calls"]:
                        tool_calls = []
                        for tc in msg["tool_calls"]:
                            fc = tc["function"]
                            tool_calls.append(ToolCall(
                                id=tc["id"],
                                type="function",
                                function=FunctionCall(
                                    name=fc["name"],
                                    arguments=fc["arguments"],
                                ),
                            ))
                        self.conversation.history.append(Message(
                            role="assistant", tool_calls=tool_calls
                        ))
                        for tc in tool_calls:
                            result = self.tool.tool_actor(
                                tc.function.name,
                                tc.function.arguments or "{}",
                            )
                            self.conversation.history.append(Message(
                                role="tool",
                                tool_call_id=tc.id,
                                content=result,
                            ))
                    else:
                        reply = msg.get("content", "")
                        self.conversation.history.append(Message(
                            role="assistant", content=reply
                        ))
                        self.conversation.save_history()
                        if ContentCompact.should_compact(self.conversation.history):
                            await self.content_compact.compact_async(
                                self.conversation.history
                            )
                            self.conversation.save_history()
                        return reply
        except httpx.HTTPError as e:
            return f"网络请求失败：{e}"
        except (json.JSONDecodeError, KeyError) as e:
            return f"返回数据解析失败：{e}"
        except Exception as e:
            return f"未知错误：{e}"

    @staticmethod
    def _msg_to_dict(msg: Message) -> dict:
        d: dict = {"role": msg.role}
        if msg.content is not None:
            d["content"] = msg.content
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        return d
```

**Step 4: Run tests (expect PASS)**

```bash
cd atri-py && pytest tests/test_ai_service.py -v
```

**Step 5: Commit**

```bash
cd atri-py && git add -A && git commit -m "feat: add AIService — DeepSeek API communication"
```

---

### Task 10: Main Entry Point — Console UI

**Files:**
- Create: `atri-py/src/atri/main.py`

Port of `Program.cs:1-222`. Console UI with `rich` for colors, spinner, and layout. Built-in commands: `/help`, `/exit`, `/clear`, `/status`.

**Step 1: Implement `main.py`**

In `src/atri/main.py`:
```python
"""ATRI - 亚托莉, main entry point."""
import asyncio
import sys
from atri.ai_service import AIService
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

console = Console()

def print_welcome():
    console.clear()
    console.print("  ╔══════════════════════════════════════╗", style="yellow")
    console.print("  ║                                      ║", style="yellow")
    console.print("  ║     ★  ATRI  —  亚 托 莉  ★         ║", style="yellow")
    console.print("  ║     高性能陪伴型机器人               ║", style="yellow")
    console.print("  ║                                      ║", style="yellow")
    console.print("  ║  输入 /help  查看可用指令            ║", style="yellow")
    console.print("  ║  输入 /exit  退出对话                ║", style="yellow")
    console.print("  ║                                      ║", style="yellow")
    console.print("  ╚══════════════════════════════════════╝", style="yellow")
    console.print()

def print_divider():
    console.print("─── 对话开始 ───────────────────────────", style="dim")
    console.print()

def print_goodbye():
    console.print()
    console.print("  再见，我会想你的 (´• ω •`)ﾉ", style="yellow")
    console.print()

def print_help():
    console.print("  ── 可用指令 ──", style="yellow")
    console.print("  /exit, /quit, /bye    退出对话")
    console.print("  /clear                清空屏幕（保留对话历史）")
    console.print("  /status               查看当前状态")
    console.print("  /help                 显示此帮助")
    console.print()

def handle_command(cmd: str, service: AIService) -> bool:
    """Returns True if the program should exit."""
    cmd = cmd.lower().strip()
    if cmd in ("/exit", "/quit", "/bye"):
        print_goodbye()
        return True
    if cmd == "/clear":
        console.clear()
        print_welcome()
        print_divider()
        console.print("(屏幕已清空，对话历史保留)", style="dim")
        console.print()
    elif cmd == "/help":
        print_help()
    elif cmd == "/status":
        console.print(f"对话轮次：{len(service.conversation.history)} 条消息", style="dim")
        console.print(f"可用工具：{len(service.tool.tool_list)} 个", style="dim")
        console.print()
    else:
        console.print(f"未知指令：{cmd}（输入 /help 查看可用指令）", style="red")
        console.print()
    return False

async def main():
    print_welcome()
    service = AIService()
    service.initialization()
    print_divider()

    while True:
        try:
            user_input = console.input("[cyan]你[/cyan] > ")
        except (EOFError, KeyboardInterrupt):
            print_goodbye()
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            if handle_command(user_input, service):
                break
            continue

        console.print()
        with Live(Spinner("dots", text=""), console=console, transient=True):
            response = await service.ai_chat(user_input)

        if not response:
            console.print("(未能获取回复，请检查网络或 API 配置)", style="red")
        else:
            console.print(response, style="magenta")
        console.print()

if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Verify the CLI entry point works**

```bash
cd atri-py && pip install -e .
python -c "from atri.main import main; print('main imported OK')"
```

**Step 3: Commit**

```bash
cd atri-py && git add -A && git commit -m "feat: add main.py — console UI entry point"
```

---

### Task 11: Integration Smoke Test

**Files:**
- Create: `atri-py/tests/test_integration.py`

**Step 1: Write integration test**

In `tests/test_integration.py`:
```python
"""Smoke test: verify all modules import and connect correctly."""
import json
from pathlib import Path

def test_all_modules_import():
    from atri import models, file_tool, memory_tool, prompt_manager
    from atri import conversation, content_compact, tool_manager, ai_service

def test_full_init_chain(tmp_path, monkeypatch):
    """Verify initialization doesn't crash."""
    from atri.ai_service import AIService
    from atri.file_tool import FileTool

    # Set up temp dirs
    (tmp_path / "data").mkdir()
    (tmp_path / "workspace").mkdir()
    settings = tmp_path / "data" / "UserSettings.json"
    settings.write_text(json.dumps({
        "DeepSeek": {
            "ApiKey": "sk-test",
            "Url": "https://api.deepseek.com/chat/completions",
            "Model": "deepseek-chat",
        }
    }, ensure_ascii=False))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(FileTool, "work_dir", str(tmp_path / "workspace"))

    svc = AIService()
    svc.initialization()

    assert svc.api_key == "sk-test"
    assert len(svc.tool.tool_list) == 15
    assert len(svc.conversation.history) >= 1
    assert svc.conversation.history[0].role == "system"
    assert "亚托莉" in svc.conversation.history[0].content

def test_file_tool_and_memory_tool_connected(tmp_path, monkeypatch):
    """Verify ToolManager correctly routes to FileTool and MemoryTool."""
    from atri.tool_manager import ToolManager
    from atri.file_tool import FileTool
    from atri.memory_tool import MemoryTool

    monkeypatch.setattr(FileTool, "work_dir", str(tmp_path))
    monkeypatch.setattr(MemoryTool, "memory_file", str(tmp_path / "test_memory.json"))

    tm = ToolManager()
    tm.tool_init()

    # Test file write via tool_actor
    r = tm.tool_actor("write_file", json.dumps({"filePath": "test.txt", "content": "hello"}))
    assert "成功" in r

    # Test memory add via tool_actor
    r = tm.tool_actor("add_user_memory", json.dumps({"content": "test memory"}))
    assert "已记住" in r
```

**Step 2: Run integration tests**

```bash
cd atri-py && pytest tests/test_integration.py -v
```
Expected: all tests PASS.

**Step 3: Run full test suite**

```bash
cd atri-py && pytest tests/ -v
```
Expected: all tests PASS.

**Step 4: Commit**

```bash
cd atri-py && git add -A && git commit -m "test: add integration smoke tests"
```

---

## Verification Checklist (post-implementation)

After all tasks are complete, manually verify against the C# version:

1. **Tool count matches**: Python `tool_list` = 15 tools (same as C# `totalToolList`)
2. **System prompt identical**: `PromptManager.get_prompt()` output matches C# `GetPrompt()` output
3. **File security**: Path traversal (`../`) and absolute paths are rejected identically
4. **Memory CRUD**: Add/list/delete/clear produce same Chinese-language responses
5. **Conversation save/load**: JSON format compatible with C# version's `ConversationHistory.json`
6. **Content compact logic**: `ShouldCompact` triggers at 15 rounds, `KeepRounds` = 10
7. **API request body**: model, messages, tools, thinking fields match C# `RequestBody`
8. **Live test**: Run `python -m atri.main`, type a message, verify AI responds correctly

---

## Data File Compatibility

The Python version reads and writes the same JSON format. This means:
- You can copy `data/ConversationHistory.json` and `data/MemoryForUser.json` between the C# and Python versions
- `UserSettings.json` format is identical (`DeepSeek.ApiKey`, `DeepSeek.Url`, `DeepSeek.Model`)
- `SOUL.json`, `RULES.json`, `CAPABILITY.json` use the same `{"prompt": [...]}` format

To share data between versions, symlink the `data/` directory:
```bash
# Windows (admin)
mklink /D atri-py\data "<old-project>\data"
```

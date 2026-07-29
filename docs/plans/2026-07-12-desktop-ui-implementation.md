# ATRI Desktop UI Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the ATRI PySide6 desktop UI as a three-panel Hermes-style chat interface (sidebar | chat with Markdown/code highlighting | file panel).

**Architecture:** 9 new Python files under `src/atri/ui/`, each one self-contained component. The core agent (`ai_service.py`, `tool_manager.py`, `prompt_manager.py`, `conversation.py`) stays untouched. Add `markdown` + `pygments` for rendering. Delete old `chat_ui.py` + `main_window.py` at the end.

**Tech Stack:** Python 3.12+, PySide6, markdown, pygments, httpx

---

### Task 1: Install new dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add markdown and pygments to project**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv add markdown pygments
```

Expected: `pyproject.toml` updated with `markdown` and `pygments` in dependencies. `uv.lock` regenerated.

**Step 2: Verify import**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "import markdown; import pygments; print('OK')"
```

Expected: prints `OK`

---

### Task 2: Create theme.py — color constants

**Files:**
- Create: `src/atri/ui/theme.py`

**Step 1: Write the file**

```python
"""Dark theme color constants matching Hermes appearance."""

# Window backgrounds
BG_MAIN = "#1a1b1e"
BG_SIDEBAR = "#1e1f22"
BG_CHAT = "#1a1b1e"
BG_INPUT = "#1e1f22"
BG_TITLEBAR = "#141517"
BG_STATUSBAR = "#141517"
BG_CODE = "#111827"

# Message bubbles
BUBBLE_USER = "#2563eb"
BUBBLE_AI = "#2d2d30"

# Text colors
TEXT_PRIMARY = "#e1e1e1"
TEXT_SECONDARY = "#9ca3af"
TEXT_WHITE = "#ffffff"

# Borders and accents
BORDER = "#2d2d30"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"

# Status colors
STATUS_SUCCESS = "#22c55e"
STATUS_WARNING = "#f59e0b"
STATUS_ERROR = "#ef4444"

FONT_FAMILY = "Segoe UI, Microsoft YaHei, sans-serif"
FONT_SIZE = 13
FONT_SIZE_SMALL = 11
CODE_FONT = "Cascadia Code, Consolas, monospace"
CODE_SIZE = 12


def global_stylesheet() -> str:
    """Return the app-wide QSS stylesheet."""
    return f"""
    QMainWindow {{
        background-color: {BG_MAIN};
    }}
    QListWidget {{
        background-color: {BG_SIDEBAR};
        color: {TEXT_PRIMARY};
        border: none;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE}px;
    }}
    QListWidget::item {{
        padding: 8px 12px;
        border-radius: 6px;
    }}
    QListWidget::item:hover {{
        background-color: {BUBBLE_AI};
    }}
    QListWidget::item:selected {{
        background-color: {ACCENT};
    }}
    QTextEdit {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 10px;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE}px;
    }}
    QTextBrowser {{
        background-color: {BG_CHAT};
        color: {TEXT_PRIMARY};
        border: none;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE}px;
    }}
    QPushButton {{
        background-color: {ACCENT};
        color: {TEXT_WHITE};
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE}px;
    }}
    QPushButton:hover {{
        background-color: {ACCENT_HOVER};
    }}
    QPushButton:disabled {{
        background-color: {BORDER};
        color: {TEXT_SECONDARY};
    }}
    QTreeView {{
        background-color: {BG_SIDEBAR};
        color: {TEXT_PRIMARY};
        border: none;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE}px;
    }}
    QTreeView::item:hover {{
        background-color: {BUBBLE_AI};
    }}
    QTreeView::item:selected {{
        background-color: {ACCENT};
    }}
    QScrollBar:vertical {{
        background: {BG_MAIN};
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QSplitter::handle {{
        background-color: {BORDER};
        width: 1px;
    }}
    QLabel {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE}px;
    }}
    QMenu {{
        background-color: {BG_SIDEBAR};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 24px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {ACCENT};
    }}
    """
```

**Step 2: Verify file runs without import errors**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.theme import global_stylesheet; print(len(global_stylesheet()))"
```

Expected: prints a number > 500

---

### Task 3: Create worker.py — background AI thread

**Files:**
- Create: `src/atri/ui/worker.py`

**Step 1: Write the file**

```python
"""Background thread that runs AIService.ai_chat() without blocking the UI."""

import asyncio
from PySide6.QtCore import QThread, Signal
from atri.ai_service import AIService


class AIWorker(QThread):
    """Runs the async AI chat loop on a background QThread.

    Emits signals for each StreamEvent type so the UI thread stays responsive.
    """

    content_chunk = Signal(str)
    tool_start = Signal(str)
    tool_result = Signal(str, str)
    message = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, ai_service: AIService, user_input: str):
        super().__init__()
        self.ai_service = ai_service
        self.user_input = user_input
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def handle_chat():
            gen = self.ai_service.ai_chat(self.user_input)
            try:
                async for event in gen:
                    if self._stop_flag:
                        break
                    if event.type == "content":
                        self.content_chunk.emit(event.text)
                    elif event.type == "tool_start":
                        self.tool_start.emit(event.tool_name or "")
                    elif event.type == "tool_result":
                        self.tool_result.emit(
                            event.tool_name or "",
                            event.text or "",
                        )
                    elif event.type == "message":
                        self.message.emit(event.text)
                    elif event.type == "done":
                        self.finished.emit()
                        return
                    elif event.type == "error":
                        self.error.emit(event.text)
                        return
            except Exception as exc:
                self.error.emit(str(exc))
            finally:
                await gen.aclose()

        try:
            loop.run_until_complete(handle_chat())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
```

**Step 2: Verify syntax**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.worker import AIWorker; print('OK')"
```

Expected: prints `OK`

---

### Task 4: Create sidebar.py — session list panel

**Files:**
- Create: `src/atri/ui/sidebar.py`

**Step 1: Write the file**

```python
"""Left sidebar: session list with create/switch/delete."""

import json
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
)
from atri import DATA_DIR
from atri.ui.theme import BG_SIDEBAR

SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_INDEX = DATA_DIR / "sessions.json"


def _ensure_sessions_dir():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> list[dict]:
    _ensure_sessions_dir()
    if not SESSIONS_INDEX.exists():
        return []
    try:
        return json.loads(SESSIONS_INDEX.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_index(sessions: list[dict]):
    _ensure_sessions_dir()
    SESSIONS_INDEX.write_text(
        json.dumps(sessions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def create_session(title: str) -> str:
    """Create a new session, return its ID."""
    session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    sessions = _load_index()
    sessions.insert(0, {
        "id": session_id,
        "title": title or "新对话",
        "created_at": datetime.now().isoformat(),
    })
    _save_index(sessions)
    return session_id


def list_sessions() -> list[dict]:
    """Return sessions newest-first."""
    return _load_index()


def delete_session(session_id: str):
    sessions = _load_index()
    sessions = [s for s in sessions if s["id"] != session_id]
    _save_index(sessions)
    history_file = SESSIONS_DIR / f"{session_id}.json"
    if history_file.exists():
        history_file.unlink()


def rename_session(session_id: str, new_title: str):
    sessions = _load_index()
    for s in sessions:
        if s["id"] == session_id:
            s["title"] = new_title
            break
    _save_index(sessions)


class Sidebar(QFrame):
    """Left panel listing all chat sessions."""

    session_selected = Signal(str)
    new_session = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setStyleSheet(f"#sidebar {{ background-color: {BG_SIDEBAR}; }}")
        self.setMinimumWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        new_btn = QPushButton("+ 新对话")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._on_new)
        layout.addWidget(new_btn)

        self._list = QListWidget()
        self._list.setCursor(Qt.CursorShape.PointingHandCursor)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self.refresh()

    def refresh(self):
        """Reload session list from disk."""
        self._list.clear()
        for session in list_sessions():
            item = QListWidgetItem(session["title"])
            item.setData(Qt.ItemDataRole.UserRole, session["id"])
            self._list.addItem(item)

    def _on_new(self):
        session_id = create_session("新对话")
        self.refresh()
        self.new_session.emit()
        self.session_selected.emit(session_id)

    def _on_item_clicked(self, item: QListWidgetItem):
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self.session_selected.emit(session_id)

    def _on_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除")
        action = menu.exec(self._list.mapToGlobal(pos))
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if action == rename_action:
            from PySide6.QtWidgets import QInputDialog
            new_title, ok = QInputDialog.getText(
                self, "重命名", "新名称:", text=item.text(),
            )
            if ok and new_title.strip():
                rename_session(session_id, new_title.strip())
                self.refresh()
        elif action == delete_action:
            delete_session(session_id)
            self.refresh()
```

**Step 2: Verify syntax**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.sidebar import create_session, list_sessions, delete_session; sid = create_session('test'); print(sid); delete_session(sid); print('OK')"
```

Expected: prints session ID and `OK`

---

### Task 5: Create thread.py — message display with Markdown + code highlighting

**Files:**
- Create: `src/atri/ui/thread.py`

**Step 1: Write the file**

```python
"""Message display area: user/AI bubbles with Markdown + code highlighting."""

import re
import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from atri.ui.theme import (
    BG_CHAT,
    BUBBLE_AI,
    BUBBLE_USER,
    CODE_BG,
    FONT_FAMILY,
    FONT_SIZE,
    TEXT_PRIMARY,
    TEXT_WHITE,
)

_CODE_BLOCK_RE = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)


def _highlight_code(lang: str, code: str) -> str:
    """Syntax-highlight a code block, return HTML."""
    try:
        lexer = get_lexer_by_name(lang, stripall=True) if lang else guess_lexer(code)
    except Exception:
        lexer = guess_lexer(code)
    formatter = HtmlFormatter(
        style="monokai",
        noclasses=True,
    )
    return highlight(code, lexer, formatter)


def _md_to_html(text: str) -> str:
    """Convert Markdown text to styled HTML for QTextBrowser.

    Code blocks are extracted, syntax-highlighted with pygments,
    then re-inserted before markdown→HTML conversion.
    """
    # Extract and highlight code blocks
    parts = []
    last_end = 0
    for match in _CODE_BLOCK_RE.finditer(text):
        parts.append(text[last_end:match.start()])
        lang = match.group(1) or ""
        code = match.group(2).strip()
        highlighted = _highlight_code(lang, code)
        parts.append(
            f'<pre style="background:{CODE_BG};padding:12px;border-radius:8px;'
            f'overflow-x:auto;font-family:monospace;font-size:12px;">'
            f"{highlighted}</pre>"
        )
        last_end = match.end()
    parts.append(text[last_end:])

    md_text = "".join(parts)
    html = markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "codehilite"],
    )
    return html


_USER_BUBBLE_TEMPLATE = """
<div style="display:flex;justify-content:flex-end;margin:8px 16px;">
  <div style="max-width:70%;background:{color};color:{text_color};
              border-radius:12px 12px 4px 12px;padding:10px 14px;
              font-family:{font};font-size:{size}px;
              word-wrap:break-word;white-space:pre-wrap;">
    {content}
  </div>
</div>
"""

_AI_BUBBLE_TEMPLATE = """
<div style="display:flex;justify-content:flex-start;margin:8px 16px;">
  <div style="max-width:85%;background:{color};color:{text_color};
              border-radius:12px 12px 12px 4px;padding:10px 14px;
              font-family:{font};font-size:{size}px;
              word-wrap:break-word;">
    {content}
  </div>
</div>
"""


class Thread(QFrame):
    """Scrollable message display with user/AI bubbles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("thread")
        self.setStyleSheet(f"#thread {{ background-color: {BG_CHAT}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setReadOnly(True)
        layout.addWidget(self._browser)

        self._has_open_ai_bubble = False

    def add_user_message(self, text: str):
        """Append a right-aligned user bubble."""
        self._finish_ai_bubble()
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = _USER_BUBBLE_TEMPLATE.format(
            color=BUBBLE_USER,
            text_color=TEXT_WHITE,
            font=FONT_FAMILY,
            size=FONT_SIZE,
            content=escaped,
        )
        self._browser.append(html)
        self._scroll_to_bottom()

    def add_ai_chunk(self, raw_text: str):
        """Append a streaming chunk to the current AI bubble."""
        html_chunk = _md_to_html(raw_text)
        if not self._has_open_ai_bubble:
            open_div = _AI_BUBBLE_TEMPLATE.format(
                color=BUBBLE_AI,
                text_color=TEXT_PRIMARY,
                font=FONT_FAMILY,
                size=FONT_SIZE,
                content="",
            ).rstrip("</div>\n").rstrip("</div>")
            self._browser.append(open_div)
            self._has_open_ai_bubble = True
            self._current_ai_html = ""
        # Diff-based append: compute what's new since last render
        self._current_ai_html = html_chunk
        # Scroll to the end and rewrite the last bubble
        cursor = self._browser.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._browser.setTextCursor(cursor)
        self._scroll_to_bottom()

    def _finish_ai_bubble(self):
        """Close the open AI bubble if any."""
        if self._has_open_ai_bubble:
            self._browser.append("</div>")
            self._has_open_ai_bubble = False
            self._current_ai_html = ""

    def add_ai_message(self, text: str):
        """Append a complete AI message as one bubble."""
        self._finish_ai_bubble()
        html = _AI_BUBBLE_TEMPLATE.format(
            color=BUBBLE_AI,
            text_color=TEXT_PRIMARY,
            font=FONT_FAMILY,
            size=FONT_SIZE,
            content=_md_to_html(text),
        )
        self._browser.append(html)
        self._scroll_to_bottom()

    def add_system_message(self, text: str):
        """Append a centered system/status note."""
        self._finish_ai_bubble()
        html = (
            f'<div style="text-align:center;margin:4px 0;color:{TEXT_PRIMARY};'
            f'font-family:{FONT_FAMILY};font-size:{FONT_SIZE}px;'
            f'opacity:0.6;">{text}</div>'
        )
        self._browser.append(html)

    def clear(self):
        """Clear all messages."""
        self._finish_ai_bubble()
        self._browser.clear()

    def _scroll_to_bottom(self):
        bar = self._browser.verticalScrollBar()
        bar.setValue(bar.maximum())
```

**Note on streaming:** The `add_ai_chunk` approach above is simple but replaces the whole AI bubble HTML on each chunk. For large messages this has a flicker. A better approach (Milestone 2): use a raw HTML buffer inside the bubble div and rewrite only the inner content. For now, the `add_ai_message` method handles complete messages correctly; streaming will be refined after the initial wiring works.

**Step 2: Verify markdown + code highlighting**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "
from atri.ui.thread import _md_to_html
result = _md_to_html('Hello **world**\n\n```python\nprint(1)\n```')
assert 'Hello' in result
assert '# Example' in result or result.startswith('<h1>')
print('OK')
"
```

Expected: prints `OK`

---

### Task 6: Create composer.py — input area

**Files:**
- Create: `src/atri/ui/composer.py`

**Step 1: Write the file**

```python
"""Bottom input area: multi-line text input + send button."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from atri.ui.theme import BG_INPUT


class Composer(QFrame):
    """Message input bar at the bottom of the chat view."""

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("composer")
        self.setStyleSheet(f"#composer {{ background-color: {BG_INPUT}; }}")
        self.setFixedHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(8)

        self._input = QTextEdit()
        self._input.setPlaceholderText("输入消息... (Enter 发送, Ctrl+Enter 换行)")
        self._input.setFixedHeight(56)
        self._input.setAcceptRichText(False)

        send_btn = QPushButton("发送")
        send_btn.setFixedSize(64, 36)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.clicked.connect(self._on_send)

        row.addWidget(self._input, 1)
        row.addWidget(send_btn)
        layout.addLayout(row)

    def keyPressEvent(self, event):
        # Enter without modifiers = send; Ctrl+Enter = newline
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._input.insertPlainText("\n")
                return
            self._on_send()
            return
        super().keyPressEvent(event)

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self.submitted.emit(text)

    def set_enabled(self, enabled: bool):
        self._input.setEnabled(enabled)
        # Find the send button and disable it too
        for child in self.findChildren(QPushButton):
            child.setEnabled(enabled)
        if enabled:
            self._input.setFocus()

    def insert_text(self, text: str):
        """Insert text at cursor position (for file path references)."""
        self._input.insertPlainText(text)
        self._input.setFocus()
```

**Step 2: Verify syntax**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.composer import Composer; print('OK')"
```

Expected: prints `OK`

---

### Task 7: Create file_panel.py — workspace file browser

**Files:**
- Create: `src/atri/ui/file_panel.py`

**Step 1: Write the file**

```python
"""Right-side file browser showing workspace directory."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileSystemModel,
    QFrame,
    QLabel,
    QPushButton,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
)
from atri import WORKSPACE_DIR
from atri.ui.theme import BG_SIDEBAR, TEXT_SECONDARY


class FilePanel(QFrame):
    """Tree view of workspace/ directory with file preview."""

    file_double_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filePanel")
        self.setStyleSheet(f"#filePanel {{ background-color: {BG_SIDEBAR}; }}")
        self.setMinimumWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("📁 workspace")
        title.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: bold; padding: 4px 0;")
        layout.addWidget(title)

        self._model = QFileSystemModel()
        self._model.setRootPath(str(WORKSPACE_DIR))
        self._model.setFilter(
            self._model.filter()
            | Qt.DirectoryFilter.NoDotAndDotDot
        )

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setRootIndex(self._model.index(str(WORKSPACE_DIR)))
        self._tree.setHeaderHidden(True)
        self._tree.setColumnHidden(1, True)
        self._tree.setColumnHidden(2, True)
        self._tree.setColumnHidden(3, True)
        self._tree.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tree.doubleClicked.connect(self._on_double_click)
        self._tree.clicked.connect(self._on_single_click)
        layout.addWidget(self._tree, 1)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFixedHeight(120)
        self._preview.setPlaceholderText("单击文件预览内容...")
        layout.addWidget(self._preview)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)

    def _on_single_click(self, index):
        file_path = self._model.filePath(index)
        try:
            from pathlib import Path
            p = Path(file_path)
            if p.is_file() and p.stat().st_size < 100_000:
                content = p.read_text(encoding="utf-8", errors="replace")
                self._preview.setPlainText(content[:5000])
            else:
                self._preview.clear()
        except Exception:
            self._preview.clear()

    def _on_double_click(self, index):
        file_path = self._model.filePath(index)
        # Only emit for files, not directories
        from pathlib import Path
        if Path(file_path).is_file():
            self.file_double_clicked.emit(file_path)

    def _refresh(self):
        self._model.setRootPath(str(WORKSPACE_DIR))
        self._tree.setRootIndex(self._model.index(str(WORKSPACE_DIR)))
```

**Step 2: Verify syntax**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.file_panel import FilePanel; print('OK')"
```

Expected: prints `OK`

---

### Task 8: Create status_bar.py — bottom status line

**Files:**
- Create: `src/atri/ui/status_bar.py`

**Step 1: Write the file**

```python
"""Bottom status bar showing model, state, and turn count."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget
from atri.ui.theme import (
    BG_STATUSBAR,
    FONT_SIZE_SMALL,
    STATUS_SUCCESS,
    STATUS_WARNING,
    TEXT_SECONDARY,
)


class StatusBar(QFrame):
    """Persistent bottom bar with model name, status, and stats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setStyleSheet(
            f"#statusBar {{ background-color: {BG_STATUSBAR}; border-top: 1px solid #2d2d30; }}"
        )
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(16)

        self._model_label = QLabel("deepseek-chat")
        self._model_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}px;"
        )

        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet(
            f"color: {STATUS_SUCCESS}; font-size: {FONT_SIZE_SMALL}px;"
        )

        self._turn_label = QLabel("")
        self._turn_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}px;"
        )

        layout.addWidget(self._model_label)
        layout.addWidget(self._status_label)
        layout.addStretch()
        layout.addWidget(self._turn_label)

    def set_model(self, name: str):
        self._model_label.setText(name)

    def set_status(self, text: str, busy: bool = False):
        self._status_label.setText(text)
        color = STATUS_WARNING if busy else STATUS_SUCCESS
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: {FONT_SIZE_SMALL}px;"
        )

    def set_turn_count(self, count: int):
        self._turn_label.setText(f"对话轮次: {count}")
```

**Step 2: Verify syntax**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.status_bar import StatusBar; print('OK')"
```

Expected: prints `OK`

---

### Task 9: Create chat_view.py — central chat area (Thread + Composer)

**Files:**
- Create: `src/atri/ui/chat_view.py`

**Step 1: Write the file**

```python
"""Central chat area: Thread (messages) on top, Composer (input) on bottom."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout
from atri.ui.composer import Composer
from atri.ui.thread import Thread


class ChatView(QFrame):
    """Assembles the Thread (message display) and Composer (input bar)."""

    message_submitted = Signal(str)
    file_path_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatView")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.thread = Thread()
        layout.addWidget(self.thread, 1)

        self.composer = Composer()
        layout.addWidget(self.composer)

        self.composer.submitted.connect(self._on_submit)

    def _on_submit(self, text: str):
        self.message_submitted.emit(text)

    def set_input_enabled(self, enabled: bool):
        self.composer.set_enabled(enabled)

    def insert_file_path(self, path: str):
        """Insert a file path reference into the composer."""
        self.composer.insert_text(path)
```

**Step 2: Verify syntax**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.chat_view import ChatView; print('OK')"
```

Expected: prints `OK`

---

### Task 10: Create app_shell.py — main window wiring everything together

**Files:**
- Create: `src/atri/ui/app_shell.py`

**Step 1: Write the file**

```python
"""Main application window: three-panel shell with AI integration."""

import asyncio
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from atri.ai_service import AIService
from atri.conversation import ConversationManager
from atri import DATA_DIR, WORKSPACE_DIR
from atri.ui.chat_view import ChatView
from atri.ui.file_panel import FilePanel
from atri.ui.sidebar import (
    Sidebar,
    create_session,
    delete_session,
    list_sessions,
    SESSIONS_DIR,
)
from atri.ui.status_bar import StatusBar
from atri.ui.theme import BG_MAIN, BG_TITLEBAR, FONT_FAMILY, FONT_SIZE, TEXT_PRIMARY
from atri.ui.worker import AIWorker


class AppShell(QMainWindow):
    """Hermes-style three-panel desktop chat window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ATRI")
        self.setMinimumSize(1024, 640)
        self.resize(1400, 860)

        # --- Core services ---
        self.ai_service = AIService()
        self.ai_service.initialization()
        self._worker: AIWorker | None = None
        self._current_session_id: str | None = None
        self._current_ai_text: str = ""

        # --- Build UI ---
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Titlebar
        titlebar = QWidget()
        titlebar.setFixedHeight(40)
        titlebar.setStyleSheet(
            f"background-color: {BG_TITLEBAR}; "
            f"color: {TEXT_PRIMARY}; "
            f"font-family: {FONT_FAMILY}; "
            f"font-size: {FONT_SIZE}px; "
            f"padding-left: 12px;"
        )
        tb_layout = QHBoxLayout(titlebar)
        tb_layout.setContentsMargins(12, 0, 12, 0)
        title_label = QLabel("ATRI")
        title_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")
        tb_layout.addWidget(title_label)
        tb_layout.addStretch()
        root.addWidget(titlebar)

        # Three-panel splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self.sidebar = Sidebar()
        self.sidebar.session_selected.connect(self._on_session_selected)
        self.sidebar.new_session.connect(self._on_new_session)

        self.chat_view = ChatView()
        self.chat_view.message_submitted.connect(self._on_user_message)

        self.file_panel = FilePanel()
        self.file_panel.file_double_clicked.connect(self._on_file_double_clicked)

        self._splitter.addWidget(self.sidebar)
        self._splitter.addWidget(self.chat_view)
        self._splitter.addWidget(self.file_panel)
        self._splitter.setSizes([260, 880, 260])
        root.addWidget(self._splitter, 1)

        # Status bar
        self.status_bar = StatusBar()
        root.addWidget(self.status_bar)

        # --- Start ---
        # Load or create initial session
        sessions = list_sessions()
        if sessions:
            self._switch_session(sessions[0]["id"])
        else:
            sid = create_session("新对话")
            self.sidebar.refresh()
            self._switch_session(sid)

    # ── session management ──────────────────────────────────────────

    def _switch_session(self, session_id: str):
        """Save current session, load a different one."""
        if self._current_session_id:
            self._save_current_history()
        self._current_session_id = session_id
        self._current_ai_text = ""
        self.chat_view.thread.clear()
        self._load_history(session_id)
        self._update_status()

    def _on_session_selected(self, session_id: str):
        if session_id == self._current_session_id:
            return
        self._switch_session(session_id)

    def _on_new_session(self):
        pass  # already handled by sidebar's new_session signal → create_session → refresh

    def _save_current_history(self):
        """Save conversation history for the current session."""
        if not self._current_session_id:
            return
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        history_file = SESSIONS_DIR / f"{self._current_session_id}.json"
        self.ai_service.conversation.save_history()
        # Copy global history to session file
        import shutil
        if Path(self.ai_service.conversation.history_file).exists():
            shutil.copy(
                self.ai_service.conversation.history_file,
                str(history_file),
            )

    def _load_history(self, session_id: str):
        """Load conversation history for a session."""
        history_file = SESSIONS_DIR / f"{session_id}.json"
        global_history = DATA_DIR / "ConversationHistory.json"
        if history_file.exists():
            import shutil
            shutil.copy(str(history_file), str(global_history))
        elif global_history.exists():
            global_history.unlink()
        self.ai_service.conversation.history.clear()
        self.ai_service.conversation.content_init()

    def _update_status(self):
        self.status_bar.set_model(self.ai_service.model)
        turn_count = len(
            [m for m in self.ai_service.conversation.history if m.role == "user"]
        )
        self.status_bar.set_turn_count(turn_count)
        self.status_bar.set_status("就绪")

    # ── message flow ─────────────────────────────────────────────────

    def _on_user_message(self, text: str):
        """User pressed send."""
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

    def _on_content_chunk(self, text: str):
        self._current_ai_text += text
        # For streaming: re-render the entire AI bubble each time.
        # This is acceptable for short-to-medium messages.
        self.chat_view.thread.add_ai_message_in_progress(self._current_ai_text)

    def _on_tool_start(self, tool_name: str):
        self.status_bar.set_status(f"调用工具: {tool_name}", busy=True)
        self.chat_view.thread.add_system_message(f"🔧 调用工具: {tool_name}")

    def _on_tool_result(self, tool_name: str, result: str):
        self.status_bar.set_status("思考中...", busy=True)

    def _on_worker_message(self, text: str):
        self.chat_view.thread.add_system_message(text)

    def _on_error(self, error_text: str):
        self._current_ai_text = ""
        self.chat_view.thread.add_system_message(f"❌ {error_text}")
        self.chat_view.set_input_enabled(True)
        self.status_bar.set_status(f"错误: {error_text}")
        self._update_status()

    def _on_finished(self):
        # Finalize AI message
        self.chat_view.thread.finalize_ai_message(self._current_ai_text)
        self._current_ai_text = ""
        self._save_current_history()
        self.chat_view.set_input_enabled(True)
        self._update_status()

    # ── file panel interactions ──────────────────────────────────────

    def _on_file_double_clicked(self, path: str):
        """Insert file path into composer."""
        rel = Path(path)
        try:
            rel = rel.relative_to(WORKSPACE_DIR)
        except ValueError:
            pass
        self.chat_view.composer.insert_text(str(rel))

    # ── lifecycle ────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._save_current_history()
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.quit()
            self._worker.wait(3000)
        super().closeEvent(event)
```

**Step 2: Verify syntax**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.app_shell import AppShell; print('OK')"
```

Expected: prints `OK`

---

### Task 11: Create app.py — application entry point

**Files:**
- Create: `src/atri/ui/app.py`

**Step 1: Write the file**

```python
"""ATRI desktop application entry point."""

import sys
from PySide6.QtWidgets import QApplication
from atri.ui.app_shell import AppShell
from atri.ui.theme import global_stylesheet


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(global_stylesheet())
    window = AppShell()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

**Step 2: Verify syntax**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.app import main; print('OK')"
```

Expected: prints `OK`

---

### Task 12: Fix streaming support in thread.py

**Files:**
- Modify: `src/atri/ui/thread.py`

**Step 1: Add streaming methods needed by app_shell**

The `add_ai_message_in_progress` and `finalize_ai_message` methods referenced by `app_shell.py` need to exist on Thread. Replace the streaming methods in thread.py:

Add these methods to the Thread class (replace the `add_ai_chunk` approach):

```python
def add_ai_message_in_progress(self, partial_text: str):
    """Replace the current in-progress AI bubble with new partial text."""
    self._finish_ai_bubble()
    html = _AI_BUBBLE_TEMPLATE.format(
        color=BUBBLE_AI,
        text_color=TEXT_PRIMARY,
        font=FONT_FAMILY,
        size=FONT_SIZE,
        content=_md_to_html(partial_text),
    )
    if not self._has_open_ai_bubble:
        self._has_open_ai_bubble = True
        self._browser.append(html)
    else:
        # Remove the last HTML block (the previous version of this bubble)
        cursor = self._browser.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.movePosition(cursor.MoveOperation.StartOfBlock, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        self._browser.append(html)
    self._scroll_to_bottom()

def finalize_ai_message(self, final_text: str):
    """Replace in-progress bubble with final version."""
    self._finish_ai_bubble()
    self.add_ai_message(final_text)
```

Revert `_finish_ai_bubble` to just close without appending:

```python
def _finish_ai_bubble(self):
    self._has_open_ai_bubble = False
```

**Step 2: Verify the full Thread class imports and syntax**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.thread import Thread; t = Thread(); t.add_user_message('hi'); t.add_ai_message('hello'); t.add_ai_message_in_progress('foo'); t.finalize_ai_message('bar'); print('OK')"
```

Expected: prints `OK`

---

### Task 13: Update pyproject.toml entry point and update __init__.py

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/atri/ui/__init__.py`

**Step 1: Change the atri-ui entry point**

Edit `pyproject.toml`, change:
```
atri-ui = "atri.ui.main_window:main"
```
to:
```
atri-ui = "atri.ui.app:main"
```

**Step 2: Update __init__.py to be empty**

Replace the contents of `src/atri/ui/__init__.py` with just an empty file (or keep existing if it's already empty).

**Step 3: Verify entry point resolves**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.app import main; print('entry point OK')"
```

Expected: prints "entry point OK"

---

### Task 14: Delete old UI files

**Files:**
- Delete: `src/atri/ui/chat_ui.py`
- Delete: `src/atri/ui/main_window.py`

**Step 1: Delete old files**

Run:
```bash
rm "D:/ClaudeCodeWorkSpace/DSPark-Code/src/atri/ui/chat_ui.py"
rm "D:/ClaudeCodeWorkSpace/DSPark-Code/src/atri/ui/main_window.py"
```

**Step 2: Verify the app still imports**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run python -c "from atri.ui.app import main; from atri.ui.app_shell import AppShell; print('all imports OK')"
```

Expected: prints "all imports OK"

---

### Task 15: End-to-end launch test

**Step 1: Launch the app**

Run:
```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code && uv run atri-ui
```

Expected:
- Window opens with dark theme
- Three panels visible: sidebar (left), chat (center), file tree (right)
- Sidebar shows "新对话" session
- File panel shows workspace/ contents
- Status bar at bottom shows model name and "就绪"
- Can type a message, press Enter, and see streaming AI response

**Step 2: Verify session persistence**

1. Send a message "hello" and wait for AI response
2. Close the window
3. Re-launch with `uv run atri-ui`
4. Verify the conversation is still visible

---

### Task 16: Commit

```bash
cd D:/ClaudeCodeWorkSpace/DSPark-Code
git add -A
git commit -m "feat: rewrite desktop UI as Hermes-style three-panel layout

Replace old C-Tutor PySide6 UI with Hermes-inspired three-panel design:
- Left sidebar: session list (create/switch/delete/rename)
- Center: chat view with Markdown rendering, code highlighting, streaming
- Right: workspace file browser with preview
- Bottom: status bar with model/status/turn count
- Dark theme matching Hermes appearance

New files: src/atri/ui/{app,app_shell,chat_view,composer,file_panel,
           sidebar,status_bar,thread,worker,theme}.py
Removed: src/atri/ui/{chat_ui,main_window}.py"
```

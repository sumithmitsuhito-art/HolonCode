# ATRI Desktop UI Redesign

**Date:** 2026-07-12
**Status:** Approved

## Overview

Rewrite the ATRI desktop UI layer to match Hermes' three-panel chat interface, using PySide6 only (no Electron, no JavaScript). The core Python agent code (`ai_service.py`, `tool_manager.py`, `prompt_manager.py`, `conversation.py`) remains untouched.

## Architecture

```
src/atri/
├── ai_service.py        ← keep, unchanged
├── tool_manager.py      ← keep, unchanged
├── prompt_manager.py    ← keep, unchanged
├── conversation.py      ← keep, unchanged
└── ui/                  ← complete rewrite
    ├── app.py           ← entry point
    ├── app_shell.py     ← window shell (QSplitter three-panel layout)
    ├── sidebar.py       ← left panel: session list
    ├── chat_view.py     ← center: thread + composer container
    ├── thread.py        ← message bubbles (Markdown + code highlight)
    ├── composer.py      ← bottom input area
    ├── file_panel.py    ← right panel: workspace file tree
    ├── status_bar.py    ← bottom status bar
    ├── worker.py        ← background AI thread (refactored from AIWorker)
    └── theme.py         ← dark/light color scheme
```

## Window Layout

```
┌─────────────────────────────────────────────────────────┐
│  Titlebar:  ATRI                                 [─][□][×]│
├──────────┬──────────────────────────────┬───────────────┤
│ Sidebar  │  Thread                      │  File Panel   │
│ (280px)  │  (flex)                      │  (280px)      │
│          │                              │               │
│ + New    │  ┌──────────────────┐       │  📁 workspace │
│ ─────    │  │ 🤖 AI message    │       │  ├── skills/  │
│ Chat 1   │  │ (Markdown+code) │       │  ├── main.py  │
│ Chat 2   │  └──────────────────┘       │  └── test.py  │
│          │                              │               │
│          │  ┌──────────────────┐       │               │
│          │  │       👤 User msg │       │               │
│          │  └──────────────────┘       │               │
│          ├──────────────────────────────│               │
│          │  Composer: [input...] [Send]│               │
├──────────┴──────────────────────────────┴───────────────┤
│  StatusBar: model │ status │ turn count                  │
└─────────────────────────────────────────────────────────┘
```

Three panels separated by `QSplitter` (draggable dividers). Default ratio: 280px | flex | 280px.

## Component Details

### app.py
Application entry point. Creates `QApplication`, initializes theme, instantiates `AppShell`, calls `window.show()`.

### app_shell.py
`QMainWindow` subclass. Contains:
- Custom titlebar (QWidget, 40px)
- QSplitter (horizontal) with Sidebar | ChatView | FilePanel
- StatusBar at bottom

Maps to Hermes' `AppShell`.

### sidebar.py
`QListWidget`-based session list:
- "+ New Chat" button at top
- List items showing session titles (from JSON files in `data/`)
- Click to switch session (loads conversation history)
- Right-click context menu: rename, delete
- Newest sessions at top

Maps to Hermes' `ChatSidebar` (simplified).

### thread.py
Message display area using `QScrollArea` + `QTextBrowser` bubbles:
- **User messages**: right-aligned, blue background bubble
- **AI messages**: left-aligned, gray background bubble
- **Markdown rendering**: `markdown` library converts MD → HTML
- **Code highlighting**: regex extract ` ```lang...``` ` blocks → `pygments` generates colored HTML
- **Streaming append**: Worker sends `content_chunk` signal → append to current AI bubble HTML (typewriter effect)
- **Auto scroll**: `scrollToBottom()` on new content

Maps to Hermes' `Thread`.

### composer.py
Input area at the bottom of ChatView:
- `QTextEdit` for multi-line input (supports Chinese IME)
- `QPushButton` "Send"
- Enter key = send, Ctrl+Enter = newline
- Disabled during AI processing
- Sends user text → displays user bubble → starts Worker

Maps to Hermes' `ChatBar` (simplified).

### file_panel.py
Right-side workspace file browser:
- `QTreeView` + `QFileSystemModel` rooted at `workspace/`
- Auto-refresh on file changes (QFileSystemModel watches filesystem)
- Single click: preview file content in bottom pane
- Double click: insert file path reference into composer
- Refresh button at bottom

Maps to Hermes' `RightSidebar/FileBrowser` (simplified).

### status_bar.py
Bottom status bar (QWidget, 32px):
- Left: current model name (e.g. "deepseek-chat")
- Center: status text ("Ready" / "Thinking..." / "Calling tool: read_file")
- Right: conversation turn count

Maps to Hermes' `StatusbarControls`.

### worker.py
`QThread` subclass, refactored from existing `AIWorker`:
- Runs `ai_service.ai_chat()` in background
- Signals:
  - `content_chunk(str)` — streaming text delta
  - `tool_start(str)` — tool invocation started
  - `tool_done(str)` — tool invocation completed
  - `finished(str)` — all done
  - `error(str)` — error occurred
- Thread-safe: only Worker touches AIService, UI only touches signals

### theme.py
Color constants for dark theme (matching Hermes dark appearance):
```python
# Backgrounds
BG_MAIN = "#1a1b1e"       # window background
BG_SIDEBAR = "#1e1f22"    # sidebar/file panel
BG_CHAT = "#1a1b1e"       # chat area

# Message bubbles
BUBBLE_USER = "#2563eb"   # blue (user)
BUBBLE_AI = "#2d2d30"     # dark gray (AI)

# Text
TEXT_PRIMARY = "#e1e1e1"
TEXT_SECONDARY = "#9ca3af"

# Code blocks
CODE_BG = "#111827"       # near black
```

## Data Flow

```
User types "write bubble sort" + presses Enter
    │
    ▼
Composer: emit submit_signal(text)
    │
    ▼
ChatView: append user bubble to Thread
ChatView: disable Composer
    │
    ▼
Worker.run(user_input)
    │
    ├─► content_chunk → Thread.append_to_current_bubble(chunk)
    │                    (streaming typewriter effect)
    │
    ├─► tool_start → StatusBar.show("Calling: read_file")
    │
    ├─► tool_done → StatusBar.show("Ready")
    │
    └─► finished → ChatView: enable Composer
                    Conversation.save_to_disk()
```

## Dependencies

Two new packages beyond existing `pyproject.toml`:

| Package | Purpose |
|---------|---------|
| `markdown` | Convert AI Markdown output to HTML for Qt rendering |
| `pygments` | Syntax highlighting for code blocks |

Install: `uv add markdown pygments`

## Feature Scope

### Included
- Three-panel layout (sidebar | chat | file panel)
- Session create/switch/delete/rename
- Streaming message display with typewriter effect
- Markdown rendering (headings, lists, bold, tables, links)
- Code block syntax highlighting (Python, JS, etc.)
- Tool call status display in status bar
- Workspace file tree browser
- Dark theme (Hermes-like appearance)

### Excluded
- File attachment upload / drag-and-drop
- Thinking/reasoning accordion fold
- @file reference system
- Voice input
- Multi-profile switching
- Terminal panel
- Preview panel
- Keyboard shortcut panel
- Plugin system

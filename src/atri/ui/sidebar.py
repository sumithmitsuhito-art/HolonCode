"""Left sidebar: session list with create/switch/delete."""

import json
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
)
from atri import DATA_DIR
from atri.conversation import ConversationManager
from atri.ui.theme import BG_SIDEBAR

SESSIONS_INDEX = DATA_DIR / "sessions.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> dict:
    """Return {'sessions': [...], 'last_active': str|None}."""
    _ensure_data_dir()
    if not SESSIONS_INDEX.exists():
        return {"sessions": [], "last_active": None}
    try:
        data = json.loads(SESSIONS_INDEX.read_text(encoding="utf-8"))
        if isinstance(data, list):
            # Migrate old flat-list format
            return {"sessions": data, "last_active": None}
        if "sessions" not in data:
            return {"sessions": [], "last_active": None}
        return data
    except (json.JSONDecodeError, OSError):
        return {"sessions": [], "last_active": None}


def _save_index(data: dict):
    _ensure_data_dir()
    SESSIONS_INDEX.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _get_sessions() -> list[dict]:
    return _load_index()["sessions"]


def create_session(title: str) -> str:
    """Create a new session, return its ID."""
    session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    data = _load_index()
    data["sessions"].insert(0, {
        "id": session_id,
        "title": title or "新对话",
        "created_at": datetime.now().isoformat(),
    })
    data["last_active"] = session_id
    _save_index(data)
    return session_id


def list_sessions() -> list[dict]:
    """Return sessions newest-first."""
    return _get_sessions()


def get_last_active_session() -> str | None:
    """Return the last active session ID, or None."""
    data = _load_index()
    sid = data.get("last_active")
    if sid and any(s["id"] == sid for s in data["sessions"]):
        return sid
    sessions = data["sessions"]
    return sessions[0]["id"] if sessions else None


def save_last_active_session(session_id: str):
    """Persist the last active session ID."""
    data = _load_index()
    data["last_active"] = session_id
    _save_index(data)


def delete_session(session_id: str):
    data = _load_index()
    data["sessions"] = [s for s in data["sessions"] if s["id"] != session_id]
    if data.get("last_active") == session_id:
        data["last_active"] = data["sessions"][0]["id"] if data["sessions"] else None
    _save_index(data)
    ConversationManager.delete_session_history(session_id)


def rename_session(session_id: str, new_title: str):
    data = _load_index()
    for s in data["sessions"]:
        if s["id"] == session_id:
            s["title"] = new_title
            break
    _save_index(data)


class Sidebar(QFrame):
    """Left panel listing all chat sessions."""

    session_selected = Signal(str)
    session_deleted = Signal(str)
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
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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

    def select_session(self, session_id: str):
        """Highlight the item for the given session ID."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == session_id:
                self._list.setCurrentItem(item)
                return

    def _on_new(self):
        session_id = create_session("新对话")
        self.refresh()
        self.select_session(session_id)
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
            new_title, ok = QInputDialog.getText(
                self, "重命名", "新名称:", text=item.text(),
            )
            if ok and new_title.strip():
                rename_session(session_id, new_title.strip())
                self.refresh()
        elif action == delete_action:
            delete_session(session_id)
            self.refresh()
            self.session_deleted.emit(session_id)

"""Left sidebar: session list with create/switch/delete."""

import json
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from atri import DATA_DIR
from atri.conversation import ConversationManager
from atri.ui.theme import BG_MAIN, BG_SIDEBAR, ACCENT, ACCENT_HOVER, TEXT_WHITE, TEXT_PRIMARY, FONT_SANS, FONT_SIZE, FONT_SIZE_SMALL, BORDER
from atri.ui.progress_dialog import ProgressDialog, C_LEARN_PROGRESS, C_LEARN_TOPICS, LEVEL_LABELS
from atri.ui.level_select_dialog import LevelSelectDialog
import json

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
    """Create a new session, return its ID. Does NOT set last_active."""
    session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    data = _load_index()
    data["sessions"].insert(0, {
        "id": session_id,
        "title": title or "新对话",
        "created_at": datetime.now().isoformat(),
    })
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
    skill_activated = Signal(str)
    c_qa_topic_selected = Signal(str)
    view_progress = Signal()
    level_selected = Signal(str, str)

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

        # Skill quick-access buttons
        skill_btn_style = (
            f"QPushButton {{"
            f"background-color: {ACCENT};"
            f"color: {TEXT_WHITE};"
            f"border: none;"
            f"border-radius: 10px;"
            f"padding: 10px 12px;"
            f"font-family: {FONT_SANS};"
            f"font-size: {FONT_SIZE_SMALL}px;"
            f"font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}"
        )

        c_tutor_btn = QPushButton("C语言知识闯关")
        c_tutor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_tutor_btn.setStyleSheet(skill_btn_style)
        c_tutor_btn.clicked.connect(self._on_tutor_clicked)
        layout.addWidget(c_tutor_btn)

        c_learn_btn = QPushButton("C语言学习")
        c_learn_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_learn_btn.setStyleSheet(skill_btn_style)
        c_learn_btn.clicked.connect(self._on_c_qa_clicked)
        layout.addWidget(c_learn_btn)

        c_qa_btn = QPushButton("C语言答疑")
        c_qa_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_qa_btn.setStyleSheet(skill_btn_style)
        c_qa_btn.clicked.connect(lambda: self.skill_activated.emit("c-qa"))
        layout.addWidget(c_qa_btn)

        view_progress_btn = QPushButton("查看学习进度")
        view_progress_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_progress_btn.setStyleSheet(
            f"QPushButton {{"
            f"background-color: transparent;"
            f"color: {TEXT_PRIMARY};"
            f"border: 1px solid {BORDER};"
            f"border-radius: 10px;"
            f"padding: 10px 12px;"
            f"font-family: {FONT_SANS};"
            f"font-size: {FONT_SIZE_SMALL}px;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {ACCENT};"
            f"color: {TEXT_WHITE};"
            f"border-color: {ACCENT};"
            f"}}"
        )
        view_progress_btn.clicked.connect(lambda: self.view_progress.emit())
        layout.addWidget(view_progress_btn)

        self.refresh()

    def _on_tutor_clicked(self):
        """Open level selection dialog for c-tutor."""
        dlg = LevelSelectDialog(self)
        dlg.level_selected.connect(
            lambda lid, name: self.level_selected.emit(lid, name)
        )
        dlg.exec()

    def _on_c_qa_clicked(self):
        """Show C knowledge point selection dialog with card-based grid + mastery labels."""
        topics_full = [
            "C语言声明语法：变量声明、初始化、声明与定义区别、复杂声明解析",
            "数据类型系统：基本类型、修饰符(short/long/signed/unsigned)、类型转换",
            "运算符优先级与结合性：完整优先级表、表达式求值顺序、副作用问题",
            "表达式与隐式转换：整型提升、浮点转换、强制类型转换、溢出规则",
            "控制流语法：if、switch、循环、break、continue、goto",
            "函数高级语法：参数传递、返回值、递归、函数声明、函数指针",
            "数组语法：数组初始化、变长数组(VLA)、多维数组、数组作为参数",
            "指针完整体系：指针声明、指针运算、多级指针、指针数组、数组指针",
            "字符串处理语法：字符数组、字符串常量、字符串函数、字符串指针",
            "结构体语法：struct、嵌套结构体、结构体初始化、结构体指针",
            "联合体与枚举：union内存共享、enum枚举类型、应用场景",
            "预处理器：#include、#define、宏函数、条件编译(#if)",
            "存储类别：auto、static、extern、变量生命周期和作用域",
            "位操作语法：&、|、^、~、<<、>>、位字段",
            "文件与工程组织：多文件编译、头文件、声明/定义分离、Makefile基础",
            "动态内存分配：malloc、calloc、realloc、free、内存泄漏与悬垂指针",
            "函数指针与回调：函数指针声明、回调机制、qsort自定义排序",
            "const与volatile：const指针与指针常量、volatile变量、类型限定符",
            "链表与基础数据结构：单向/双向链表、栈与队列的C语言实现",
            "可变参数与标准库：stdarg.h、va_list、常用标准库函数与头文件",
            "typedef与类型别名：typedef用法、与#define区别、函数指针类型定义",
            "编译过程详解：预处理→编译→汇编→链接、gcc各阶段与常用选项",
            "调试技巧与断言：gdb基础、assert断言、常见运行时错误排查方法",
            "多文件模块化设计：模块划分、静态函数、extern声明、头文件保护",
            "C标准与跨平台：C89/C99/C11/C17差异、未定义行为、可移植性建议",
            "常见陷阱与最佳实践：悬垂else、宏副作用、缓冲区溢出、编码规范",
            "综合实战项目：综合运用各知识点解决实际编程问题",
        ]
        topics_short = C_LEARN_TOPICS

        # Read c-learn progress for mastery labels
        progress = {}
        if C_LEARN_PROGRESS.exists():
            try:
                progress = json.loads(C_LEARN_PROGRESS.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        topics_data = progress.get("topics", {})

        dlg = QDialog(self)
        dlg.setWindowTitle("C语言知识点学习")
        dlg.setMinimumSize(900, 600)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_MAIN};
                font-family: {FONT_SANS};
            }}
            QLabel {{
                color: {TEXT_PRIMARY};
                font-family: {FONT_SANS};
                font-size: {FONT_SIZE}px;
            }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)

        title = QLabel("请选择要学习的知识点：")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; }}
            QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 6px; min-height: 30px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        # General button — full row
        general_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 10px;
                padding: 12px 14px;
                font-family: {FONT_SANS};
                font-size: {FONT_SIZE_SMALL}px;
                font-weight: 600;
                outline: none;
            }}
            QPushButton:hover {{
                background-color: {ACCENT};
                color: {TEXT_WHITE};
                border-color: {ACCENT};
            }}
        """
        general_btn = QPushButton("我遇到点问题（通用）")
        general_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        general_btn.setStyleSheet(general_style)
        general_btn.clicked.connect(lambda: (
            self.c_qa_topic_selected.emit("我遇到点C语言问题"),
            dlg.accept(),
        ))
        grid.addWidget(general_btn, 0, 0, 1, 3)

        # Topic cards
        card_base_style = f"""
            QFrame {{
                background-color: #81C784;
                border-left: 4px solid {ACCENT_HOVER};
                border-radius: 8px;
                padding: 4px;
            }}
            QFrame:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """

        for i, (full, short) in enumerate(zip(topics_full, topics_short)):
            row = i // 3 + 1
            col = i % 3

            topic_data = topics_data.get(str(i), {})
            level = topic_data.get("level", 0)

            card = QFrame()
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setStyleSheet(card_base_style)
            card.setMinimumHeight(80)

            card_inner = QVBoxLayout(card)
            card_inner.setContentsMargins(10, 8, 10, 8)
            card_inner.setSpacing(4)

            num_lbl = QLabel(f"{i + 1}. {short}")
            num_lbl.setStyleSheet(f"color: {TEXT_WHITE}; font-weight: 600; font-size: {FONT_SIZE_SMALL + 1}px;")
            num_lbl.setWordWrap(True)
            num_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            card_inner.addWidget(num_lbl)

            if level > 0:
                level_text = LEVEL_LABELS.get(level, "")
                level_lbl = QLabel(f"[ {level_text} ]")
                level_lbl.setStyleSheet(f"color: rgba(255,255,255,0.75); font-weight: 600; font-size: {FONT_SIZE_SMALL}px;")
                level_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                card_inner.addWidget(level_lbl)

            # Make card clickable
            def make_handler(f=full, idx=i):
                return lambda: (
                    self.c_qa_topic_selected.emit(
                        f"请给我详细讲解以下知识点：{idx + 1} — {f}"
                    ),
                    dlg.accept(),
                )
            card.mousePressEvent = lambda e, h=make_handler(): h()

            grid.addWidget(card, row, col)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)
        current = self._list.currentItem()
        current_sid = current.data(Qt.ItemDataRole.UserRole) if current else None
        dlg.exec()
        self.refresh()
        if current_sid:
            self.select_session(current_sid)

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
                self._list.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
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

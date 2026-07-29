"""Left sidebar: session list with create/switch/delete."""

import json
from datetime import datetime, date, timedelta
from pathlib import Path
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from atri import DATA_DIR
from atri.conversation import ConversationManager
from atri.ui.theme import (
    BG_MAIN, BG_SIDEBAR, PAGE_BG, ACCENT, ACCENT_HOVER,
    BADGE_DONE_BG, BADGE_DONE_TEXT, BADGE_PENDING_BG, BADGE_PENDING_TEXT,
    TEXT_WHITE, TEXT_PRIMARY, TEXT_SECONDARY,
    FONT_SANS, FONT_SIZE, FONT_SIZE_SMALL, BORDER,
    CARD_BG, CARD_HOVER, CARD_RADIUS, FILE_SELECTION, RADIUS_MD,
)
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
    c_qa_review_selected = Signal(str, str)  # 新增：模块id, 模块名称
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

        self._current_session_id: str | None = None
        self._session_frames: dict[str, QFrame] = {}

        self._session_scroll = QScrollArea()
        self._session_scroll.setWidgetResizable(True)
        self._session_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._session_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        self._session_scroll.viewport().setStyleSheet("background: transparent;")
        self._session_container = QWidget()
        self._session_container.setStyleSheet("background: transparent;")
        self._session_layout = QVBoxLayout(self._session_container)
        self._session_layout.setContentsMargins(0, 0, 0, 0)
        self._session_layout.setSpacing(0)
        self._session_layout.addStretch()
        self._session_scroll.setWidget(self._session_container)
        layout.addWidget(self._session_scroll)

        # Separator between sessions and skill buttons
        sep_wrap = QVBoxLayout()
        sep_wrap.setContentsMargins(4, 6, 4, 6)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {TEXT_SECONDARY};")
        sep_wrap.addWidget(sep)
        layout.addLayout(sep_wrap)

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

        c_qa_btn = QPushButton("C语言答疑(角色互换)")
        c_qa_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_qa_btn.setStyleSheet(skill_btn_style)
        c_qa_btn.clicked.connect(self._on_c_qa_review_clicked)
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

    def _on_c_qa_review_clicked(self):
        """Open module selection dialog for c-qa role-reversal review."""
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

        dlg = QDialog(self)
        dlg.setWindowTitle("C语言角色互换答疑")
        dlg.setMinimumSize(900, 600)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {PAGE_BG};
                font-family: {FONT_SANS};
            }}
            QLabel {{
                color: {TEXT_PRIMARY};
                font-family: {FONT_SANS};
                font-size: {FONT_SIZE}px;
            }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("角色互换复习模式")
        title.setStyleSheet("font-weight: 700; font-size: 16px;")
        layout.addWidget(title)

        desc = QLabel(
            "选择一个知识点模块，小洛会对这个模块的知识点\"记不太清\"，\n"
            "通过向你提问的方式引导你回顾和巩固该模块的知识。"
        )
        desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        tip = QLabel("教学相长：最好的学习方式就是教别人！")
        tip.setStyleSheet(f"color: {ACCENT}; font-size: {FONT_SIZE_SMALL}px; font-weight: 600;")
        layout.addWidget(tip)

        topic_title = QLabel("请选择要回顾的知识点模块：")
        topic_title.setStyleSheet("font-weight: 600; margin-top: 8px;")
        layout.addWidget(topic_title)

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
        grid.setSpacing(16)

        card_style = f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: {CARD_RADIUS}px;
            }}
            QFrame:hover {{
                background-color: {CARD_HOVER};
                border-color: {ACCENT};
                border-width: 2px;
            }}
        """

        for i, (full, short) in enumerate(zip(topics_full, topics_short)):
            gr = i // 3
            gc = i % 3

            card = QFrame()
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setStyleSheet(card_style)
            card.setMinimumHeight(80)

            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(12)
            shadow.setOffset(0, 3)
            shadow.setColor(QColor(60, 120, 70, 15))
            card.setGraphicsEffect(shadow)

            card_inner = QVBoxLayout(card)
            card_inner.setContentsMargins(14, 12, 14, 12)
            card_inner.setSpacing(4)

            num_lbl = QLabel(f"{i + 1}. {short}")
            num_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 600; font-size: {FONT_SIZE_SMALL}px;")
            num_lbl.setWordWrap(True)
            num_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            card_inner.addWidget(num_lbl)

            hint_lbl = QLabel("点击选择 →")
            hint_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px;")
            hint_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            card_inner.addWidget(hint_lbl)
            card_inner.addStretch()

            def make_handler(f=full, idx=i):
                return lambda: (
                    self.c_qa_review_selected.emit(str(idx), f),
                    dlg.accept(),
                )
            card.mousePressEvent = lambda e, h=make_handler(): h()

            grid.addWidget(card, gr, gc)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll, 1)

        dlg.exec()
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
                background-color: {PAGE_BG};
                font-family: {FONT_SANS};
            }}
            QLabel {{
                color: {TEXT_PRIMARY};
                font-family: {FONT_SANS};
                font-size: {FONT_SIZE}px;
            }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

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
        grid.setSpacing(20)

        # General button — full row
        general_style = f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_MD}px;
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
        card_style = f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: {CARD_RADIUS}px;
            }}
            QFrame:hover {{
                background-color: {CARD_HOVER};
                border-color: {ACCENT};
                border-width: 2px;
            }}
        """

        for i, (full, short) in enumerate(zip(topics_full, topics_short)):
            gr = i // 3 + 1
            gc = i % 3

            topic_data = topics_data.get(str(i), {})
            level = topic_data.get("level", 0)

            card = QFrame()
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setStyleSheet(card_style)
            card.setMinimumHeight(100)

            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(16)
            shadow.setOffset(0, 4)
            shadow.setColor(QColor(60, 120, 70, 20))
            card.setGraphicsEffect(shadow)

            card_inner = QVBoxLayout(card)
            card_inner.setContentsMargins(16, 14, 16, 14)
            card_inner.setSpacing(6)

            num_lbl = QLabel(f"{i + 1}. {short}")
            num_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 700; font-size: {FONT_SIZE}px;")
            num_lbl.setWordWrap(True)
            num_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            card_inner.addWidget(num_lbl)

            card_inner.addStretch()

            # Badge
            badge_layout = QHBoxLayout()
            badge_layout.setContentsMargins(0, 0, 0, 0)
            if level >= 3:
                badge_text = LEVEL_LABELS.get(level, f"Lv.{level}")
                badge_bg = BADGE_DONE_BG
                badge_color = BADGE_DONE_TEXT
            elif level > 0:
                badge_text = LEVEL_LABELS.get(level, f"Lv.{level}")
                badge_bg = BADGE_PENDING_BG
                badge_color = TEXT_SECONDARY
            else:
                badge_text = "未学习"
                badge_bg = BADGE_PENDING_BG
                badge_color = BADGE_PENDING_TEXT

            badge = QLabel(f"[ {badge_text} ]")
            badge.setStyleSheet(f"""
                background-color: {badge_bg};
                color: {badge_color};
                font-weight: 600;
                font-size: {FONT_SIZE_SMALL - 1}px;
                border-radius: 10px;
                padding: 4px 12px;
            """)
            badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            badge_layout.addWidget(badge)
            badge_layout.addStretch()
            card_inner.addLayout(badge_layout)

            # Make card clickable
            def make_handler(f=full, idx=i):
                return lambda: (
                    self.c_qa_topic_selected.emit(
                        f"请给我详细讲解以下知识点：{idx + 1} — {f}"
                    ),
                    dlg.accept(),
                )
            card.mousePressEvent = lambda e, h=make_handler(): h()

            grid.addWidget(card, gr, gc)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)
        current_sid = self._current_session_id
        dlg.exec()
        self.refresh()
        if current_sid:
            self.select_session(current_sid)

    def _group_sessions(self, sessions: list[dict]) -> list[tuple[str, list[dict]]]:
        """Group sessions by date: Today, Yesterday, This Week, Earlier."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        buckets: dict[str, list[dict]] = {"今天": [], "昨天": [], "本周": [], "更早": []}
        for s in sessions:
            created = s.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created).date()
            except (ValueError, TypeError):
                buckets["更早"].append(s)
                continue

            if dt == today:
                buckets["今天"].append(s)
            elif dt == yesterday:
                buckets["昨天"].append(s)
            elif dt >= week_ago:
                buckets["本周"].append(s)
            else:
                buckets["更早"].append(s)

        return [(label, items) for label, items in buckets.items() if items]

    def _format_time(self, created_at: str) -> str:
        """Format created_at as human-readable time subtitle."""
        try:
            dt = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            return ""
        now = datetime.now()
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        elif dt.date() >= now.date() - timedelta(days=7):
            weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            return f"{weekdays[dt.weekday()]} {dt.strftime('%H:%M')}"
        else:
            return dt.strftime("%m-%d %H:%M")

    def refresh(self):
        """Rebuild session list grouped by time."""
        while self._session_layout.count() > 1:
            item = self._session_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._session_frames.clear()

        sessions = list_sessions()
        groups = self._group_sessions(sessions)

        for group_label, group_sessions in groups:
            header = QLabel(group_label)
            header.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-weight: 600;"
                f"font-size: {FONT_SIZE_SMALL + 1}px;"
                f"padding: 16px 8px 4px 8px;"
            )
            self._session_layout.insertWidget(
                self._session_layout.count() - 1, header
            )

            for session in group_sessions:
                sid = session["id"]
                title = session.get("title", "新对话")
                time_str = self._format_time(session.get("created_at", ""))

                row = QFrame()
                row.setCursor(Qt.CursorShape.PointingHandCursor)
                row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                row.customContextMenuRequested.connect(
                    lambda pos, s=sid, t=title, f=row: self._on_session_menu(pos, s, t, f)
                )
                row.mousePressEvent = lambda e, s=sid: self._on_session_click(s)
                row.setMinimumHeight(46)

                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(8, 5, 8, 5)
                row_layout.setSpacing(1)

                title_lbl = QLabel(title)
                title_lbl.setObjectName("session_title")
                title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                title_lbl.setWordWrap(True)
                row_layout.addWidget(title_lbl)

                if time_str:
                    time_lbl = QLabel(time_str)
                    time_lbl.setObjectName("session_time")
                    time_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    row_layout.addWidget(time_lbl)

                self._session_frames[sid] = row
                row.installEventFilter(self)
                self._apply_session_style(row, sid == self._current_session_id)
                self._session_layout.insertWidget(
                    self._session_layout.count() - 1, row
                )

    def _apply_session_style(self, row: QFrame, selected: bool):
        # Store selected state as a dynamic property so the event filter
        # can read it without an extra dict lookup.
        row.setProperty("_selected", selected)
        row.setAutoFillBackground(True)

        if selected:
            row.setStyleSheet(
                f"QFrame {{ background-color: {ACCENT}; border-radius: 8px; }}"
            )
            title_color = TEXT_WHITE
            title_weight = "600"
            time_color = "rgba(255,255,255,0.7)"
        else:
            row.setStyleSheet(
                f"QFrame {{ background: transparent; border-radius: 8px; }}"
            )
            title_color = TEXT_PRIMARY
            title_weight = "normal"
            time_color = TEXT_SECONDARY

        # Style child labels individually — avoids cascade interference.
        title_lbl = row.findChild(QLabel, "session_title")
        if title_lbl:
            title_lbl.setStyleSheet(
                f"color: {title_color}; font-weight: {title_weight};"
                f"font-size: {FONT_SIZE}px; background: transparent;"
            )

        time_lbl = row.findChild(QLabel, "session_time")
        if time_lbl:
            time_lbl.setStyleSheet(
                f"color: {time_color}; font-size: {FONT_SIZE_SMALL - 1}px;"
                f"background: transparent;"
            )

    def eventFilter(self, obj, event):
        """Hover highlight for unselected session rows."""
        if event.type() == QEvent.Type.Enter:
            selected = obj.property("_selected")
            if not selected:
                obj.setStyleSheet(
                    f"QFrame {{ background-color: {FILE_SELECTION}; border-radius: 8px; }}"
                )
                self._restyle_children(obj, hover=True)
        elif event.type() == QEvent.Type.Leave:
            selected = obj.property("_selected")
            if not selected:
                obj.setStyleSheet(
                    f"QFrame {{ background: transparent; border-radius: 8px; }}"
                )
                self._restyle_children(obj, hover=False)
        return super().eventFilter(obj, event)

    def _restyle_children(self, row: QFrame, hover: bool):
        """Re-apply child QLabel styles after a parent stylesheet change."""
        title_lbl = row.findChild(QLabel, "session_title")
        if title_lbl:
            title_lbl.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: {FONT_SIZE}px;"
                f"background: transparent;"
            )
        time_lbl = row.findChild(QLabel, "session_time")
        if time_lbl:
            time_lbl.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL - 1}px;"
                f"background: transparent;"
            )

    def select_session(self, session_id: str):
        """Highlight the session frame and scroll to it."""
        old_sid = self._current_session_id
        self._current_session_id = session_id

        # Un-highlight old
        if old_sid and old_sid in self._session_frames:
            self._apply_session_style(self._session_frames[old_sid], False)

        # Highlight new
        if session_id in self._session_frames:
            frame = self._session_frames[session_id]
            self._apply_session_style(frame, True)
            self._session_scroll.ensureWidgetVisible(frame)

    def _on_new(self):
        session_id = create_session("新对话")
        self.refresh()
        self.select_session(session_id)
        self.new_session.emit()
        self.session_selected.emit(session_id)

    def _on_session_click(self, session_id: str):
        self.select_session(session_id)
        self.session_selected.emit(session_id)

    def _on_session_menu(self, pos, session_id: str, title: str, row: QFrame):
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除")
        action = menu.exec(row.mapToGlobal(pos))
        if action == rename_action:
            new_title, ok = QInputDialog.getText(
                self, "重命名", "新名称:", text=title,
            )
            if ok and new_title.strip():
                rename_session(session_id, new_title.strip())
                self.refresh()
                if session_id == self._current_session_id:
                    self.select_session(session_id)
        elif action == delete_action:
            delete_session(session_id)
            self.refresh()
            if session_id == self._current_session_id:
                self._current_session_id = None
            self.session_deleted.emit(session_id)

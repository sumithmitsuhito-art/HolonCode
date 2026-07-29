"""Level selection dialog for c-tutor: grouped grid of levels with card-based design."""

import json
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from atri.ui.theme import (
    PAGE_BG,
    ACCENT,
    BADGE_DONE_BG,
    BADGE_DONE_TEXT,
    BADGE_PENDING_BG,
    BADGE_PENDING_TEXT,
    BORDER,
    CARD_BG,
    CARD_HOVER,
    CARD_RADIUS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    FONT_SANS,
    FONT_SIZE,
    FONT_SIZE_SMALL,
)
from atri import DATA_DIR

C_TUTOR_PROGRESS = DATA_DIR / "c-tutor-progress.json"

C_TUTOR_LEVELS = [
    # === 入门基础 ===
    ("01", "Hello World 与程序结构", "code"),
    ("02", "变量与数据类型", "code"),
    ("17", "常量与格式化输入输出", "code"),
    ("debug01", "基础语法排错", "debug"),
    ("choice01", "基础概念选择", "choice"),
    ("choice03", "数据类型与标识符选择", "choice"),
    ("fill04", "程序结构与数据类型填空", "fill"),
    # === 运算符与表达式 ===
    ("03", "运算符与表达式", "code"),
    ("18", "表达式求值与类型转换", "code"),
    ("debug09", "运算符与表达式排错", "debug"),
    ("choice04", "运算符与表达式选择", "choice"),
    ("fill05", "运算符与表达式填空", "fill"),
    # === 流程控制 ===
    ("04", "分支结构", "code"),
    ("debug02", "控制流排错", "debug"),
    ("05", "循环结构", "code"),
    ("19", "循环进阶——嵌套与图案输出", "code"),
    ("debug10", "分支结构排错", "debug"),
    ("fill01", "控制流填空", "fill"),
    ("fill06", "循环进阶填空", "fill"),
    ("choice05", "流程控制选择", "choice"),
    # === 数组 ===
    ("06", "一维数组", "code"),
    ("20", "二维数组", "code"),
    ("21", "字符数组与字符串基础", "code"),
    ("debug03", "数组与循环排错", "debug"),
    ("debug11", "二维数组与边界排错", "debug"),
    ("choice02", "数组与循环选择", "choice"),
    ("fill07", "数组填空", "fill"),
    # === 函数 ===
    ("07", "函数基础", "code"),
    ("22", "递归函数入门", "code"),
    ("23", "函数进阶——作用域与存储类别", "code"),
    ("debug04", "指针排错", "debug"),
    ("debug12", "函数与递归排错", "debug"),
    ("choice06", "函数选择", "choice"),
    ("fill08", "函数填空", "fill"),
    # === 指针 ===
    ("08", "指针基础", "code"),
    ("24", "指针与数组", "code"),
    ("25", "指针与字符串", "code"),
    ("26", "多级指针与指针数组", "code"),
    ("debug13", "指针进阶排错", "debug"),
    ("choice07", "指针选择", "choice"),
    ("fill02", "指针与字符串填空", "fill"),
    # === 字符串与结构体 ===
    ("09", "字符串处理", "code"),
    ("27", "结构体基础", "code"),
    ("28", "结构体进阶——嵌套与结构体数组", "code"),
    ("29", "共用体与枚举类型", "code"),
    ("10", "结构体与文件操作", "code"),
    ("debug05", "综合排错 I", "debug"),
    ("debug14", "结构体与共用体排错", "debug"),
    ("choice08", "结构体与共用体选择", "choice"),
    ("fill09", "结构体填空", "fill"),
    # === 文件操作 ===
    ("30", "文件操作进阶——随机读写", "code"),
    ("31", "文件与结构体综合应用", "code"),
    ("debug15", "文件操作排错", "debug"),
    ("choice09", "文件操作选择", "choice"),
    # === 进阶主题 ===
    ("11", "动态内存分配", "code"),
    ("debug06", "内存管理排错", "debug"),
    ("12", "单向链表", "code"),
    ("13", "位运算", "code"),
    ("32", "编译预处理与宏", "code"),
    ("debug07", "综合排错 II", "debug"),
    ("debug16", "宏与位运算排错", "debug"),
    ("14", "递归与分治", "code"),
    ("15", "栈与队列", "code"),
    ("debug08", "数据结构排错", "debug"),
    ("16", "函数指针与回调", "code"),
    ("fill03", "进阶综合填空", "fill"),
    ("choice10", "进阶综合选择", "choice"),
    # === 综合实战 ===
    ("33", "综合实战——学生成绩管理系统", "code"),
    ("debug17", "综合实战排错", "debug"),
    ("fill10", "综合实战填空", "fill"),
]


def _sort_key(item):
    """Extract numeric part from level ID for natural ordering."""
    lid = item[0]
    num = "".join(c for c in lid if c.isdigit())
    return int(num) if num else 0


TYPE_GROUPS = [
    ("编程题", sorted([l for l in C_TUTOR_LEVELS if l[2] == "code"], key=_sort_key)),
    ("改错题", sorted([l for l in C_TUTOR_LEVELS if l[2] == "debug"], key=_sort_key)),
    ("选择/填空题", sorted([l for l in C_TUTOR_LEVELS if l[2] in ("choice", "fill")], key=_sort_key)),
]


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


class LevelSelectDialog(QDialog):
    """Dialog for selecting a c-tutor challenge level."""

    level_selected = Signal(str, str)  # (level_id, level_name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择闯关关卡")
        self.setMinimumSize(800, 550)
        self.resize(800, 550)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {PAGE_BG};
                font-family: {FONT_SANS};
            }}
        """)

        self._selected_emit = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        # ── Header ──────────────────────────────────────────────────
        progress = _read_json(C_TUTOR_PROGRESS)
        levels = progress.get("levels", {})
        total = len(C_TUTOR_LEVELS)
        completed = sum(
            1 for v in levels.values()
            if isinstance(v, dict) and v.get("completed")
        )
        pct = int(completed / total * 100) if total > 0 else 0

        header = QFrame()
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        header_left = QVBoxLayout()
        header_left.setSpacing(4)
        title_lbl = QLabel("C语言闯关训练")
        title_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {TEXT_PRIMARY};"
        )
        header_left.addWidget(title_lbl)
        progress_text = QLabel(f"已完成 {completed} / {total} 关")
        progress_text.setStyleSheet(
            f"font-size: {FONT_SIZE_SMALL}px; color: {TEXT_SECONDARY};"
        )
        header_left.addWidget(progress_text)
        header_layout.addLayout(header_left)
        header_layout.addStretch()

        pct_label = QLabel(f"{pct}%")
        pct_label.setStyleSheet(
            f"font-size: 28px; font-weight: 700; color: {ACCENT};"
        )
        header_layout.addWidget(pct_label)

        layout.addWidget(header)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        layout.addWidget(sep)

        # ── Scroll area ─────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 6px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(20)

        for group_title, group_levels in TYPE_GROUPS:
            group_label = QLabel(group_title)
            group_label.setStyleSheet(f"""
                font-weight: 600;
                font-size: {FONT_SIZE}px;
                color: {TEXT_SECONDARY};
                padding: 4px 0;
            """)
            container_layout.addWidget(group_label)

            grid = QGridLayout()
            grid.setSpacing(20)

            for i, (lid, name, _ltype) in enumerate(group_levels):
                gr, gc = divmod(i, 3)
                grid.addWidget(
                    self._make_card(lid, name, levels.get(lid)), gr, gc
                )

            container_layout.addLayout(grid)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self._fade_anim = anim

    def _make_card(self, lid: str, name: str, level_data: dict | None) -> QFrame:
        completed = bool(level_data and level_data.get("completed"))
        score = level_data.get("score", 0) if level_data else 0

        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
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
        """)
        card.setMinimumHeight(120)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(60, 120, 70, 20))
        card.setGraphicsEffect(shadow)

        card.mousePressEvent = lambda e, l=lid, n=name: self._on_select(l, n)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(20, 16, 20, 16)
        inner.setSpacing(6)

        # Level ID — large and bold
        id_lbl = QLabel(f"关卡 {lid}")
        id_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-weight: 700;"
            f"font-size: {FONT_SIZE + 4}px;"
        )
        id_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        inner.addWidget(id_lbl)

        # Title
        title_lbl = QLabel(name)
        title_lbl.setStyleSheet(f"color: #333; font-size: {FONT_SIZE}px;")
        title_lbl.setWordWrap(True)
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        inner.addWidget(title_lbl)

        inner.addStretch()

        # Badge — pill style, hug content
        badge_layout = QHBoxLayout()
        badge_layout.setContentsMargins(0, 0, 0, 0)

        if completed:
            badge_text = f"✓ 已完成 · {score}分"
            badge_bg = BADGE_DONE_BG
            badge_color = BADGE_DONE_TEXT
        else:
            badge_text = "进行中"
            badge_bg = BADGE_PENDING_BG
            badge_color = BADGE_PENDING_TEXT

        badge = QLabel(badge_text)
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
        inner.addLayout(badge_layout)

        return card

    def _on_select(self, lid: str, name: str):
        if self._selected_emit:
            return
        self._selected_emit = True
        self.level_selected.emit(lid, name)
        self.accept()

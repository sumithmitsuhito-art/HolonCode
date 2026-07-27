"""Level selection dialog for c-tutor: grouped grid of 19 levels."""

import json
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from atri.ui.theme import (
    BG_MAIN,
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_WHITE,
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

TYPE_GROUPS = [
    ("编程题", [l for l in C_TUTOR_LEVELS if l[2] == "code"]),
    ("改错题", [l for l in C_TUTOR_LEVELS if l[2] == "debug"]),
    ("选择/填空题", [l for l in C_TUTOR_LEVELS if l[2] in ("choice", "fill")]),
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
                background-color: {BG_MAIN};
                font-family: {FONT_SANS};
            }}
        """)

        self._selected_emit = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        title = QLabel("选择闯关关卡")
        title.setStyleSheet(f"font-size: {FONT_SIZE + 2}px; font-weight: bold;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; }}
            QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 6px; min-height: 30px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(16)

        progress = _read_json(C_TUTOR_PROGRESS)
        levels = progress.get("levels", {})

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
            grid.setSpacing(8)

            for i, (lid, name, ltype) in enumerate(group_levels):
                card = self._make_card(lid, name, ltype, levels.get(lid))
                row, col = divmod(i, 3)
                grid.addWidget(card, row, col)

            container_layout.addLayout(grid)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    def _make_card(self, lid: str, name: str, ltype: str, level_data: dict | None) -> QFrame:
        if level_data and level_data.get("completed"):
            status_text = f"得分: {level_data.get('score', 0)}"
        else:
            status_text = "进行中"

        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #81C784;
                border-left: 4px solid {ACCENT_HOVER};
                border-radius: 8px;
                padding: 12px;
            }}
            QFrame:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """)
        card.setMinimumHeight(80)
        card.mousePressEvent = lambda e, l=lid, n=name: self._on_select(l, n)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(4)

        title_lbl = QLabel(f"关卡 {lid}")
        title_lbl.setStyleSheet(f"color: {TEXT_WHITE}; font-weight: 600; font-size: {FONT_SIZE}px;")
        title_lbl.setWordWrap(True)
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        inner.addWidget(title_lbl)

        sub = QLabel(name)
        sub.setStyleSheet(f"color: rgba(255,255,255,0.8); font-size: {FONT_SIZE_SMALL}px;")
        sub.setWordWrap(True)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        inner.addWidget(sub)

        status_lbl = QLabel(status_text)
        status_lbl.setStyleSheet(f"color: rgba(255,255,255,0.75); font-weight: 600; font-size: {FONT_SIZE_SMALL}px;")
        status_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        inner.addWidget(status_lbl)

        return card

    def _on_select(self, lid: str, name: str):
        if self._selected_emit:
            return
        self._selected_emit = True
        self.level_selected.emit(lid, name)
        self.accept()

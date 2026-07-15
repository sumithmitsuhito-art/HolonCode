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
    ("01", "Hello World 与程序结构", "code"),
    ("02", "变量与数据类型", "code"),
    ("debug01", "基础语法排错", "debug"),
    ("choice01", "基础概念选择", "choice"),
    ("03", "运算符与表达式", "code"),
    ("04", "分支结构", "code"),
    ("debug02", "控制流排错", "debug"),
    ("fill01", "控制流填空", "fill"),
    ("05", "循环结构", "code"),
    ("06", "数组", "code"),
    ("debug03", "数组与循环排错", "debug"),
    ("choice02", "数组与循环选择", "choice"),
    ("07", "函数", "code"),
    ("08", "指针基础", "code"),
    ("debug04", "指针排错", "debug"),
    ("09", "字符串", "code"),
    ("10", "结构体与文件操作", "code"),
    ("debug05", "综合排错", "debug"),
    ("fill02", "指针与字符串填空", "fill"),
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

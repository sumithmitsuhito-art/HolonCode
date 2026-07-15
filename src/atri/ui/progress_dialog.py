"""Progress viewer dialog: tabbed card-based visualization for c-tutor and c-learn progress."""

import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
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
C_LEARN_PROGRESS = DATA_DIR / "c-learn-progress.json"

LEVEL_LABELS = {1: "了解", 2: "理解", 3: "掌握", 4: "熟练"}

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

C_LEARN_TOPICS = [
    "声明语法",
    "数据类型系统",
    "运算符优先级与结合性",
    "表达式与隐式转换",
    "控制流语法",
    "函数高级语法",
    "数组语法",
    "指针完整体系",
    "字符串处理语法",
    "结构体语法",
    "联合体与枚举",
    "预处理器",
    "存储类别",
    "位操作语法",
    "文件与工程组织",
    "动态内存分配",
    "函数指针与回调",
    "const与volatile",
    "链表与基础数据结构",
    "可变参数与标准库",
    "typedef与类型别名",
    "编译过程详解",
    "调试技巧与断言",
    "多文件模块化设计",
    "C标准与跨平台",
    "常见陷阱与最佳实践",
    "综合实战项目",
]

TYPE_LABELS = {"code": "编程题", "debug": "改错题", "choice": "选择题", "fill": "填空题"}


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


class ProgressDialog(QDialog):
    """Tabbed dialog showing c-tutor and c-learn progress as cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("学习进度")
        self.setMinimumSize(800, 550)
        self.resize(800, 550)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_MAIN};
                font-family: {FONT_SANS};
            }}
        """)

        self._current_tab = "c-tutor"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        title = QLabel("学习进度")
        title.setStyleSheet(f"font-size: {FONT_SIZE + 2}px; font-weight: bold;")
        layout.addWidget(title)

        # Tab buttons
        tab_layout = QHBoxLayout()
        tab_layout.setSpacing(0)

        self._tutor_tab_btn = QPushButton("闯关进度")
        self._tutor_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tutor_tab_btn.clicked.connect(lambda: self._switch_tab("c-tutor"))
        tab_layout.addWidget(self._tutor_tab_btn)

        self._learn_tab_btn = QPushButton("知识点进度")
        self._learn_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._learn_tab_btn.clicked.connect(lambda: self._switch_tab("c-learn"))
        tab_layout.addWidget(self._learn_tab_btn)

        tab_layout.addStretch()
        layout.addLayout(tab_layout)

        # Scrollable card area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; }}
            QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 6px; min-height: 30px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        self._card_widget = QWidget()
        self._card_layout = QGridLayout(self._card_widget)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(8)
        self._scroll.setWidget(self._card_widget)
        layout.addWidget(self._scroll, 1)

        # Bottom: clear button
        bottom = QHBoxLayout()
        bottom.addStretch()
        self._clear_btn = QPushButton("清空当前选项卡进度")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 10px;
                padding: 8px 20px;
                font-size: {FONT_SIZE_SMALL}px;
                outline: none;
            }}
            QPushButton:hover {{
                background: #FFE0E0;
                color: #C72E4D;
                border-color: #C72E4D;
            }}
        """)
        self._clear_btn.clicked.connect(self._on_clear)
        bottom.addWidget(self._clear_btn)
        layout.addLayout(bottom)

        self._switch_tab("c-tutor")

    def _switch_tab(self, tab: str):
        self._current_tab = tab
        active_style = f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {TEXT_WHITE};
                border: none;
                border-radius: 10px;
                padding: 8px 20px;
                font-weight: 600;
                font-size: {FONT_SIZE}px;
                outline: none;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                border-radius: 10px;
                padding: 8px 20px;
                font-size: {FONT_SIZE}px;
                outline: none;
            }}
            QPushButton:hover {{ color: {TEXT_PRIMARY}; }}
        """
        self._tutor_tab_btn.setStyleSheet(active_style if tab == "c-tutor" else inactive_style)
        self._learn_tab_btn.setStyleSheet(active_style if tab == "c-learn" else inactive_style)
        self._clear_btn.setText(
            "清空闯关进度" if tab == "c-tutor" else "清空知识点进度"
        )
        self._rebuild_cards()

    def _rebuild_cards(self):
        while self._card_layout.count():
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._current_tab == "c-tutor":
            self._build_tutor_cards()
        else:
            self._build_learn_cards()

    def _build_tutor_cards(self):
        progress = _read_json(C_TUTOR_PROGRESS)
        levels = progress.get("levels", {})

        for i, (lid, name, ltype) in enumerate(C_TUTOR_LEVELS):
            card = self._make_card(
                title=name,
                subtitle=f"关卡 {lid}  ·  {TYPE_LABELS.get(ltype, '')}",
                status_text=self._tutor_status(levels.get(lid)),
            )
            row, col = divmod(i, 3)
            self._card_layout.addWidget(card, row, col)

    def _build_learn_cards(self):
        progress = _read_json(C_LEARN_PROGRESS)
        topics = progress.get("topics", {})

        for i, name in enumerate(C_LEARN_TOPICS):
            topic = topics.get(str(i), {})
            level = topic.get("level", 0)
            card = self._make_card(
                title=f"{i + 1}. {name}",
                subtitle="",
                status_text=self._learn_status(level),
            )
            row, col = divmod(i, 3)
            self._card_layout.addWidget(card, row, col)

    def _make_card(self, title: str, subtitle: str, status_text: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #81C784;
                border-left: 4px solid {ACCENT_HOVER};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        card.setMinimumHeight(80)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {TEXT_WHITE}; font-weight: 600; font-size: {FONT_SIZE}px;")
        title_lbl.setWordWrap(True)
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        inner.addWidget(title_lbl)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet(f"color: rgba(255,255,255,0.8); font-size: {FONT_SIZE_SMALL}px;")
            sub.setWordWrap(True)
            sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            inner.addWidget(sub)

        status_lbl = QLabel(status_text)
        status_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        status_lbl.setStyleSheet(f"""
            color: rgba(255,255,255,0.75);
            font-weight: 600;
            font-size: {FONT_SIZE_SMALL}px;
        """)
        inner.addWidget(status_lbl)

        return card

    def _tutor_status(self, level_data: dict | None) -> str:
        if level_data and level_data.get("completed"):
            score = level_data.get("score", 0)
            return f"得分: {score}"
        return "进行中"

    def _learn_status(self, level: int) -> str:
        if level >= 4:
            return f"· {LEVEL_LABELS[4]}"
        elif level >= 3:
            return f"· {LEVEL_LABELS[3]}"
        elif level >= 2:
            return f"· {LEVEL_LABELS[2]}"
        elif level >= 1:
            return f"· {LEVEL_LABELS[1]}"
        return "— 未学习"

    def _on_clear(self):
        label = "闯关进度" if self._current_tab == "c-tutor" else "知识点进度"
        reply = QMessageBox.question(
            self,
            "确认清空",
            f"确定要清空所有{label}吗？\n此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._current_tab == "c-tutor":
            self._reset_tutor_progress()
        else:
            self._reset_learn_progress()
        self._rebuild_cards()

    def _reset_tutor_progress(self):
        data = {"total_score": 0, "total_levels": 19, "completed_levels": 0, "levels": {}}
        C_TUTOR_PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        C_TUTOR_PROGRESS.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _reset_learn_progress(self):
        data = {"total_topics": 27, "completed_topics": 0, "topics": {}}
        C_LEARN_PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        C_LEARN_PROGRESS.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

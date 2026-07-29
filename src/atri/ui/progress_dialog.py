"""Progress viewer dialog: card-based visualization for c-tutor and c-learn progress."""

import json
from pathlib import Path
from PySide6.QtCore import Qt, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
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
    PAGE_BG,
    ACCENT,
    ACCENT_HOVER,
    BADGE_DONE_BG,
    BADGE_DONE_TEXT,
    BADGE_PENDING_BG,
    BADGE_PENDING_TEXT,
    BORDER,
    CARD_BG,
    CARD_HOVER,
    CARD_RADIUS,
    DANGER,
    DANGER_BG,
    RADIUS_MD,
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


def _sort_key(item):
    lid = item[0]
    num = "".join(c for c in lid if c.isdigit())
    return int(num) if num else 0


TUTOR_SORTED = sorted(C_TUTOR_LEVELS, key=_sort_key)


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
                background-color: {PAGE_BG};
                font-family: {FONT_SANS};
            }}
        """)

        self._current_tab = "c-tutor"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        # ── Header ──────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        header_left = QVBoxLayout()
        header_left.setSpacing(4)
        title_lbl = QLabel("学习进度")
        title_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {TEXT_PRIMARY};"
        )
        header_left.addWidget(title_lbl)
        self._header_sub = QLabel("")
        self._header_sub.setStyleSheet(
            f"font-size: {FONT_SIZE_SMALL}px; color: {TEXT_SECONDARY};"
        )
        header_left.addWidget(self._header_sub)
        header_layout.addLayout(header_left)
        header_layout.addStretch()

        # Tab buttons
        self._tutor_tab_btn = QPushButton("闯关进度")
        self._tutor_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tutor_tab_btn.clicked.connect(lambda: self._switch_tab("c-tutor"))
        header_layout.addWidget(self._tutor_tab_btn)

        self._learn_tab_btn = QPushButton("知识点进度")
        self._learn_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._learn_tab_btn.clicked.connect(lambda: self._switch_tab("c-learn"))
        header_layout.addWidget(self._learn_tab_btn)

        layout.addWidget(header)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        layout.addWidget(sep)

        # ── Scroll area ─────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 6px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self._card_widget = QWidget()
        self._card_layout = QGridLayout(self._card_widget)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(20)
        self._scroll.setWidget(self._card_widget)
        layout.addWidget(self._scroll, 1)

        # ── Bottom: clear button ────────────────────────────────────
        bottom = QHBoxLayout()
        bottom.addStretch()
        self._clear_btn = QPushButton("清空闯关进度")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_MD}px;
                padding: 8px 20px;
                font-size: {FONT_SIZE_SMALL}px;
                outline: none;
            }}
            QPushButton:hover {{
                background: {DANGER_BG};
                color: {DANGER};
                border-color: {DANGER};
            }}
            QPushButton:pressed {{
                background: {DANGER};
                color: {TEXT_WHITE};
            }}
        """)
        self._clear_btn.clicked.connect(self._on_clear)
        bottom.addWidget(self._clear_btn)
        layout.addLayout(bottom)

        self._switch_tab("c-tutor")

    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self._fade_anim = anim

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
        self._tutor_tab_btn.setStyleSheet(
            active_style if tab == "c-tutor" else inactive_style
        )
        self._learn_tab_btn.setStyleSheet(
            active_style if tab == "c-learn" else inactive_style
        )
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
        total = len(C_TUTOR_LEVELS)
        completed = sum(
            1 for v in levels.values()
            if isinstance(v, dict) and v.get("completed")
        )
        self._header_sub.setText(f"已完成 {completed} / {total} 关")

        for i, (lid, name, ltype) in enumerate(TUTOR_SORTED):
            data = levels.get(lid)
            card = self._make_card(
                title=name,
                subtitle=f"关卡 {lid}  ·  {TYPE_LABELS.get(ltype, '')}",
                completed=bool(data and data.get("completed")),
                score=data.get("score", 0) if data else 0,
                learn_level=0,
            )
            r, c = divmod(i, 3)
            self._card_layout.addWidget(card, r, c)

    def _build_learn_cards(self):
        progress = _read_json(C_LEARN_PROGRESS)
        topics = progress.get("topics", {})
        total = len(C_LEARN_TOPICS)
        completed = sum(
            1 for v in topics.values()
            if isinstance(v, dict) and v.get("level", 0) >= 2
        )
        self._header_sub.setText(f"已掌握 {completed} / {total} 个知识点")

        for i, name in enumerate(C_LEARN_TOPICS):
            topic = topics.get(str(i), {})
            level = topic.get("level", 0) if isinstance(topic, dict) else 0
            card = self._make_card(
                title=f"{i + 1}. {name}",
                subtitle="",
                completed=level >= 3,
                score=0,
                learn_level=level,
            )
            r, c = divmod(i, 3)
            self._card_layout.addWidget(card, r, c)

    def _make_card(self, title: str, subtitle: str, completed: bool,
                   score: int, learn_level: int) -> QFrame:
        card = QFrame()
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
        card.setMinimumHeight(110)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(60, 120, 70, 20))
        card.setGraphicsEffect(shadow)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(20, 16, 20, 16)
        inner.setSpacing(6)

        # Title
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-weight: 700;"
            f"font-size: {FONT_SIZE + 2}px;"
        )
        title_lbl.setWordWrap(True)
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        inner.addWidget(title_lbl)

        # Subtitle
        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}px;"
            )
            sub.setWordWrap(True)
            sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            inner.addWidget(sub)

        inner.addStretch()

        # Badge
        badge_layout = QHBoxLayout()
        badge_layout.setContentsMargins(0, 0, 0, 0)

        if learn_level > 0:
            badge_text = LEVEL_LABELS.get(learn_level, f"Lv.{learn_level}")
            badge_bg = _learn_badge_bg(learn_level)
            badge_color = BADGE_DONE_TEXT if learn_level >= 3 else TEXT_SECONDARY
        elif completed:
            badge_text = f"✓ 已完成 · {score}分"
            badge_bg = BADGE_DONE_BG
            badge_color = BADGE_DONE_TEXT
        elif subtitle:
            # Tutor cards without completion
            badge_text = "进行中"
            badge_bg = BADGE_PENDING_BG
            badge_color = BADGE_PENDING_TEXT
        else:
            badge_text = "— 未学习"
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
        data = {
            "total_score": 0, "total_levels": 70, "completed_levels": 0,
            "levels": {},
        }
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


def _learn_badge_bg(level: int) -> str:
    if level >= 4:
        return "#C8E6C9"
    elif level >= 3:
        return "#E8F5E9"
    elif level >= 2:
        return "#FFF9C4"
    return BADGE_PENDING_BG

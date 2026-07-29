# Sidebar 学习进度 & 关卡选择 & c-learn 进度追踪 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构侧边栏按钮功能，增加进度可视化窗口、关卡选择对话框、c-learn 进度追踪系统

**Architecture:** 新建 3 个文件（progress_dialog.py、level_select_dialog.py、c-learn/plugin.py），修改 3 个文件（sidebar.py、app_shell.py、c-learn/SKILL.md）。进度数据分两套独立存储（c-tutor-progress.json + c-learn-progress.json），通过双选项卡对话框可视化展示。

**Tech Stack:** PySide6 QDialog / QFrame 卡片布局、Python json 存储、SkillLoader @tool 装饰器

---

### Task 1: 创建 c-learn 进度追踪 plugin.py

**Files:**
- Create: `skills/c-learn/plugin.py`

**Step 1: 编写完整 plugin.py**

参考 `skills/c-tutor/plugin.py` 的结构，使用 `c_learn_` 前缀避免 tool 名称冲突。

```python
"""C-learn progress management: load/save/reset knowledge-point mastery progress.

Progress is stored in data/c-learn-progress.json.

When loaded via SkillLoader.load_plugin(), the @tool decorator is injected
into the module namespace before exec.  For direct imports (tests), the
fallback no-op decorator keeps function signatures unchanged.
"""

import json
from datetime import date
from atri import DATA_DIR

PROGRESS_FILE = DATA_DIR / "c-learn-progress.json"

try:
    tool  # noqa: F823 — injected by SkillLoader
except NameError:
    def tool(func=None, **kwargs):
        """No-op fallback for when plugin is imported outside SkillLoader."""
        if func is None:
            return lambda f: f
        return func


def _default_progress() -> dict:
    return {
        "total_topics": 27,
        "completed_topics": 0,
        "topics": {},
    }


def _read_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return _default_progress()
    try:
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _default_progress()


def _write_progress(data: dict):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_FILE)


@tool
def c_learn_load_progress():
    """读取C语言知识点学习的当前进度，包括所有27个知识点的掌握等级（1=了解/2=理解/3=掌握/4=熟练）。"""
    return _read_progress()


@tool
def c_learn_save_progress(topic_id: str, level: int, note: str = ""):
    """保存某个知识点的掌握程度。topic_id为知识点编号(0-26)，level为掌握等级(1=了解/2=理解/3=掌握/4=熟练)，note为可选备注。"""
    data = _read_progress()
    topic_id = str(topic_id)
    prev = data["topics"].get(topic_id, {})
    prev_level = prev.get("level", 0)
    data["topics"][topic_id] = {
        "name": prev.get("name", ""),
        "level": level,
        "updated_at": date.today().isoformat(),
        "note": note or prev.get("note", ""),
    }
    if prev_level == 0 and level > 0:
        data["completed_topics"] = data.get("completed_topics", 0) + 1
    elif prev_level > 0 and level == 0:
        data["completed_topics"] = max(0, data.get("completed_topics", 0) - 1)
    _write_progress(data)
    return {
        "topic_id": topic_id,
        "level": level,
        "completed_topics": data["completed_topics"],
        "total_topics": data["total_topics"],
    }


@tool
def c_learn_reset_progress(confirm: str):
    """清空所有知识点学习进度（不可恢复）。confirm 必须为 "yes" 才会执行。"""
    if confirm != "yes":
        return "请将 confirm 参数设为 'yes' 以确认清空全部知识点学习进度。"
    _write_progress(_default_progress())
    return "所有知识点学习进度已清空。"
```

**Step 2: 验证 plugin 可被加载**

```bash
cd D:\ClaudeCodeWorkSpace\DSPark-Code && uv run python -c "from atri.skill_loader import SkillLoader; m = SkillLoader.load_plugin('c-learn'); print(m.c_learn_load_progress())"
```
Expected: 打印默认进度 JSON `{"total_topics": 27, "completed_topics": 0, "topics": {}}`

**Step 3: 提交**

```bash
git add skills/c-learn/plugin.py
git commit -m "feat: add c-learn progress tracking plugin with c_learn_ prefixed tools

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 更新 c-learn SKILL.md 增加进度记录指令

**Files:**
- Modify: `skills/c-learn/SKILL.md`

**Step 1: 在"行为准则"部分末尾追加进度记录规则**

在 SKILL.md 中 `## 行为准则` 部分末尾（"答疑后追问规则"之前），插入以下内容：

```markdown
### 进度记录

> 每次答疑前后必须检查并更新学习进度，确保学习轨迹可追踪。

- 答疑开始时，先调用 c_learn_load_progress 查看用户的知识点掌握情况
- 已掌握的知识点简要回顾即可，不需要从头讲解；未学过的知识点从基础开始
- 答疑结束后，评估用户对当前知识点的掌握程度，调用 c_learn_save_progress 更新进度
- 等级判断标准：
  - **了解(1)**：用户大概知道这个概念，能用自己的话描述但写不出代码
  - **理解(2)**：用户能写出简单代码，但遇到变化或边界情况需要帮助
  - **掌握(3)**：用户能独立写出正确代码，能回答追问问题
  - **熟练(4)**：用户不仅能写代码，还能指出更好的写法、解释底层原理
- 如果用户的学习涉及多个知识点，分别更新每个知识点的掌握等级
- 用户说"标记XX为已掌握/熟练"等，按用户要求更新对应知识点等级
```

**Step 2: 提交**

```bash
git add skills/c-learn/SKILL.md
git commit -m "feat: add progress recording rules to c-learn SKILL.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 创建进度查看对话框 progress_dialog.py

**Files:**
- Create: `src/atri/ui/progress_dialog.py`

**Step 1: 编写 ProgressDialog**

```python
"""Progress viewer dialog: tabbed card-based visualization for c-tutor and c-learn progress."""

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
    BG_SIDEBAR,
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_WHITE,
    FONT_SANS,
    FONT_SIZE,
    FONT_SIZE_SMALL,
    STATUS_SUCCESS,
    STATUS_WARNING,
)
from atri import DATA_DIR

C_TUTOR_PROGRESS = DATA_DIR / "c-tutor-progress.json"
C_LEARN_PROGRESS = DATA_DIR / "c-learn-progress.json"

# Level labels and colors for c-learn
LEVEL_LABELS = {1: "了解", 2: "理解", 3: "掌握", 4: "熟练"}
LEVEL_COLORS = {1: "#9CA3AF", 2: "#3B82F6", 3: "#10B981", 4: "#F59E0B"}

# c-tutor level definitions (matching SKILL.md)
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

# c-learn topic names (matching SKILL.md and sidebar dialog)
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

TYPE_ICONS = {"code": "💻", "debug": "🐛", "choice": "📝", "fill": "✏️"}


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import json
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

        # Title
        title = QLabel("📊 学习进度")
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
        self._clear_btn = QPushButton("🗑 清空当前选项卡进度")
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
            "🗑 清空闯关进度" if tab == "c-tutor" else "🗑 清空知识点进度"
        )
        self._rebuild_cards()

    def _rebuild_cards(self):
        # Clear existing cards
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
                title=f"{TYPE_ICONS.get(ltype, '')} {lid}",
                subtitle=name,
                status=self._tutor_status(levels.get(lid)),
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
                status=self._learn_status(level),
            )
            row, col = divmod(i, 3)
            self._card_layout.addWidget(card, row, col)

    def _make_card(self, title: str, subtitle: str, status: tuple) -> QFrame:
        status_text, status_color, border_color = status
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SIDEBAR};
                border-left: 4px solid {border_color};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        card.setMinimumHeight(80)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-weight: 600; font-size: {FONT_SIZE}px;")
        title_lbl.setWordWrap(True)
        inner.addWidget(title_lbl)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}px;")
            sub.setWordWrap(True)
            inner.addWidget(sub)

        status_lbl = QLabel(status_text)
        status_lbl.setStyleSheet(f"""
            color: {status_color};
            font-weight: 600;
            font-size: {FONT_SIZE_SMALL}px;
        """)
        inner.addWidget(status_lbl)

        return card

    def _tutor_status(self, level_data: dict | None) -> tuple:
        if level_data and level_data.get("completed"):
            score = level_data.get("score", 0)
            return (f"✅ 得分: {score}", STATUS_SUCCESS, "#43A047")
        return ("🔄 进行中", TEXT_SECONDARY, BORDER)

    def _learn_status(self, level: int) -> tuple:
        if level >= 4:
            return (f"🏅 {LEVEL_LABELS[4]}", LEVEL_COLORS[4], LEVEL_COLORS[4])
        elif level >= 3:
            return (f"✅ {LEVEL_LABELS[3]}", LEVEL_COLORS[3], LEVEL_COLORS[3])
        elif level >= 2:
            return (f"📘 {LEVEL_LABELS[2]}", LEVEL_COLORS[2], LEVEL_COLORS[2])
        elif level >= 1:
            return (f"📙 {LEVEL_LABELS[1]}", LEVEL_COLORS[1], LEVEL_COLORS[1])
        return ("— 未学习", TEXT_SECONDARY, BORDER)

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
        import json
        data = {"total_score": 0, "total_levels": 19, "completed_levels": 0, "levels": {}}
        C_TUTOR_PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        C_TUTOR_PROGRESS.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _reset_learn_progress(self):
        import json
        data = {"total_topics": 27, "completed_topics": 0, "topics": {}}
        C_LEARN_PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        C_LEARN_PROGRESS.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
```

**Step 2: 验证模块可导入**

```bash
cd D:\ClaudeCodeWorkSpace\DSPark-Code && uv run python -c "from atri.ui.progress_dialog import ProgressDialog; print('OK')"
```
Expected: `OK`

**Step 3: 提交**

```bash
git add src/atri/ui/progress_dialog.py
git commit -m "feat: add ProgressDialog with tabbed tutor/learn progress cards

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 创建闯关关卡选择对话框 level_select_dialog.py

**Files:**
- Create: `src/atri/ui/level_select_dialog.py`

**Step 1: 编写 LevelSelectDialog**

```python
"""Level selection dialog for c-tutor: grouped grid of 19 levels."""

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
    BG_SIDEBAR,
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_WHITE,
    FONT_SANS,
    FONT_SIZE,
    FONT_SIZE_SMALL,
    STATUS_SUCCESS,
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
    ("💻 编程题", [l for l in C_TUTOR_LEVELS if l[2] == "code"]),
    ("🐛 改错题", [l for l in C_TUTOR_LEVELS if l[2] == "debug"]),
    ("📝 选择/填空题", [l for l in C_TUTOR_LEVELS if l[2] in ("choice", "fill")]),
]

TYPE_ICONS = {"code": "💻", "debug": "🐛", "choice": "📝", "fill": "✏️"}


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import json
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

        self._selected_emit = False  # avoid double emit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        title = QLabel("🎯 选择闯关关卡")
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
        icon = TYPE_ICONS.get(ltype, "")
        if level_data and level_data.get("completed"):
            status_text = f"✅ 得分: {level_data.get('score', 0)}"
            status_color = STATUS_SUCCESS
            border_color = "#43A047"
        else:
            status_text = "🔄 进行中"
            status_color = TEXT_SECONDARY
            border_color = BORDER

        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SIDEBAR};
                border-left: 4px solid {border_color};
                border-radius: 8px;
                padding: 12px;
            }}
            QFrame:hover {{
                background-color: {ACCENT};
            }}
        """)
        card.setMinimumHeight(80)
        card.mousePressEvent = lambda e, l=lid, n=name: self._on_select(l, n)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(4)

        title_lbl = QLabel(f"{icon} 关卡 {lid}")
        title_lbl.setStyleSheet(f"font-weight: 600; font-size: {FONT_SIZE}px;")
        title_lbl.setWordWrap(True)
        inner.addWidget(title_lbl)

        sub = QLabel(name)
        sub.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}px;")
        sub.setWordWrap(True)
        inner.addWidget(sub)

        status_lbl = QLabel(status_text)
        status_lbl.setStyleSheet(f"color: {status_color}; font-weight: 600; font-size: {FONT_SIZE_SMALL}px;")
        inner.addWidget(status_lbl)

        return card

    def _on_select(self, lid: str, name: str):
        if self._selected_emit:
            return
        self._selected_emit = True
        self.level_selected.emit(lid, name)
        self.accept()
```

**Step 2: 验证模块可导入**

```bash
cd D:\ClaudeCodeWorkSpace\DSPark-Code && uv run python -c "from atri.ui.level_select_dialog import LevelSelectDialog; print('OK')"
```
Expected: `OK`

**Step 3: 提交**

```bash
git add src/atri/ui/level_select_dialog.py
git commit -m "feat: add LevelSelectDialog with grouped card grid for c-tutor levels

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 修改 sidebar.py — 信号变更 + 优化知识点对话框 + 集成进度/关卡对话框

**Files:**
- Modify: `src/atri/ui/sidebar.py`

**Step 1: 更新 import**

在文件头部：
- 删掉 `QInputDialog`（重命名仍需要，保留）
- 删除 `from PySide6.QtWidgets import (QDialog, QGridLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget)` 中的已有导入
- 新增：`from atri.ui.progress_dialog import ProgressDialog, C_LEARN_PROGRESS, C_LEARN_TOPICS, LEVEL_LABELS, LEVEL_COLORS`
- 新增：`from atri.ui.level_select_dialog import LevelSelectDialog`
- 新增：`import json`

旧 imports 行：
```python
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
```

保持不变（所有需要的都存在）。

新增 imports（在 theme import 之后）：
```python
from atri.ui.progress_dialog import ProgressDialog
from atri.ui.level_select_dialog import LevelSelectDialog
import json
```

**Step 2: 替换 clear_progress 信号为 view_progress**

将：
```python
clear_progress = Signal()
```
改为：
```python
view_progress = Signal()
```

**Step 3: 新增 level_selected 信号**

在 `c_qa_topic_selected` 之后添加：
```python
level_selected = Signal(str, str)
```

**Step 4: 替换"清空学习进度"按钮为"查看学习进度"按钮**

将 clear_btn 的定义和连接改为：
```python
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
```

**Step 5: 修改"闯关"按钮 — 打开 LevelSelectDialog**

将：
```python
c_tutor_btn.clicked.connect(lambda: self.skill_activated.emit("c-tutor"))
```
改为：
```python
c_tutor_btn.clicked.connect(self._on_tutor_clicked)
```

新增方法：
```python
def _on_tutor_clicked(self):
    """Open level selection dialog for c-tutor."""
    dlg = LevelSelectDialog(self)
    dlg.level_selected.connect(
        lambda lid, name: self.level_selected.emit(lid, name)
    )
    dlg.exec()
```

**Step 6: 优化知识点对话框 — 卡片式布局 + 掌握等级标签**

替换 `_on_c_qa_clicked` 方法：

```python
def _on_c_qa_clicked(self):
    """Show C knowledge point selection dialog with card-based grid + mastery labels."""
    topics_short = C_LEARN_TOPICS
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
            background-color: {BG_SIDEBAR};
            border-left: 4px solid {BORDER};
            border-radius: 8px;
            padding: 4px;
        }}
        QFrame:hover {{
            background-color: {ACCENT};
            border-left-color: {ACCENT_HOVER};
        }}
    """

    for i, (full, short) in enumerate(zip(topics_full, topics_short)):
        row = i // 3 + 1  # +1 because row 0 is general button
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
        num_lbl.setStyleSheet(f"font-weight: 600; font-size: {FONT_SIZE_SMALL + 1}px;")
        num_lbl.setWordWrap(True)
        card_inner.addWidget(num_lbl)

        if level > 0:
            level_text = LEVEL_LABELS.get(level, "")
            level_color = LEVEL_COLORS.get(level, TEXT_SECONDARY)
            level_lbl = QLabel(f"[ {level_text} ]")
            level_lbl.setStyleSheet(f"color: {level_color}; font-weight: 600; font-size: {FONT_SIZE_SMALL}px;")
            card_inner.addWidget(level_lbl)

        # Make card clickable
        def make_handler(f=full, idx=i):
            return lambda: (
                self.c_qa_topic_selected.emit(
                    f"请给我详细讲解以下知识点：{idx + 1} — {f}"
                ),
                dlg.accept(),
            )
        card.mousePressEvent = lambda e, h=make_handler(): h()()

        grid.addWidget(card, row, col)

    scroll.setWidget(grid_widget)
    layout.addWidget(scroll)
    dlg.exec()
```

**Step 7: 提交**

```bash
git add src/atri/ui/sidebar.py
git commit -m "feat: replace clear_progress with view_progress, add level select, optimize topic dialog cards

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: 修改 app_shell.py — 信号连线 + 逻辑迁移

**Files:**
- Modify: `src/atri/ui/app_shell.py`

**Step 1: 新增 import**

在文件头部新增：
```python
from atri.ui.progress_dialog import ProgressDialog
```

**Step 2: 替换 clear_progress → view_progress 信号连接**

将：
```python
self.sidebar.clear_progress.connect(self._on_clear_progress)
```
改为：
```python
self.sidebar.view_progress.connect(self._on_view_progress)
```

**Step 3: 新增 level_selected 信号连接**

在 sidebar 信号连接区添加：
```python
self.sidebar.level_selected.connect(self._on_level_selected)
```

**Step 4: 删除 _on_clear_progress 方法，新增 _on_view_progress 和 _on_level_selected 方法**

删除整个 `_on_clear_progress` 方法（第 250-273 行）。

新增两个方法：
```python
def _on_view_progress(self):
    """Open the progress viewer dialog."""
    dlg = ProgressDialog(self)
    dlg.exec()

def _on_level_selected(self, level_id: str, level_name: str):
    """Activate c-tutor skill with specific level selected."""
    from atri.skill_loader import SkillLoader
    if not SkillLoader.skill_exists("c-tutor"):
        return
    result = self.ai_service.tool.tool_actor(
        "activate_skill",
        '{"name":"c-tutor"}',
        self.ai_service.active_skills,
    )
    self.chat_view.thread.add_skill_message(result)
    self.status_bar.set_status("技能已激活: c-tutor")
    self._update_status()
    # Auto-send level selection message
    if level_id.startswith("debug"):
        level_label = f"改错关卡 {level_id.replace('debug', '')}"
    elif level_id.startswith("choice"):
        level_label = f"选择题关卡 {level_id.replace('choice', '')}"
    elif level_id.startswith("fill"):
        level_label = f"填空题关卡 {level_id.replace('fill', '')}"
    else:
        level_label = f"关卡 {level_id}"
    self.chat_view.submit_text(f"开始闯关{level_label} — {level_name}")
```

**Step 5: 修改 _on_skill_activated 中 c-tutor 的处理逻辑**

c-tutor 不再需要通过 sidebar 直接 activate（现在通过 level_selected 触发），但当用户通过 `/c-tutor` slash 命令或手动激活时保留兜底行为。当前的 c-tutor 分支保持不变：

```python
if skill_name == "c-tutor":
    self.chat_view.submit_text("开始C语言知识闯关，先查看我的学习进度，然后从上次的进度继续")
```

**Step 6: 提交**

```bash
git add src/atri/ui/app_shell.py
git commit -m "feat: wire view_progress and level_selected signals, remove _on_clear_progress

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: 端到端验证

**Step 1: 验证所有模块可导入**

```bash
cd D:\ClaudeCodeWorkSpace\DSPark-Code && uv run python -c "
from atri.ui.progress_dialog import ProgressDialog
from atri.ui.level_select_dialog import LevelSelectDialog
from atri.skill_loader import SkillLoader
m = SkillLoader.load_plugin('c-learn')
print('c_learn tools:', [t.function.name for t in SkillLoader.extract_tools(m)])
print('All imports OK')
"
```
Expected: `c_learn tools: ['c_learn_load_progress', 'c_learn_save_progress', 'c_learn_reset_progress']` 然后 `All imports OK`

**Step 2: 启动 GUI 验证无崩溃**

```bash
cd D:\ClaudeCodeWorkSpace\DSPark-Code && timeout 5 uv run atri-ui 2>&1 || true
```
Expected: 窗口启动无 Python 异常（5 秒后自动关闭）

**Step 3: 提交（如有遗漏变更）**

```bash
git status
```

---

### 文件变更总览

| 文件 | 操作 | Task |
|------|------|------|
| `skills/c-learn/plugin.py` | 新建 | 1 |
| `skills/c-learn/SKILL.md` | 修改 | 2 |
| `src/atri/ui/progress_dialog.py` | 新建 | 3 |
| `src/atri/ui/level_select_dialog.py` | 新建 | 4 |
| `src/atri/ui/sidebar.py` | 修改 | 5 |
| `src/atri/ui/app_shell.py` | 修改 | 6 |

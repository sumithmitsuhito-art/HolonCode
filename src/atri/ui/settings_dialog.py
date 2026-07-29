"""Settings dialog for editing UserSettings.json and SOUL.json."""

import json
from pathlib import Path
from PySide6.QtCore import Qt, QPropertyAnimation
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from atri import DATA_DIR
from atri.ui import theme as _theme
from atri.ui.theme import (
    ACCENT,
    ACCENT_HOVER,
    BORDER,
    BG_INPUT,
    FONT_SANS,
    FONT_SIZE,
    FONT_SIZE_SMALL,
    RADIUS_MD,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_WHITE,
)

_USER_SETTINGS = DATA_DIR / "UserSettings.json"
_SOUL = DATA_DIR / "SOUL.json"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class SettingsDialog(QDialog):
    """Configuration dialog for API and persona settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(620, 520)
        self.setMinimumSize(500, 400)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_api_tab(), "API 设置")
        self._tabs.addTab(self._build_soul_tab(), "角色设定")
        self._tabs.addTab(self._build_learning_tab(), "学习设置")
        self._tabs.addTab(self._build_display_tab(), "显示")
        root.addWidget(self._tabs, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        cancel = QPushButton("取消")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_MD}px;
                padding: 8px 20px;
                font-size: {FONT_SIZE}px;
                font-weight: normal;
            }}
            QPushButton:hover {{
                background: {BG_INPUT};
                border-color: {TEXT_SECONDARY};
            }}
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("保存")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {TEXT_WHITE};
                border: none;
                border-radius: {RADIUS_MD}px;
                padding: 8px 24px;
                font-size: {FONT_SIZE}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """)
        save.clicked.connect(self._on_save)
        btn_row.addWidget(save)

        root.addLayout(btn_row)

    # ── API tab ────────────────────────────────────────────────────────

    def _build_api_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        desc = QLabel("DeepSeek API 配置，修改后需要重启应用生效。")
        desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(10)

        config = _read_json(_USER_SETTINGS)
        ds = config.get("DeepSeek", {})

        self._api_key = QLineEdit(ds.get("ApiKey", ""))
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setPlaceholderText("sk-...")
        form.addRow("ApiKey", self._api_key)

        self._api_url = QLineEdit(ds.get("Url", "https://api.deepseek.com/chat/completions"))
        self._api_url.setPlaceholderText("https://api.deepseek.com/chat/completions")
        form.addRow("Url", self._api_url)

        self._api_model = QLineEdit(ds.get("Model", "deepseek-chat"))
        self._api_model.setPlaceholderText("deepseek-chat")
        form.addRow("Model", self._api_model)

        layout.addLayout(form)
        layout.addStretch()
        return w

    # ── Soul tab ───────────────────────────────────────────────────────

    def _build_soul_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        desc = QLabel("角色设定（SOUL.json），每行一条，空行会被自动忽略。")
        desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(desc)

        self._soul_edit = QTextEdit()
        self._soul_edit.setAcceptRichText(False)
        self._soul_edit.setStyleSheet(
            f"background-color: {BG_INPUT};"
            f"color: {TEXT_PRIMARY};"
            f"border: 1px solid {BORDER};"
            f"border-radius: 10px;"
            f"padding: 12px;"
            f"font-family: {FONT_SANS};"
            f"font-size: {FONT_SIZE}px;"
        )

        soul = _read_json(_SOUL)
        prompt = soul.get("prompt", [])
        if isinstance(prompt, list):
            lines = [line for line in prompt if isinstance(line, str) and line.strip()]
            self._soul_edit.setPlainText("\n".join(lines))
        elif isinstance(prompt, str):
            self._soul_edit.setPlainText(prompt)

        layout.addWidget(self._soul_edit, 1)
        return w

    # ── Learning tab ──────────────────────────────────────────────────

    def _build_learning_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        desc = QLabel("C语言学习难度设置，AI 会根据此难度调整讲解深度。")
        desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(10)

        self._difficulty = QComboBox()
        self._difficulty.addItem("简单 — 适合零基础入门，用生活比喻、最基础的例子", "easy")
        self._difficulty.addItem("中等 — 适合有一定基础，涵盖常用语法和实践", "medium")
        self._difficulty.addItem("困难 — 适合进阶，深入底层原理、陷阱和最佳实践", "hard")
        self._difficulty.addItem("自适应 — AI 根据对话判断你的水平，自动调整难度", "adaptive")

        config = _read_json(_USER_SETTINGS)
        learning = config.get("Learning", {})
        current_diff = learning.get("Difficulty", "medium")
        idx = self._difficulty.findData(current_diff)
        if idx >= 0:
            self._difficulty.setCurrentIndex(idx)

        form.addRow("学习难度", self._difficulty)

        layout.addLayout(form)

        hint = QLabel(
            "提示：\n"
            "• 选择「自适应」后，AI 会在对话中评估你的理解程度，动态调整讲解难度\n"
            "• 你也可以在对话中随时说「讲简单点」或「讲深入点」来临时调整\n"
            "• 难度设置仅影响 C 语言学习/答疑相关技能的讲解方式"
        )
        hint.setStyleSheet(f"color: {TEXT_SECONDARY};")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()
        return w

    # ── Display tab ───────────────────────────────────────────────────

    def _build_display_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        desc = QLabel("调整聊天字体大小，即时生效。")
        desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(10)

        self._chat_font_size = QSpinBox()
        self._chat_font_size.setRange(10, 24)
        self._chat_font_size.setValue(_theme.CHAT_FONT_SIZE)
        self._chat_font_size.setSuffix(" px")
        self._chat_font_size.setFixedWidth(120)
        form.addRow("聊天字体大小", self._chat_font_size)

        layout.addLayout(form)
        layout.addStretch()
        return w

    # ── animation ──────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self._fade_anim = anim

    # ── save ───────────────────────────────────────────────────────────

    def _on_save(self):
        # Save UserSettings
        config = _read_json(_USER_SETTINGS)
        if "DeepSeek" not in config:
            config["DeepSeek"] = {}
        config["DeepSeek"]["ApiKey"] = self._api_key.text().strip()
        config["DeepSeek"]["Url"] = self._api_url.text().strip()
        config["DeepSeek"]["Model"] = self._api_model.text().strip()

        # Save learning difficulty
        if "Learning" not in config:
            config["Learning"] = {}
        config["Learning"]["Difficulty"] = self._difficulty.currentData()

        # Save UI settings
        if "UI" not in config:
            config["UI"] = {}
        config["UI"]["ChatFontSize"] = self._chat_font_size.value()

        _write_json(_USER_SETTINGS, config)

        # Save SOUL
        soul_text = self._soul_edit.toPlainText().strip()
        lines = [line for line in soul_text.split("\n") if line.strip()]
        _write_json(_SOUL, {"prompt": lines})

        # Apply font size immediately
        _theme.CHAT_FONT_SIZE = self._chat_font_size.value()

        self.accept()

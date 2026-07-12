"""Settings dialog for editing UserSettings.json and SOUL.json."""

import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from atri import DATA_DIR
from atri.ui.theme import (
    BORDER,
    BG_INPUT,
    FONT_SANS,
    FONT_SIZE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
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
        root.addWidget(self._tabs, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton("取消")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("保存")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
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

    # ── save ───────────────────────────────────────────────────────────

    def _on_save(self):
        # Save UserSettings
        config = _read_json(_USER_SETTINGS)
        if "DeepSeek" not in config:
            config["DeepSeek"] = {}
        config["DeepSeek"]["ApiKey"] = self._api_key.text().strip()
        config["DeepSeek"]["Url"] = self._api_url.text().strip()
        config["DeepSeek"]["Model"] = self._api_model.text().strip()
        _write_json(_USER_SETTINGS, config)

        # Save SOUL
        soul_text = self._soul_edit.toPlainText().strip()
        lines = [line for line in soul_text.split("\n") if line.strip()]
        _write_json(_SOUL, {"prompt": lines})

        self.accept()

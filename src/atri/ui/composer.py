"""Bottom input area: multi-line text input + send button + skill autocomplete."""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QTextEdit, QVBoxLayout,
)
from atri.ui import theme as _theme
from atri.ui.theme import (
    ACCENT, BG_INPUT, BG_SIDEBAR, BORDER, FONT_SANS, FONT_SIZE,
    TEXT_PRIMARY, TEXT_WHITE,
)


class Composer(QFrame):
    """Message input bar at the bottom of the chat view."""

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("composer")
        self.setStyleSheet(f"#composer {{ background-color: {BG_INPUT}; }}")
        self.setFixedHeight(68)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(8)

        self._input = QTextEdit()
        self._input.setPlaceholderText("输入消息…  Enter 发送  ·  Ctrl+Enter 换行  ·  / 查看技能")
        self._input.setFixedHeight(44)
        self._input.setAcceptRichText(False)
        self._apply_font_size()
        self._input.installEventFilter(self)
        self._input.textChanged.connect(self._on_text_changed)

        self._send_btn = QPushButton("▶")
        self._send_btn.setFixedSize(48, 44)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {TEXT_WHITE};
                border: none;
                border-radius: 12px;
                font-size: 32px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {_theme.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {ACCENT};
            }}
        """)

        row.addWidget(self._input, 1)
        row.addWidget(self._send_btn)
        layout.addLayout(row)

        # Skill autocomplete
        self._slash_commands: dict[str, str] = {}
        self._suggestion_list: QListWidget | None = None
        self._suppress_suggestions = False

    def _apply_font_size(self):
        self._input.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                color: {TEXT_PRIMARY};
                border: none;
                font-family: {FONT_SANS};
                font-size: {_theme.CHAT_FONT_SIZE}px;
            }}
        """)

    def apply_chat_font_size(self):
        """Public method to refresh font size after settings change."""
        self._apply_font_size()

    def set_slash_commands(self, commands: list[dict]):
        """Set available slash commands with their descriptions."""
        self._slash_commands = {c["name"]: c.get("description", "") for c in commands}

    # ── skill autocomplete ─────────────────────────────────────────

    def _on_text_changed(self):
        if self._suppress_suggestions:
            return
        text = self._input.toPlainText()
        if text.startswith("/") and " " not in text:
            prefix = text[1:].lower()
            matches = [(n, d) for n, d in self._slash_commands.items() if n.startswith(prefix)]
            # Sort: exact match first, then alphabetical
            matches.sort(key=lambda x: (x[0] != prefix, x[0]))
            if matches:
                self._show_suggestions(matches)
                return
        self._hide_suggestions()

    def _show_suggestions(self, matches: list[tuple[str, str]]):
        if self._suggestion_list is None:
            sl = QListWidget()
            sl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            sl.setFocusProxy(self._input)
            sl.setStyleSheet(f"""
                QListWidget {{
                    background: {BG_SIDEBAR};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                    font-family: {FONT_SANS};
                    font-size: {FONT_SIZE}px;
                    color: {TEXT_PRIMARY};
                    outline: none;
                }}
                QListWidget::item {{
                    padding: 6px 12px;
                    border-radius: 6px;
                }}
                QListWidget::item:hover {{
                    background: {ACCENT}22;
                }}
                QListWidget::item:selected {{
                    background: {ACCENT};
                    color: {TEXT_WHITE};
                    outline: none;
                }}
            """)
            sl.itemClicked.connect(self._on_suggestion_clicked)
            sl.setWindowFlags(Qt.WindowType.ToolTip)
            sl.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self._suggestion_list = sl

        sl = self._suggestion_list
        sl.clear()
        item_height = 36
        for name, desc in matches:
            text = f"/{name}"
            if desc:
                text += f"  —  {desc}"
            sl.addItem(QListWidgetItem(text))
        sl.setCurrentRow(0)
        popup_h = min(len(matches), 6) * item_height + 8
        sl.setFixedHeight(popup_h)

        # Position above the input
        input_rect = self._input.rect()
        global_pos = self._input.mapToGlobal(input_rect.topLeft())
        popup_width = max(240, self._input.width())
        sl.setFixedWidth(popup_width)
        sl.move(global_pos.x(), global_pos.y() - popup_h)
        sl.show()
        self._input.setFocus()

    def _hide_suggestions(self):
        if self._suggestion_list:
            self._suggestion_list.hide()

    def _apply_suggestion(self):
        if not self._suggestion_list or not self._suggestion_list.currentItem():
            return
        full_text = self._suggestion_list.currentItem().text()
        # Extract just "/name" part (before " — desc")
        skill_name = full_text.split("  —")[0]
        self._suppress_suggestions = True
        self._input.setText(skill_name + " ")
        self._suppress_suggestions = False
        self._hide_suggestions()
        cursor = self._input.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._input.setTextCursor(cursor)
        self._input.setFocus()

    def _on_suggestion_clicked(self, item: QListWidgetItem):
        self._input.setFocus()
        self._apply_suggestion()

    # ── keyboard handling ──────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj == self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            popup_visible = self._suggestion_list and self._suggestion_list.isVisible()

            if popup_visible:
                if key in (Qt.Key.Key_Escape, Qt.Key.Key_Tab,
                           Qt.Key.Key_Down, Qt.Key.Key_Up):
                    if key == Qt.Key.Key_Escape:
                        self._hide_suggestions()
                    elif key == Qt.Key.Key_Tab:
                        self._apply_suggestion()
                    elif key == Qt.Key.Key_Down:
                        row = self._suggestion_list.currentRow()
                        if row < self._suggestion_list.count() - 1:
                            self._suggestion_list.setCurrentRow(row + 1)
                    elif key == Qt.Key.Key_Up:
                        row = self._suggestion_list.currentRow()
                        if row > 0:
                            self._suggestion_list.setCurrentRow(row - 1)
                    return True

            # Send on Enter (unless Ctrl+Enter for newline)
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    return False
                if popup_visible:
                    self._apply_suggestion()
                else:
                    self._on_send()
                return True

        return super().eventFilter(obj, event)

    # ── send ───────────────────────────────────────────────────────

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self.submitted.emit(text)

    def set_enabled(self, enabled: bool):
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        if enabled:
            self._input.setFocus()

    def insert_text(self, text: str):
        """Insert text at cursor position."""
        self._input.insertPlainText(text)
        self._input.setFocus()

    def submit_text(self, text: str):
        """Set the input text and immediately send it."""
        self._input.setText(text)
        self._on_send()

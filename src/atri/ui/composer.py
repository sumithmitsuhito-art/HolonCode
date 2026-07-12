"""Bottom input area: multi-line text input + send button."""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout
from atri.ui.theme import BG_INPUT


class Composer(QFrame):
    """Message input bar at the bottom of the chat view."""

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("composer")
        self.setStyleSheet(f"#composer {{ background-color: {BG_INPUT}; }}")
        self.setFixedHeight(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(8)

        self._input = QTextEdit()
        self._input.setPlaceholderText("输入消息... (Enter 发送, Ctrl+Enter 换行)")
        self._input.setFixedHeight(40)
        self._input.setAcceptRichText(False)
        self._input.installEventFilter(self)

        self._send_btn = QPushButton("发送")
        self._send_btn.setFixedSize(64, 40)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._on_send)

        row.addWidget(self._input, 1)
        row.addWidget(self._send_btn)
        layout.addLayout(row)

    def eventFilter(self, obj, event):
        if obj == self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    return False
                self._on_send()
                return True
        return super().eventFilter(obj, event)

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

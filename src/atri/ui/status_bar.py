"""Bottom status bar showing model, state, and turn count."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from atri.ui.theme import (
    BG_STATUSBAR,
    FONT_SIZE_SMALL,
    STATUS_SUCCESS,
    STATUS_WARNING,
    TEXT_SECONDARY,
)


class StatusBar(QFrame):
    """Persistent bottom bar with model name, status, and stats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setStyleSheet(
            f"#statusBar {{ background-color: {BG_STATUSBAR}; border-top: 1px solid #2d2d30; }}"
        )
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(16)

        self._model_label = QLabel("deepseek-chat")
        self._model_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}px;"
        )

        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet(
            f"color: {STATUS_SUCCESS}; font-size: {FONT_SIZE_SMALL}px;"
        )

        self._turn_label = QLabel("")
        self._turn_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}px;"
        )

        layout.addWidget(self._model_label)
        layout.addWidget(self._status_label)
        layout.addStretch()
        layout.addWidget(self._turn_label)

    def set_model(self, name: str):
        self._model_label.setText(name)

    def set_status(self, text: str, busy: bool = False):
        self._status_label.setText(text)
        color = STATUS_WARNING if busy else STATUS_SUCCESS
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: {FONT_SIZE_SMALL}px;"
        )

    def set_turn_count(self, count: int):
        self._turn_label.setText(f"对话轮次: {count}")

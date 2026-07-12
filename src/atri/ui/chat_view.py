"""Central chat area: Thread (messages) on top, Composer (input) on bottom."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout
from atri.ui.composer import Composer
from atri.ui.thread import Thread


class ChatView(QFrame):
    """Assembles the Thread (message display) and Composer (input bar)."""

    message_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatView")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.thread = Thread()
        layout.addWidget(self.thread, 1)

        self.composer = Composer()
        layout.addWidget(self.composer)

        self.composer.submitted.connect(self._on_submit)

    def _on_submit(self, text: str):
        self.message_submitted.emit(text)

    def set_input_enabled(self, enabled: bool):
        self.composer.set_enabled(enabled)

    def insert_file_path(self, path: str):
        """Insert a file path reference into the composer."""
        self.composer.insert_text(path)

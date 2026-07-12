"""HolonCode desktop application entry point."""

import sys
from PySide6.QtWidgets import QApplication
from atri.ui.app_shell import AppShell
from atri.ui.theme import global_stylesheet


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(global_stylesheet())
    window = AppShell()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

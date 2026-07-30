"""HolonCode desktop application entry point."""

import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from atri import RESOURCE_DIR
from atri.ui.app_shell import AppShell
from atri.ui.theme import global_stylesheet


def main():
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(RESOURCE_DIR / "icon" / "头像.png")))
    app.setStyleSheet(global_stylesheet())
    window = AppShell()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

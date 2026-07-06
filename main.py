"""
main.py
Entry point for the YT Audio desktop app.

Run with:  python main.py
"""

import sys

from PyQt5.QtWidgets import QApplication, QMessageBox

from ui.main_window import MainWindow
import core.db as db


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep running when window is hidden to tray

    try:
        db.init_db()
        window = MainWindow()
    except RuntimeError as exc:
        QMessageBox.critical(None, "YT Audio - startup error", str(exc))
        return 1

    window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())

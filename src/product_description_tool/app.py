import os
import sys

os.environ.setdefault("PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE", "1")

from PySide6.QtWidgets import QApplication

from product_description_tool.config import ConfigStore
from product_description_tool.main_window import MainWindow


def run() -> int:
    os.environ.setdefault("QT_API", "pyside6")
    app = QApplication(sys.argv)
    app.setApplicationName("Product Description Tool")
    app.setOrganizationName("Codex")

    config_store = ConfigStore()
    window = MainWindow(config_store=config_store)
    window.show()
    return app.exec()

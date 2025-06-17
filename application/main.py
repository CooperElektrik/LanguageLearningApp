import sys
import os
import logging
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication, QSettings

from typing import Optional

try:
    from . import settings
    from . import utils
except ImportError:
    # Fallback for scenarios where main.py might be run in an unusual context
    # or if settings/utils are needed before sys.path is fully configured.
    import settings
    import utils 

# Determine the application directory and the project root
_application_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_application_dir)

utils.set_app_root_dir(_application_dir) # utils.get_resource_path needs the 'application' dir as its base for relative paths like "ui/styles"

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
    # logger is defined after setup_logging, so use print or basicConfig for early debug if needed
    # logging.debug(f"Added project root '{_project_root}' to sys.path for main application.")

def setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=settings.LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger(__name__)
    return logger

def main():
    # Logger setup should happen early
    global logger # Make logger accessible globally in this module after setup
    logger = setup_logging()
    if _project_root not in sys.path: # Log after logger is available
        logger.debug(f"Project root '{_project_root}' was already in sys.path or just added.")

    app = QApplication(sys.argv)
    QCoreApplication.setOrganizationName(settings.ORG_NAME)
    QCoreApplication.setApplicationName(settings.APP_NAME)

    logger.info(f"{settings.APP_NAME} application starting...")

    # The MainWindow now handles the course selection and initialization internally.
    # With project root on sys.path, use absolute import for MainWindow
    try:
        from application.ui.main_window import MainWindow
    except ImportError: # Nuitka will complain without this
        from ui.main_window import MainWindow
    main_window = MainWindow()
    # Initial translation is now handled inside MainWindow's __init__
    main_window.show()

    logger.info("Application main window shown.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
import sys
import os
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication

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

logger = setup_logging()
if _project_root not in sys.path: # Log after logger is available
    logger.debug(f"Project root '{_project_root}' was already in sys.path or just added.")

def setup_translations(app: QApplication) -> QTranslator:
    """Sets up application translations."""
    locale_name = settings.FORCE_LOCALE if settings.FORCE_LOCALE else QLocale.system().name()
    translator = QTranslator(app)
    qm_file_path = utils.get_resource_path(os.path.join(settings.LOCALIZATION_DIR, f"app_{locale_name}.qm"))
    if not translator.load(qm_file_path):
        lang_name = locale_name.split('_')[0]
        qm_file_path = utils.get_resource_path(os.path.join(settings.LOCALIZATION_DIR, f"app_{lang_name}.qm"))
        translator.load(qm_file_path)
    
    if translator.isEmpty():
        logger.warning(f"Could not load translation file. Running in default (English).")
    else:
        logger.info(f"Loaded translation file: {qm_file_path}")
    
    app.installTranslator(translator)
    return translator


def apply_application_theme(app: QApplication):
    """Loads and applies the QSS theme."""
    theme_abs_path = utils.get_resource_path(os.path.join(settings.THEME_DIR, settings.DEFAULT_THEME_FILE))
    if os.path.exists(theme_abs_path):
        try:
            with open(theme_abs_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            logger.info(f"Successfully applied theme from: {theme_abs_path}")
        except Exception as e:
            logger.error(f"Failed to apply theme from {theme_abs_path}: {e}")
    else:
        logger.error(f"Theme QSS file not found at: {theme_abs_path}")


def main():
    app = QApplication(sys.argv)
    QCoreApplication.setOrganizationName(settings.ORG_NAME)
    QCoreApplication.setApplicationName(settings.APP_NAME)

    setup_translations(app)
    apply_application_theme(app)
    
    logger.info(f"{settings.APP_NAME} application starting...")

    # The MainWindow now handles the course selection and initialization internally.
    # With project root on sys.path, use absolute import for MainWindow
    from application.ui.main_window import MainWindow
    main_window = MainWindow()
    main_window.show()

    logger.info("Application main window shown.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
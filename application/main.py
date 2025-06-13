import sys
import os
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication

try:
    from . import settings
    from . import utils
except ImportError:
    import settings
    import utils

_project_root_for_paths = os.path.dirname(os.path.abspath(__file__))
utils.set_app_root_dir(_project_root_for_paths)

if _project_root_for_paths not in sys.path:
    sys.path.insert(0, _project_root_for_paths)

from ui.main_window import MainWindow

def setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=settings.LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger(__name__)
    return logger

logger = setup_logging()

def setup_translations(app: QApplication) -> QTranslator:
    """Sets up application translations."""
    locale_name = settings.FORCE_LOCALE if settings.FORCE_LOCALE else QLocale.system().name()
    translator = QTranslator(app)
    qm_file_path = utils.get_resource_path(os.path.join(settings.LOCALIZATION_DIR, f"ll_{locale_name}.qm"))
    if not translator.load(qm_file_path):
        lang_name = locale_name.split('_')[0]
        qm_file_path = utils.get_resource_path(os.path.join(settings.LOCALIZATION_DIR, f"ll_{lang_name}.qm"))
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
    main_window = MainWindow()
    main_window.show()

    logger.info("Application main window shown.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
import sys
import os
import logging
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication
from typing import Optional

# Attempt to import new settings and utils
try:
    from . import settings
    from . import utils
except ImportError:
    # Fallback for environments where relative import might fail during dev,
    # though with proper project structure, this shouldn't be needed.
    import settings
    import utils

# Determine and set the application root directory for utils.get_resource_path
# This is typically the directory containing this main.py file.
# If main.py is in 'application/', then 'application/' is the app_root_dir for non-frozen.
_project_root_for_paths = os.path.dirname(os.path.abspath(__file__))
utils.set_app_root_dir(_project_root_for_paths)

# Ensure project_root (application directory) is in sys.path for module imports
# This allows imports like "from core.course_manager import CourseManager"
if _project_root_for_paths not in sys.path:
    sys.path.insert(0, _project_root_for_paths)

# Now other modules can be imported
from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.main_window import MainWindow

# Logger setup (moved to a function)
def setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=settings.LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Get root logger for the application, or specific loggers as needed
    # logger = logging.getLogger(settings.APP_NAME) # Or __name__ if preferred
    # For now, keep it simple as it was:
    logger = logging.getLogger(__name__) # Will be '__main__' if this script is the entry point
    return logger

logger = setup_logging() # Initialize logger after function definition

def setup_translations(app: QApplication) -> QTranslator:
    """Sets up application translations."""
    locale_name = settings.FORCE_LOCALE if settings.FORCE_LOCALE else QLocale.system().name()
    logger.info(f"System locale detected: {locale_name}. Attempting to load translations.")

    translator = QTranslator(app) # Parent it to app for lifetime management
    
    # Attempt to load the .qm file for the full system locale (e.g., en_US)
    qm_file_name_locale = f"ll_{locale_name}.qm"
    qm_file_path_relative_locale = os.path.join(settings.LOCALIZATION_DIR, qm_file_name_locale)
    qm_file_path_locale_abs = utils.get_resource_path(qm_file_path_relative_locale)

    loaded_successfully = False
    if os.path.exists(qm_file_path_locale_abs):
        if translator.load(qm_file_path_locale_abs):
            logger.info(f"Successfully loaded translation file: {qm_file_path_locale_abs}")
            loaded_successfully = True
        else:
            logger.warning(f"Failed to load QM file (exists but invalid?): {qm_file_path_locale_abs}. Error: {translator.errorString()}")

    if not loaded_successfully:
        logger.warning(f"Full locale translation file not found or failed to load: {qm_file_path_locale_abs}")
        lang_name = locale_name.split('_')[0] # e.g., 'en' from 'en_US'
        if lang_name != locale_name: # Only try language-only if full locale was different
            qm_file_name_lang_only = f"ll_{lang_name}.qm"
            qm_file_path_relative_lang_only = os.path.join(settings.LOCALIZATION_DIR, qm_file_name_lang_only)
            qm_file_path_lang_only_abs = utils.get_resource_path(qm_file_path_relative_lang_only)
            logger.info(f"Attempting to load language-only translation: {qm_file_path_lang_only_abs}")
            if os.path.exists(qm_file_path_lang_only_abs):
                if translator.load(qm_file_path_lang_only_abs):
                    logger.info(f"Successfully loaded language-only translation file: {qm_file_path_lang_only_abs}")
                    loaded_successfully = True
                else:
                    logger.warning(f"Failed to load QM file (exists but invalid?): {qm_file_path_lang_only_abs}. Error: {translator.errorString()}")
            else:
                logger.warning(f"Language-only translation file not found: {qm_file_path_lang_only_abs}")
        
    if not loaded_successfully:
        final_path_attempted = qm_file_path_lang_only_abs if lang_name != locale_name and not os.path.exists(qm_file_path_locale_abs) else qm_file_path_locale_abs
        logger.warning(f"Could not load any translation file (final attempt: {final_path_attempted}). Running in default (English).")
    
    app.installTranslator(translator)
    return translator


def apply_application_theme(app: QApplication):
    """Loads and applies the QSS theme."""
    theme_relative_path = os.path.join(settings.THEME_DIR, settings.DEFAULT_THEME_FILE)
    theme_abs_path = utils.get_resource_path(theme_relative_path)
    logger.info(f"Attempting to load theme from: {theme_abs_path}")
    
    if os.path.exists(theme_abs_path):
        try:
            with open(theme_abs_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            logger.info(f"Successfully applied theme from: {theme_abs_path}")
        except Exception as e:
            logger.error(f"Failed to apply theme from {theme_abs_path}: {e}. Using default Qt style.")
    else:
        logger.error(f"Theme QSS file not found at: {theme_abs_path}. Using default Qt style.")


def initialize_core_services() -> tuple[Optional[CourseManager], Optional[ProgressManager]]:
    """Initializes and returns core services like CourseManager and ProgressManager."""
    main_manifest_abs_path = utils.get_resource_path(settings.MANIFEST_FILENAME)
    logger.info(f"Attempting to load main manifest from: {main_manifest_abs_path}")

    course_manager = CourseManager(manifest_path=main_manifest_abs_path)
    progress_manager = None

    if course_manager.manifest_data and course_manager.course:
        progress_manager = ProgressManager(
            course_id=course_manager.manifest_data.get("course_id", "default_course_id")
        )
        logger.info("CourseManager and ProgressManager initialized successfully.")
    else:
        logger.error(
            "Critical: Course or manifest data not loaded. ProgressManager might not function correctly or use a default ID."
        )
        # Use QCoreApplication.translate for strings outside QObject context if app is running
        if QApplication.instance():
             QMessageBox.critical(
                None, 
                QCoreApplication.translate("main", "Application Initialization Error"), 
                QCoreApplication.translate("main", "Failed to load critical course data from manifest. The application may not work as expected. Please check for 'manifest.yaml' and its content file.")
            )
        # Initialize ProgressManager with a fallback ID if course loading fails
        progress_manager = ProgressManager(course_id="fallback_critical_error_course_id")
        logger.warning("Proceeding with a fallback ProgressManager due to course load failure.")

    return course_manager, progress_manager


def main():
    app = QApplication(sys.argv)
    QCoreApplication.setOrganizationName(settings.ORG_NAME)
    QCoreApplication.setApplicationName(settings.APP_NAME)

    # Setup translation first, so subsequent UI elements can be translated
    # Note: setup_translations now parents translator to app and installs it.
    setup_translations(app)

    logger.info(f"{settings.APP_NAME} application starting...")
    logger.info(f"Application resource base directory (app_root_for_paths): {_project_root_for_paths}")
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        logger.info(f"Running FROZEN. MEIPASS bundle root: {sys._MEIPASS}")

    apply_application_theme(app)
    
    course_manager, progress_manager = initialize_core_services()

    main_window = MainWindow(course_manager, progress_manager)
    main_window.show()

    logger.info("Application main window shown.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
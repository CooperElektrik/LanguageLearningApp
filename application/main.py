# application/main.py

import sys
import os
import logging
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication 

project_root = os.path.dirname(os.path.abspath(__file__))

if project_root not in sys.path:
    sys.path.insert(0, project_root)


def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, accounting for Nuitka's
    _MEIPASS temporary directory when the app is frozen.
    'relative_path' is assumed to be relative to the bundle root (MEIPASS)
    or the 'application' directory (project_root) during development.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running in a Nuitka bundle
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        # Running in a normal Python environment.
        # project_root here is the 'application' directory.
        return os.path.join(project_root, relative_path)


from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.main_window import MainWindow


logging.basicConfig(
    level=logging.DEBUG, # DEBUG level for more detailed logs
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__) # Will be '__main__' if this script is the entry point


def main():
    # --- Setup Translation ---
    locale_name = QLocale.system().name()
    # For testing, uncomment and set a specific locale like 'fr' or 'vi'
    # locale_name = "vi" 
    logger.info(f"System locale detected: {locale_name}. Attempting to load translations.")

    translator = QTranslator()
    
    # Attempt to load the .qm file for the system locale
    # Paths are relative to the 'application' directory (or bundle root)
    qm_file_name_locale = f"ll_{locale_name}.qm"
    qm_file_path_relative_locale = os.path.join("localization", qm_file_name_locale)
    qm_file_path = get_resource_path(qm_file_path_relative_locale)

    if not os.path.exists(qm_file_path):
        logger.warning(f"Full locale translation file not found: {qm_file_path}")
        lang_name = locale_name.split('_')[0]
        qm_file_name_lang_only = f"ll_{lang_name}.qm"
        qm_file_path_relative_lang_only = os.path.join("localization", qm_file_name_lang_only)
        qm_file_path = get_resource_path(qm_file_path_relative_lang_only)
        logger.info(f"Attempting to load language-only translation: {qm_file_path}")

    if translator.load(qm_file_path):
        logger.info(f"Successfully loaded translation file: {qm_file_path}")
    else:
        # This warning will show the final path tried, which helps debugging
        logger.warning(f"Could not load translation file from tried path: {qm_file_path}. Running in default (English).")
    # --- End Translation Setup ---

    app = QApplication(sys.argv)
    app.installTranslator(translator) # Install translator for the application

    logger.info("LL application starting...")
    logger.info(f"Application resource base directory (project_root): {project_root}")
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        logger.info(f"Running FROZEN. MEIPASS bundle root: {sys._MEIPASS}")


    # --- Load Theme ---
    # Path relative to the 'application' directory (or bundle root for Nuitka)
    win95_qss_relative_path = os.path.join("ui", "styles", "win95_theme.qss")
    win95_qss_file_path = get_resource_path(win95_qss_relative_path)
    logger.info(f"Attempting to load Win95 theme from: {win95_qss_file_path}")
    
    try:
        with open(win95_qss_file_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        logger.info(f"Successfully applied Win95 theme from: {win95_qss_file_path}")
    except FileNotFoundError:
        logger.error(f"Win95 theme QSS file not found at: {win95_qss_file_path}. Using default Qt style.")
    except Exception as e:
        logger.error(f"Failed to apply Win95 theme: {e}")
    # --- End Theme Loading ---

    # --- Determine Main Manifest Path ---
    # manifest.yaml is expected to be at the root of the 'application' dir / bundle root
    main_manifest_path = get_resource_path("manifest.yaml")
    logger.info(f"Attempting to load main manifest from: {main_manifest_path}")
    # --- End Main Manifest Path ---

    course_manager = CourseManager(manifest_path=main_manifest_path)

    if course_manager.manifest_data and course_manager.course:
        progress_manager = ProgressManager(
            course_id=course_manager.manifest_data.get("course_id", "default_course_id")
        )
    else:
        logger.error(
            "Critical: Course or manifest data not loaded. ProgressManager might not function correctly or use a default ID."
        )
        # Use QCoreApplication.translate for strings outside QObject context if app is running
        # But this early, QMessageBox is fine directly if app instance exists
        if QApplication.instance(): # Check if app exists before showing QMessageBox
             QMessageBox.critical(
                None, 
                QCoreApplication.translate("main", "Application Initialization Error"), 
                QCoreApplication.translate("main", "Failed to load critical course data from manifest. The application may not work as expected. Please check for 'manifest.yaml' and its content file.")
            )
        progress_manager = ProgressManager(course_id="fallback_critical_error_course_id")
        # Consider whether to proceed or exit if the course is essential
        # For now, it will proceed, and MainWindow init will show another message.

    main_window = MainWindow(course_manager, progress_manager)
    main_window.show()

    logger.info("Application main window shown.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
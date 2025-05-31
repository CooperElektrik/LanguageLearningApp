import sys
import os
import logging
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.main_window import MainWindow


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    # Determine the path to the translations directory
    translations_dir = os.path.join(project_root, "localization")
    
    # Get the system locale (e.g., 'en_US', 'fr_FR')
    locale_name = QLocale.system().name() # Or hardcode 'fr' for testing French
    print(locale_name)
    locale_name = "vi"

    # Create a QTranslator instance
    translator = QTranslator()
    
    # Attempt to load the .qm file for the system locale
    # The .qm file should be named based on the locale, e.g., 'll_fr.qm' for French
    # The 'll' prefix is a common convention for application translations
    qm_file_path = os.path.join(translations_dir, f"ll_{locale_name}.qm")
    if not os.path.exists(qm_file_path):
        # Fallback to language-only if full locale not found (e.g., 'en_US' -> 'en')
        lang_name = locale_name.split('_')[0]
        qm_file_path = os.path.join(translations_dir, f"ll_{lang_name}.qm")

    if translator.load(qm_file_path):
        logger.info(f"Loaded translation file: {qm_file_path}")
    else:
        logger.warning(f"Could not load translation file: {qm_file_path}. Running in default language.")

    app = QApplication(sys.argv)
    app.installTranslator(translator)

    logger.info("LL application starting...")

    logger.info(f"Project root: {project_root}")

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        main_manifest_path = os.path.join(sys._MEIPASS, "manifest.yaml")
        logger.info(f"Running frozen app. Manifest path: {main_manifest_path}")
    else:
        main_manifest_path = os.path.join(project_root, "manifest.yaml")
        logger.info(f"Running in development. Manifest path: {main_manifest_path}")

    course_manager = CourseManager(manifest_path=main_manifest_path)

    if course_manager.manifest_data and course_manager.course:
        progress_manager = ProgressManager(
            course_id=course_manager.manifest_data.get("course_id", "default_course")
        )
    else:
        logger.error(
            "Course or manifest data not loaded. ProgressManager might not function correctly or use a default ID."
        )
        progress_manager = ProgressManager(course_id="fallback_course_id_error")

    main_window = MainWindow(course_manager, progress_manager)
    main_window.show()

    logger.info("Application main window shown.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

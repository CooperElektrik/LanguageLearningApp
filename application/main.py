import sys
import os
import logging
from PySide6.QtWidgets import QApplication

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
    app = QApplication(sys.argv)
    logger.info("LL application starting...")

    logger.info(f"Project root: {project_root}")
    course_manager = CourseManager(manifest_dir=project_root)

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

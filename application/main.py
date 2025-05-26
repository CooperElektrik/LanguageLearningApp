import sys
import os
import logging
from PySide6.QtWidgets import QApplication

# Add project root to Python path to allow imports like `from core.models import ...`
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.main_window import MainWindow


# Configure basic logging for the whole application
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout) # Log to console
        # You could add logging.FileHandler("app.log") here as well
    ]
)
logger = logging.getLogger(__name__)


def main():
    app = QApplication(sys.argv)
    logger.info("LL application starting...")

    # Initialize managers
    # CourseManager will try to load manifest.yaml from its current directory by default
    # which is the project root where main.py is.
    logger.info(f"Project root: {project_root}")
    course_manager = CourseManager(manifest_dir=project_root) # Pass project root explicitly
    
    if course_manager.manifest_data and course_manager.course:
        progress_manager = ProgressManager(course_id=course_manager.manifest_data.get("course_id", "default_course"))
    else:
        logger.error("Course or manifest data not loaded. ProgressManager might not function correctly or use a default ID.")
        # Create a dummy progress manager or handle this state
        progress_manager = ProgressManager(course_id="fallback_course_id_error")


    main_window = MainWindow(course_manager, progress_manager)
    main_window.show()

    logger.info("Application main window shown.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
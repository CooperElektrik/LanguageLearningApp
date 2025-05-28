import sys
import logging
import os
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QApplication, QMessageBox
from PySide6.QtGui import QIcon, QAction # Optional: for window icon
from PySide6.QtCore import Qt

from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.views.course_overview_view import CourseOverviewView
from ui.views.lesson_view import LessonView
from ui.views.review_view import ReviewView

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

_current_dir = os.path.dirname(os.path.abspath(__file__))
_dark_theme_qss_path = os.path.join(_current_dir, 'styles', 'dark_theme.qss')

class MainWindow(QMainWindow):
    def __init__(self, course_manager: CourseManager, progress_manager: ProgressManager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        if not self.course_manager.course:
            QMessageBox.critical(self, "Course Load Error",
                                 "Failed to load course. Please check manifest.yaml and course content file.\n"
                                 "See console logs for details.")
            # Application should probably exit or offer to select a different manifest
            # For now, it will show a blank window.
            self.course_load_failed = True
        else:
            self.course_load_failed = False


        self.setWindowTitle(f"LL - {self.course_manager.get_course_title() or 'Language Learning'}")
        self.setGeometry(100, 100, 800, 600)
        # self.setWindowIcon(QIcon("path/to/your/icon.png")) # Optional

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        if not self.course_load_failed:
            self._setup_views()
            self._setup_menu_bar()
            self.show_course_overview()
        else:
            # Handle the UI state when course loading fails (e.g., show an error message widget)
            # For now, the window will be mostly empty.
            pass

        with open(_dark_theme_qss_path, 'r') as f:
            self.setStyleSheet(f.read())

    def _setup_views(self):
        self.course_overview_view = CourseOverviewView(self.course_manager, self.progress_manager)
        self.lesson_view = LessonView(self.course_manager, self.progress_manager)
        self.review_view = ReviewView(self.course_manager, self.progress_manager)

        self.stacked_widget.addWidget(self.course_overview_view)
        self.stacked_widget.addWidget(self.lesson_view)
        self.stacked_widget.addWidget(self.review_view)

        # Connect signals
        self.course_overview_view.lesson_selected.connect(self.start_lesson)
        self.lesson_view.lesson_completed_signal.connect(self.handle_lesson_completion)
        self.lesson_view.back_to_overview_signal.connect(self.show_course_overview)
        self.review_view.review_session_finished.connect(self.show_course_overview)
        self.review_view.back_to_overview_signal.connect(self.show_course_overview)

    def _setup_menu_bar(self): # NEW METHOD
        menu_bar = self.menuBar()
        learning_menu = menu_bar.addMenu("&Learning")

        self.start_review_action = QAction("&Start Review", self)
        self.start_review_action.setShortcut(Qt.CTRL | Qt.Key_R)
        self.start_review_action.setStatusTip("Start a spaced repetition review session")
        self.start_review_action.triggered.connect(self.start_review_session)
        learning_menu.addAction(self.start_review_action)

    def show_course_overview(self):
        if hasattr(self, 'course_overview_view') and self.course_overview_view:
             self.course_overview_view.refresh_view() # Update statuses
             self.stacked_widget.setCurrentWidget(self.course_overview_view)
        else:
            logger.warning("Course overview view not available. Course might not have loaded.")


    def start_lesson(self, lesson_id: str):
        if hasattr(self, 'lesson_view') and self.lesson_view:
            logger.info(f"Starting lesson: {lesson_id}")
            self.lesson_view.start_lesson(lesson_id)
            self.stacked_widget.setCurrentWidget(self.lesson_view)
        else:
            logger.warning("Lesson view not available. Course might not have loaded.")


    def handle_lesson_completion(self, lesson_id: str):
        logger.info(f"Lesson {lesson_id} completed. Returning to overview.")
        # Progress is already saved by LessonView calling ProgressManager
        self.show_course_overview() # This will also refresh the overview

    def start_review_session(self): # NEW SLOT
        if not self.course_manager.course:
            QMessageBox.warning(self, "Review Session", "No course loaded to start a review session.")
            return

        self.review_view.start_review_session()
        self.stacked_widget.setCurrentWidget(self.review_view)
        logger.info("Started review session.")

    def closeEvent(self, event):
        # Ensure progress is saved on close, though it should be saved after each lesson.
        # This is a fallback.
        if self.progress_manager and not self.course_load_failed:
            self.progress_manager.save_progress()
            logger.info("Application closing, final progress save attempt.")
        super().closeEvent(event)
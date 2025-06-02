import sys
import logging
import os
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QApplication, QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.views.course_overview_view import CourseOverviewView
from ui.views.lesson_view import LessonView
from ui.views.review_view import ReviewView
from ui.views.progress_view import ProgressView
from ui.views.glossary_view import GlossaryView

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

_current_dir = os.path.dirname(os.path.abspath(__file__))


class MainWindow(QMainWindow):
    def __init__(
        self,
        course_manager: CourseManager,
        progress_manager: ProgressManager,
        parent=None,
    ):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        if not self.course_manager.course:
            QMessageBox.critical(
                self,
                self.tr("Course Load Error"),
                self.tr("Failed to load course. Please check manifest.yaml and course content file.\n"
                        "See console logs for details."),
            )
            self.course_load_failed = True
        else:
            self.course_load_failed = False

        self.setWindowTitle(
            self.tr("LL - {0}").format(self.course_manager.get_course_title() or self.tr('Language Learning'))
        )
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setGeometry(100, 100, 480, 600)
        self.setFixedSize(480, 600)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        if not self.course_load_failed:
            self._setup_views()
            self._setup_menu_bar()
            self.show_course_overview()
        else:
            pass

    def _setup_views(self):
        self.course_overview_view = CourseOverviewView(
            self.course_manager, self.progress_manager
        )
        self.lesson_view = LessonView(self.course_manager, self.progress_manager)
        self.review_view = ReviewView(self.course_manager, self.progress_manager)
        self.progress_view = ProgressView(self.course_manager,self.progress_manager)
        self.glossary_view = GlossaryView(self.course_manager)

        self.stacked_widget.addWidget(self.course_overview_view)
        self.stacked_widget.addWidget(self.lesson_view)
        self.stacked_widget.addWidget(self.review_view)
        self.stacked_widget.addWidget(self.progress_view)
        self.stacked_widget.addWidget(self.glossary_view)

        self.course_overview_view.lesson_selected.connect(self.start_lesson)
        self.lesson_view.lesson_completed_signal.connect(self.handle_lesson_completion)
        self.lesson_view.back_to_overview_signal.connect(self.show_course_overview)
        self.review_view.review_session_finished.connect(self.show_course_overview)
        self.review_view.back_to_overview_signal.connect(self.show_course_overview)
        self.glossary_view.back_to_overview_signal.connect(self.show_course_overview)

        self.course_overview_view.start_review_session_requested.connect(self.start_review_session)
        self.progress_view.back_to_overview_signal.connect(self.show_course_overview)

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()
        learning_menu = menu_bar.addMenu(self.tr("&Learning"))

        self.start_review_action = QAction(self.tr("&Start Review"), self)
        self.start_review_action.setShortcut(Qt.CTRL | Qt.Key_R)
        self.start_review_action.setStatusTip(
            self.tr("Start a spaced repetition review session")
        )
        self.start_review_action.triggered.connect(self.start_review_session)
        learning_menu.addAction(self.start_review_action)

        self.show_progress_action = QAction(self.tr("&Progress"), self)
        self.show_progress_action.setShortcut(Qt.CTRL | Qt.Key_P)
        self.show_progress_action.setStatusTip(self.tr("View your learning progress and achievements"))
        self.show_progress_action.triggered.connect(self.show_progress_view)
        learning_menu.addAction(self.show_progress_action)

        self.show_glossary_action = QAction(self.tr("&Glossary"), self)
        self.show_glossary_action.setShortcut(Qt.CTRL | Qt.Key_G)
        self.show_glossary_action.setStatusTip(self.tr("View the course glossary"))
        self.show_glossary_action.triggered.connect(self.show_glossary_view)
        learning_menu.addAction(self.show_glossary_action)

    def show_progress_view(self):
        if not self.course_manager.course:
            QMessageBox.warning(
                self, self.tr("Progress View"), self.tr("No course loaded to view progress.")
            )
            return
        if hasattr(self, "progress_view") and self.progress_view:
            self.progress_view.refresh_view() # Refresh stats before showing
            self.stacked_widget.setCurrentWidget(self.progress_view)
            logger.info("Showing progress view.")
        else:
            logger.warning("Progress view not available.")

    def show_course_overview(self):
        if hasattr(self, "course_overview_view") and self.course_overview_view:
            self.course_overview_view.refresh_view()
            self.stacked_widget.setCurrentWidget(self.course_overview_view)
        else:
            logger.warning(
                "Course overview view not available. Course might not have loaded."
            )

    def start_lesson(self, lesson_id: str):
        if hasattr(self, "lesson_view") and self.lesson_view:
            logger.info(f"Starting lesson: {lesson_id}")
            self.lesson_view.start_lesson(lesson_id)
            self.stacked_widget.setCurrentWidget(self.lesson_view)
        else:
            logger.warning("Lesson view not available. Course might not have loaded.")

    def handle_lesson_completion(self, lesson_id: str):
        logger.info(f"Lesson {lesson_id} completed. Returning to overview.")
        self.show_course_overview()

    def start_review_session(self):
        if not self.course_manager.course:
            QMessageBox.warning(
                self, self.tr("Review Session"), self.tr("No course loaded to start a review session.")
            )
            return

        self.review_view.start_review_session()
        self.stacked_widget.setCurrentWidget(self.review_view)
        logger.info("Started review session.")

    def show_glossary_view(self):
        if not self.course_manager.course:
            QMessageBox.warning(
                self, self.tr("Glossary"), self.tr("No course loaded to view glossary.")
            )
            return
        if self.course_manager.get_glossary_entries():
            if hasattr(self, "glossary_view") and self.glossary_view:
                self.glossary_view.refresh_view() # Refresh list before showing
                self.stacked_widget.setCurrentWidget(self.glossary_view)
                logger.info("Showing glossary view.")
            else:
                logger.warning("Glossary view not available.")
        else:
            QMessageBox.information(
                self, self.tr("Glossary Empty"), self.tr("No glossary entries found for this course.")
            )
            logger.info("Attempted to show glossary view, but glossary is empty.")

    def closeEvent(self, event):
        if self.progress_manager and not self.course_load_failed:
            self.progress_manager.save_progress()
            logger.info("Application closing, final progress save attempt.")
        super().closeEvent(event)

import sys
import logging
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox, QLabel
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QCoreApplication

from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.views.course_overview_view import CourseOverviewView
from ui.views.lesson_view import LessonView
from ui.views.review_view import ReviewView
from ui.views.progress_view import ProgressView
from ui.views.glossary_view import GlossaryView

logger = logging.getLogger(__name__)

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
        self.course_load_failed = False # Initialize

        if not self.course_manager.course:
            QMessageBox.critical(
                self,
                QCoreApplication.translate("MainWindow", "Course Load Error"),
                QCoreApplication.translate("MainWindow", "Failed to load critical course data.\n"
                                         "The application may not function correctly.\n"
                                         "Please check console logs for details and ensure 'manifest.yaml' and content files are valid."),
            )
            self.course_load_failed = True
        
        self.setWindowTitle(
            self.tr("LL - {0}").format(self.course_manager.get_course_title() or self.tr('Language Learning'))
        )
        # self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setGeometry(100, 100, 480, 600)
        self.setFixedSize(480, 600)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        if not self.course_load_failed:
            self._setup_views()
            self._setup_menu_bar()
            self.show_course_overview()
        else:
            error_label = QLabel(self.tr("Failed to load course. Please check logs and restart."), self)
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setWordWrap(True)
            self.stacked_widget.addWidget(error_label)
            self.stacked_widget.setCurrentWidget(error_label)
            logger.error("MainWindow initialized in a course-load-failed state. Limited functionality.")


    def _setup_views(self):
        """Initializes and adds all views to the stacked widget and connects signals."""
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

        # Connect signals
        self.course_overview_view.lesson_selected.connect(self.start_lesson)
        self.course_overview_view.start_review_session_requested.connect(self.start_review_session)
        
        self.lesson_view.lesson_completed_signal.connect(self.handle_lesson_completion)
        self.lesson_view.back_to_overview_signal.connect(self.show_course_overview)
        
        self.review_view.review_session_finished.connect(self.show_course_overview) # Or a different view like progress
        self.review_view.back_to_overview_signal.connect(self.show_course_overview)
        
        self.progress_view.back_to_overview_signal.connect(self.show_course_overview)
        self.glossary_view.back_to_overview_signal.connect(self.show_course_overview)

    def _setup_menu_bar(self):
        """Sets up the main menu bar and its actions."""
        menu_bar = self.menuBar()
        
        # Learning Menu
        learning_menu = menu_bar.addMenu(self.tr("&Learning"))

        self.start_review_action = QAction(self.tr("&Start Review"), self)
        self.start_review_action.setShortcut(Qt.CTRL | Qt.Key_R) # Using Qt.CTRL instead of Qt.CTRL
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

    def _is_course_available(self, action_description_tr: str) -> bool:
        """
        Checks if a course is loaded. If not, shows a warning QMessageBox.
        Returns True if course is available, False otherwise.
        """
        if self.course_load_failed or not self.course_manager.course:
            QMessageBox.warning(
                self,
                action_description_tr, # Title of the warning
                self.tr("No course is currently loaded or the course failed to load. This feature is unavailable.")
            )
            return False
        return True

    def show_progress_view(self):
        if not self._is_course_available(self.tr("Progress View")):
            return
        
        if hasattr(self, "progress_view") and self.progress_view:
            self.progress_view.refresh_view() # Refresh stats before showing
            self.stacked_widget.setCurrentWidget(self.progress_view)
            logger.info("Showing progress view.")
        else:
            logger.warning("Progress view not available (should not happen if course loaded).")

    def show_course_overview(self):
        if self.course_load_failed: # If course failed to load initially, don't try to show overview
            logger.warning("Attempted to show course overview, but course loading failed.")
            return

        if hasattr(self, "course_overview_view") and self.course_overview_view:
            self.course_overview_view.refresh_view()
            self.stacked_widget.setCurrentWidget(self.course_overview_view)
            logger.info("Showing course overview.")
        else:
            logger.error("Course overview view not available despite course load success. Internal error.")
            QMessageBox.critical(self, self.tr("Internal Error"), self.tr("Course overview cannot be displayed."))


    def start_lesson(self, lesson_id: str):
        if self.course_load_failed: # Should already be handled by overview view not emitting signal
            return
        
        # No need for _is_course_available here, as lesson_id implies a course context
        if hasattr(self, "lesson_view") and self.lesson_view:
            logger.info(f"Starting lesson: {lesson_id}")
            self.lesson_view.start_lesson(lesson_id)
            self.stacked_widget.setCurrentWidget(self.lesson_view)
        else:
            logger.warning("Lesson view not available (should not happen if course loaded).")


    def handle_lesson_completion(self, lesson_id: str):
        logger.info(f"Lesson {lesson_id} completed. Returning to overview.")
        self.show_course_overview() # Refresh overview to show updated progress


    def start_review_session(self):
        if not self._is_course_available(self.tr("Review Session")):
            return

        if hasattr(self, "review_view") and self.review_view:
            self.review_view.start_review_session() # This method itself should check for due exercises
            if self.review_view.total_exercises_in_session > 0: # Only switch if session actually starts
                self.stacked_widget.setCurrentWidget(self.review_view)
                logger.info("Started review session.")
            # If no exercises are due, ReviewView's start_review_session will show a message and not proceed.
        else:
            logger.warning("Review view not available (should not happen if course loaded).")


    def show_glossary_view(self):
        if not self._is_course_available(self.tr("Glossary")):
            return
        
        # Check if glossary itself has entries
        if not self.course_manager.get_glossary_entries():
            QMessageBox.information(
                self, 
                self.tr("Glossary Empty"), 
                self.tr("No glossary entries found for this course.")
            )
            logger.info("Attempted to show glossary view, but glossary is empty.")
            return

        if hasattr(self, "glossary_view") and self.glossary_view:
            self.glossary_view.refresh_view() # Refresh list before showing
            self.stacked_widget.setCurrentWidget(self.glossary_view)
            logger.info("Showing glossary view.")
        else:
            logger.warning("Glossary view not available (should not happen if course loaded).")


    def closeEvent(self, event):
        """Handles application close events, ensuring progress is saved."""
        logger.info("Application close event triggered.")
        if self.progress_manager and not self.course_load_failed:
            try:
                self.progress_manager.save_progress()
                logger.info("Progress saved successfully on application close.")
            except Exception as e:
                logger.error(f"Error saving progress on close: {e}")
                # Optionally, inform the user if saving failed critically
                # QMessageBox.critical(self, self.tr("Save Error"), self.tr("Could not save progress: {0}").format(str(e)))
        super().closeEvent(event)
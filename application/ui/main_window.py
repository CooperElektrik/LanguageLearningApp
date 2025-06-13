import sys
import logging
from PySide6.QtWidgets import (
    QMainWindow, QStackedWidget, QMessageBox, QLabel, QWidget, QHBoxLayout, 
    QVBoxLayout, QDockWidget, QInputDialog
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QCoreApplication

from typing import Optional

from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.views.course_overview_view import CourseOverviewView
from ui.views.lesson_view import LessonView
from ui.views.review_view import ReviewView
from ui.views.progress_view import ProgressView
from ui.views.glossary_view import GlossaryView
from ui.views.course_selection_view import CourseSelectionView
from ui.dialogs.glossary_detail_dialog import GlossaryDetailDialog


logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.course_manager: Optional[CourseManager] = None
        self.progress_manager: Optional[ProgressManager] = None
        
        self.setWindowTitle(self.tr("LinguaLearn"))
        self.setGeometry(100, 100, 960, 720)

        self.main_stack = QStackedWidget()
        self.setCentralWidget(self.main_stack)

        self.course_selection_view = CourseSelectionView()
        self.course_selection_view.course_selected.connect(self.load_course)
        self.main_stack.addWidget(self.course_selection_view)

    def load_course(self, manifest_path: str):
        """Initializes core services and builds the main UI after a course is selected."""
        logger.info(f"Loading course from manifest: {manifest_path}")
        self.course_manager = CourseManager(manifest_path=manifest_path)
        
        if not self.course_manager.course:
            QMessageBox.critical(self, self.tr("Course Load Error"), self.tr("Failed to load critical course data."))
            return

        self.progress_manager = ProgressManager(course_id=self.course_manager.course.course_id)
        
        self._setup_main_ui()
        self.main_stack.deleteLater()
        self.main_stack = None

        self.setWindowTitle(f"LL - {self.course_manager.get_course_title()}")
        self.show_course_overview()


    def _setup_main_ui(self):
        """Sets up the main UI components after a course has been loaded."""

        # --- Setup Dock Widgets ---
        self.navigation_dock_widget = QDockWidget(self.tr("Course Navigation"), self)
        self.navigation_dock_widget.setObjectName("navigation_dock_widget")
        self.course_overview_view = CourseOverviewView(self.course_manager, self.progress_manager)
        self.navigation_dock_widget.setWidget(self.course_overview_view)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.navigation_dock_widget)

        self.progress_dock_widget = QDockWidget(self.tr("Progress & Achievements"), self)
        self.progress_dock_widget.setObjectName("progress_dock_widget")
        self.progress_view = ProgressView(self.course_manager, self.progress_manager)
        self.progress_dock_widget.setWidget(self.progress_view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.progress_dock_widget)

        # --- Setup Central Widget ---
        self.right_panel_stack = QStackedWidget()
        self.right_panel_stack.setObjectName("right_panel_stack")
        self.setCentralWidget(self.right_panel_stack) # Set it on the QMainWindow itself

        # Instantiate views
        self.lesson_view = LessonView(self.course_manager, self.progress_manager)
        self.review_view = ReviewView(self.course_manager, self.progress_manager)
        self.glossary_view = GlossaryView(self.course_manager)
        self.right_panel_placeholder = QLabel(self.tr("Select a lesson or start a review."), alignment=Qt.AlignCenter)
        self.right_panel_placeholder.setWordWrap(True)

        self.right_panel_stack.addWidget(self.right_panel_placeholder)
        self.right_panel_stack.addWidget(self.lesson_view)
        self.right_panel_stack.addWidget(self.review_view)
        self.right_panel_stack.addWidget(self.glossary_view)

        # Connect signals
        self.course_overview_view.lesson_selected.connect(self.start_lesson)
        self.course_overview_view.start_review_session_requested.connect(self.start_review_session)
        self.course_overview_view.start_weakest_review_requested.connect(self.start_weakest_review_session)
        
        self.lesson_view.lesson_completed_signal.connect(self.handle_lesson_completion)
        self.lesson_view.back_to_overview_signal.connect(self.show_course_overview)
        self.review_view.review_session_finished.connect(self.show_course_overview)
        self.review_view.back_to_overview_signal.connect(self.show_course_overview)
        self.glossary_view.back_to_overview_signal.connect(self.show_course_overview)

        self._setup_menu_bar()


    def _setup_menu_bar(self):
        menu_bar = self.menuBar()
        menu_bar.clear() # Clear any previous menu
        
        learning_menu = menu_bar.addMenu(self.tr("&Learning"))
        learning_menu.addAction(self.tr("&Start Review"), self.start_review_session, Qt.CTRL | Qt.Key_R)
        learning_menu.addAction(self.tr("Review &Weak Items"), self.start_weakest_review_session)
        learning_menu.addAction(self.tr("&Glossary"), self.show_glossary_view, Qt.CTRL | Qt.Key_G)

        view_menu = menu_bar.addMenu(self.tr("&View"))
        view_menu.addAction(self.navigation_dock_widget.toggleViewAction())
        view_menu.addAction(self.progress_dock_widget.toggleViewAction())

    def _set_docks_enabled(self, enabled: bool):
        if hasattr(self, 'navigation_dock_widget'):
            self.navigation_dock_widget.setEnabled(enabled)
        if hasattr(self, 'progress_dock_widget'):
            self.progress_dock_widget.setEnabled(enabled)

    def show_course_overview(self):
        if not self.course_manager: return
        self.course_overview_view.refresh_view()
        self.progress_view.refresh_view()
        self.right_panel_stack.setCurrentWidget(self.right_panel_placeholder)
        self._set_docks_enabled(True)
        logger.info("Showing course overview.")

    def start_lesson(self, lesson_id: str):
        if not self.course_manager: return
        self._set_docks_enabled(False)
        self.lesson_view.start_lesson(lesson_id)
        self.right_panel_stack.setCurrentWidget(self.lesson_view)

    def start_review_session(self):
        if not self.course_manager: return
        exercises = self.progress_manager.get_due_exercises(self.course_manager.get_all_exercises())
        self.review_view.start_review_session(exercises, "Due Items Review")
        if self.review_view.total_exercises_in_session > 0:
            self._set_docks_enabled(False)
            self.right_panel_stack.setCurrentWidget(self.review_view)

    def start_weakest_review_session(self):
        if not self.course_manager: return
        exercises = self.progress_manager.get_weakest_exercises(self.course_manager.get_all_exercises())
        self.review_view.start_review_session(exercises, "Weak Items Review")
        if self.review_view.total_exercises_in_session > 0:
            self._set_docks_enabled(False)
            self.right_panel_stack.setCurrentWidget(self.review_view)

    def handle_lesson_completion(self, lesson_id: str):
        logger.info(f"Lesson {lesson_id} completed.")
        self.show_course_overview()

    def show_glossary_view(self):
        if not self.course_manager: return
        if not self.course_manager.get_glossary_entries():
            QMessageBox.information(self, self.tr("Glossary Empty"), self.tr("No glossary entries for this course."))
            return
        self._set_docks_enabled(False)
        self.glossary_view.refresh_view()
        self.right_panel_stack.setCurrentWidget(self.glossary_view)

    def closeEvent(self, event):
        if self.progress_manager:
            self.progress_manager.save_progress()
        super().closeEvent(event)
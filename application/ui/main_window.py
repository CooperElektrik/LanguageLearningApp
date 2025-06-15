import sys
import logging
import os
from PySide6.QtWidgets import (
    QMainWindow, QStackedWidget, QMessageBox, QLabel, QWidget, QFileDialog, QToolBar,
    QVBoxLayout, QDockWidget
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QCoreApplication, QSettings

from typing import Optional

from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.views.course_overview_view import CourseOverviewView
from ui.views.lesson_view import LessonView
from ui.views.review_view import ReviewView
from ui.views.progress_view import ProgressView
from ui.views.glossary_view import GlossaryView
from ui.views.course_selection_view import CourseSelectionView
from ui.views.course_editor_view import CourseEditorView
from ui.dialogs.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.course_manager: Optional[CourseManager] = None
        self.progress_manager: Optional[ProgressManager] = None
        
        self.setWindowTitle(self.tr("LinguaLearn"))
        self.setGeometry(100, 100, 1024, 768)

        # Main stack to switch between app states (selection, learning, editing)
        self.main_stack = QStackedWidget()
        self.setCentralWidget(self.main_stack) # Set this ONCE and never change it.

        # Create the permanent course selection page
        self.course_selection_view = CourseSelectionView()
        self.course_selection_view.course_selected.connect(self._load_course_for_learning)
        self.main_stack.addWidget(self.course_selection_view)

        # Placeholders for other modes' main widgets
        self.learning_widget = None
        self.editor_view = None

        self._return_to_selection_screen() # Start in the selection screen

    def _load_course_for_learning(self, manifest_path: str):
        """Initializes services and UI for the LEARNING mode."""
        self.course_manager = CourseManager(manifest_path=manifest_path)
        if not self.course_manager.course:
            QMessageBox.critical(self, self.tr("Course Load Error"), self.tr("Failed to load course."))
            return
        self.progress_manager = ProgressManager(course_id=self.course_manager.course.course_id)
        
        self._setup_learning_ui()
        self.setWindowTitle(f"LL - {self.course_manager.get_course_title()}")
        self.show_course_overview()

    def _load_course_for_editing(self):
        """Opens a file dialog and loads a course into the EDITOR mode."""
        manifest_path, _ = QFileDialog.getOpenFileName(self, self.tr("Open Course Manifest"), "", "YAML Files (*.yaml)")
        if not manifest_path: return

        editor_course_manager = CourseManager(manifest_path=manifest_path)
        if not editor_course_manager.course:
            QMessageBox.critical(self, self.tr("Course Load Error"), self.tr("Failed to load selected course for editing."))
            return

        self._setup_editing_ui(editor_course_manager)
        self.setWindowTitle(f"LL Editor - {editor_course_manager.get_course_title()}")

    def _setup_learning_ui(self):
        """Builds the main learning interface with docks and views."""
        # self._clear_dynamic_widgets()

        # The learning UI has docks, so it needs its own QMainWindow instance.
        # We then add this entire QMainWindow as a page to the main stack.
        self.learning_widget = QMainWindow()
        
        right_panel_stack = QStackedWidget()
        self.learning_widget.setCentralWidget(right_panel_stack)

        self.navigation_dock_widget = QDockWidget(self.tr("Course Navigation"), self.learning_widget)
        course_overview_view = CourseOverviewView(self.course_manager, self.progress_manager)
        self.navigation_dock_widget.setWidget(course_overview_view)
        self.learning_widget.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.navigation_dock_widget)

        self.progress_dock_widget = QDockWidget(self.tr("Progress"), self.learning_widget)
        progress_view = ProgressView(self.course_manager, self.progress_manager)
        self.progress_dock_widget.setWidget(progress_view)
        self.learning_widget.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.progress_dock_widget)
        
        # We need to store these view references to switch the stack inside this learning_widget
        self.learning_ui_views = {
            "overview": course_overview_view,
            "progress": progress_view,
            "lesson": LessonView(self.course_manager, self.progress_manager),
            "review": ReviewView(self.course_manager, self.progress_manager),
            "glossary": GlossaryView(self.course_manager),
            "placeholder": QLabel(self.tr("Select a lesson or start a review."), alignment=Qt.AlignCenter),
            "central_stack": right_panel_stack
        }

        right_panel_stack.addWidget(self.learning_ui_views["placeholder"])
        right_panel_stack.addWidget(self.learning_ui_views["lesson"])
        right_panel_stack.addWidget(self.learning_ui_views["review"])
        right_panel_stack.addWidget(self.learning_ui_views["glossary"])

        course_overview_view.lesson_selected.connect(self.start_lesson)
        course_overview_view.start_review_session_requested.connect(self.start_review_session)
        self.learning_ui_views["review"].review_session_finished.connect(self.show_course_overview)
        self.learning_ui_views["review"].back_to_overview_signal.connect(self.show_course_overview)
        self.learning_ui_views["lesson"].back_to_overview_signal.connect(self.show_course_overview)
        
        self.main_stack.addWidget(self.learning_widget)
        self.main_stack.setCurrentWidget(self.learning_widget)
        self._setup_learning_menu()

        self.menuBar().setVisible(False)

    def _setup_editing_ui(self, course_manager):
        """Builds the editing interface."""
        # self._clear_dynamic_widgets()
        
        self.editor_view = CourseEditorView(course_manager)
        self.editor_view.editor_closed.connect(self._return_to_selection_screen)
        
        self.main_stack.addWidget(self.editor_view)
        self.main_stack.setCurrentWidget(self.editor_view)
        self.menuBar().clear()

        self.menuBar().setVisible(False)

    def _setup_file_menu(self):
        """Menu for the initial selection screen."""
        self.menuBar().clear()
        file_menu = self.menuBar().addMenu(self.tr("&File"))
        file_menu.addAction(self.tr("Open Course for Editing..."), self._load_course_for_editing)
        file_menu.addSeparator()
        file_menu.addAction(self.tr("&Settings..."), self.show_settings_dialog)
        file_menu.addSeparator()
        file_menu.addAction(self.tr("&Quit"), self.close)

    def _setup_learning_menu(self):
        """Menu for the main learning mode."""
        # Use the menu bar from the nested QMainWindow for learning mode
        menu_bar = self.learning_widget.menuBar()
        menu_bar.clear()
        file_menu = menu_bar.addMenu(self.tr("&File"))
        file_menu.addAction(self.tr("Return to Course Selection"), self._return_to_selection_screen)
        file_menu.addSeparator()
        file_menu.addAction(self.tr("&Settings..."), self.show_settings_dialog)

        learning_menu = menu_bar.addMenu(self.tr("&Learning"))
        learning_menu.addAction(self.tr("Start Due Review"), self.start_review_session)

        view_menu = menu_bar.addMenu(self.tr("&View"))
        if hasattr(self, "navigation_dock_widget") and self.navigation_dock_widget:
            view_menu.addAction(self.navigation_dock_widget.toggleViewAction())
        if hasattr(self, "progress_dock_widget") and self.progress_dock_widget:
            view_menu.addAction(self.progress_dock_widget.toggleViewAction())

    def _return_to_selection_screen(self):
        self._clear_dynamic_widgets()
        self.setWindowTitle(self.tr("LinguaLearn"))
        self.main_stack.setCurrentWidget(self.course_selection_view)
        self.menuBar().setVisible(True)
        self._setup_file_menu()

    def _clear_dynamic_widgets(self):
        """Removes learning or editor widgets from the stack to prevent memory leaks."""
        if self.learning_widget:
            self.main_stack.removeWidget(self.learning_widget)
            self.learning_widget.deleteLater()
            self.learning_widget = None
            self.learning_ui_views = {}
        if self.editor_view:
            self.main_stack.removeWidget(self.editor_view)
            self.editor_view.deleteLater()
            self.editor_view = None

        self.course_manager = None
        self.progress_manager = None

    def show_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    # --- Learning Mode Methods ---
    def show_course_overview(self):
        if not self.learning_widget: return
        self.learning_ui_views["overview"].refresh_view()
        self.learning_ui_views["progress"].refresh_view()
        self.learning_ui_views["central_stack"].setCurrentWidget(self.learning_ui_views["placeholder"])

    def start_lesson(self, lesson_id: str):
        if not self.learning_widget: return
        lesson_view = self.learning_ui_views["lesson"]
        lesson_view.start_lesson(lesson_id)
        self.learning_ui_views["central_stack"].setCurrentWidget(lesson_view)

    def start_review_session(self):
        if not self.learning_widget: return
        review_view = self.learning_ui_views["review"]
        review_view.start_review_session()
        if review_view.total_exercises_in_session > 0:
            self.learning_ui_views["central_stack"].setCurrentWidget(review_view)

    # --- Overridden Events ---
    def closeEvent(self, event):
        if self.progress_manager:
            self.progress_manager.save_progress()
        
        if self.editor_view and self.editor_view.is_dirty:
            self.editor_view.close_editor()
            if self.editor_view.isVisible():
                event.ignore()
                return

        super().closeEvent(event)
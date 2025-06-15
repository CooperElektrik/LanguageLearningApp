import logging
from PySide6.QtWidgets import (
    QMainWindow, QStackedWidget, QMessageBox, QLabel, QWidget, QFileDialog, QToolBar,
    QVBoxLayout, QDockWidget
)
from PySide6.QtCore import Qt
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

        # This container holds the course selection view and is the "home" state
        self.selection_container = QWidget()
        layout = QVBoxLayout(self.selection_container)
        layout.setContentsMargins(0,0,0,0)
        self.course_selection_view = CourseSelectionView()
        self.course_selection_view.course_selected.connect(self._load_course_for_learning)
        layout.addWidget(self.course_selection_view)

        self._setup_file_menu()
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

        self.right_panel_stack = QStackedWidget()
        self.setCentralWidget(self.right_panel_stack)

        self.navigation_dock_widget = QDockWidget(self.tr("Course Navigation"), self)
        self.course_overview_view = CourseOverviewView(self.course_manager, self.progress_manager)
        self.navigation_dock_widget.setWidget(self.course_overview_view)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.navigation_dock_widget)

        self.progress_dock_widget = QDockWidget(self.tr("Progress & Achievements"), self)
        self.progress_view = ProgressView(self.course_manager, self.progress_manager)
        self.progress_dock_widget.setWidget(self.progress_view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.progress_dock_widget)

        self.lesson_view = LessonView(self.course_manager, self.progress_manager)
        self.review_view = ReviewView(self.course_manager, self.progress_manager)
        self.glossary_view = GlossaryView(self.course_manager)
        self.right_panel_placeholder = QLabel(self.tr("Select a lesson or start a review."), alignment=Qt.AlignCenter)
        
        self.right_panel_stack.addWidget(self.right_panel_placeholder)
        self.right_panel_stack.addWidget(self.lesson_view)
        self.right_panel_stack.addWidget(self.review_view)
        self.right_panel_stack.addWidget(self.glossary_view)

        self.course_overview_view.lesson_selected.connect(self.start_lesson)
        self.course_overview_view.start_review_session_requested.connect(self.start_review_session)
        self.review_view.review_session_finished.connect(self.show_course_overview)
        self.lesson_view.back_to_overview_signal.connect(self.show_course_overview)
        
        self._setup_learning_menu()

    def _setup_editing_ui(self, course_manager):
        """Builds the editing interface."""
        # self._clear_dynamic_widgets()
        
        self.editor_view = CourseEditorView(course_manager)
        self.editor_view.editor_closed.connect(self._return_to_selection_screen)
        self.setCentralWidget(self.editor_view)
        self.menuBar().clear()

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
        self.menuBar().clear()
        file_menu = self.menuBar().addMenu(self.tr("&File"))
        file_menu.addAction(self.tr("Return to Course Selection"), self._return_to_selection_screen)
        file_menu.addSeparator()
        file_menu.addAction(self.tr("&Settings..."), self.show_settings_dialog)

        learning_menu = self.menuBar().addMenu(self.tr("&Learning"))
        learning_menu.addAction(self.tr("Start Due Review"), self.start_review_session)

        view_menu = self.menuBar().addMenu(self.tr("&View"))
        view_menu.addAction(self.navigation_dock_widget.toggleViewAction())
        view_menu.addAction(self.progress_dock_widget.toggleViewAction())

    def _return_to_selection_screen(self):
        self._clear_dynamic_widgets()
        self.setWindowTitle(self.tr("LinguaLearn"))
        self.setCentralWidget(self.selection_container)
        self._setup_file_menu()

    def _clear_dynamic_widgets(self):
        """Removes all docks and the central widget to prepare for a new UI state."""
        for dock in self.findChildren(QDockWidget):
            self.removeDockWidget(dock)
            dock.deleteLater()
        
        # Take the central widget out so we can delete it.
        # This prevents it from being deleted by Qt automatically when a new one is set.
        current_central = self.takeCentralWidget()
        if current_central and current_central != self.selection_container:
            current_central.deleteLater()

        self.course_manager = None
        self.progress_manager = None
        self.navigation_dock_widget = None
        self.progress_dock_widget = None
        self.editor_view = None

    def show_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    # --- Learning Mode Methods ---
    def show_course_overview(self):
        if not self.course_manager: return
        self.course_overview_view.refresh_view()
        self.progress_view.refresh_view()
        self.right_panel_stack.setCurrentWidget(self.right_panel_placeholder)

    def start_lesson(self, lesson_id: str):
        if not hasattr(self, 'lesson_view') or not self.lesson_view: return
        self.lesson_view.start_lesson(lesson_id)
        self.right_panel_stack.setCurrentWidget(self.lesson_view)

    def start_review_session(self):
        if not hasattr(self, 'review_view') or not self.review_view: return
        self.review_view.start_review_session()
        if self.review_view.total_exercises_in_session > 0:
            self.right_panel_stack.setCurrentWidget(self.review_view)

    def closeEvent(self, event):
        if self.progress_manager:
            self.progress_manager.save_progress()
        
        # Check for unsaved changes if in editor mode
        if hasattr(self, 'editor_view') and self.editor_view and self.editor_view.is_dirty:
            self.editor_view.close_editor()
            # If the user cancels the close, we should ignore the event
            if self.editor_view.isVisible():
                event.ignore()
                return

        super().closeEvent(event)
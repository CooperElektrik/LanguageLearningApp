import sys
import logging
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox, QLabel, QWidget, QHBoxLayout, QVBoxLayout, QDockWidget
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
        self.setGeometry(100, 100, 960, 720)

        # The QMainWindow will now manage the layout with its central widget and dock widgets.

        if not self.course_load_failed:
            self._setup_views()
            self._setup_menu_bar()
            self.show_course_overview() # Go to initial state
        else:
            # If course fails to load, we still need a central widget.
            error_widget = QWidget()
            error_layout = QVBoxLayout(error_widget)
            error_label = QLabel(self.tr("Failed to load course. Please check logs and restart."), self)
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setWordWrap(True)
            error_layout.addWidget(error_label)
            self.setCentralWidget(error_widget)
            logger.error("MainWindow initialized in a course-load-failed state. Limited functionality.")


    def _setup_views(self):
        """Initializes and adds all views to the correct panels and connects signals."""
        
        # --- Setup Navigation Dock Widget (Left Panel) ---
        self.navigation_dock_widget = QDockWidget(self.tr("Course Navigation"), self)
        self.navigation_dock_widget.setObjectName("navigation_dock_widget")
        self.course_overview_view = CourseOverviewView(
            self.course_manager, self.progress_manager
        )
        self.navigation_dock_widget.setWidget(self.course_overview_view)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.navigation_dock_widget)

        # --- Setup Progress Dock Widget ---
        self.progress_dock_widget = QDockWidget(self.tr("Progress & Achievements"), self)
        self.progress_dock_widget.setObjectName("progress_dock_widget")
        self.progress_view = ProgressView(self.course_manager,self.progress_manager)
        self.progress_dock_widget.setWidget(self.progress_view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.progress_dock_widget) # Default to right side

        # --- Setup Central Widget (Right Panel Stack) ---
        self.right_panel_stack = QStackedWidget()
        self.right_panel_stack.setObjectName("right_panel_stack")
        self.setCentralWidget(self.right_panel_stack)

        self.lesson_view = LessonView(self.course_manager, self.progress_manager)
        self.review_view = ReviewView(self.course_manager, self.progress_manager)
        self.glossary_view = GlossaryView(self.course_manager)

        self.right_panel_placeholder = QWidget()
        placeholder_layout = QVBoxLayout(self.right_panel_placeholder)
        placeholder_layout.setAlignment(Qt.AlignCenter)
        placeholder_label = QLabel(self.tr("Select a lesson to begin, start a review session, or view the glossary from the menu."))
        placeholder_label.setObjectName("placeholder_label")
        placeholder_label.setWordWrap(True)
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_layout.addWidget(placeholder_label)

        self.right_panel_stack.addWidget(self.right_panel_placeholder)
        self.right_panel_stack.addWidget(self.lesson_view)
        self.right_panel_stack.addWidget(self.review_view)
        self.right_panel_stack.addWidget(self.glossary_view)

        # --- Connect Signals ---
        self.course_overview_view.lesson_selected.connect(self.start_lesson)
        self.course_overview_view.start_review_session_requested.connect(self.start_review_session)
        
        self.lesson_view.lesson_completed_signal.connect(self.handle_lesson_completion)
        self.lesson_view.back_to_overview_signal.connect(self.show_course_overview)
        
        self.review_view.review_session_finished.connect(self.show_course_overview)
        self.review_view.back_to_overview_signal.connect(self.show_course_overview)
        
        self.glossary_view.back_to_overview_signal.connect(self.show_course_overview)

    def _setup_menu_bar(self):
        """Sets up the main menu bar and its actions."""
        menu_bar = self.menuBar()
        
        # --- Learning Menu ---
        learning_menu = menu_bar.addMenu(self.tr("&Learning"))

        self.start_review_action = QAction(self.tr("&Start Review"), self)
        self.start_review_action.setShortcut(Qt.CTRL | Qt.Key_R)
        self.start_review_action.setStatusTip(
            self.tr("Start a spaced repetition review session")
        )
        self.start_review_action.triggered.connect(self.start_review_session)
        learning_menu.addAction(self.start_review_action)

        self.show_glossary_action = QAction(self.tr("&Glossary"), self)
        self.show_glossary_action.setShortcut(Qt.CTRL | Qt.Key_G)
        self.show_glossary_action.setStatusTip(self.tr("View the course glossary"))
        self.show_glossary_action.triggered.connect(self.show_glossary_view)
        learning_menu.addAction(self.show_glossary_action)

        # --- View Menu ---
        view_menu = menu_bar.addMenu(self.tr("&View"))
        # Add actions to toggle visibility of both dock widgets
        view_menu.addAction(self.navigation_dock_widget.toggleViewAction())
        view_menu.addAction(self.progress_dock_widget.toggleViewAction())


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
    
    def _dump_state(self) -> None:
        """
        Dumps the current state of the course and progress for debugging.
        """
        state_str = "--- Application State Dump ---\n"
        
        if self.course_load_failed:
            state_str += "Course Load Status: FAILED\n"
            return state_str # No further state to dump if course failed

        state_str += "Course Load Status: SUCCESS\n"
        state_str += f"Course Title: {self.course_manager.get_course_title()}\n"
        state_str += f"Total XP: {self.progress_manager.get_total_xp()}\n"
        state_str += f"Current Streak: {self.progress_manager.get_current_streak()} days\n"
        state_str += f"Current View: {type(self.right_panel_stack.currentWidget()).__name__}\n"
        
        state_str += "\n--- Units and Lessons Status ---\n"
        units = self.course_manager.get_units()
        if not units:
            state_str += "No units defined.\n"
        else:
            for unit in units:
                state_str += f"Unit: {unit.title} (ID: {unit.unit_id})\n"
                if not unit.lessons:
                    state_str += "  No lessons in this unit.\n"
                else:
                    for lesson in unit.lessons:
                        is_unlocked = self.progress_manager.is_lesson_unlocked(lesson.lesson_id, self.course_manager)
                        is_completed = self.progress_manager.is_lesson_completed(lesson.lesson_id, self.course_manager)
                        status = "Completed" if is_completed else ("Unlocked" if is_unlocked else "Locked")
                        state_str += f"  Lesson: {lesson.title} (ID: {lesson.lesson_id}) - Status: {status}\n"
        
        state_str += "\n--- SRS Status (Due Exercises) ---\n"
        all_exercises = self.course_manager.get_all_exercises()
        due_exercises = self.progress_manager.get_due_exercises(all_exercises, limit=None) # Get all due

        if not due_exercises:
            state_str += "No exercises currently due for review.\n"
        else:
            state_str += f"Total due exercises: {len(due_exercises)}\n"
            for i, exercise in enumerate(due_exercises):
                srs_data = self.progress_manager.get_exercise_srs_data(exercise.exercise_id)
                due_date_str = srs_data.get('next_review_due').strftime('%Y-%m-%d %H:%M') if srs_data.get('next_review_due') else "N/A (New)"
                state_str += f"  Due #{i+1}: ID: {exercise.exercise_id}, Prompt: \"{exercise.prompt or exercise.source_word or 'N/A'}\", Due: {due_date_str}\n"
        
        state_str += "\n--- End of State Dump ---\n"
        logger.debug(f"Application State Dump:\n{state_str}") # Log the dump for easier access

    def show_progress_view(self):
        # This method is now obsolete as progress is always visible.
        pass

    def show_course_overview(self):
        if self.course_load_failed:
            return

        # Refresh the views inside the docks
        self.course_overview_view.refresh_view()
        self.progress_view.refresh_view()

        # Set the central widget to the placeholder
        self.right_panel_stack.setCurrentWidget(self.right_panel_placeholder)
        
        # Enable both dock widgets for interaction
        self.navigation_dock_widget.setEnabled(True)
        self.progress_dock_widget.setEnabled(True)
        
        logger.info("Showing course overview (home state). Dock panels enabled.")


    def start_lesson(self, lesson_id: str):
        if self.course_load_failed:
            return
        
        if hasattr(self, "lesson_view") and self.lesson_view:
            logger.info(f"Starting lesson: {lesson_id}")
            # Disable both dock widgets
            self.navigation_dock_widget.setEnabled(False)
            self.progress_dock_widget.setEnabled(False)
            
            # Start lesson and switch central widget
            self.lesson_view.start_lesson(lesson_id)
            self.right_panel_stack.setCurrentWidget(self.lesson_view)
        else:
            logger.warning("Lesson view not available (should not happen if course loaded).")


    def handle_lesson_completion(self, lesson_id: str):
        logger.info(f"Lesson {lesson_id} completed. Returning to overview.")
        self._dump_state()
        self.show_course_overview() # Refresh overview and return to home state


    def start_review_session(self):
        if not self._is_course_available(self.tr("Review Session")):
            return

        if hasattr(self, "review_view") and self.review_view:
            self.review_view.start_review_session()
            if self.review_view.total_exercises_in_session > 0:
                # Disable both dock widgets
                self.navigation_dock_widget.setEnabled(False)
                self.progress_dock_widget.setEnabled(False)
                # Switch central widget
                self.right_panel_stack.setCurrentWidget(self.review_view)
                logger.info("Started review session.")
        else:
            logger.warning("Review view not available (should not happen if course loaded).")


    def show_glossary_view(self):
        if not self._is_course_available(self.tr("Glossary")):
            return
        
        if not self.course_manager.get_glossary_entries():
            QMessageBox.information(
                self, 
                self.tr("Glossary Empty"), 
                self.tr("No glossary entries found for this course.")
            )
            return

        if hasattr(self, "glossary_view") and self.glossary_view:
            # Disable both dock widgets
            self.navigation_dock_widget.setEnabled(False)
            self.progress_dock_widget.setEnabled(False)
            # Refresh and switch central widget
            self.glossary_view.refresh_view()
            self.right_panel_stack.setCurrentWidget(self.glossary_view)
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
        super().closeEvent(event)
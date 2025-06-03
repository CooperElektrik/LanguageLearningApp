import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QGroupBox,
    QStyle,
)
from PySide6.QtCore import Signal, Qt
from core.course_manager import CourseManager
from core.progress_manager import ProgressManager

logger = logging.getLogger(__name__)

class CourseOverviewView(QWidget):
    lesson_selected = Signal(str) # lesson_id
    start_review_session_requested = Signal()

    def __init__(self, course_manager: CourseManager, progress_manager: ProgressManager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Course Title
        title_label = QLabel(
            self.course_manager.get_course_title() or self.tr("Language Course")
        )
        title_label.setObjectName("course_title_label") # For QSS
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title_label)

        # XP Label
        self.xp_label = QLabel()
        self.xp_label.setObjectName("xp_total_label")
        self.xp_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.main_layout.addWidget(self.xp_label)

        # SRS/Daily Review Section
        self.srs_groupbox = QGroupBox(self.tr("Daily Review"))
        self.srs_groupbox.setObjectName("srs_groupbox")
        srs_layout = QVBoxLayout(self.srs_groupbox)

        self.due_count_label = QLabel()
        self.due_count_label.setObjectName("srs_due_count_label")
        self.due_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        srs_layout.addWidget(self.due_count_label)

        self.start_review_button = QPushButton()
        self.start_review_button.setObjectName("start_review_button_main")
        self.start_review_button.clicked.connect(self.start_review_session_requested.emit)
        srs_layout.addWidget(self.start_review_button)
        self.main_layout.addWidget(self.srs_groupbox)

        # Units and Lessons Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("course_units_scroll_area")
        self.scroll_area.setWidgetResizable(True)
        
        self.scroll_content_widget = QWidget() # Container for the units_layout
        self.units_layout = QVBoxLayout(self.scroll_content_widget)
        self.units_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.scroll_content_widget)

        self.main_layout.addWidget(self.scroll_area)
        
        # Initial population of dynamic content
        self.refresh_view()


    def _clear_layout(self, layout: QVBoxLayout):
        """Helper to remove all widgets from a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    # If item is a layout, clear it recursively (not strictly needed here but good practice)
                    sub_layout = item.layout()
                    if sub_layout is not None:
                        self._clear_layout(sub_layout)


    def _populate_course_units(self):
        """Clears and repopulates the units and lessons display."""
        self._clear_layout(self.units_layout) # Clear previous unit groupboxes

        units = self.course_manager.get_units()
        if not units:
            no_units_label = QLabel(self.tr("No units available in this course."))
            no_units_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.units_layout.addWidget(no_units_label)
            return

        all_course_units_for_unlock_check = units # For clarity, or pass self.course_manager.get_units() directly

        for unit in units:
            unit_groupbox = QGroupBox(unit.title)
            unit_groupbox.setObjectName("unit_groupbox")
            unit_layout = QVBoxLayout(unit_groupbox)

            if not unit.lessons:
                no_lessons_label = QLabel(self.tr("This unit has no lessons."))
                unit_layout.addWidget(no_lessons_label)
            else:
                for lesson in unit.lessons:
                    is_completed = self.progress_manager.is_lesson_completed(
                        lesson.lesson_id, self.course_manager
                    )
                    is_unlocked = self.progress_manager.is_lesson_unlocked(
                        lesson.lesson_id,
                        self.course_manager,
                    )

                    lesson_button = QPushButton(lesson.title)
                    lesson_button.setObjectName("lesson_button")

                    icon = None
                    status_property = "locked" # For QSS styling via custom property
                    if is_completed:
                        icon = self.style().standardIcon(QStyle.SP_DialogApplyButton) # Example: Checkmark like icon
                        status_property = "completed"
                    elif is_unlocked:
                        icon = self.style().standardIcon(QStyle.SP_MediaPlay) # Play icon
                        status_property = "unlocked"
                    else:
                        icon = self.style().standardIcon(QStyle.SP_DialogCancelButton) # Example: Lock or NoEntry icon
                        # status_property remains "locked"
                    
                    if icon:
                        lesson_button.setIcon(icon)
                    
                    lesson_button.setProperty("status", status_property) # For QSS: button[status="completed"] {...}

                    if is_unlocked or is_completed: # Clickable if unlocked or completed (to review)
                        lesson_button.setEnabled(True)
                        lesson_button.clicked.connect(
                            # Use a lambda that captures current lesson_id
                            lambda checked=False, lid=lesson.lesson_id: self.lesson_selected.emit(lid)
                        )
                    else: # Locked
                        lesson_button.setEnabled(False)
                        # Disabled appearance will be handled by QSS or default Qt style for disabled buttons

                    unit_layout.addWidget(lesson_button)
            
            self.units_layout.addWidget(unit_groupbox)

    def refresh_view(self):
        """Refreshes all dynamic content in the view."""
        if self.course_manager.course is None: # Should not happen if MainWindow handles course_load_failed
            logger.warning("RefreshView called but no course is loaded.")
            # Display an error or clear the view
            self._clear_layout(self.units_layout)
            self.xp_label.setText(self.tr("Course not loaded."))
            self.due_count_label.setText(self.tr("N/A"))
            self.start_review_button.setText(self.tr("N/A"))
            self.start_review_button.setEnabled(False)
            return

        # Refresh XP label
        self.xp_label.setText(self.tr("Total XP: {0}").format(self.progress_manager.get_total_xp()))

        # Refresh SRS Dashboard
        all_exercises = self.course_manager.get_all_exercises()
        # Get all due exercises for an accurate count, review view will limit actual session size
        due_exercises_count = len(self.progress_manager.get_due_exercises(all_exercises, limit=None)) 
        
        if due_exercises_count > 0:
            self.due_count_label.setText(self.tr("{0} exercises due for review.").format(due_exercises_count))
            self.start_review_button.setEnabled(True)
            self.start_review_button.setText(self.tr("Start Review Session"))
        else:
            self.due_count_label.setText(self.tr("No exercises due for review right now!")) # Simplified
            self.start_review_button.setEnabled(False)
            self.start_review_button.setText(self.tr("No Reviews Due"))

        # Re-populate course units (lessons/units)
        self._populate_course_units()
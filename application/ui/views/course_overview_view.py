import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QGroupBox,
    QStyle,
    QHBoxLayout,
)  # Add QEvent
from PySide6.QtCore import Signal, Qt, QEvent  # Add QEvent
from core.course_manager import CourseManager
from core.progress_manager import ProgressManager

logger = logging.getLogger(__name__)


class CourseOverviewView(QWidget):
    lesson_selected = Signal(str)  # lesson_id
    start_review_session_requested = Signal()
    start_weakest_review_requested = Signal()  # New signal

    def __init__(
        self,
        course_manager: CourseManager,
        progress_manager: ProgressManager,
        parent=None,
    ):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Course Title
        self.course_title_label = (
            QLabel()
        )  # Will be set in refresh_view or retranslateUi
        self.course_title_label.setObjectName("course_title_label")  # For QSS
        self.course_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.course_title_label)

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

        review_buttons_layout = QHBoxLayout()
        self.start_review_button = QPushButton(self.tr("Review Due"))
        self.start_review_button.setObjectName("start_review_button_main")
        self.start_review_button.clicked.connect(
            self.start_review_session_requested.emit
        )
        review_buttons_layout.addWidget(self.start_review_button)

        self.start_weak_review_button = QPushButton(self.tr("Review Weak"))
        self.start_weak_review_button.setObjectName("start_weak_review_button")
        self.start_weak_review_button.setToolTip(
            self.tr("Review items you struggle with the most.")
        )
        self.start_weak_review_button.clicked.connect(
            self.start_weakest_review_requested.emit
        )
        # review_buttons_layout.addWidget(self.start_weak_review_button)

        srs_layout.addLayout(review_buttons_layout)
        self.main_layout.addWidget(self.srs_groupbox)

        # Units and Lessons Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("course_units_scroll_area")
        self.scroll_area.setWidgetResizable(True)

        self.scroll_content_widget = QWidget()
        self.scroll_content_widget.setObjectName("course_units_container")
        self.units_layout = QVBoxLayout(self.scroll_content_widget)
        self.units_layout.setSpacing(10)
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
                    sub_layout = item.layout()
                    if sub_layout is not None:
                        self._clear_layout(sub_layout)

    def _populate_course_units(self):
        """Clears and repopulates the units and lessons display."""
        self._clear_layout(self.units_layout)  # Clear previous unit groupboxes

        units = self.course_manager.get_units()
        if not units:
            no_units_label = QLabel(self.tr("No units available in this course."))
            no_units_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.units_layout.addWidget(no_units_label)
            return

        all_course_units_for_unlock_check = units

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
                    status_property = "locked"
                    if is_completed:
                        icon = self.style().standardIcon(QStyle.SP_DialogApplyButton)
                        status_property = "completed"
                    elif is_unlocked:
                        icon = self.style().standardIcon(QStyle.SP_MediaPlay)
                        status_property = "unlocked"
                    else:
                        icon = self.style().standardIcon(QStyle.SP_DialogCancelButton)

                    if icon:
                        lesson_button.setIcon(icon)

                    lesson_button.setProperty("status", status_property)
                    if is_unlocked or is_completed:
                        lesson_button.setEnabled(True)
                        lesson_button.clicked.connect(
                            lambda checked=False, lid=lesson.lesson_id: self.lesson_selected.emit(
                                lid
                            )
                        )
                    else:
                        lesson_button.setEnabled(False)

                    unit_layout.addWidget(lesson_button)

            self.units_layout.addWidget(unit_groupbox)

    def refresh_view(self):
        """Refreshes all dynamic content in the view."""
        if self.course_manager.course is None:
            logger.warning("RefreshView called but no course is loaded.")
            self._clear_layout(self.units_layout)
            self.xp_label.setText(self.tr("Course not loaded."))
            self.due_count_label.setText(self.tr("N/A"))
            self.start_review_button.setEnabled(False)
            self.start_weak_review_button.setEnabled(False)
            return

        # Set course title (can be retranslated)
        self.course_title_label.setText(
            self.course_manager.get_course_title() or self.tr("Language Course")
        )

        self.xp_label.setText(
            self.tr("Total XP: {0}").format(self.progress_manager.get_total_xp())
        )

        all_exercises = self.course_manager.get_all_exercises()
        due_exercises_count = len(
            self.progress_manager.get_due_exercises(all_exercises, limit=None)
        )
        weak_exercises_count = len(
            self.progress_manager.get_weakest_exercises(all_exercises, limit=None)
        )

        if due_exercises_count > 0:
            self.due_count_label.setText(
                self.tr("{0} exercises due for review.").format(due_exercises_count)
            )
            self.start_review_button.setEnabled(True)
        else:
            self.due_count_label.setText(
                self.tr("No exercises due for review right now!")
            )
            self.start_review_button.setEnabled(False)

        self.start_weak_review_button.setEnabled(weak_exercises_count > 0)

        self._populate_course_units()

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        # Retranslate static parts
        self.course_title_label.setText(
            self.course_manager.get_course_title() or self.tr("Language Course")
        )
        self.srs_groupbox.setTitle(self.tr("Daily Review"))
        self.start_review_button.setText(self.tr("Review Due"))
        # self.start_weak_review_button.setText(self.tr("Review Weak"))
        self.start_weak_review_button.setToolTip(
            self.tr("Review items you struggle with the most.")
        )

        # Refresh dynamic parts that also contain translatable strings
        self.refresh_view()  # This will re-populate units/lessons and update due_count_label, xp_label

        logger.debug("CourseOverviewView retranslated.")

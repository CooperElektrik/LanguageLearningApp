# application/tools/widgets/exercise_preview_widget.py

import logging
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from application.core.models import Exercise
from application.ui.widgets.exercise_widgets import (
    BaseExerciseWidget,
    ContextBlockWidget,
    FillInTheBlankExerciseWidget,
    ListenSelectExerciseWidget,
    MultipleChoiceExerciseWidget,
    SentenceJumbleExerciseWidget,
    TranslationExerciseWidget,
)

logger = logging.getLogger(__name__)


class MockCourseManager(QObject):
    """Provides a lightweight runtime context for previewing exercise widgets."""

    def __init__(
        self,
        course_languages: dict[str, str] | None = None,
        course_content_base_dir: str | None = None,
        parent=None,
        manifest: dict[str, Any] | None = None,
    ):
        if isinstance(parent, dict) and manifest is None:
            manifest = parent
            parent = None
        super().__init__(parent)
        self.manifest = manifest or {}
        languages = course_languages or {}
        if not languages and self.manifest:
            languages = {
                "target": self.manifest.get("target_language", "Target Language"),
                "source": self.manifest.get("source_language", "Source Language"),
            }
        self.target_language = languages.get("target", "Target Language")
        self.source_language = languages.get("source", "Source Language")
        self.course_content_base_dir = course_content_base_dir or ""
        self.course_title = self.manifest.get("course_title", "Mock Course")

        try:
            from application.core.models import Course
            self.course = Course(
                course_id=self.get_course_id(),
                title=self.course_title,
                units=[],
            )
        except Exception:
            self.course = None

    def get_course_title(self) -> str:
        return self.course_title

    def get_course_id(self) -> str:
        return self.manifest.get("course_id", "mock_course_id")

    def get_all_exercises(self) -> list:
        return []

    def get_lesson(self, lesson_id: str):
        from application.core.models import Lesson
        return Lesson(lesson_id=lesson_id, title=f"Mock Lesson {lesson_id}", exercises=[])

    def get_target_language(self) -> str:
        return self.target_language

    def get_source_language(self) -> str:
        return self.source_language

    def get_course_content_directory(self) -> str:
        return self.course_content_base_dir

    def get_course_manifest_directory(self) -> str:
        return self.course_content_base_dir

    def get_asset_directory(self) -> str:
        return self.course_content_base_dir

    def get_glossary_entries(self) -> list:
        return []

    def get_glossary_entry_by_word(self, word: str):
        return None

    def get_formatted_prompt_data(self, exercise: Exercise) -> dict[str, Any]:
        return {"args": [exercise.prompt or exercise.sentence_template or ""]}

    def check_answer(self, exercise: Exercise, user_answer: str) -> tuple[bool, str]:
        correct_display = "N/A"
        ex_type = exercise.type
        if ex_type in ["translate_to_target", "translate_to_source"]:
            correct_display = exercise.answer or "Missing Answer"
        elif ex_type in ["multiple_choice_translation", "image_association"]:
            correct_option = next(
                (opt for opt in exercise.options if getattr(opt, "correct", False)),
                None,
            )
            correct_display = correct_option.text if correct_option else "No Correct Option"
        elif ex_type == "fill_in_the_blank":
            correct_display = exercise.correct_option or "Missing Correct Option"
        elif ex_type == "sentence_jumble":
            correct_display = " ".join(exercise.words) if exercise.words else "Missing Words"
        elif ex_type == "dictation":
            correct_display = exercise.answer or "Missing Answer"
        return False, f"Correct answer: {correct_display}"


def create_preview_exercise_widget(
    exercise: Exercise, mock_mgr: MockCourseManager, parent: QWidget | None = None
) -> QWidget:
    """Instantiates the runtime learner widget for an exercise in preview mode."""
    ex_type = exercise.type
    if ex_type in ["translate_to_target", "translate_to_source", "dictation"]:
        return TranslationExerciseWidget(exercise, mock_mgr, parent=parent)
    elif ex_type in ["multiple_choice_translation", "image_association"]:
        return MultipleChoiceExerciseWidget(exercise, mock_mgr, parent=parent)
    elif ex_type == "fill_in_the_blank":
        return FillInTheBlankExerciseWidget(exercise, mock_mgr, parent=parent)
    elif ex_type == "sentence_jumble":
        return SentenceJumbleExerciseWidget(exercise, mock_mgr, parent=parent)
    elif ex_type == "context_block":
        return ContextBlockWidget(exercise, mock_mgr, parent=parent)
    elif ex_type == "listen_and_select":
        return ListenSelectExerciseWidget(exercise, mock_mgr, parent=parent)
    else:
        label = QLabel(f"Preview unavailable for exercise type: {ex_type}", parent=parent)
        label.setAlignment(Qt.AlignCenter)
        return label


class ExercisePreviewWidget(QWidget):
    """
    Self-contained, reusable exercise preview widget that renders live exercises,
    allows testing responses, and checks answers via MockCourseManager.
    Used by both the LivePreviewPane in the editor dock and the modal ExercisePreviewDialog.
    """

    preview_refreshed = Signal()

    def __init__(
        self,
        course_languages: dict[str, str] | None = None,
        course_content_base_dir: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("ExercisePreviewWidget")
        self.course_languages = course_languages or {"target": "Target Language", "source": "Source Language"}
        self.course_content_base_dir = course_content_base_dir
        self.current_exercise: Exercise | None = None
        self.current_preview_widget: QWidget | None = None
        self.mock_course_manager = MockCourseManager(
            self.course_languages, self.course_content_base_dir, self
        )

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        self.title_label = QLabel("<b>Live Exercise Preview</b>")
        self.type_badge = QLabel("")
        self.type_badge.setStyleSheet(
            "background-color: #3867d6; color: white; border-radius: 4px; padding: 2px 6px; font-weight: bold; font-size: 11px;"
        )
        self.type_badge.setVisible(False)

        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.type_badge)
        header_layout.addStretch(1)

        self.refresh_button = QPushButton("↻ Refresh")
        self.refresh_button.setToolTip("Refresh preview with latest values")
        self.refresh_button.clicked.connect(self.refresh_preview)
        header_layout.addWidget(self.refresh_button)

        main_layout.addLayout(header_layout)

        # Preview Container inside scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.preview_container = QFrame()
        self.preview_container_layout = QVBoxLayout(self.preview_container)
        self.preview_container_layout.setContentsMargins(6, 6, 6, 6)
        self.preview_container_layout.setAlignment(Qt.AlignCenter)

        self.placeholder_label = QLabel("Select an exercise to preview in real-time.")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #888899; font-style: italic;")
        self.preview_container_layout.addWidget(self.placeholder_label)

        self.scroll_area.setWidget(self.preview_container)
        main_layout.addWidget(self.scroll_area, 1)

        # Bottom test bar
        self.test_bar = QWidget()
        test_bar_layout = QHBoxLayout(self.test_bar)
        test_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.feedback_label = QLabel("Preview Mode: Inputs not graded")
        self.feedback_label.setStyleSheet("color: #888899; font-size: 11px;")
        test_bar_layout.addWidget(self.feedback_label, 1)

        self.show_answer_button = QPushButton("Show Answer")
        self.show_answer_button.clicked.connect(self.show_answer)
        self.show_answer_button.setEnabled(False)
        test_bar_layout.addWidget(self.show_answer_button)

        main_layout.addLayout(test_bar_layout)

    def set_course_context(self, languages: dict[str, str] | None, base_dir: str | None):
        if languages:
            self.course_languages = languages
        self.course_content_base_dir = base_dir
        self.mock_course_manager = MockCourseManager(
            self.course_languages, self.course_content_base_dir, self
        )

    def update_preview(self, exercise: Exercise | None):
        """Renders the live interactive view for the given exercise."""
        self.current_exercise = exercise
        self.feedback_label.setText("Preview Mode: Inputs not graded")
        self.feedback_label.setStyleSheet("color: #888899; font-size: 11px;")

        # Clear existing preview widget
        if self.current_preview_widget:
            self.preview_container_layout.removeWidget(self.current_preview_widget)
            self.current_preview_widget.deleteLater()
            self.current_preview_widget = None

        if not exercise or not isinstance(exercise, Exercise):
            self.type_badge.setVisible(False)
            self.placeholder_label.setVisible(True)
            self.placeholder_label.setText("Select an exercise to preview in real-time.")
            self.show_answer_button.setEnabled(False)
            return

        self.placeholder_label.setVisible(False)
        self.type_badge.setText(exercise.type.replace("_", " ").upper())
        self.type_badge.setVisible(True)
        self.show_answer_button.setEnabled(True)

        try:
            widget = create_preview_exercise_widget(
                exercise, self.mock_course_manager, self.preview_container
            )
            self.current_preview_widget = widget
            self.preview_container_layout.addWidget(widget)
            if hasattr(widget, "set_focus_on_input"):
                widget.set_focus_on_input()
        except Exception as e:
            logger.error(f"Error creating live preview: {e}")
            err_label = QLabel(f"Error loading preview: {e}")
            err_label.setStyleSheet("color: #ff5252;")
            self.current_preview_widget = err_label
            self.preview_container_layout.addWidget(err_label)

    def refresh_preview(self):
        if self.current_exercise:
            self.update_preview(self.current_exercise)
        self.preview_refreshed.emit()

    def show_answer(self):
        if not self.current_exercise:
            return
        _, msg = self.mock_course_manager.check_answer(self.current_exercise, "")
        self.feedback_label.setText(msg)
        self.feedback_label.setStyleSheet("color: #4b7bec; font-weight: bold; font-size: 11px;")

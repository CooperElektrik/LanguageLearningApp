import os
import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import (
    Qt,
    QObject,
)
from PySide6.QtGui import QFont
from typing import Dict, Tuple, Any

try:
    from application.core.models import Exercise

    from application.core.course_manager import (
        PROMPT_KEY_CONTEXT_BLOCK,
        PROMPT_KEY_DEFAULT,
        PROMPT_KEY_DICTATION,
        PROMPT_KEY_FIB,
        PROMPT_KEY_IMAGE_ASSOCIATION,
        PROMPT_KEY_LISTEN_SELECT,
        PROMPT_KEY_MCQ_TRANSLATION,
        PROMPT_KEY_SENTENCE_JUMBLE,
        PROMPT_KEY_TRANSLATE_TO_SOURCE,
        PROMPT_KEY_TRANSLATE_TO_TARGET
    )

    from application.ui.widgets.exercise_widgets import (
        TranslationExerciseWidget,
        MultipleChoiceExerciseWidget,
        FillInTheBlankExerciseWidget,
        BaseExerciseWidget,
        ListenSelectExerciseWidget,
        SentenceJumbleExerciseWidget,
        ContextBlockWidget
    )
except ImportError as e:
    logging.error(f"Failed to import core or UI widgets for preview dialog. Error: {e}", stack_info=True)

    class Exercise:
        pass

    class BaseExerciseWidget:
        pass

    class TranslationExerciseWidget:
        pass

    class MultipleChoiceExerciseWidget:
        pass

    class FillInTheBlankExerciseWidget:
        pass


logger = logging.getLogger(__name__)


class MockCourseManager(QObject):
    def __init__(
        self,
        course_languages: Dict[str, str],
        course_content_base_dir: str,
        parent=None,
    ):
        super().__init__(parent)
        self.target_language = course_languages.get("target", "Target Language")
        self.source_language = course_languages.get("source", "Source Language")
        self.course_content_base_dir = course_content_base_dir

    def get_target_language(self) -> str:
        return self.target_language

    def get_source_language(self) -> str:
        return self.source_language

    def get_course_content_directory(self) -> str:
        return self.course_content_base_dir

    def get_course_manifest_directory(self) -> str:
        return self.course_content_base_dir

    def get_formatted_prompt(self, exercise: Exercise) -> str:
        """Mimics CourseManager's method for formatting prompts."""
        if exercise.type == "translate_to_target":
            return f"Translate to {self.target_language}: \"{exercise.prompt or ''}\""
        elif exercise.type == "translate_to_source":
            return f"Translate to {self.source_language}: \"{exercise.prompt or ''}\""
        elif exercise.type == "multiple_choice_translation":
            return f"Choose the {self.target_language} translation for: \"{exercise.source_word or ''}\" ({self.source_language})"
        elif exercise.type == "fill_in_the_blank":
            return f"{exercise.sentence_template or ''} (Hint: {exercise.translation_hint or ''})"
        return (
            exercise.prompt
            or exercise.source_word
            or exercise.sentence_template
            or "Exercise Prompt (no text)"
        )
    
    def get_formatted_prompt_data(self, exercise: Exercise) -> Dict[str, Any]:
        """
        Returns a dictionary with a template_key and arguments for formatting the prompt.
        """
        prompt_text = exercise.prompt or ""

        if exercise.type == "translate_to_target":
            return {"template_key": PROMPT_KEY_TRANSLATE_TO_TARGET, "args": [self.target_language, prompt_text]}
        elif exercise.type == "translate_to_source":
            return {"template_key": PROMPT_KEY_TRANSLATE_TO_SOURCE, "args": [self.source_language, prompt_text]}
        elif exercise.type == "dictation":
            return {"template_key": PROMPT_KEY_DICTATION, "args": [prompt_text]}
        elif exercise.type == "multiple_choice_translation":
            return {"template_key": PROMPT_KEY_MCQ_TRANSLATION, "args": [self.target_language, exercise.source_word or "", self.source_language]}
        elif exercise.type == "fill_in_the_blank":
            return {"template_key": PROMPT_KEY_FIB, "args": [exercise.sentence_template or "", exercise.translation_hint or ""]}
        elif exercise.type == "image_association":
            return {"template_key": PROMPT_KEY_IMAGE_ASSOCIATION, "args": [prompt_text]}
        elif exercise.type == "listen_and_select":
            return {"template_key": PROMPT_KEY_LISTEN_SELECT, "args": [prompt_text]}
        elif exercise.type == "sentence_jumble":
            return {"template_key": PROMPT_KEY_SENTENCE_JUMBLE, "args": [prompt_text]}
        elif exercise.type == "context_block":
            return {"template_key": PROMPT_KEY_CONTEXT_BLOCK, "args": [exercise.title or ""]}
        
        return {"template_key": PROMPT_KEY_DEFAULT, "args": [prompt_text]}

    def check_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """Minimal mock check_answer for preview. Just provides the correct answer."""
        correct_answer_display = "N/A"
        if exercise.type in ["translate_to_target", "translate_to_source"]:
            correct_answer_display = exercise.answer or "Missing Answer"
        elif exercise.type == "multiple_choice_translation":
            correct_option = next(
                (opt for opt in exercise.options if opt.correct), None
            )
            correct_answer_display = (
                correct_option.text if correct_option else "No Correct Option"
            )
        elif exercise.type == "fill_in_the_blank":
            correct_answer_display = exercise.correct_option or "Missing Correct Option"

        return (
            False,
            f"Correct answer: {correct_answer_display}",
        )


class ExercisePreviewDialog(QDialog):
    def __init__(
        self,
        exercise: Exercise,
        course_languages: Dict[str, str],
        course_content_base_dir: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(
            f"Preview: {exercise.type.replace('_', ' ').title()} Exercise"
        )
        self.setMinimumSize(500, 300)

        self.exercise = exercise
        self.mock_course_manager = MockCourseManager(
            course_languages, course_content_base_dir, self
        )

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        title_label = QLabel(
            f"Exercise Type: {self.exercise.type.replace('_', ' ').title()}"
        )
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        main_layout.addWidget(self._create_separator())

        self.exercise_widget_container = QFrame()
        self.exercise_widget_container.setFrameShape(QFrame.StyledPanel)
        self.exercise_widget_container.setFrameShadow(QFrame.Sunken)
        exercise_widget_layout = QVBoxLayout(self.exercise_widget_container)

        self.current_exercise_widget: BaseExerciseWidget = None

        if (
            self.exercise.type == "translate_to_target"
            or self.exercise.type == "translate_to_source"
            or self.exercise.type == "dictation"
        ):
            self.current_exercise_widget = TranslationExerciseWidget(
                self.exercise, self.mock_course_manager
            )
        elif (
            self.exercise.type == "multiple_choice_translation"
            or self.exercise.type == "image_association"   
        ):
            self.current_exercise_widget = MultipleChoiceExerciseWidget(
                self.exercise, self.mock_course_manager
            )
        elif self.exercise.type == "fill_in_the_blank":
            self.current_exercise_widget = FillInTheBlankExerciseWidget(
                self.exercise, self.mock_course_manager
            )
        elif self.exercise.type == "sentence_jumble":
            self.current_exercise_widget = SentenceJumbleExerciseWidget(self.exercise, self.mock_course_manager)
        elif self.exercise.type == "context_block":
            self.current_exercise_widget = ContextBlockWidget(self.exercise, self.mock_course_manager)
        elif self.exercise.type == "listen_and_select":
            self.current_exercise_widget = ListenSelectExerciseWidget(
                self.exercise, self.mock_course_manager
            )
        else:
            self.current_exercise_widget = QLabel(
                "No preview available for this exercise type."
            )
            self.current_exercise_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if self.current_exercise_widget:
            exercise_widget_layout.addWidget(self.current_exercise_widget)

        main_layout.addWidget(self.exercise_widget_container, 1)

        self.feedback_label = QLabel("Preview mode: Answer submission is not tracked.")
        self.feedback_label.setFont(QFont("Arial", 10))
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.feedback_label)

        button_layout = QHBoxLayout()
        self.show_answer_button = QPushButton("Show Answer")
        self.show_answer_button.clicked.connect(self._show_answer)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        button_layout.addStretch(1)
        button_layout.addWidget(self.show_answer_button)
        button_layout.addWidget(self.close_button)
        button_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        if hasattr(self.current_exercise_widget, "set_focus_on_input"):
            self.current_exercise_widget.set_focus_on_input()

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator

    def _show_answer(self):
        if self.current_exercise_widget:
            _, feedback_text = self.mock_course_manager.check_answer(self.exercise, "")
            self.feedback_label.setText(feedback_text)
            self.feedback_label.setStyleSheet("color: blue; font-weight: bold;")
            self.show_answer_button.setEnabled(False)

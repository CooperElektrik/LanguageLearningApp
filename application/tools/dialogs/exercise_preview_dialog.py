import os
import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QMessageBox, QFrame, QStyle) # Added QStyle for standard icons
from PySide6.QtCore import Qt, QUrl, QObject, Signal # Added QObject, Signal for mock CourseManager
from PySide6.QtGui import QFont, QIcon # Added QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput # For audio playback in preview
from typing import Dict, Tuple

try:
    from core.models import Exercise
    # Import actual ExerciseWidgets from the main application's UI
    from ui.widgets.exercise_widgets import (
        TranslationExerciseWidget, MultipleChoiceExerciseWidget, 
        FillInTheBlankExerciseWidget, BaseExerciseWidget
    )
except ImportError as e:
    logging.error(f"Failed to import core or UI widgets for preview dialog. Error: {e}")
    # Fallback to dummy classes for graceful degradation
    class Exercise: pass
    class BaseExerciseWidget: pass
    class TranslationExerciseWidget: pass
    class MultipleChoiceExerciseWidget: pass
    class FillInTheBlankExerciseWidget: pass


logger = logging.getLogger(__name__)

# --- Mock CourseManager for Preview Context ---
# This minimal mock provides just what the ExerciseWidgets need (formatted prompt, audio base dir).
class MockCourseManager(QObject): # Inherit QObject for signals if needed, not strictly for this mock
    def __init__(self, course_languages: Dict[str, str], course_content_base_dir: str, parent=None):
        super().__init__(parent)
        self._target_language = course_languages.get('target', 'Target Language')
        self._source_language = course_languages.get('source', 'Source Language')
        self._course_content_base_dir = course_content_base_dir

    def get_target_language(self) -> str:
        return self._target_language

    def get_source_language(self) -> str:
        return self._source_language

    def get_course_content_directory(self) -> str:
        return self._course_content_base_dir
    
    def get_course_manifest_directory(self) -> str:
        return self._course_content_base_dir

    def get_formatted_prompt(self, exercise: Exercise) -> str:
        """Mimics CourseManager's method for formatting prompts."""
        if exercise.type == "translate_to_target":
            return f"Translate to {self._target_language}: \"{exercise.prompt or ''}\""
        elif exercise.type == "translate_to_source":
            return f"Translate to {self._source_language}: \"{exercise.prompt or ''}\""
        elif exercise.type == "multiple_choice_translation":
            return f"Choose the {self._target_language} translation for: \"{exercise.source_word or ''}\" ({self._source_language})"
        elif exercise.type == "fill_in_the_blank":
            return f"{exercise.sentence_template or ''} (Hint: {exercise.translation_hint or ''})"
        return exercise.prompt or exercise.source_word or exercise.sentence_template or "Exercise Prompt (no text)"

    def check_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """Minimal mock check_answer for preview. Just provides the correct answer."""
        correct_answer_display = "N/A"
        if exercise.type in ["translate_to_target", "translate_to_source"]:
            correct_answer_display = exercise.answer or "Missing Answer"
        elif exercise.type == "multiple_choice_translation":
            correct_option = next((opt for opt in exercise.options if opt.correct), None)
            correct_answer_display = correct_option.text if correct_option else "No Correct Option"
        elif exercise.type == "fill_in_the_blank":
            correct_answer_display = exercise.correct_option or "Missing Correct Option"
        
        return False, f"Correct answer: {correct_answer_display}" # Always return False, provide correct answer

# --- Exercise Preview Dialog ---
class ExercisePreviewDialog(QDialog):
    def __init__(self, exercise: Exercise, course_languages: Dict[str, str], course_content_base_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Preview: {exercise.type.replace('_', ' ').title()} Exercise")
        self.setMinimumSize(500, 300)

        self.exercise = exercise
        self.mock_course_manager = MockCourseManager(course_languages, course_content_base_dir, self)

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Title/Type Label
        title_label = QLabel(f"Exercise Type: {self.exercise.type.replace('_', ' ').title()}")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        main_layout.addWidget(self._create_separator())

        # Placeholder for exercise widget
        self.exercise_widget_container = QFrame()
        self.exercise_widget_container.setFrameShape(QFrame.StyledPanel)
        self.exercise_widget_container.setFrameShadow(QFrame.Sunken)
        exercise_widget_layout = QVBoxLayout(self.exercise_widget_container)
        
        self.current_exercise_widget: BaseExerciseWidget = None

        # Instantiate the correct ExerciseWidget based on type
        if self.exercise.type == "translate_to_target" or self.exercise.type == "translate_to_source":
            self.current_exercise_widget = TranslationExerciseWidget(self.exercise, self.mock_course_manager)
        elif self.exercise.type == "multiple_choice_translation":
            self.current_exercise_widget = MultipleChoiceExerciseWidget(self.exercise, self.mock_course_manager)
        elif self.exercise.type == "fill_in_the_blank":
            self.current_exercise_widget = FillInTheBlankExerciseWidget(self.exercise, self.mock_course_manager)
        else:
            self.current_exercise_widget = QLabel("No preview available for this exercise type.")
            self.current_exercise_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if self.current_exercise_widget:
            exercise_widget_layout.addWidget(self.current_exercise_widget)
        
        main_layout.addWidget(self.exercise_widget_container, 1) # Exercise widget takes up space

        # Feedback label for preview messages
        self.feedback_label = QLabel("Preview mode: Answer submission is not tracked.")
        self.feedback_label.setFont(QFont("Arial", 10))
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.feedback_label)

        # Action buttons
        button_layout = QHBoxLayout()
        self.show_answer_button = QPushButton("Show Answer")
        self.show_answer_button.clicked.connect(self._show_answer)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept) # Accept closes the dialog

        button_layout.addStretch(1)
        button_layout.addWidget(self.show_answer_button)
        button_layout.addWidget(self.close_button)
        button_layout.addStretch(1)
        main_layout.addLayout(button_layout)
        
        # Initial focus
        if hasattr(self.current_exercise_widget, 'set_focus_on_input'):
            self.current_exercise_widget.set_focus_on_input()

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator

    def _show_answer(self):
        if self.current_exercise_widget:
            # Call the mock course manager's check_answer to get the feedback string
            # Pass dummy user_answer, as we only care about the second element of the tuple.
            _, feedback_text = self.mock_course_manager.check_answer(self.exercise, "") 
            self.feedback_label.setText(feedback_text)
            self.feedback_label.setStyleSheet("color: blue; font-weight: bold;")
            self.show_answer_button.setEnabled(False) # Disable after showing
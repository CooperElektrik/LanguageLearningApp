import os
import logging
from typing import Optional, List, Tuple, Any, Dict, Callable

from .models import Course, Unit, Lesson, Exercise, GlossaryEntry
from . import course_loader
from . import glossary_loader

logger = logging.getLogger(__name__)

# Constants for prompt template keys, used for i18n
PROMPT_KEY_TRANSLATE_TO_TARGET = "prompt_translate_to_target" # e.g., "Translate to %s: \"%s\""
PROMPT_KEY_TRANSLATE_TO_SOURCE = "prompt_translate_to_source" # e.g., "Translate to %s: \"%s\""
PROMPT_KEY_MCQ_TRANSLATION = "prompt_mcq_translation"       # e.g., "Choose the %s translation for: \"%s\" (%s)"
PROMPT_KEY_FIB = "prompt_fib"                               # e.g., "%s (Hint: %s)"
PROMPT_KEY_DEFAULT = "prompt_default_exercise_text"         # e.g., "Exercise Prompt: %s"


class CourseManager:
    def __init__(self, manifest_path: str):
        self.course: Optional[Course] = None
        self.manifest_data: Optional[dict] = None
        self.target_language: str = "Unknown"
        self.source_language: str = "Unknown"
        self.glossary: List[GlossaryEntry] = []

        self.manifest_path = manifest_path

        # Initialize answer checker dispatch map
        self._answer_checkers: Dict[str, Callable[[Exercise, str], Tuple[bool, str]]] = {
            "translate_to_target": self._check_translation_answer,
            "translate_to_source": self._check_translation_answer,
            "multiple_choice_translation": self._check_multiple_choice_answer,
            "fill_in_the_blank": self._check_fill_in_the_blank_answer,
        }

        self._load_course_from_manifest()

    def _load_course_from_manifest(self):
        """
        Loads the course manifest and then the associated course content and glossary.
        Handles errors internally and sets course/manifest_data/glossary attributes.
        """
        self.manifest_data = course_loader.load_manifest(self.manifest_path)
        if not self.manifest_data:
            logger.error("Failed to load manifest. Course cannot be initialized.")
            return

        self.target_language = self.manifest_data.get("target_language", "Unknown Target")
        self.source_language = self.manifest_data.get("source_language", "Unknown Source")

        # --- Load Course Content ---
        content_filename = self.manifest_data.get("content_file")
        if not content_filename:
            logger.error("Manifest does not specify a 'content_file'. Course content cannot be loaded.")
            return

        manifest_dir_abs = os.path.dirname(os.path.abspath(self.manifest_path))
        content_filepath = os.path.join(manifest_dir_abs, content_filename)

        self.course = course_loader.load_course_content(
            content_filepath,
            self.manifest_data.get("course_id", "unknown_course"),
            self.manifest_data.get("course_title", "Untitled Course"),
            self.target_language,
            self.source_language,
            self.manifest_data.get("version", "0.0.0"),
            self.manifest_data.get("author"),
            self.manifest_data.get("description"),
        )
        if self.course:
            logger.info(f"Course '{self.course.title}' content loaded successfully from {content_filepath}.")
        else:
            logger.error(f"Failed to load course content from {content_filepath}.")
        
        # --- Load Glossary ---
        glossary_filename = self.manifest_data.get("glossary_file")
        if glossary_filename:
            glossary_filepath = os.path.join(manifest_dir_abs, glossary_filename)
            self.glossary = glossary_loader.load_glossary(glossary_filepath)
        else:
            logger.info("Manifest does not specify a 'glossary_file'. Skipping glossary loading.")

    def get_glossary_entries(self) -> List[GlossaryEntry]:
        """Returns the loaded glossary entries."""
        return self.glossary

    def get_course_content_directory(self) -> Optional[str]:
        """Returns the directory where the current course's content file is located."""
        if self.manifest_data and self.manifest_data.get("content_file"):
            manifest_dir_abs = os.path.dirname(os.path.abspath(self.manifest_path))
            content_filepath = os.path.join(
                manifest_dir_abs, self.manifest_data["content_file"]
            )
            return os.path.dirname(content_filepath)
        elif self.manifest_path and os.path.exists(self.manifest_path):
            # Fallback to manifest directory if content_file not specified/found
            return os.path.dirname(os.path.abspath(self.manifest_path))
        return None

    def get_course_manifest_directory(self) -> Optional[str]:
        """Returns the directory where the current course's manifest file is located."""
        if self.manifest_path and os.path.exists(self.manifest_path):
            return os.path.dirname(os.path.abspath(self.manifest_path))
        return None

    def get_course_title(self) -> Optional[str]:
        return self.course.title if self.course else None

    def get_target_language(self) -> str:
        return self.target_language

    def get_source_language(self) -> str:
        return self.source_language

    def get_units(self) -> List[Unit]:
        return self.course.units if self.course else []

    def get_lesson(self, lesson_id: str) -> Optional[Lesson]:
        if not self.course:
            return None
        for unit in self.course.units:
            for lesson in unit.lessons:
                if lesson.lesson_id == lesson_id:
                    return lesson
        return None

    def get_exercises(self, lesson_id: str) -> List[Exercise]:
        lesson = self.get_lesson(lesson_id)
        return lesson.exercises if lesson else []

    def get_all_exercises(self) -> List[Exercise]: # Corrected type hint to Exercise
        """Returns a flat list of all Exercise objects across all units and lessons."""
        all_exercises = []
        if self.course:
            for unit in self.course.units:
                for lesson in unit.lessons:
                    all_exercises.extend(lesson.exercises)
        return all_exercises

    def get_lesson_exercise_count(self, lesson_id: str) -> int:
        return len(self.get_exercises(lesson_id))

    def _check_translation_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """Checks answer for translate_to_target/source exercise types."""
        correct_answer_display = exercise.answer
        is_correct = user_answer.lower() == exercise.answer.lower()
        return is_correct, f"Correct: {correct_answer_display}" if is_correct else f"Incorrect. Correct: {correct_answer_display}"

    def _check_multiple_choice_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """Checks answer for multiple_choice_translation exercise type."""
        correct_option = next((opt for opt in exercise.options if opt.correct), None)
        if not correct_option:
            logger.error(f"No correct option defined for MC exercise {exercise.exercise_id}. Cannot check answer.")
            return False, "Error: Exercise configuration issue (no correct answer)."
        
        correct_answer_display = correct_option.text
        is_correct = user_answer.lower() == correct_option.text.lower()
        return is_correct, f"Correct: {correct_answer_display}" if is_correct else f"Incorrect. Correct: {correct_answer_display}"

    def _check_fill_in_the_blank_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """Checks answer for fill_in_the_blank exercise type."""
        correct_answer_display = exercise.correct_option
        if not correct_answer_display:
            logger.error(f"No correct option defined for FIB exercise {exercise.exercise_id}. Cannot check answer.")
            return False, "Error: Exercise configuration issue (no correct answer)."
        
        is_correct = user_answer.lower() == correct_answer_display.lower()
        return is_correct, f"Correct: {correct_answer_display}" if is_correct else f"Incorrect. Correct: {correct_answer_display}"

    def check_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """
        Dispatches to the correct answer checking method based on exercise type.
        Returns (is_correct, feedback_text).
        """
        checker = self._answer_checkers.get(exercise.type)
        if checker:
            return checker(exercise, user_answer.strip()) # Strip whitespace from user answer
        else:
            logger.warning(f"Answer checking not implemented for exercise type: {exercise.type} (ID: {exercise.exercise_id})")
            return False, "Cannot check this exercise type."

    def get_formatted_prompt_data(self, exercise: Exercise) -> Dict[str, Any]:
        """
        Returns a dictionary with a template_key and arguments for formatting the prompt.
        The UI widget (e.g., BaseExerciseWidget) will be responsible for translating the template_key.
        """
        if exercise.type == "translate_to_target":
            return {
                "template_key": PROMPT_KEY_TRANSLATE_TO_TARGET,
                "args": [self.target_language, exercise.prompt or ""]
            }
        elif exercise.type == "translate_to_source":
            return {
                "template_key": PROMPT_KEY_TRANSLATE_TO_SOURCE,
                "args": [self.source_language, exercise.prompt or ""]
            }
        elif exercise.type == "multiple_choice_translation":
            return {
                "template_key": PROMPT_KEY_MCQ_TRANSLATION,
                "args": [self.target_language, exercise.source_word or "", self.source_language]
            }
        elif exercise.type == "fill_in_the_blank":
            return {
                "template_key": PROMPT_KEY_FIB,
                "args": [exercise.sentence_template or "", exercise.translation_hint or ""]
            }
        
        # Default case for generic prompt or unsupported type
        return {
            "template_key": PROMPT_KEY_DEFAULT,
            "args": [exercise.prompt or ""]
        }
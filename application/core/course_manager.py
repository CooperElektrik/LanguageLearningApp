
import os
import logging
from typing import Optional, List, Tuple, Any, Dict, Callable

from .models import Course, Unit, Lesson, Exercise, GlossaryEntry
from . import course_loader
from . import glossary_loader
from application import utils # For developer mode check

logger = logging.getLogger(__name__)

# Constants for prompt template keys, used for i18n
PROMPT_KEY_TRANSLATE_TO_TARGET = "prompt_translate_to_target"
PROMPT_KEY_TRANSLATE_TO_SOURCE = "prompt_translate_to_source"
PROMPT_KEY_MCQ_TRANSLATION = "prompt_mcq_translation"
PROMPT_KEY_FIB = "prompt_fib"
PROMPT_KEY_DEFAULT = "prompt_default_exercise_text"
PROMPT_KEY_IMAGE_ASSOCIATION = "prompt_image_association"
PROMPT_KEY_LISTEN_SELECT = "prompt_listen_select"
PROMPT_KEY_SENTENCE_JUMBLE = "prompt_sentence_jumble"
PROMPT_KEY_CONTEXT_BLOCK = "prompt_context_block"
PROMPT_KEY_DICTATION = "prompt_dictation"


class CourseManager:
    def __init__(self, manifest_path: str):
        self.course: Optional[Course] = None
        self.manifest_data: Optional[dict] = None
        self.target_language: str = "Unknown"
        self.source_language: str = "Unknown"
        self.glossary: List[GlossaryEntry] = []
        # NEW: A map for efficient, case-insensitive glossary lookups.
        # Key: lowercase word, Value: GlossaryEntry object.
        self.glossary_map: Dict[str, GlossaryEntry] = {}

        self.manifest_path = manifest_path

        # Initialize answer checker dispatch map
        self._answer_checkers: Dict[str, Callable[[Exercise, str], Tuple[bool, str]]] = {
            "translate_to_target": self._check_translation_answer,
            "translate_to_source": self._check_translation_answer,
            "dictation": self._check_translation_answer,
            "multiple_choice_translation": self._check_multiple_choice_answer,
            "image_association": self._check_multiple_choice_answer,
            "listen_and_select": self._check_multiple_choice_answer,
            "fill_in_the_blank": self._check_fill_in_the_blank_answer,
            "sentence_jumble": self._check_sentence_jumble_answer,
            "context_block": self._check_completion_answer,
        }

        self._load_course_from_manifest()

    def _load_course_from_manifest(self):
        """
        Loads the course manifest and then the associated course content and glossary.
        """
        if utils.is_developer_mode_active():
            # Log course ID if available from manifest_path for better context
            course_name_for_log = os.path.basename(os.path.dirname(self.manifest_path))
            logger.info(f"Developer Mode active for CourseManager (course: {course_name_for_log}). Course locking mechanisms (if any) would be bypassed.")

        self.manifest_data = course_loader.load_manifest(self.manifest_path)
        if not self.manifest_data:
            logger.error("Failed to load manifest. Course cannot be initialized.")
            return
        self.target_language = self.manifest_data.get("target_language", "Unknown Target")
        self.source_language = self.manifest_data.get("source_language", "Unknown Source")

        content_filename = self.manifest_data.get("content_file")
        if not content_filename:
            logger.error("Manifest does not specify a 'content_file'.")
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
        
        glossary_filename = self.manifest_data.get("glossary_file")
        if glossary_filename:
            glossary_filepath = os.path.join(manifest_dir_abs, glossary_filename)
            self.glossary = glossary_loader.load_glossary(glossary_filepath)
            self._build_glossary_map() # NEW: Build the lookup map
        else:
            logger.info("Manifest does not specify a 'glossary_file'. Skipping glossary loading.")

    def _build_glossary_map(self):
        """Populates the glossary_map for fast word lookups."""
        self.glossary_map = {entry.word.lower(): entry for entry in self.glossary}
        logger.info(f"Built glossary map with {len(self.glossary_map)} unique entries.")

    def get_glossary_entry_by_word(self, word: str) -> Optional[GlossaryEntry]:
        """
        Efficiently retrieves a glossary entry by word (case-insensitive).
        Returns None if the word is not found in the glossary.
        """
        return self.glossary_map.get(word.lower())

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

    def get_all_exercises(self) -> List[Exercise]:
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
        """Checks answer for translation and dictation exercise types."""
        correct_answer_display = exercise.answer
        is_correct = user_answer.strip().lower() == exercise.answer.lower()
        return is_correct, f"Correct: {correct_answer_display}" if is_correct else f"Incorrect. Correct: {correct_answer_display}"

    def _check_multiple_choice_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """Checks answer for multiple choice exercise types."""
        correct_option = next((opt for opt in exercise.options if opt.correct), None)
        if not correct_option:
            logger.error(f"No correct option defined for MC exercise {exercise.exercise_id}.")
            return False, "Error: Exercise configuration issue (no correct answer)."
        
        correct_answer_display = correct_option.text
        is_correct = user_answer.lower() == correct_option.text.lower()
        return is_correct, f"Correct: {correct_answer_display}" if is_correct else f"Incorrect. Correct: {correct_answer_display}"

    def _check_fill_in_the_blank_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """Checks answer for fill_in_the_blank exercise type."""
        correct_answer_display = exercise.correct_option
        if not correct_answer_display:
            logger.error(f"No correct option defined for FIB exercise {exercise.exercise_id}.")
            return False, "Error: Exercise configuration issue (no correct answer)."
        
        is_correct = user_answer.lower() == correct_answer_display.lower()
        return is_correct, f"Correct: {correct_answer_display}" if is_correct else f"Incorrect. Correct: {correct_answer_display}"

    def _check_sentence_jumble_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """Checks answer for sentence_jumble exercise type."""
        correct_answer_display = exercise.answer
        is_correct = " ".join(user_answer.lower().split()) == " ".join(correct_answer_display.lower().split())
        return is_correct, f"Correct: {correct_answer_display}" if is_correct else f"Incorrect. Correct: {correct_answer_display}"

    def _check_completion_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """Checks answers for exercises that are completed via a single action."""
        is_correct = user_answer.lower() == "completed"
        return is_correct, "Continue" if is_correct else "Activity not completed."

    def check_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """
        Dispatches to the correct answer checking method based on exercise type.
        """
        checker = self._answer_checkers.get(exercise.type)
        if checker:
            return checker(exercise, user_answer.strip())
        else:
            logger.warning(f"Answer checking not implemented for exercise type: {exercise.type} (ID: {exercise.exercise_id})")
            return False, "Cannot check this exercise type."

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
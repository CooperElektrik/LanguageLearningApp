import os
import logging
import sys
from typing import Optional, List, Tuple, Any
from .models import Course, Unit, Lesson, Exercise, GlossaryEntry
from . import course_loader
from . import glossary_loader

logger = logging.getLogger(__name__)


class CourseManager:
    def __init__(self, manifest_path: str):
        self.course: Optional[Course] = None
        self.manifest_data: Optional[dict] = None
        self.target_language: str = "Unknown"
        self.source_language: str = "Unknown"
        self.glossary: List[GlossaryEntry] = []

        self.manifest_path = manifest_path

        self._load_course_from_manifest()

    def _load_course_from_manifest(self):
        self.manifest_data = course_loader.load_manifest(self.manifest_path)
        if not self.manifest_data:
            logger.error("Failed to load manifest. Course cannot be initialized.")
            return

        self.target_language = self.manifest_data.get(
            "target_language", "Unknown Target"
        )
        self.source_language = self.manifest_data.get(
            "source_language", "Unknown Source"
        )

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
            logger.info(f"Course '{self.course.title}' initialized successfully.")
        else:
            logger.error(f"Failed to load course content from {content_filepath}.")

        glossary_filename = self.manifest_data.get("glossary_file")
        if glossary_filename:
            glossary_filepath = os.path.join(manifest_dir_abs, glossary_filename)
            self.glossary = glossary_loader.load_glossary(glossary_filepath)
        else:
            logger.info("Manifest does not specify a 'glossary_file'. Skipping glossary loading.")

        self.course = course_loader.load_course_content(
            content_filepath, # This is already correctly resolved relative to manifest_path
            self.manifest_data.get("course_id", "unknown_course"),
            self.manifest_data.get("course_title", "Untitled Course"),
            self.target_language,
            self.source_language,
            self.manifest_data.get("version", "0.0.0"),
            self.manifest_data.get("author"),
            self.manifest_data.get("description"),
        )
        if self.course:
            logger.info(f"Course '{self.course.title}' initialized successfully.")
        else:
            logger.error(f"Failed to load course content from {content_filepath}.")
        
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
        if (
            self.course
            and self.manifest_data
            and self.manifest_data.get("content_file")
        ):
            manifest_dir_abs = os.path.dirname(os.path.abspath(self.manifest_path))
            content_filepath = os.path.join(
                manifest_dir_abs, self.manifest_data["content_file"]
            )
            return os.path.dirname(content_filepath)
        elif self.manifest_path:
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

    def get_exercise(self, lesson_id: str, exercise_index: int) -> Optional[Exercise]:
        exercises = self.get_exercises(lesson_id)
        if 0 <= exercise_index < len(exercises):
            return exercises[exercise_index]
        return None

    def get_all_exercises(self) -> List[Any]:
        """Returns a flat list of all Exercise objects across all units and lessons."""
        all_exercises = []
        if self.course:
            for unit in self.course.units:
                for lesson in unit.lessons:
                    all_exercises.extend(lesson.exercises)
        return all_exercises

    def get_lesson_exercise_count(self, lesson_id: str) -> int:
        return len(self.get_exercises(lesson_id))

    def check_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
        """
        Checks the user's answer against the correct answer for the given exercise.
        """
        user_answer = user_answer.strip().lower()
        correct_answer_display = ""

        if exercise.type in ["translate_to_target", "translate_to_source"]:
            correct_answer_display = exercise.answer
            is_correct = user_answer == exercise.answer.lower()

        elif exercise.type == "multiple_choice_translation":
            correct_option = next(
                (opt for opt in exercise.options if opt.correct), None
            )
            if not correct_option:
                logger.error(
                    f"No correct option defined for MC exercise {exercise.exercise_id}"
                )
                return False, "Error: Exercise configuration issue."
            correct_answer_display = correct_option.text
            is_correct = user_answer == correct_option.text.lower()

        elif exercise.type == "fill_in_the_blank":
            correct_answer_display = exercise.correct_option
            is_correct = user_answer == exercise.correct_option.lower()

        else:
            logger.warning(
                f"Answer checking not implemented for exercise type: {exercise.type}"
            )
            return False, "Cannot check this exercise type."

        if is_correct:
            return True, f"Correct! The answer is: {correct_answer_display}"
        else:
            return False, f"Incorrect. The correct answer is: {correct_answer_display}"

    def get_formatted_prompt(self, exercise: Exercise) -> str:
        """Formats the prompt text, incorporating language names etc."""
        if exercise.type == "translate_to_target":
            return f'Translate to {self.target_language}: "{exercise.prompt}"'
        elif exercise.type == "translate_to_source":
            return f'Translate to {self.source_language}: "{exercise.prompt}"'
        elif exercise.type == "multiple_choice_translation":
            return f'Choose the {self.target_language} translation for: "{exercise.source_word}" ({self.source_language})'
        elif exercise.type == "fill_in_the_blank":
            return f"{exercise.sentence_template} (Hint: {exercise.translation_hint})"
        return exercise.prompt or "Exercise Prompt"

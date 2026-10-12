import logging
import os
from collections.abc import Callable
from typing import Any

import Levenshtein

from . import course_loader, glossary_loader
from .models import Course, Exercise, GlossaryEntry, Lesson, Unit
from .whisper_engine import _FASTER_WHISPER_AVAILABLE

try:
    from application import utils  # For developer mode check
except ImportError:
    import utils

import settings as app_settings
from PySide6.QtCore import QObject

logger = logging.getLogger(__name__)


class CourseManager(QObject):
    def __init__(self, manifest_path: str, parent):
        super().__init__(parent=parent)  # Call QObject's constructor
        # All existing attributes become instance attributes
        self.course: Course | None = None
        self.manifest_data: dict | None = None
        self.target_language: str = "Unknown"
        self.source_language: str = "Unknown"
        self.target_language_code: str | None = None
        self.glossary: list[GlossaryEntry] = []
        self.use_shared_pool: bool = False

        self.manifest_path = manifest_path

        # Initialize answer checker dispatch map
        self._answer_checkers: dict[
            str, Callable[[Exercise, str], tuple[bool, str]]
        ] = {
            "translate_to_target": self._check_translation_answer,
            "translate_to_source": self._check_translation_answer,
            "dictation": self._check_translation_answer,
            "multiple_choice_translation": self._check_multiple_choice_answer,
            "image_association": self._check_multiple_choice_answer,
            "listen_and_select": self._check_multiple_choice_answer,
            "fill_in_the_blank": self._check_fill_in_the_blank_answer,
            "sentence_jumble": self._check_sentence_jumble_answer,
            "context_block": self._check_completion_answer,
            "pronunciation_practice": self._check_pronunciation_answer,
        }
        logger.debug(f"CourseManager initialized for manifest: {manifest_path}")
        if os.path.exists(manifest_path):
            self._load_course_from_manifest()

    def _load_course_from_manifest(self):
        """
        Loads the course manifest and then the associated course content and glossary.
        """
        if utils.is_developer_mode_active():
            # Log course ID if available from manifest_path for better context
            course_name_for_log = os.path.basename(os.path.dirname(self.manifest_path))
            logger.info(
                f"Developer Mode active for CourseManager (course: {course_name_for_log}). Course locking mechanisms (if any) would be bypassed."
            )

        self.manifest_data = course_loader.load_manifest(self.manifest_path)
        if not self.manifest_data:
            logger.error("Failed to load manifest. Course cannot be initialized.")
            return
        logger.debug("Manifest loaded. Extracting course metadata.")
        self.target_language = self.manifest_data.get(
            "target_language", "Unknown Target"
        )
        self.source_language = self.manifest_data.get(
            "source_language", "Unknown Source"
        )
        self.target_language_code = self.manifest_data.get("target_language_code")
        logger.debug(
            f"Target Language: {self.target_language}, Source Language: {self.source_language}"
        )

        # Handle asset pool
        self.use_shared_pool = self.manifest_data.get("use_shared_pool", False)
        if self.use_shared_pool:
            logger.info("Course is configured to use the shared asset pool.")

        content_filename = self.manifest_data.get("content_file")
        if not content_filename:
            logger.error("Manifest does not specify a 'content_file'.")
            return
        logger.debug(f"Content file specified: {content_filename}")

        manifest_dir_abs = os.path.dirname(os.path.abspath(self.manifest_path))
        content_filepath = os.path.join(manifest_dir_abs, content_filename)
        logger.debug(f"Absolute path to content file: {content_filepath}")

        self.course = course_loader.load_course_content(
            content_filepath,
            self.manifest_data.get("course_id", "unknown_course"),
            self.manifest_data.get("course_title", "Untitled Course"),
            self.target_language,
            self.source_language,
            self.manifest_data.get("version", "0.0.0"),
            self.manifest_data.get("author"),
            self.manifest_data.get("description"),
            self.manifest_data.get("image_file"),
            manifest_dir_abs,  # course_base_dir
            os.path.join(os.path.dirname(manifest_dir_abs), "pool"),  # pool_base_dir
        )
        if self.course:
            logger.info(
                f"Course '{self.course.title}' content loaded successfully from {content_filepath}."
            )
        else:
            logger.error(
                f"Failed to load course content from {content_filepath}. Course object is None."
            )

        glossary_filename = self.manifest_data.get("glossary_file")
        if glossary_filename:
            glossary_filepath = os.path.join(manifest_dir_abs, glossary_filename)
            logger.debug(f"Attempting to load glossary from: {glossary_filepath}")
            self.glossary = glossary_loader.load_glossary(
                glossary_filepath,
                manifest_dir_abs,
                os.path.join(os.path.dirname(manifest_dir_abs), "pool"),
            )
            if self.glossary:
                self._build_glossary_map()
                logger.info(
                    f"Glossary loaded successfully with {len(self.glossary)} entries."
                )
            else:
                logger.warning(
                    f"Failed to load glossary from {glossary_filepath}. Glossary will be empty."
                )
        else:
            logger.info(
                "Manifest does not specify a 'glossary_file'. Skipping glossary loading."
            )

    def _build_glossary_map(self):
        """Populates the glossary_map for fast word lookups."""
        self.glossary_map = {entry.word.lower(): entry for entry in self.glossary}
        logger.info(f"Built glossary map with {len(self.glossary_map)} unique entries.")

    def get_glossary_entries(self) -> list[GlossaryEntry]:
        """Returns the loaded glossary entries."""
        return self.glossary

    def get_glossary_entry_by_word(self, word: str) -> GlossaryEntry | None:
        """
        Finds a glossary entry by its 'word' field, case-insensitively.
        Returns the first match or None.
        """
        word_lower = word.lower()
        for entry in self.glossary:
            if entry.word.lower() == word_lower:
                return entry
        return None

    def get_course_content_directory(self) -> str | None:
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

    def get_course_manifest_directory(self) -> str | None:
        """Returns the directory where the current course's manifest file is located."""
        if self.manifest_path and os.path.exists(self.manifest_path):
            return os.path.dirname(os.path.abspath(self.manifest_path))
        return None

    def get_asset_directory(self) -> str | None:
        """Returns the primary directory for course assets (shared pool or manifest dir)."""
        if self.use_shared_pool:
            # Construct path to application/courses/pool from the manifest path
            # This is a bit brittle, but it's the most reliable way without a global app context
            manifest_dir = self.get_course_manifest_directory()
            if manifest_dir:
                # Navigate up from the course directory to the application directory
                # e.g., from D:\...\py-bsc-2\application\courses\my-course to D:\...\py-bsc-2\application
                application_dir = os.path.dirname(os.path.dirname(manifest_dir))
                pool_path = os.path.join(application_dir, "courses", "pool")
                if os.path.isdir(pool_path):
                    return pool_path
                else:
                    logger.warning(
                        f"Shared asset pool enabled, but directory not found at: {pool_path}"
                    )
        return self.get_course_manifest_directory()

    def get_course_title(self) -> str | None:
        return self.course.title if self.course else None

    def get_target_language(self) -> str:
        return self.target_language

    def get_target_language_code(self) -> str | None:
        return self.target_language_code

    def get_source_language(self) -> str:
        return self.source_language

    def get_units(self) -> list[Unit]:
        return self.course.units if self.course else []

    def get_lesson(self, lesson_id: str) -> Lesson | None:
        if not self.course:
            return None
        for unit in self.course.units:
            for lesson in unit.lessons:
                if lesson.lesson_id == lesson_id:
                    return lesson
        return None

    def get_exercises(self, lesson_id: str) -> list[Exercise]:
        lesson = self.get_lesson(lesson_id)
        return lesson.exercises if lesson else []

    def get_all_exercises(self) -> list[Exercise]:
        """Returns a flat list of all Exercise objects across all units and lessons."""
        all_exercises = []
        if self.course:
            for unit in self.course.units:
                for lesson in unit.lessons:
                    all_exercises.extend(lesson.exercises)
        return all_exercises

    def _normalize_answer_for_comparison(
        self, text: str, for_pronunciation: bool = False
    ) -> str:
        """Normalizes text for comparison (lowercase, strip, optionally remove punctuation)."""
        text_norm = text.lower().strip()
        if for_pronunciation:
            # For pronunciation, be more aggressive with punctuation removal
            import string

            # Remove all standard punctuation
            text_norm = text_norm.translate(str.maketrans("", "", string.punctuation))
            # Optional: normalize whitespace to single spaces if multiple spaces might occur
            text_norm = " ".join(text_norm.split())
        return text_norm

    def _get_effective_tolerance(self, exercise: Exercise) -> int:
        """Determines the Levenshtein tolerance for a given exercise."""
        if exercise.allowed_levenshtein_distance is not None:
            return exercise.allowed_levenshtein_distance
        if exercise.type == "pronunciation_practice":
            return app_settings.LEVENSHTEIN_TOLERANCE_PRONUNCIATION
        if exercise.type == "dictation":
            return app_settings.LEVENSHTEIN_TOLERANCE_DICTATION
        # Add other type-specific defaults here if needed
        return app_settings.LEVENSHTEIN_TOLERANCE_DEFAULT

    def _check_translation_answer(
        self, exercise: Exercise, user_answer: str
    ) -> tuple[bool, str]:
        """Checks answer for translation and dictation exercise types."""
        correct_answer_display = exercise.answer

        user_answer_norm = self._normalize_answer_for_comparison(
            user_answer, for_pronunciation=(exercise.type == "dictation")
        )
        correct_answer_norm = self._normalize_answer_for_comparison(
            exercise.answer, for_pronunciation=(exercise.type == "dictation")
        )

        tolerance = self._get_effective_tolerance(exercise)
        distance = Levenshtein.distance(user_answer_norm, correct_answer_norm)
        is_correct_exact = user_answer_norm == correct_answer_norm
        is_correct_fuzzy = distance <= tolerance

        if is_correct_exact:
            return True, self.tr("Correct: {0}").format(correct_answer_display)
        elif is_correct_fuzzy:
            return True, self.tr(
                "Accepted (close match). Correct: {0}. You wrote: {1}"
            ).format(correct_answer_display, user_answer)
        else:
            return False, self.tr("Incorrect. Correct: {0}. You wrote: {1}").format(
                correct_answer_display, user_answer
            )

    def _check_multiple_choice_answer(
        self, exercise: Exercise, user_answer: str
    ) -> tuple[bool, str]:
        """Checks answer for multiple choice exercise types."""
        try:
            selected_index = int(user_answer)
        except (ValueError, TypeError):
            return False, self.tr("Invalid answer format.")

        if not (0 <= selected_index < len(exercise.options)):
            return False, self.tr("Selected option is out of range.")

        selected_option = exercise.options[selected_index]
        correct_option = next((opt for opt in exercise.options if opt.correct), None)

        if not correct_option:
            logger.error(
                f"No correct option defined for MC exercise {exercise.exercise_id}."
            )
            return False, self.tr(
                "Error: Exercise configuration issue (no correct answer)."
            )

        correct_answer_display = correct_option.text or correct_option.image_file

        is_correct = selected_option.correct
        return is_correct, (
            self.tr("Correct: {0}").format(correct_answer_display)
            if is_correct
            else self.tr("Incorrect. Correct: {0}").format(correct_answer_display)
        )

    def _check_fill_in_the_blank_answer(
        self, exercise: Exercise, user_answer: str
    ) -> tuple[bool, str]:
        """Checks answer for fill_in_the_blank exercise type."""
        try:
            selected_index = int(user_answer)
        except (ValueError, TypeError):
            return False, self.tr("Invalid answer format.")

        if not (0 <= selected_index < len(exercise.options)):
            return False, self.tr("Selected option is out of range.")

        selected_option_text = exercise.options[selected_index].text
        correct_answer_display = exercise.correct_option

        if not correct_answer_display:
            logger.error(
                f"No correct option defined for FIB exercise {exercise.exercise_id}."
            )
            return False, "Error: Exercise configuration issue (no correct answer)."

        user_answer_norm = self._normalize_answer_for_comparison(selected_option_text)
        correct_answer_norm = self._normalize_answer_for_comparison(
            correct_answer_display
        )

        tolerance = self._get_effective_tolerance(exercise)
        distance = Levenshtein.distance(user_answer_norm, correct_answer_norm)
        is_correct_exact = user_answer_norm == correct_answer_norm
        is_correct_fuzzy = distance <= tolerance

        if is_correct_exact:
            return True, self.tr("Correct: {0}").format(correct_answer_display)
        elif is_correct_fuzzy:
            return True, self.tr(
                "Accepted (close match). Correct: {0}. You wrote: {1}"
            ).format(correct_answer_display, selected_option_text)
        else:
            return False, self.tr("Incorrect. Correct: {0}. You wrote: {1}").format(
                correct_answer_display, selected_option_text
            )

    def _check_sentence_jumble_answer(
        self, exercise: Exercise, user_answer: str
    ) -> tuple[bool, str]:
        """Checks answer for sentence_jumble exercise type."""
        correct_answer_display = exercise.answer
        # For jumble, user_answer is already space-joined. We compare normalized strings.
        user_answer_norm = self._normalize_answer_for_comparison(user_answer)
        correct_answer_norm = self._normalize_answer_for_comparison(
            correct_answer_display
        )

        user_answer_norm = self._normalize_answer_for_comparison(user_answer)
        correct_answer_norm = self._normalize_answer_for_comparison(
            correct_answer_display
        )

        is_correct = (
            user_answer_norm == correct_answer_norm
        )  # Jumble should usually be exact order
        return is_correct, (
            self.tr("Correct: {0}").format(correct_answer_display)
            if is_correct
            else self.tr("Incorrect. Correct: {0}. You arranged: {1}").format(
                correct_answer_display, user_answer
            )
        )

    def _check_completion_answer(
        self, exercise: Exercise, user_answer: str
    ) -> tuple[bool, str]:
        """Context block exercises are completed by a single action and are always correct."""
        return True, "Continue"

    def _is_selected_stt_engine_available(self) -> bool:
        """Returns whether the currently selected STT engine backend is importable.

        The default engine is VOSK, so gating pronunciation on faster_whisper
        availability alone (as was previously done) rejected every valid answer
        for users running the default configuration.
        """
        try:
            import settings as app_settings
            from PySide6.QtCore import QSettings

            engine = QSettings().value(
                app_settings.QSETTINGS_KEY_STT_ENGINE,
                app_settings.STT_ENGINE_DEFAULT,
                type=str,
            )
            if engine == app_settings.STT_ENGINE_VOSK:
                from .vosk_manager import _VOSK_AVAILABLE

                return _VOSK_AVAILABLE
            if engine == app_settings.STT_ENGINE_WHISPER:
                return _FASTER_WHISPER_AVAILABLE
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Could not determine STT engine availability: {e}")
        return False

    def _check_pronunciation_answer(
        self, exercise: Exercise, user_transcription: str
    ) -> tuple[bool, str]:
        """Checks answer for pronunciation exercises by comparing transcription."""
        if not self._is_selected_stt_engine_available():
            return False, self.tr(
                "Pronunciation exercises require the selected speech-to-text engine, which is not installed."
            )

        target_text_display = exercise.target_pronunciation_text

        user_transcription_norm = self._normalize_answer_for_comparison(
            user_transcription, for_pronunciation=True
        )
        target_text_norm = self._normalize_answer_for_comparison(
            target_text_display, for_pronunciation=True
        )

        tolerance = self._get_effective_tolerance(exercise)
        distance = Levenshtein.distance(user_transcription_norm, target_text_norm)
        is_correct_exact = user_transcription_norm == target_text_norm
        is_correct_fuzzy = distance <= tolerance

        if is_correct_exact:
            return True, self.tr("Excellent match!")
        elif is_correct_fuzzy:
            return True, self.tr("Good (close match)!")
        else:
            return False, self.tr("Needs improvement. See comparison below.")

    def check_answer(self, exercise: Exercise, user_answer: str) -> tuple[bool, str]:
        """
        Dispatches to the correct answer checking method based on exercise type.
        """
        checker = self._answer_checkers.get(exercise.type)
        if checker:
            return checker(exercise, user_answer.strip())  # Pass user_answer stripped
        else:
            logger.warning(
                self.tr(
                    "Answer checking not implemented for exercise type: {0} (ID: {1})"
                ).format(exercise.type, exercise.exercise_id)
            )
            return False, self.tr("Cannot check this exercise type.")

    def get_formatted_prompt_data(self, exercise: Exercise) -> dict[str, Any]:
        """
        Returns a dictionary with the formatted prompt text ready for display.
        """
        return {"args": [exercise.prompt or exercise.sentence_template or ""]}

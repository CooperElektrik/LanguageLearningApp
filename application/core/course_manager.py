import os
import logging
import Levenshtein
import shutil
from typing import Optional, List, Tuple, Any, Dict, Callable

from .models import Course, Unit, Lesson, Exercise, GlossaryEntry
from . import course_loader
from . import glossary_loader
from .whisper_engine import _FASTER_WHISPER_AVAILABLE

try:
    from application import utils  # For developer mode check
except ImportError:
    import utils
from PySide6.QtCore import QObject

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

DEFAULT_GLOBAL_LEVENSHTEIN_TOLERANCE = 1  # For most text-based inputs
PRONUNCIATION_LEVENSHTEIN_TOLERANCE = 5  # More lenient for transcriptions
DICTATION_LEVENSHTEIN_TOLERANCE = 2


class CourseManager(QObject):
    def __init__(self, manifest_path: str, parent):
        super().__init__(parent=parent)  # Call QObject's constructor
        # All existing attributes become instance attributes
        self.course: Optional[Course] = None
        self.manifest_data: Optional[dict] = None
        self.target_language: str = "Unknown"
        self.source_language: str = "Unknown"
        self.target_language_code: Optional[str] = None
        self.glossary: List[GlossaryEntry] = []
        self.use_shared_pool: bool = False

        self.manifest_path = manifest_path

        # Initialize answer checker dispatch map
        self._answer_checkers: Dict[
            str, Callable[[Exercise, str], Tuple[bool, str]]
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

    def pull_course_from_git(self, git_url: str, progress_callback: Optional[Callable] = None):
        """
        Pulls a course from a git repository.
        """
        import git
        import tempfile
        from PySide6.QtWidgets import QMessageBox

        class Progress(git.remote.RemoteProgress):
            def update(self, op_code, cur_count, max_count=None, message=''):
                if progress_callback:
                    progress = cur_count / (max_count or 100.0) * 100
                    
                    stage_message = ""
                    if op_code & git.remote.RemoteProgress.COUNTING:
                        stage_message = "Counting objects..."
                    elif op_code & git.remote.RemoteProgress.COMPRESSING:
                        stage_message = "Compressing objects..."
                    elif op_code & git.remote.RemoteProgress.WRITING:
                        stage_message = "Writing objects..."
                    elif op_code & git.remote.RemoteProgress.RECEIVING:
                        stage_message = "Receiving objects..."
                    elif op_code & git.remote.RemoteProgress.RESOLVING:
                        stage_message = "Resolving deltas..."
                    elif op_code & git.remote.RemoteProgress.CHECKING_OUT:
                        stage_message = "Checking out files..."
                    
                    if stage_message:
                        progress_callback(progress, stage_message)

        try:
            # Create a temporary directory to clone the repository
            with tempfile.TemporaryDirectory() as temp_dir:
                if progress_callback:
                    progress_callback(0, "Cloning repository...")
                # Clone the repository into the temporary directory
                repo = git.Repo.clone_from(git_url, temp_dir, progress=Progress())

                if progress_callback:
                    progress_callback(50, "Copying files...")

                # Get the course ID from the manifest file
                manifest_path = os.path.join(temp_dir, "manifest.yaml")
                if not os.path.exists(manifest_path):
                    raise FileNotFoundError("manifest.yaml not found in the repository root.")

                manifest_data = course_loader.load_manifest(manifest_path)
                if not manifest_data:
                    raise ValueError("Failed to load manifest data.")

                course_id = manifest_data.get("course_id")
                if not course_id:
                    raise ValueError("course_id not found in manifest.yaml.")

                # Create the course directory if it doesn't exist
                course_dir = os.path.join(utils.get_app_root_dir(), "courses", course_id)
                if not os.path.exists(course_dir):
                    os.makedirs(course_dir)

                # Copy the course files from the temporary directory to the course directory
                for item in os.listdir(temp_dir):
                    s = os.path.join(temp_dir, item)
                    d = os.path.join(course_dir, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)

                if progress_callback:
                    progress_callback(100, "Download complete. Installing...")

                # Load the course from the new location
                self.manifest_path = os.path.join(course_dir, "manifest.yaml")
                self._load_course_from_manifest()

                if progress_callback:
                    progress_callback(100, "Course installed successfully.")

        except git.exc.GitCommandError as e:
            logger.error(f"Git command error: {e}")
            QMessageBox.critical(None, "Git Error", f"Failed to pull course from Git: {e}")
        except Exception as e:
            logger.error(f"Error pulling course from git: {e}")
            QMessageBox.critical(None, "Error", f"An unexpected error occurred: {e}")

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
        logger.debug(f"Target Language: {self.target_language}, Source Language: {self.source_language}")

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
            manifest_dir_abs, # course_base_dir
            os.path.join(os.path.dirname(manifest_dir_abs), "pool") # pool_base_dir
        )
        if self.course:
            logger.info(
                f"Course '{self.course.title}' content loaded successfully from {content_filepath}."
            )
        else:
            logger.error(f"Failed to load course content from {content_filepath}. Course object is None.")

        glossary_filename = self.manifest_data.get("glossary_file")
        if glossary_filename:
            glossary_filepath = os.path.join(manifest_dir_abs, glossary_filename)
            logger.debug(f"Attempting to load glossary from: {glossary_filepath}")
            self.glossary = glossary_loader.load_glossary(glossary_filepath, manifest_dir_abs, os.path.join(os.path.dirname(manifest_dir_abs), "pool"))
            if self.glossary:
                self._build_glossary_map()
                logger.info(f"Glossary loaded successfully with {len(self.glossary)} entries.")
            else:
                logger.warning(f"Failed to load glossary from {glossary_filepath}. Glossary will be empty.")
        else:
            logger.info(
                "Manifest does not specify a 'glossary_file'. Skipping glossary loading."
            )

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

    def get_glossary_entry_by_word(self, word: str) -> Optional[GlossaryEntry]:
        """
        Finds a glossary entry by its 'word' field, case-insensitively.
        Returns the first match or None.
        """
        word_lower = word.lower()
        for entry in self.glossary:
            if entry.word.lower() == word_lower:
                return entry
        return None

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

    def get_asset_directory(self) -> Optional[str]:
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
                    logger.warning(f"Shared asset pool enabled, but directory not found at: {pool_path}")
        return self.get_course_manifest_directory()

    def get_course_title(self) -> Optional[str]:
        return self.course.title if self.course else None

    def get_target_language(self) -> str:
        return self.target_language

    def get_target_language_code(self) -> Optional[str]:
        return self.target_language_code

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
            return PRONUNCIATION_LEVENSHTEIN_TOLERANCE
        if exercise.type == "dictation":
            return DICTATION_LEVENSHTEIN_TOLERANCE
        # Add other type-specific defaults here if needed
        return DEFAULT_GLOBAL_LEVENSHTEIN_TOLERANCE

    def _check_translation_answer(
        self, exercise: Exercise, user_answer: str
    ) -> Tuple[bool, str]:
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
    ) -> Tuple[bool, str]:
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
    ) -> Tuple[bool, str]:
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
    ) -> Tuple[bool, str]:
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
    ) -> Tuple[bool, str]:
        """Checks answers for exercises that are completed via a single action."""
        is_correct = user_answer.lower() == "completed"
        return is_correct, "Continue" if is_correct else "Activity not completed."

    def _check_pronunciation_answer(
        self, exercise: Exercise, user_transcription: str
    ) -> Tuple[bool, str]:
        """Checks answer for pronunciation exercises by comparing transcription."""
        if not _FASTER_WHISPER_AVAILABLE:
            return False, self.tr("Pronunciation exercises require faster_whisper, which is not installed.")

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

        base_feedback = f"Target: {target_text_display}\nYou said: {user_transcription}"

        if is_correct_exact:
            return True, self.tr("Excellent match!")
        elif is_correct_fuzzy:
            return True, self.tr("Good (close match)!")
        else:
            return False, self.tr("Needs improvement. See comparison below.")

    def check_answer(self, exercise: Exercise, user_answer: str) -> Tuple[bool, str]:
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

    def get_formatted_prompt_data(self, exercise: Exercise) -> Dict[str, Any]:
        """
        Returns a dictionary with a template_key and arguments for formatting the prompt.
        """
        return {"template_key": PROMPT_KEY_DEFAULT, "args": [exercise.prompt or exercise.sentence_template or ""]}

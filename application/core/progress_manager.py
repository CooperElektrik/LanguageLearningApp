import json
import os
import logging
from typing import Dict, Set, Optional, Any, List, Tuple
from PySide6.QtCore import QStandardPaths
from collections import defaultdict
from datetime import datetime, timedelta, date

from application import utils  # For developer mode check
import settings  # For ORG_NAME, APP_NAME, PROGRESS_DATA_SUBDIR

from .models import Exercise, Lesson, Unit  # For type hinting

logger = logging.getLogger(__name__)


class ProgressManager:
    def __init__(self, course_id: str):
        self.course_id = course_id

        app_data_base_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        if not app_data_base_dir:
            logger.warning(
                "Could not determine standard AppDataLocation. Falling back to current working directory for progress."
            )
            app_data_base_dir = os.getcwd()

        self.progress_data_dir = os.path.join(
            app_data_base_dir, settings.PROGRESS_DATA_SUBDIR
        )
        self.progress_file = os.path.join(
            self.progress_data_dir, f"{self.course_id}_progress.json"
        )

        # Initialize progress data structures with new 'is_initially_learned' flag
        self.exercise_srs_data: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "last_reviewed": None,
                "next_review_due": None,
                "interval_days": 0,
                "ease_factor": 2.5,
                "repetitions": 0,
                "correct_in_a_row": 0,
                "is_initially_learned": False,  # NEW FLAG for lesson progression
            }
        )
        self.xp: int = 0
        self.last_study_date: Optional[date] = None
        self.current_streak_days: int = 0
        self.exercise_notes: Dict[str, str] = {}

        self._ensure_data_dir_exists()
        self.load_progress()

    def _ensure_data_dir_exists(self):
        """Ensures the progress data directory exists, creating it if necessary."""
        if not os.path.exists(self.progress_data_dir):
            try:
                os.makedirs(self.progress_data_dir, exist_ok=True)
                logger.info(
                    f"Created progress data directory: {self.progress_data_dir}"
                )
            except OSError as e:
                logger.error(
                    f"Could not create progress data directory {self.progress_data_dir}: {e}. Application may not function correctly."
                )

    def load_progress(self):
        """Loads progress data from the JSON file."""
        if not os.path.exists(self.progress_file):
            logger.info(
                f"No progress file found for course '{self.course_id}' at {self.progress_file}. Starting fresh."
            )
            return

        try:
            with open(self.progress_file, "r", encoding="utf-8") as f:
                data = json.load(f)

                raw_srs_data = data.get("exercise_srs_data", {})
                for ex_id, srs_attrs in raw_srs_data.items():
                    # Convert datetime strings back to datetime objects
                    if srs_attrs.get("last_reviewed"):
                        srs_attrs["last_reviewed"] = datetime.fromisoformat(
                            srs_attrs["last_reviewed"]
                        )
                    if srs_attrs.get("next_review_due"):
                        srs_attrs["next_review_due"] = datetime.fromisoformat(
                            srs_attrs["next_review_due"]
                        )

                    # Ensure new flag exists for older progress files
                    if "is_initially_learned" not in srs_attrs:
                        # For existing data, if repetitions > 0, assume it was initially learned.
                        srs_attrs["is_initially_learned"] = (
                            srs_attrs.get("repetitions", 0) > 0
                        )
                        logger.info(
                            f"Populated 'is_initially_learned' for {ex_id} based on repetitions."
                        )

                    self.exercise_srs_data[ex_id] = srs_attrs

                self.xp = data.get("xp", 0)

                raw_last_study_date = data.get("last_study_date")
                if raw_last_study_date:
                    self.last_study_date = date.fromisoformat(raw_last_study_date)
                self.current_streak_days = data.get("current_streak_days", 0)

                self.exercise_notes = data.get("exercise_notes", {})

                logger.info(
                    f"Progress loaded for course '{self.course_id}' from {self.progress_file}."
                )
        except json.JSONDecodeError as e:
            logger.error(
                f"Error decoding JSON from progress file {self.progress_file}: {e}. Progress may be lost."
            )
        except Exception as e:
            logger.error(
                f"Failed to load progress from {self.progress_file}: {e}. Progress may be reset."
            )
            # Reset all progress data if loading fails critically
            self.exercise_srs_data = defaultdict(
                lambda: {
                    "last_reviewed": None,
                    "next_review_due": None,
                    "interval_days": 0,
                    "ease_factor": 2.5,
                    "repetitions": 0,
                    "correct_in_a_row": 0,
                    "is_initially_learned": False,
                }
            )
            self.xp = 0
            self.last_study_date = None
            self.current_streak_days = 0
            self.exercise_notes = {}

    def save_progress(self):
        """Saves current progress data to the JSON file."""
        self._ensure_data_dir_exists()

        srs_data_for_save = {}
        for ex_id, srs_attrs in self.exercise_srs_data.items():
            srs_copy = srs_attrs.copy()
            if srs_copy.get("last_reviewed") is not None:
                srs_copy["last_reviewed"] = srs_copy["last_reviewed"].isoformat()
            if srs_copy.get("next_review_due") is not None:
                srs_copy["next_review_due"] = srs_copy["next_review_due"].isoformat()
            srs_data_for_save[ex_id] = srs_copy

        data = {
            "exercise_srs_data": srs_data_for_save,
            "xp": self.xp,
            "last_study_date": (
                self.last_study_date.isoformat() if self.last_study_date else None
            ),
            "current_streak_days": self.current_streak_days,
            "exercise_notes": self.exercise_notes,
        }
        try:
            with open(self.progress_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.debug(
                f"Progress saved for course '{self.course_id}' to {self.progress_file}"
            )
            return True
        except IOError as e:
            logger.error(f"Could not write progress to file {self.progress_file}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while saving progress: {e}")
        return False

    def get_exercise_note(self, exercise_id: str) -> Optional[str]:
        """Retrieves the personal note for a given exercise ID."""
        return self.exercise_notes.get(exercise_id)

    def save_exercise_note(self, exercise_id: str, note_text: str):
        """Saves or updates the note for a given exercise ID. Clears note if text is empty."""
        if note_text and note_text.strip():
            self.exercise_notes[exercise_id] = note_text.strip()
        elif exercise_id in self.exercise_notes:
            del self.exercise_notes[exercise_id]

        self.save_progress()
        logger.debug(f"Note updated for exercise '{exercise_id}'.")

    def get_total_xp(self) -> int:
        return self.xp

    def _calculate_srs_parameters(
        self, srs_attrs: Dict[str, Any], quality_score_sm2: int
    ):
        """
        Implements the SM-2 algorithm to update SRS attributes for an exercise.
        quality_score_sm2: 0-5 (0=Again, 3=Hard, 4=Good, 5=Easy)
        """
        q = quality_score_sm2

        if q < 3:  # Incorrect answer or major difficulty
            srs_attrs["repetitions"] = 0
            srs_attrs["correct_in_a_row"] = 0
            srs_attrs["interval_days"] = 0  # Effectively makes it due immediately
            srs_attrs["ease_factor"] = max(1.3, srs_attrs["ease_factor"] - 0.20)
        else:  # Correct answer
            srs_attrs["correct_in_a_row"] += 1
            srs_attrs["repetitions"] += 1

            if srs_attrs["repetitions"] == 1:
                srs_attrs["interval_days"] = 1
            elif srs_attrs["repetitions"] == 2:
                srs_attrs["interval_days"] = 6
            else:
                srs_attrs["interval_days"] = round(
                    srs_attrs["interval_days"] * srs_attrs["ease_factor"]
                )

            srs_attrs["ease_factor"] += 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
            srs_attrs["ease_factor"] = max(1.3, srs_attrs["ease_factor"])

        # NEW: Set 'is_initially_learned' if criteria are met and it's not already true
        if (
            not srs_attrs["is_initially_learned"]
            and srs_attrs["repetitions"] >= 1
            and quality_score_sm2 >= 3
        ):
            srs_attrs["is_initially_learned"] = True
            logger.debug(
                f"Exercise '{srs_attrs.get('exercise_id', 'N/A')}' marked as initially learned."
            )

        srs_attrs["last_reviewed"] = datetime.now()
        srs_attrs["next_review_due"] = srs_attrs["last_reviewed"] + timedelta(
            days=srs_attrs["interval_days"]
        )

    def update_exercise_srs_data(
        self,
        exercise_id: str,
        is_correct: bool,
        xp_awarded: int = 0,
        quality_score_sm2: int = 4,
    ):
        """
        Updates SRS parameters for an exercise and adds XP.
        is_correct indicates if the user's answer was objectively correct.
        quality_score_sm2 (0-5) reflects user's self-assessment of recall difficulty.
        """
        srs_attrs = self.exercise_srs_data[exercise_id]
        srs_attrs["exercise_id"] = exercise_id

        if not is_correct and quality_score_sm2 >= 3:
            logger.debug(
                f"Forcing SM2 quality to 0 for objectively incorrect answer '{exercise_id}'."
            )
            quality_score_sm2 = 0

        self._calculate_srs_parameters(srs_attrs, quality_score_sm2)

        if xp_awarded > 0:
            self.xp += xp_awarded
            logger.info(
                f"XP awarded for '{exercise_id}': +{xp_awarded}. Total XP: {self.xp}"
            )
            self._update_study_streak()

        self.save_progress()
        logger.debug(
            f"SRS updated for '{exercise_id}': next_due={srs_attrs['next_review_due'].strftime('%Y-%m-%d') if srs_attrs['next_review_due'] else 'N/A'}, "
            f"interval={srs_attrs['interval_days']}, reps={srs_attrs['repetitions']}, EF={srs_attrs['ease_factor']:.2f}, "
            f"init_learned={srs_attrs['is_initially_learned']}"
        )

    def _update_study_streak(self):
        """
        Updates the study streak based on the current date.
        Called when XP is awarded (i.e., on a successful exercise).
        """
        today = date.today()
        if self.last_study_date is None:
            self.current_streak_days = 1
        elif self.last_study_date == today - timedelta(days=1):
            self.current_streak_days += 1
        elif self.last_study_date < today - timedelta(days=1):
            self.current_streak_days = 1

        self.last_study_date = today
        logger.info(
            f"Study streak updated to: {self.current_streak_days} days. Last study: {self.last_study_date}"
        )

    def get_current_streak(self) -> int:
        """
        Returns the current study streak in days.
        Checks if the streak is still valid based on the last study date.
        """
        today = date.today()
        if self.last_study_date is None:
            return 0
        if self.last_study_date == today:
            return self.current_streak_days
        if self.last_study_date == today - timedelta(days=1):
            return self.current_streak_days
        self.current_streak_days = 0  # Streak broken
        return 0

    def get_exercise_srs_data(self, exercise_id: str) -> Dict[str, Any]:
        """Returns the current SRS attributes for a specific exercise."""
        return self.exercise_srs_data[exercise_id]

    def get_due_exercises(
        self, all_course_exercises: List[Exercise], limit: Optional[int] = None
    ) -> List[Exercise]:
        """
        Returns a list of exercise objects that are due for review, sorted by due date.
        An exercise is due if it has never been reviewed (repetitions == 0) OR
        if its next_review_due date is in the past or present.
        """
        due_exercises = []
        now = datetime.now()

        for exercise in all_course_exercises:
            srs_attrs = self.exercise_srs_data[exercise.exercise_id]

            if srs_attrs["repetitions"] == 0 or (
                srs_attrs["next_review_due"] and srs_attrs["next_review_due"] <= now
            ):
                due_exercises.append(exercise)

        due_exercises.sort(
            key=lambda ex: (
                self.exercise_srs_data[ex.exercise_id]["next_review_due"]
                or datetime.min,
                self.exercise_srs_data[ex.exercise_id]["repetitions"],
            )
        )

        return due_exercises[:limit] if limit is not None else due_exercises

    def get_weakest_exercises(
        self, all_course_exercises: List[Exercise], limit: Optional[int] = None
    ) -> List[Exercise]:
        """
        Returns a list of exercises the user struggles with, sorted by ease factor.
        Only includes exercises that have been reviewed at least once.
        """
        reviewed_exercises = []
        for exercise in all_course_exercises:
            srs_attrs = self.exercise_srs_data[exercise.exercise_id]
            # Only consider exercises that have been seen at least once
            if srs_attrs["repetitions"] > 0:
                reviewed_exercises.append(exercise)

        # Sort by ease_factor (ascending), then by last_reviewed (oldest first)
        reviewed_exercises.sort(
            key=lambda ex: (
                self.exercise_srs_data[ex.exercise_id]["ease_factor"],
                self.exercise_srs_data[ex.exercise_id]["last_reviewed"] or datetime.min,
            )
        )

        return reviewed_exercises[:limit] if limit is not None else reviewed_exercises

    def get_lesson_completion_status(self, lesson_exercises: List[Exercise]) -> bool:
        """
        Determines if a lesson is considered 'completed' for display purposes.
        A lesson is completed if ALL its exercises have been 'initially learned'
        (i.e., 'is_initially_learned' flag is True for all of them).
        """
        if not lesson_exercises:
            return True  # An empty lesson is considered completed

        for exercise in lesson_exercises:
            srs_attrs = self.exercise_srs_data[exercise.exercise_id]
            if not srs_attrs["is_initially_learned"]:  # Check the new flag
                return False  # At least one exercise not yet initially learned
        return True  # All exercises are initially learned

    def _find_lesson_position(
        self, lesson_id: str, all_units: List[Unit]
    ) -> Optional[Tuple[int, int]]:
        """
        Finds the (unit_index, lesson_index) of a given lesson_id within all units.
        Returns None if not found.
        """
        for unit_idx, unit in enumerate(all_units):
            for lesson_idx, lesson in enumerate(unit.lessons):
                if lesson.lesson_id == lesson_id:
                    return unit_idx, lesson_idx
        return None

    def _is_previous_lesson_completed(
        self,
        unit_idx: int,
        lesson_idx: int,
        all_units: List[Unit],
        course_manager_ref: Any,
    ) -> bool:
        """
        Checks if the previous lesson in the same unit is completed.
        Assumes (unit_idx, lesson_idx) are valid and lesson_idx > 0.
        """
        current_unit = all_units[unit_idx]
        prev_lesson = current_unit.lessons[lesson_idx - 1]
        return self.get_lesson_completion_status(
            course_manager_ref.get_exercises(prev_lesson.lesson_id)
        )

    def _is_previous_unit_completed(
        self, unit_idx: int, all_units: List[Unit], course_manager_ref: Any
    ) -> bool:
        """
        Checks if all lessons in the previous unit are completed.
        Assumes unit_idx > 0.
        """
        prev_unit = all_units[unit_idx - 1]
        for lesson_in_prev_unit in prev_unit.lessons:
            if not self.get_lesson_completion_status(
                course_manager_ref.get_exercises(lesson_in_prev_unit.lesson_id)
            ):
                return False  # Found an uncompleted lesson in the previous unit
        return True

    def is_lesson_unlocked(
        self,
        lesson_id: str,
        course_manager_ref: Any,
    ) -> bool:
        """
        Determines if a lesson is unlocked for progression.
        Unlock rules:
        1. The first lesson of the first unit is always unlocked.
        2. Any other lesson is unlocked if the immediately preceding lesson (in the same unit) is completed.
        3. The first lesson of any subsequent unit is unlocked if ALL lessons in the immediately preceding unit are completed.
        4. If Developer Mode is active, all lessons are considered unlocked.
        """
        if utils.is_developer_mode_active():
            logger.debug(
                f"Developer Mode: Lesson '{lesson_id}' is considered unlocked."
            )
            return True

        all_units = course_manager_ref.get_units()

        position = self._find_lesson_position(lesson_id, all_units)
        if position is None:
            logger.warning(
                f"Lesson '{lesson_id}' not found in course structure for unlocking check."
            )
            return False

        unit_idx, lesson_idx = position

        # Rule 1: First lesson of the first unit is always unlocked
        if unit_idx == 0 and lesson_idx == 0:
            return True

        # Rule 2: Lesson is not the first in its unit, check previous lesson in same unit
        if lesson_idx > 0:
            return self._is_previous_lesson_completed(
                unit_idx, lesson_idx, all_units, course_manager_ref
            )

        # Rule 3: Lesson is the first in its unit, but not the first unit overall.
        # Check if all lessons in the previous unit are completed.
        if unit_idx > 0 and lesson_idx == 0:
            return self._is_previous_unit_completed(
                unit_idx, all_units, course_manager_ref
            )

        return False  # Default to locked if no explicit unlock rule applies

    def is_lesson_completed(self, lesson_id: str, course_manager_ref: Any) -> bool:
        """
        Checks if a lesson is considered completed based on all its exercises
        having been 'initially learned'. This is the primary check for progression.
        """
        lesson_exercises = course_manager_ref.get_exercises(lesson_id)
        return self.get_lesson_completion_status(lesson_exercises)

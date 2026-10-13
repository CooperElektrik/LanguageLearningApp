import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from PySide6.QtCore import QStandardPaths

try:
    from application import utils  # For developer mode check
except ImportError:
    import utils
import settings  # For ORG_NAME, APP_NAME, PROGRESS_DATA_SUBDIR

from .models import Exercise, Unit  # For type hinting

logger = logging.getLogger(__name__)

# SM-2 scheduling constants
SM2_DEFAULT_EASE_FACTOR = 2.5
SM2_MIN_EASE_FACTOR = 1.3
SM2_MAX_INTERVAL_DAYS = 365 * 10  # Cap at 10 years


@dataclass
class Achievement:
    """Represents a user achievement."""

    id: str
    title: str
    description: str
    icon: str
    is_unlocked: bool = False


def default_srs_record() -> dict[str, Any]:
    """Returns a fresh, unreviewed SRS record for an exercise."""
    return {
        "last_reviewed": None,
        "next_review_due": None,
        "interval_days": 0,
        "ease_factor": SM2_DEFAULT_EASE_FACTOR,
        "repetitions": 0,
        "correct_in_a_row": 0,
        "is_initially_learned": False,  # Gates lesson progression
    }


def apply_sm2_review(
    srs_attrs: dict[str, Any],
    quality_score_sm2: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Applies the SM-2 spaced-repetition update to ``srs_attrs`` in place.

    Pure with respect to everything except the passed-in record and the clock,
    so it can be unit-tested without touching the filesystem.  ``quality_score"
    ``_sm2`` is 0-5 (0=Again, 3=Hard, 4=Good, 5=Easy).
    """
    now = now or datetime.now()
    q = quality_score_sm2

    if q < 3:  # Incorrect answer or major difficulty
        srs_attrs["repetitions"] = 0
        srs_attrs["correct_in_a_row"] = 0
        srs_attrs["interval_days"] = 0  # Effectively makes it due immediately
        srs_attrs["ease_factor"] = max(SM2_MIN_EASE_FACTOR, srs_attrs["ease_factor"] - 0.20)
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
        srs_attrs["ease_factor"] = max(SM2_MIN_EASE_FACTOR, srs_attrs["ease_factor"])

    srs_attrs["interval_days"] = min(srs_attrs["interval_days"], SM2_MAX_INTERVAL_DAYS)

    if (
        not srs_attrs["is_initially_learned"]
        and srs_attrs["repetitions"] >= 1
        and quality_score_sm2 >= 3
    ):
        srs_attrs["is_initially_learned"] = True

    srs_attrs["last_reviewed"] = now
    srs_attrs["next_review_due"] = now + timedelta(days=srs_attrs["interval_days"])
    return srs_attrs


class ProgressManager:
    def __init__(self, course_id: str):
        self.course_id = course_id
        logger.info(f"Initializing ProgressManager for course: {course_id}")

        app_data_base_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        if not app_data_base_dir:
            logger.warning(
                "Could not determine standard AppDataLocation. Falling back to current working directory for progress."
            )
            app_data_base_dir = os.getcwd()

        self.progress_data_dir = os.path.join(app_data_base_dir, settings.PROGRESS_DATA_SUBDIR)
        self.progress_file = os.path.join(self.progress_data_dir, f"{self.course_id}_progress.json")
        logger.debug(f"Progress file path set to: {self.progress_file}")

        # Initialize progress data structures with new 'is_initially_learned' flag
        self.exercise_srs_data: dict[str, dict[str, Any]] = {}
        self.xp: int = 0
        self.last_study_date: date | None = None
        self.current_streak_days: int = 0
        self.exercise_notes: dict[str, str] = {}
        self.lesson_progress: dict[str, dict[str, Any]] = {}

        self._ensure_data_dir_exists()
        self.load_progress()

    def _ensure_data_dir_exists(self):
        """Ensures the progress data directory exists, creating it if necessary."""
        if not os.path.exists(self.progress_data_dir):
            try:
                os.makedirs(self.progress_data_dir, exist_ok=True)
                logger.info(f"Created progress data directory: {self.progress_data_dir}")
            except OSError as e:
                logger.error(
                    f"Could not create progress data directory {self.progress_data_dir}: {e}. Application may not function correctly."
                )

    def _parse_progress_dict(self, data: dict[str, Any]):
        """Parses loaded progress dictionary into internal state."""
        raw_srs_data = data.get("exercise_srs_data", {})
        for ex_id, srs_attrs in raw_srs_data.items():
            # Convert datetime strings back to datetime objects
            if srs_attrs.get("last_reviewed"):
                srs_attrs["last_reviewed"] = datetime.fromisoformat(srs_attrs["last_reviewed"])
            if srs_attrs.get("next_review_due"):
                srs_attrs["next_review_due"] = datetime.fromisoformat(srs_attrs["next_review_due"])

            # Ensure new flag exists for older progress files
            if "is_initially_learned" not in srs_attrs:
                srs_attrs["is_initially_learned"] = srs_attrs.get("repetitions", 0) > 0
                logger.info(
                    f"Populated 'is_initially_learned' for {ex_id} based on repetitions for backward compatibility."
                )

            self.exercise_srs_data[ex_id] = srs_attrs

        self.xp = data.get("xp", 0)
        logger.debug(f"Loaded XP: {self.xp}")

        raw_last_study_date = data.get("last_study_date")
        if raw_last_study_date:
            self.last_study_date = date.fromisoformat(raw_last_study_date)
            logger.debug(f"Loaded last study date: {self.last_study_date}")
        self.current_streak_days = data.get("current_streak_days", 0)
        logger.debug(f"Loaded current streak: {self.current_streak_days} days.")

        self.exercise_notes = data.get("exercise_notes", {})
        logger.debug(f"Loaded {len(self.exercise_notes)} exercise notes.")

        self.lesson_progress = data.get("lesson_progress", {})
        logger.debug(f"Loaded progress for {len(self.lesson_progress)} lessons.")

    def load_progress(self):
        """Loads progress data from the JSON file, with automatic backup fallback."""
        bak_file = f"{self.progress_file}.bak"
        loaded = False

        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self._parse_progress_dict(data)
                    loaded = True
                    logger.info(
                        f"Progress loaded for course '{self.course_id}' from {self.progress_file}. "
                        f"Total exercises with SRS data: {len(self.exercise_srs_data)}"
                    )
            except (json.JSONDecodeError, OSError) as e:
                logger.error(
                    f"Error reading progress file {self.progress_file}: {e}. Attempting backup recovery."
                )

        if not loaded and os.path.exists(bak_file):
            try:
                with open(bak_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self._parse_progress_dict(data)
                    loaded = True
                    logger.warning(
                        f"Successfully recovered progress for course '{self.course_id}' from backup file {bak_file}."
                    )
                    self.save_progress()  # Re-persist recovered data
            except Exception as e:
                logger.error(f"Failed to recover progress from backup file {bak_file}: {e}")

        if not loaded:
            if not os.path.exists(self.progress_file):
                logger.info(
                    f"No progress file found for course '{self.course_id}' at {self.progress_file}. Starting fresh."
                )
            else:
                logger.warning("Resetting all progress data due to critical loading failure.")
            self.exercise_srs_data = {}
            self.xp = 0
            self.last_study_date = None
            self.current_streak_days = 0
            self.exercise_notes = {}
            self.lesson_progress = {}

    def save_progress(self):
        """Saves current progress data atomically with automatic backup."""
        import shutil

        logger.info(
            f"Attempting to save progress for course '{self.course_id}' to {self.progress_file}"
        )
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
            "schema_version": 1,
            "exercise_srs_data": srs_data_for_save,
            "xp": self.xp,
            "last_study_date": (self.last_study_date.isoformat() if self.last_study_date else None),
            "current_streak_days": self.current_streak_days,
            "exercise_notes": self.exercise_notes,
            "lesson_progress": self.lesson_progress,
        }

        tmp_file = f"{self.progress_file}.tmp"
        bak_file = f"{self.progress_file}.bak"

        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())

            # Keep backup of previous healthy progress file
            if os.path.exists(self.progress_file):
                try:
                    shutil.copy2(self.progress_file, bak_file)
                except OSError as be:
                    logger.warning(f"Could not create backup of progress file: {be}")

            os.replace(tmp_file, self.progress_file)
            logger.info(
                f"Progress saved successfully for course '{self.course_id}' to {self.progress_file}"
            )
            return True
        except OSError as e:
            logger.error(f"Could not write progress to file {self.progress_file}: {e}")
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
        except Exception as e:
            logger.error(f"An unexpected error occurred while saving progress: {e}")
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
        return False

    def set_lesson_progress(self, lesson_id: str, last_exercise_index: int):
        """Updates the last viewed exercise index for a specific lesson."""
        if lesson_id not in self.lesson_progress:
            self.lesson_progress[lesson_id] = {}
        self.lesson_progress[lesson_id]["last_exercise_index"] = last_exercise_index
        self.lesson_progress[lesson_id]["last_updated"] = datetime.now().isoformat()
        logger.debug(f"Set lesson '{lesson_id}' progress to index {last_exercise_index}")
        self.save_progress()

    def get_lesson_progress(self, lesson_id: str) -> int | None:
        """Retrieves the last viewed exercise index for a specific lesson."""
        progress = self.lesson_progress.get(lesson_id)
        if progress:
            return progress.get("last_exercise_index")
        return None

    def get_exercise_note(self, exercise_id: str) -> str | None:
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

    def _calculate_srs_parameters(self, srs_attrs: dict[str, Any], quality_score_sm2: int):
        """Applies the (pure) SM-2 update to one exercise's SRS attributes."""
        apply_sm2_review(srs_attrs, quality_score_sm2)
        logger.debug(
            f"Exercise '{srs_attrs.get('exercise_id', 'N/A')}' SRS updated: "
            f"interval_days={srs_attrs['interval_days']}, "
            f"init_learned={srs_attrs['is_initially_learned']}"
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
        logger.debug(
            f"Updating SRS data for exercise '{exercise_id}'. Correct: {is_correct}, Quality: {quality_score_sm2}"
        )
        if exercise_id not in self.exercise_srs_data:
            self.exercise_srs_data[exercise_id] = default_srs_record()
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
            logger.info(f"XP awarded for '{exercise_id}': +{xp_awarded}. Total XP: {self.xp}")
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
        Pure getter without side-effect mutations or disk saves.
        """
        today = date.today()
        if self.last_study_date is None:
            return 0
        if self.last_study_date == today:
            return self.current_streak_days
        if self.last_study_date == today - timedelta(days=1):
            return self.current_streak_days
        return 0

    def get_exercise_progress(self, exercise_id: str) -> dict[str, Any]:
        """
        Returns the SRS attributes for an exercise without populating
        or dirtying disk-bound records during pure read queries.
        """
        if exercise_id in self.exercise_srs_data:
            return self.exercise_srs_data[exercise_id]
        return default_srs_record()

    def get_exercise_srs_data(self, exercise_id: str) -> dict[str, Any]:
        """Returns the current SRS attributes for a specific exercise."""
        return self.get_exercise_progress(exercise_id)

    def record_exercise_attempt(
        self,
        exercise_id: str,
        is_correct: bool,
        xp_awarded: int = 0,
        quality_score_sm2: int = 4,
    ):
        """Records an exercise attempt, updating SRS attributes, streak, and persisting progress."""
        self.update_exercise_srs_data(
            exercise_id=exercise_id,
            is_correct=is_correct,
            xp_awarded=xp_awarded,
            quality_score_sm2=quality_score_sm2,
        )
        if xp_awarded == 0 and is_correct:
            self._update_study_streak()
            self.save_progress()

    def record_lesson_completion(self, lesson_id: str, xp_awarded: int = 0):
        """Records the completion of a lesson, updating streak, clearing in-progress index, and persisting progress."""
        if lesson_id not in self.lesson_progress:
            self.lesson_progress[lesson_id] = {}
        self.lesson_progress[lesson_id]["last_exercise_index"] = 0
        self.lesson_progress[lesson_id]["last_updated"] = datetime.now().isoformat()
        self._update_study_streak()
        if xp_awarded > 0:
            self.xp += xp_awarded
        self.save_progress()

    def get_retention_stats(self, all_course_exercises: list[Exercise]) -> dict[str, Any]:
        """Calculates memory retention and mastery metrics using the SM-2 / Ebbinghaus decay model."""
        import math

        now = datetime.now()
        total = len(all_course_exercises)
        learned_count = 0
        mastered_count = 0
        due_count = 0
        retention_sum = 0.0

        for ex in all_course_exercises:
            srs = self.exercise_srs_data.get(ex.exercise_id, {})
            reps = srs.get("repetitions", 0)
            is_learned = srs.get("is_initially_learned", False)
            last_rev = srs.get("last_reviewed")
            interval = srs.get("interval_days", 0)

            if is_learned or reps > 0:
                learned_count += 1
                if last_rev:
                    delta_days = max(0.0, (now - last_rev).total_seconds() / 86400.0)
                    stability = max(1.0, float(interval))
                    retention = math.exp(-delta_days / stability)
                else:
                    retention = 1.0

                retention_sum += retention
                if reps >= 2 and retention >= 0.8:
                    mastered_count += 1
                if retention < 0.85 or (
                    srs.get("next_review_due") and srs.get("next_review_due") <= now
                ):
                    due_count += 1

        avg_retention = (retention_sum / learned_count * 100.0) if learned_count > 0 else 0.0
        return {
            "total_exercises": total,
            "learned_count": learned_count,
            "mastered_count": mastered_count,
            "due_count": due_count,
            "average_retention": round(avg_retention, 1),
        }

    def get_due_exercises(
        self, all_course_exercises: list[Exercise], limit: int | None = None
    ) -> list[Exercise]:
        """
        Returns a list of exercise objects that are due for review, sorted by due date.
        An exercise is only due for review if it has been learned (is_initially_learned is True
        or repetitions > 0) AND its next review date is in the past or present.
        Unlearned exercises are not marked due for review.
        """
        due_exercises = []
        now = datetime.now()

        for exercise in all_course_exercises:
            srs_attrs = self.get_exercise_progress(exercise.exercise_id)
            is_learned = (
                srs_attrs.get("is_initially_learned") is True or srs_attrs.get("repetitions", 0) > 0
            )
            next_due = srs_attrs.get("next_review_due") or srs_attrs.get("next_review_date")

            if is_learned and (next_due and next_due <= now):
                due_exercises.append(exercise)

        # Priority: overdue reviewed exercises sorted by earliest next review date
        due_exercises.sort(
            key=lambda ex: (
                self.get_exercise_progress(ex.exercise_id).get("next_review_due")
                or self.get_exercise_progress(ex.exercise_id).get("next_review_date")
                or datetime.max,
                self.get_exercise_progress(ex.exercise_id).get("repetitions", 0),
            )
        )

        return due_exercises[:limit] if limit is not None else due_exercises

    def get_weakest_exercises(
        self, all_course_exercises: list[Exercise], limit: int | None = None
    ) -> list[Exercise]:
        """
        Returns a list of exercises the user struggles with, sorted by ease factor.
        Only includes exercises that have been reviewed at least once.
        """
        reviewed_exercises = []
        for exercise in all_course_exercises:
            srs_attrs = self.get_exercise_progress(exercise.exercise_id)
            # Only consider exercises that have been seen at least once
            if srs_attrs.get("repetitions", 0) > 0:
                reviewed_exercises.append(exercise)

        # Sort by ease_factor (ascending), then by last_reviewed (oldest first)
        reviewed_exercises.sort(
            key=lambda ex: (
                self.get_exercise_progress(ex.exercise_id).get(
                    "ease_factor", SM2_DEFAULT_EASE_FACTOR
                ),
                self.get_exercise_progress(ex.exercise_id).get("last_reviewed") or datetime.min,
            )
        )

        return reviewed_exercises[:limit] if limit is not None else reviewed_exercises

    def get_lesson_completion_status(self, lesson_exercises: list[Exercise]) -> bool:
        """
        Determines if a lesson is considered 'completed' for display purposes.
        A lesson is completed if ALL its exercises have been 'initially learned'
        (i.e., 'is_initially_learned' flag is True for all of them).
        """
        if not lesson_exercises:
            return True  # An empty lesson is considered completed

        for exercise in lesson_exercises:
            srs_attrs = self.get_exercise_progress(exercise.exercise_id)
            if not srs_attrs.get("is_initially_learned", False):  # Check the new flag
                return False  # At least one exercise not yet initially learned
        return True  # All exercises are initially learned

    def _find_lesson_position(
        self, lesson_id: str, all_units: list[Unit]
    ) -> tuple[int, int] | None:
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
        all_units: list[Unit],
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
        self, unit_idx: int, all_units: list[Unit], course_manager_ref: Any
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
            logger.debug(f"Developer Mode: Lesson '{lesson_id}' is considered unlocked.")
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
            return self._is_previous_unit_completed(unit_idx, all_units, course_manager_ref)

        return False  # Default to locked if no explicit unlock rule applies

    def is_lesson_completed(self, lesson_id: str, course_manager_ref: Any) -> bool:
        """
        Checks if a lesson is considered completed based on all its exercises
        having been 'initially learned'. This is the primary check for progression.
        """
        lesson_exercises = course_manager_ref.get_exercises(lesson_id)
        return self.get_lesson_completion_status(lesson_exercises)

    def get_achievements(self, course_manager_ref: Any = None) -> list[Achievement]:
        """
        Returns the list of achievements and their unlocked status for the current course.
        """
        all_completed = False
        if course_manager_ref and getattr(course_manager_ref, "course", None):
            units = course_manager_ref.get_units()
            all_lessons = [lesson for unit in units for lesson in unit.lessons]
            if all_lessons:
                all_completed = all(
                    self.is_lesson_completed(lesson.lesson_id, course_manager_ref)
                    for lesson in all_lessons
                )

        total_xp = self.get_total_xp()
        streak = self.get_current_streak()

        return [
            Achievement(
                id="first_step",
                title="First Step",
                description="Complete your first lesson.",
                icon="novice.png",
                is_unlocked=(total_xp >= 10),
            ),
            Achievement(
                id="xp_enthusiast",
                title="XP Enthusiast",
                description="Reach 1000 XP.",
                icon="enthusiast.png",
                is_unlocked=(total_xp >= 1000),
            ),
            Achievement(
                id="7_day_streak",
                title="7-Day Streak",
                description="Study for 7 consecutive days.",
                icon="7day.png",
                is_unlocked=(streak >= 7),
            ),
            Achievement(
                id="30_day_streak",
                title="30-Day Streak",
                description="Study for 30 consecutive days.",
                icon="30day.png",
                is_unlocked=(streak >= 30),
            ),
            Achievement(
                id="all_lessons_completed",
                title="Lesson Master",
                description="Complete all lessons in the course.",
                icon="master.png",
                is_unlocked=all_completed,
            ),
        ]

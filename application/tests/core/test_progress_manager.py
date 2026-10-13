from datetime import datetime

from core.models import Exercise
from freezegun import freeze_time


def test_progress_save_and_load(progress_manager):
    """Tests that progress data can be saved and reloaded."""
    ex_id = "u1l1_ex1"
    progress_manager.update_exercise_srs_data(ex_id, is_correct=True, xp_awarded=10)

    # Create a new manager instance to load the saved data
    new_progress_manager = type(progress_manager)(progress_manager.course_id)

    assert new_progress_manager.get_total_xp() == 10
    srs_data = new_progress_manager.get_exercise_srs_data(ex_id)
    assert srs_data["repetitions"] == 1


@freeze_time("2023-01-01 12:00:00")
def test_study_streak_logic(progress_manager):
    """Tests the daily study streak logic using time mocking."""
    ex_id = "u1l1_ex1"

    # Day 1: Start streak
    progress_manager.update_exercise_srs_data(ex_id, is_correct=True, xp_awarded=10)
    assert progress_manager.get_current_streak() == 1

    # Day 1, later: Streak does not increase
    with freeze_time("2023-01-01 18:00:00"):
        progress_manager.update_exercise_srs_data(ex_id, is_correct=True, xp_awarded=10)
        assert progress_manager.get_current_streak() == 1

    # Day 2: Continue streak
    with freeze_time("2023-01-02 12:00:00"):
        progress_manager.update_exercise_srs_data(ex_id, is_correct=True, xp_awarded=10)
        assert progress_manager.get_current_streak() == 2

    # Day 4: Break streak
    with freeze_time("2023-01-04 12:00:00"):
        progress_manager.update_exercise_srs_data(ex_id, is_correct=True, xp_awarded=10)
        assert progress_manager.get_current_streak() == 1


def test_srs_updates(progress_manager):
    """Tests the SRS algorithm's response to correct and incorrect answers."""
    ex_id = "u1l1_ex1"

    # First correct answer
    progress_manager.update_exercise_srs_data(ex_id, is_correct=True)
    srs_data = progress_manager.get_exercise_srs_data(ex_id)
    assert srs_data["repetitions"] == 1
    assert srs_data["interval_days"] == 1
    assert srs_data["ease_factor"] == 2.5

    # Incorrect answer
    progress_manager.update_exercise_srs_data(ex_id, is_correct=False)
    srs_data = progress_manager.get_exercise_srs_data(ex_id)
    assert srs_data["repetitions"] == 0  # Resets
    assert srs_data["interval_days"] == 0  # Due immediately
    assert srs_data["ease_factor"] < 2.6  # Should be lower than after one success


def test_lesson_completion_and_unlocking(course_manager, progress_manager):
    """Tests the logic for marking lessons as complete and unlocking the next ones."""
    lesson1_id = "u1l1"
    lesson2_id = "u1l2"

    # Initially, lesson 1 is unlocked, lesson 2 is not
    assert progress_manager.is_lesson_unlocked(lesson1_id, course_manager) is True
    assert progress_manager.is_lesson_unlocked(lesson2_id, course_manager) is False
    assert progress_manager.is_lesson_completed(lesson1_id, course_manager) is False

    # Complete all exercises in lesson 1
    for ex in course_manager.get_exercises(lesson1_id):
        progress_manager.update_exercise_srs_data(ex.exercise_id, is_correct=True)

    # Now, lesson 1 should be complete and lesson 2 should be unlocked
    assert progress_manager.is_lesson_completed(lesson1_id, course_manager) is True
    assert progress_manager.is_lesson_unlocked(lesson2_id, course_manager) is True


def test_progress_backup_recovery(progress_manager):
    """Tests that corrupted progress files automatically recover from .bak backup."""
    import os

    ex_id = "u1l1_ex1"
    progress_manager.update_exercise_srs_data(ex_id, is_correct=True, xp_awarded=50)
    assert progress_manager.save_progress() is True

    # Make sure .bak exists by saving a second time with more XP
    progress_manager.xp = 75
    assert progress_manager.save_progress() is True

    bak_file = f"{progress_manager.progress_file}.bak"
    assert os.path.exists(bak_file)

    # Corrupt the main progress file intentionally
    with open(progress_manager.progress_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json corrupted content ")

    # Create new manager instance; should fall back to .bak and restore
    new_manager = type(progress_manager)(progress_manager.course_id)
    assert new_manager.get_total_xp() > 0
    assert new_manager.get_exercise_srs_data(ex_id)["repetitions"] == 1


@freeze_time("2023-01-01 12:00:00")
def test_get_current_streak_does_not_save_or_mutate_on_broken_streak(progress_manager, monkeypatch):
    """Verifies get_current_streak is pure: does not mutate current_streak_days and does not save."""
    ex_id = "u1l1_ex1"
    progress_manager.update_exercise_srs_data(ex_id, is_correct=True, xp_awarded=10)
    assert progress_manager.get_current_streak() == 1
    assert progress_manager.current_streak_days == 1

    # Move forward 3 days so streak is broken
    with freeze_time("2023-01-04 12:00:00"):
        save_called = False
        original_save = progress_manager.save_progress

        def mock_save(*args, **kwargs):
            nonlocal save_called
            save_called = True
            return original_save(*args, **kwargs)

        monkeypatch.setattr(progress_manager, "save_progress", mock_save)

        # Pure getter read
        streak = progress_manager.get_current_streak()
        assert streak == 0
        assert save_called is False, "get_current_streak() should not call save_progress()"
        assert progress_manager.current_streak_days == 1, (
            "get_current_streak() should not mutate in-memory state"
        )

        # Now record an exercise attempt on day 4 - this should recalculate and save
        progress_manager.record_exercise_attempt(ex_id, is_correct=True, xp_awarded=10)
        assert save_called is True, "Saving should happen during exercise attempt"
        assert progress_manager.get_current_streak() == 1
        assert progress_manager.current_streak_days == 1


def test_get_due_exercises_excludes_unlearned_exercises(progress_manager):
    """Verifies get_due_exercises only returns learned exercises whose review is due, excluding unlearned ones."""
    now = datetime(2026, 1, 10, 12, 0, 0)

    ex_unlearned = Exercise(
        exercise_id="ex_unlearned", type="translate_to_target", prompt="Unlearned"
    )
    ex_learned_not_due = Exercise(
        exercise_id="ex_learned_not_due", type="translate_to_target", prompt="Future"
    )
    ex_learned_due = Exercise(
        exercise_id="ex_learned_due", type="translate_to_target", prompt="Due"
    )

    all_exercises = [ex_unlearned, ex_learned_not_due, ex_learned_due]

    # Set up learned exercises:
    # 1. ex_learned_due: reviewed in the past, review due date is past
    progress_manager.exercise_srs_data["ex_learned_due"] = {
        "is_initially_learned": True,
        "repetitions": 1,
        "next_review_due": datetime(2026, 1, 5, 12, 0, 0),
        "last_reviewed": datetime(2026, 1, 4, 12, 0, 0),
        "interval_days": 1,
        "ease_factor": 2.5,
    }

    # 2. ex_learned_not_due: review due date is in the future
    progress_manager.exercise_srs_data["ex_learned_not_due"] = {
        "is_initially_learned": True,
        "repetitions": 2,
        "next_review_due": datetime(2026, 1, 20, 12, 0, 0),
        "last_reviewed": datetime(2026, 1, 9, 12, 0, 0),
        "interval_days": 11,
        "ease_factor": 2.5,
    }

    from freezegun import freeze_time

    with freeze_time(now):
        due = progress_manager.get_due_exercises(all_exercises)

    # Only ex_learned_due should be returned
    assert len(due) == 1
    assert due[0].exercise_id == "ex_learned_due"

    # ex_unlearned should not be populated in exercise_srs_data
    assert "ex_unlearned" not in progress_manager.exercise_srs_data


def test_get_exercise_progress_does_not_populate_or_dirty_records(progress_manager):
    """Verifies reading exercise progress for unlearned exercises does not populate or dirty internal state."""
    assert len(progress_manager.exercise_srs_data) == 0

    p = progress_manager.get_exercise_progress("non_existent_exercise")
    assert p["is_initially_learned"] is False
    assert p["repetitions"] == 0
    assert p["next_review_due"] is None

    # exercise_srs_data must remain empty
    assert "non_existent_exercise" not in progress_manager.exercise_srs_data
    assert len(progress_manager.exercise_srs_data) == 0


def test_lesson_view_skip_requeues_in_mistakes_queue(course_manager, progress_manager):
    """Verifies that skipping an exercise re-queues it in mistakes_queue."""
    import sys
    import types
    from unittest.mock import MagicMock

    added_modules = []
    for mod in ("numpy", "sounddevice", "soundfile", "py7zr", "markdown"):
        if mod not in sys.modules:
            m = types.ModuleType(mod)
            if mod == "numpy":
                m.int16 = int
                m.frombuffer = lambda *a, **k: []
            sys.modules[mod] = m
            added_modules.append(mod)

    try:
        from application.ui.views.lesson_view import LessonView

        stt_mock = MagicMock()
        view = LessonView(course_manager, progress_manager, stt_mock)
        ex = Exercise(
            exercise_id="ex_test_skip", type="translate_to_target", prompt="Skip me", answer="Test"
        )
        view.current_exercise_obj = ex
        view.mistakes_queue = []

        view._on_skip()

        # Must be added to mistakes_queue so the user cannot bypass it
        assert ex in view.mistakes_queue
        # It must not be marked initially learned
        assert (
            progress_manager.get_exercise_progress("ex_test_skip")["is_initially_learned"] is False
        )
    finally:
        for mod in added_modules:
            sys.modules.pop(mod, None)

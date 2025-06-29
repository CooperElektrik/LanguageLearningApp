from freezegun import freeze_time
from datetime import timedelta


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

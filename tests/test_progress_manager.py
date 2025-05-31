
import pytest
import os
import json
import uuid
from application.core.progress_manager import ProgressManager
from application.core.models import Course, Unit, Lesson, Exercise # Import Exercise
from datetime import date, timedelta


def test_initial_progress(progress_manager_instance: ProgressManager):
    assert progress_manager_instance.get_total_xp() == 0


def test_update_exercise_srs_data(progress_manager_instance: ProgressManager):
    exercise_id = "ex1"

    # First correct answer (quality 5)
    progress_manager_instance.update_exercise_srs_data(
        exercise_id, is_correct=True, xp_awarded=10, quality_score_sm2=5
    )
    srs_data = progress_manager_instance.get_exercise_srs_data(exercise_id)
    assert srs_data["repetitions"] == 1
    assert srs_data["interval_days"] == 1
    assert srs_data["correct_in_a_row"] == 1
    assert srs_data["ease_factor"] == 2.6 # 2.5 + 0.1
    assert progress_manager_instance.get_total_xp() == 10

    # Second correct answer (quality 5)
    progress_manager_instance.update_exercise_srs_data(
        exercise_id, is_correct=True, xp_awarded=10, quality_score_sm2=5
    )
    srs_data = progress_manager_instance.get_exercise_srs_data(exercise_id)
    assert srs_data["repetitions"] == 2
    assert srs_data["interval_days"] == 6 # Should be 6 for 2nd rep
    assert srs_data["correct_in_a_row"] == 2
    assert srs_data["ease_factor"] == 2.7 # 2.6 + 0.1
    assert progress_manager_instance.get_total_xp() == 20

    # Incorrect answer (quality 0)
    progress_manager_instance.update_exercise_srs_data(
        exercise_id, is_correct=False, xp_awarded=10, quality_score_sm2=0
    )
    srs_data = progress_manager_instance.get_exercise_srs_data(exercise_id)
    assert srs_data["repetitions"] == 0 # Repetitions reset
    assert srs_data["interval_days"] == 0 # Interval reset
    assert srs_data["correct_in_a_row"] == 0 # Correct in a row reset
    assert srs_data["ease_factor"] == 2.5 # 2.7 - 0.2 = 2.5 (max(1.3, 2.5))
    assert (
        progress_manager_instance.get_total_xp() == 20
    )  # XP doesn't increase on incorrect


def test_save_and_load_progress(
    tmp_path,
):
    course_id = f"test_saveload_{uuid.uuid4().hex}"
    pm_data_dir = tmp_path / "saveload_pm_data_isolated"

    pm1 = ProgressManager(course_id=course_id, data_dir=str(pm_data_dir))
    assert pm1.get_total_xp() == 0
    pm1.update_exercise_srs_data("ex1", is_correct=True, xp_awarded=10)
    pm1.update_exercise_srs_data("ex2", is_correct=True, xp_awarded=10)

    pm2 = ProgressManager(course_id=course_id, data_dir=str(pm_data_dir))
    assert pm2.get_total_xp() == 20 # Corrected method name
    srs_data_ex1 = pm2.get_exercise_srs_data("ex1")
    assert srs_data_ex1["repetitions"] > 0
    srs_data_ex2 = pm2.get_exercise_srs_data("ex2")
    assert srs_data_ex2["repetitions"] > 0


@pytest.fixture
def course_for_unlock_test() -> Course:
    u1_lessons = [
        Lesson(lesson_id="u1l1", title="L1.1", unit_id="u1", exercises=[]),
        Lesson(lesson_id="u1l2", title="L1.2", unit_id="u1", exercises=[]),
    ]
    u1 = Unit(unit_id="u1", title="U1", lessons=u1_lessons)

    u2_lessons = [Lesson(lesson_id="u2l1", title="L2.1", unit_id="u2", exercises=[])]
    u2 = Unit(unit_id="u2", title="U2", lessons=u2_lessons)

    return Course(
        course_id="unlock_test_course",
        title="Unlock Test Course",
        target_language="test_tgt",
        source_language="test_src",
        version="1.0",
        units=[u1, u2],
    )


def test_lesson_completion_status(progress_manager_instance: ProgressManager):
    pm = progress_manager_instance
    
    # Mock Exercise objects for testing
    lesson_exercises = [
        Exercise(exercise_id="lesson1_ex1", type="test"),
        Exercise(exercise_id="lesson1_ex2", type="test"),
        Exercise(exercise_id="lesson1_ex3", type="test"),
    ] 

    # Initially not completed
    assert pm.get_lesson_completion_status("lesson1", lesson_exercises) is False

    # Complete one exercise
    pm.update_exercise_srs_data("lesson1_ex1", is_correct=True)
    assert pm.get_lesson_completion_status("lesson1", lesson_exercises) is False

    # Complete all exercises at least once
    pm.update_exercise_srs_data("lesson1_ex2", is_correct=True)
    pm.update_exercise_srs_data("lesson1_ex3", is_correct=True)
    assert pm.get_lesson_completion_status("lesson1", lesson_exercises) is True


def test_lesson_unlocking_logic(
    progress_manager_instance: ProgressManager, course_for_unlock_test: Course
):
    pm = progress_manager_instance
    course = course_for_unlock_test
    all_units = course.units
    unit1 = next(u for u in all_units if u.unit_id == "u1")
    unit2 = next(u for u in all_units if u.unit_id == "u2")

    # Mock CourseManager for `is_lesson_unlocked`
    # It needs a get_exercises method that returns Exercise objects
    class MockCourseManagerForUnlock:
        def get_exercises(self, lesson_id: str):
            return [
                Exercise(exercise_id=f"{lesson_id}_ex{i}", type="test")
                for i in range(3)
            ]

    mock_course_manager_ref = MockCourseManagerForUnlock() # Instance of the mock

    assert (
        pm.is_lesson_unlocked(
            lesson_id="u1l1",
            unit_lessons=unit1.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager_ref, # Pass the instance
        )
        is True
    )
    assert (
        pm.is_lesson_unlocked(
            lesson_id="u1l2",
            unit_lessons=unit1.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager_ref, # Pass the instance
        )
        is False
    )
    assert (
        pm.is_lesson_unlocked(
            lesson_id="u2l1",
            unit_lessons=unit2.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager_ref, # Pass the instance
        )
        is False
    )

    # To unlock u1l2, u1l1 must be completed (all its exercises reviewed >= 1 time)
    for i in range(3):
        pm.update_exercise_srs_data(f"u1l1_ex{i}", is_correct=True)

    assert (
        pm.is_lesson_completed("u1l1", mock_course_manager_ref) # Pass the instance here
        is True
    )

    assert (
        pm.is_lesson_unlocked(
            lesson_id="u1l2",
            unit_lessons=unit1.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager_ref, # Pass the instance
        )
        is True
    )
    assert (
        pm.is_lesson_unlocked(
            lesson_id="u2l1",
            unit_lessons=unit2.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager_ref, # Pass the instance
        )
        is False
    )

    # To unlock u2l1, all lessons in u1 must be completed (u1l1 and u1l2)
    for i in range(3):
        pm.update_exercise_srs_data(f"u1l2_ex{i}", is_correct=True)
    assert (
        pm.is_lesson_completed("u1l2", mock_course_manager_ref) # Pass the instance here
        is True
    )

    assert (
        pm.is_lesson_unlocked(
            lesson_id="u2l1",
            unit_lessons=unit2.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager_ref, # Pass the instance
        )
        is True
    )

def test_initial_streak_and_last_study_date(progress_manager_instance: ProgressManager):
    """Test that initially streak is 0 and last_study_date is None."""
    assert progress_manager_instance.get_current_streak() == 0
    assert progress_manager_instance.last_study_date is None

def test_streak_first_day_study(progress_manager_instance: ProgressManager):
    """Test streak becomes 1 after the first study session."""
    pm = progress_manager_instance
    # Simulate a successful exercise completion
    pm.update_exercise_srs_data("ex_streak1", is_correct=True) 
    
    assert pm.get_current_streak() == 1
    assert pm.last_study_date == date.today()

def test_streak_consecutive_days(progress_manager_instance: ProgressManager):
    """Test streak increments on consecutive study days."""
    pm = progress_manager_instance
    today = date.today()

    # Day 1
    pm.last_study_date = today - timedelta(days=2) # Simulate studied day before yesterday
    pm.current_streak_days = 0 # Ensure clean start for this test's logic
    pm._update_study_streak() # Call directly to set 'today' as last_study_date and streak to 1
    assert pm.get_current_streak() == 1
    assert pm.last_study_date == today
    
    # Simulate Day 2 (next day)
    # To simulate next day, we manually set last_study_date as 'today' (which was prev. 'yesterday')
    # and then call _update_study_streak as if it's the 'new today'
    pm.last_study_date = today # This is now considered 'yesterday' for the next call
    # To properly test, we need to mock 'date.today()' or manually manipulate last_study_date
    # Simpler approach for unit test: directly manipulate state.
    pm.last_study_date = today - timedelta(days=1) # Set it to yesterday
    pm.current_streak_days = 1 # Reflecting that yesterday was a study day
    pm._update_study_streak() # This call is now for 'today'
    assert pm.get_current_streak() == 2
    assert pm.last_study_date == today

    # Simulate Day 3
    pm.last_study_date = today - timedelta(days=1) # Set to yesterday relative to a "new today"
    pm.current_streak_days = 2
    pm._update_study_streak()
    assert pm.get_current_streak() == 3
    assert pm.last_study_date == today

def test_streak_broken_then_resumed(progress_manager_instance: ProgressManager):
    """Test streak resets if a day is missed, then restarts."""
    pm = progress_manager_instance
    today = date.today()

    # Studied 2 days ago
    pm.last_study_date = today - timedelta(days=2)
    pm.current_streak_days = 1 # Was 1 after studying 2 days ago
    
    # Now, study "today" (after missing yesterday)
    pm._update_study_streak() 
    assert pm.get_current_streak() == 1 # Streak should reset to 1
    assert pm.last_study_date == today

def test_streak_multiple_studies_same_day(progress_manager_instance: ProgressManager):
    """Test multiple studies on the same day don't increment streak beyond 1 for that day."""
    pm = progress_manager_instance
    
    pm.update_exercise_srs_data("ex_sameday1", is_correct=True)
    assert pm.get_current_streak() == 1
    assert pm.last_study_date == date.today()

    pm.update_exercise_srs_data("ex_sameday2", is_correct=True)
    assert pm.get_current_streak() == 1 # Still 1 for the same day
    assert pm.last_study_date == date.today()

def test_streak_resets_on_load_after_gap(tmp_path):
    """Test streak is correctly 0 if loaded after a study gap."""
    course_id = "streak_gap_test"
    pm_data_dir = tmp_path / "streak_gap_data"
    os.makedirs(pm_data_dir, exist_ok=True)
    
    pm1 = ProgressManager(course_id=course_id, data_dir=str(pm_data_dir))
    # Simulate study 2 days ago
    pm1.last_study_date = date.today() - timedelta(days=2)
    pm1.current_streak_days = 5 # Artificially set a streak
    pm1.save_progress()

    # Load progress (simulating app opening on a new day, after the gap)
    pm2 = ProgressManager(course_id=course_id, data_dir=str(pm_data_dir))
    # get_current_streak() should detect the gap and reset streak
    assert pm2.get_current_streak() == 0 
    # last_study_date should still be the old date until a new study occurs
    assert pm2.last_study_date == date.today() - timedelta(days=2)

    # Now, simulate a study session on the current day with pm2
    pm2.update_exercise_srs_data("ex_after_gap", is_correct=True)
    assert pm2.get_current_streak() == 1
    assert pm2.last_study_date == date.today()

# --- NEW TESTS FOR EXERCISE NOTES ---

def test_save_and_retrieve_exercise_note(progress_manager_instance: ProgressManager):
    """Test saving and retrieving a note for an exercise."""
    pm = progress_manager_instance
    exercise_id = "note_ex1"
    note_text = "This is a test note."

    assert pm.get_exercise_note(exercise_id) is None # Initially no note

    pm.save_exercise_note(exercise_id, note_text)
    assert pm.get_exercise_note(exercise_id) == note_text

def test_update_exercise_note(progress_manager_instance: ProgressManager):
    """Test updating an existing note."""
    pm = progress_manager_instance
    exercise_id = "note_ex2"
    initial_note = "Initial note."
    updated_note = "Updated note text."

    pm.save_exercise_note(exercise_id, initial_note)
    assert pm.get_exercise_note(exercise_id) == initial_note

    pm.save_exercise_note(exercise_id, updated_note)
    assert pm.get_exercise_note(exercise_id) == updated_note

def test_delete_exercise_note_by_empty_string(progress_manager_instance: ProgressManager):
    """Test that saving an empty string for a note deletes it."""
    pm = progress_manager_instance
    exercise_id = "note_ex3"
    note_text = "A note to be deleted."

    pm.save_exercise_note(exercise_id, note_text)
    assert pm.get_exercise_note(exercise_id) == note_text

    pm.save_exercise_note(exercise_id, "") # Save empty string
    assert pm.get_exercise_note(exercise_id) is None # Note should be gone

    pm.save_exercise_note(exercise_id, "   ") # Save whitespace string
    assert pm.get_exercise_note(exercise_id) is None # Note should also be gone

def test_notes_persistence_across_save_load(tmp_path):
    """Test notes are correctly saved and loaded."""
    course_id = f"test_notes_persist_{uuid.uuid4().hex}"
    pm_data_dir = tmp_path / "notes_persist_data"

    pm1 = ProgressManager(course_id=course_id, data_dir=str(pm_data_dir))
    exercise_id1 = "persist_ex1"
    note1 = "Note for ex1."
    exercise_id2 = "persist_ex2"
    note2 = "Note for ex2, a bit longer."

    pm1.save_exercise_note(exercise_id1, note1)
    pm1.save_exercise_note(exercise_id2, note2)
    # save_progress is called within save_exercise_note, so no explicit call needed here.

    # Create a new ProgressManager instance to load the saved data
    pm2 = ProgressManager(course_id=course_id, data_dir=str(pm_data_dir))
    assert pm2.get_exercise_note(exercise_id1) == note1
    assert pm2.get_exercise_note(exercise_id2) == note2
    assert pm2.get_exercise_note("non_existent_ex") is None
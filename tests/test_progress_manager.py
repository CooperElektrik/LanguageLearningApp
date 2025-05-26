import pytest
import os
import json
import uuid # For unique course_ids in save/load test
from application.core.progress_manager import ProgressManager
from application.core.models import Course, Unit, Lesson # For unlock test

# The progress_manager_instance fixture is now correctly isolated by conftest.py

def test_initial_progress(progress_manager_instance: ProgressManager):
    assert progress_manager_instance.get_total_xp() == 0
    assert not progress_manager_instance.is_lesson_completed("any_lesson")
    assert progress_manager_instance.get_lesson_score("any_lesson") == 0

def test_mark_lesson_completed(progress_manager_instance: ProgressManager):
    lesson_id = "l1"
    
    # First completion
    progress_manager_instance.mark_lesson_completed(lesson_id, score=15)
    assert progress_manager_instance.is_lesson_completed(lesson_id) is True
    assert progress_manager_instance.get_lesson_score(lesson_id) == 15
    assert progress_manager_instance.get_total_xp() == 15

    # Mark again, score and XP should accumulate based on current ProgressManager logic
    progress_manager_instance.mark_lesson_completed(lesson_id, score=10)
    assert progress_manager_instance.get_lesson_score(lesson_id) == 25 # 15 + 10
    assert progress_manager_instance.get_total_xp() == 25 # 15 + 10

def test_save_and_load_progress(tmp_path): # Use tmp_path directly for this test's specific setup
    course_id = f"test_saveload_{uuid.uuid4().hex}"
    pm_data_dir = tmp_path / "saveload_pm_data_isolated"
    # ProgressManager will create this directory if its internal logic for _ensure_data_dir_exists is robust.

    # Instance 1: Save progress
    pm1 = ProgressManager(course_id=course_id, data_dir=str(pm_data_dir))
    assert pm1.get_total_xp() == 0 # Verify initial state
    pm1.mark_lesson_completed("lessonA", score=20)
    pm1.mark_lesson_completed("lessonB", score=30)
    # save_progress is called internally by mark_lesson_completed

    # Instance 2: Load progress
    pm2 = ProgressManager(course_id=course_id, data_dir=str(pm_data_dir)) # Same course_id and data_dir
    assert pm2.is_lesson_completed("lessonA") is True
    assert pm2.is_lesson_completed("lessonB") is True
    assert not pm2.is_lesson_completed("lessonC") # Verify a non-completed lesson
    assert pm2.get_total_xp() == 50 # 20 + 30
    assert pm2.get_lesson_score("lessonA") == 20
    assert pm2.get_lesson_score("lessonB") == 30


@pytest.fixture
def course_for_unlock_test() -> Course:
    # Create a minimal course structure for testing unlock logic
    # Unit 1: u1l1, u1l2
    # Unit 2: u2l1
    u1_lessons = [
        Lesson(lesson_id="u1l1", title="L1.1", unit_id="u1", exercises=[]),
        Lesson(lesson_id="u1l2", title="L1.2", unit_id="u1", exercises=[])
    ]
    u1 = Unit(unit_id="u1", title="U1", lessons=u1_lessons)
    
    u2_lessons = [
        Lesson(lesson_id="u2l1", title="L2.1", unit_id="u2", exercises=[])
    ]
    u2 = Unit(unit_id="u2", title="U2", lessons=u2_lessons)
    
    return Course(course_id="unlock_test_course", title="Unlock Test Course", 
                  target_language="test_tgt", source_language="test_src", version="1.0", 
                  units=[u1, u2])


def test_lesson_unlocking_logic(progress_manager_instance: ProgressManager, course_for_unlock_test: Course):
    pm = progress_manager_instance # This PM is fresh and isolated
    course = course_for_unlock_test
    all_units = course.units
    unit1 = next(u for u in all_units if u.unit_id == "u1")
    unit2 = next(u for u in all_units if u.unit_id == "u2")
    
    # First lesson of first unit always unlocked
    assert pm.is_lesson_unlocked(lesson_id="u1l1", unit_lessons=unit1.lessons, all_units=all_units) is True
    # Second lesson of first unit initially locked
    assert pm.is_lesson_unlocked(lesson_id="u1l2", unit_lessons=unit1.lessons, all_units=all_units) is False
    # First lesson of second unit initially locked
    assert pm.is_lesson_unlocked(lesson_id="u2l1", unit_lessons=unit2.lessons, all_units=all_units) is False

    # Complete first lesson
    pm.mark_lesson_completed("u1l1")
    assert pm.is_lesson_unlocked(lesson_id="u1l2", unit_lessons=unit1.lessons, all_units=all_units) is True # Now u1l2 is unlocked
    assert pm.is_lesson_unlocked(lesson_id="u2l1", unit_lessons=unit2.lessons, all_units=all_units) is False # u2l1 still locked

    # Complete second lesson of first unit
    pm.mark_lesson_completed("u1l2")
    # Now u2l1 (first lesson of unit 2) should be unlocked because all of unit 1 is complete
    assert pm.is_lesson_unlocked(lesson_id="u2l1", unit_lessons=unit2.lessons, all_units=all_units) is True
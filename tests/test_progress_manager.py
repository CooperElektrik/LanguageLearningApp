import pytest
import os
import json
import uuid
from application.core.progress_manager import ProgressManager
from application.core.models import Course, Unit, Lesson


def test_initial_progress(progress_manager_instance: ProgressManager):
    assert progress_manager_instance.get_total_xp() == 0


def test_update_exercise_srs_data(progress_manager_instance: ProgressManager):
    exercise_id = "ex1"

    # First correct answer
    progress_manager_instance.update_exercise_srs_data(
        exercise_id, is_correct=True, xp_awarded=10, quality_score_sm2=5
    )
    srs_data = progress_manager_instance.get_exercise_srs_data(exercise_id)
    assert srs_data["repetitions"] == 1
    assert srs_data["interval_days"] == 1
    assert srs_data["correct_in_a_row"] == 1
    assert srs_data["ease_factor"] > 2.5
    assert progress_manager_instance.get_total_xp() == 10

    # Second correct answer
    progress_manager_instance.update_exercise_srs_data(
        exercise_id, is_correct=True, xp_awarded=10, quality_score_sm2=5
    )
    srs_data = progress_manager_instance.get_exercise_srs_data(exercise_id)
    assert srs_data["repetitions"] == 2
    assert srs_data["interval_days"] == 6
    assert srs_data["correct_in_a_row"] == 2
    assert srs_data["ease_factor"] > 2.5
    assert progress_manager_instance.get_total_xp() == 20

    # Incorrect answer
    progress_manager_instance.update_exercise_srs_data(
        exercise_id, is_correct=False, xp_awarded=10, quality_score_sm2=0
    )
    srs_data = progress_manager_instance.get_exercise_srs_data(exercise_id)
    assert srs_data["repetitions"] == 0
    assert srs_data["interval_days"] == 0
    assert srs_data["correct_in_a_row"] == 0
    assert srs_data["ease_factor"] < 2.5
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
    assert pm2.get_total_total_xp() == 20
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
    lesson_exercises = [
        {"exercise_id": "lesson1_ex1"},
        {"exercise_id": "lesson1_ex2"},
        {"exercise_id": "lesson1_ex3"},
    ]  # Mock exercise objects with exercise_id

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

    mock_course_manager = type(
        "MockCourseManager",
        (),
        {
            "get_exercises": lambda self, lesson_id: [
                type("Exercise", (), {"exercise_id": f"{lesson_id}_ex{i}"})()
                for i in range(3)
            ]  # Mock 3 exercises per lesson
        },
    )()

    assert (
        pm.is_lesson_unlocked(
            lesson_id="u1l1",
            unit_lessons=unit1.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager,
        )
        is True
    )
    assert (
        pm.is_lesson_unlocked(
            lesson_id="u1l2",
            unit_lessons=unit1.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager,
        )
        is False
    )
    assert (
        pm.is_lesson_unlocked(
            lesson_id="u2l1",
            unit_lessons=unit2.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager,
        )
        is False
    )

    # To unlock u1l2, u1l1 must be completed (all its exercises reviewed >= 1 time)
    for i in range(3):
        pm.update_exercise_srs_data(f"u1l1_ex{i}", is_correct=True)

    assert (
        pm.is_lesson_completed("u1l1", mock_course_manager.get_exercises("u1l1"))
        is True
    )

    assert (
        pm.is_lesson_unlocked(
            lesson_id="u1l2",
            unit_lessons=unit1.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager,
        )
        is True
    )
    assert (
        pm.is_lesson_unlocked(
            lesson_id="u2l1",
            unit_lessons=unit2.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager,
        )
        is False
    )

    # To unlock u2l1, all lessons in u1 must be completed (u1l1 and u1l2)
    for i in range(3):
        pm.update_exercise_srs_data(f"u1l2_ex{i}", is_correct=True)
    assert (
        pm.is_lesson_completed("u1l2", mock_course_manager.get_exercises("u1l2"))
        is True
    )

    assert (
        pm.is_lesson_unlocked(
            lesson_id="u2l1",
            unit_lessons=unit2.lessons,
            all_units=all_units,
            course_manager_ref=mock_course_manager,
        )
        is True
    )

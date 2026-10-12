"""The validator used to reject valid ``pronunciation_practice`` exercises."""

from core.models import Course, Exercise, Lesson, Unit
from tools.course_validator import perform_course_content_validation


def _course_with(exercise):
    lesson = Lesson(lesson_id="u1l1", title="L1", exercises=[exercise])
    unit = Unit(unit_id="unit1", title="U1", lessons=[lesson])
    return Course(
        course_id="c1",
        title="Test",
        target_language="Vietnamese",
        source_language="English",
        version="1.0",
        units=[unit],
    )


def test_pronunciation_practice_is_accepted():
    exercise = Exercise(
        exercise_id="e1",
        type="pronunciation_practice",
        prompt="Say hello",
        target_pronunciation_text="xin chao",
    )
    errors = perform_course_content_validation(_course_with(exercise), "/tmp")
    assert not any("Invalid exercise type" in e for e in errors), errors


def test_pronunciation_practice_requires_target_text():
    exercise = Exercise(
        exercise_id="e1", type="pronunciation_practice", prompt="Say hello"
    )
    errors = perform_course_content_validation(_course_with(exercise), "/tmp")
    assert any("target_pronunciation_text" in e for e in errors), errors


def test_unknown_type_is_rejected():
    exercise = Exercise(exercise_id="e1", type="not_a_real_type")
    errors = perform_course_content_validation(_course_with(exercise), "/tmp")
    assert any("Invalid exercise type" in e for e in errors), errors

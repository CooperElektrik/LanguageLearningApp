"""Tests for CourseValidator expansions (glossary file validation and duplicate ID detection)."""

from application.core.models import Course, Exercise, Lesson, Unit
from application.tools.course_validator import (
    perform_course_content_validation,
    perform_manifest_validation,
)


def test_manifest_validation_catches_missing_glossary(tmp_path):
    manifest_file = tmp_path / "manifest.yaml"
    manifest_data = {
        "course_id": "test_c",
        "course_title": "Test Course",
        "target_language": "Spanish",
        "source_language": "English",
        "content_file": "content.yaml",
        "glossary_file": "nonexistent_glossary.yaml",
    }
    # Create content file so content check passes
    (tmp_path / "content.yaml").write_text("units: []", encoding="utf-8")

    errors = perform_manifest_validation(manifest_data, str(manifest_file))
    assert any("glossary_file" in err for err in errors)


def test_course_content_validation_catches_global_duplicates():
    ex1 = Exercise(exercise_id="dup_ex", type="translate_to_target", prompt="A", answer="B")
    ex2 = Exercise(exercise_id="dup_ex", type="translate_to_target", prompt="C", answer="D")

    lesson1 = Lesson(lesson_id="dup_lesson", title="L1", exercises=[ex1])
    lesson2 = Lesson(lesson_id="dup_lesson", title="L2", exercises=[ex2])

    unit1 = Unit(unit_id="u1", title="U1", lessons=[lesson1])
    unit2 = Unit(unit_id="u2", title="U2", lessons=[lesson2])

    course = Course(
        course_id="c1",
        title="Test",
        target_language="Spanish",
        source_language="English",
        version="1.0",
        units=[unit1, unit2],
    )

    errors = perform_course_content_validation(course, ".")
    assert any("Course-wide duplicate lesson_id" in err for err in errors)
    assert any("Course-wide duplicate exercise_id" in err for err in errors)

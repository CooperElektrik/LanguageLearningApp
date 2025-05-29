import pytest
from application.core.course_manager import CourseManager
from application.core.models import (
    Exercise,
    ExerciseOption,
)


@pytest.fixture
def course_manager_instance(sample_course_obj):
    manager = CourseManager(manifest_dir=".")
    manager.course = sample_course_obj
    manager.target_language = sample_course_obj.target_language
    manager.source_language = sample_course_obj.source_language
    return manager


def test_check_answer_translate_correct(course_manager_instance):
    exercise = Exercise(
        exercise_id="t1", type="translate_to_target", prompt="Hello", answer="Saluton"
    )
    is_correct, feedback = course_manager_instance.check_answer(exercise, "saluton")
    assert is_correct is True
    assert "Saluton" in feedback


def test_check_answer_translate_incorrect(course_manager_instance):
    exercise = Exercise(
        exercise_id="t2", type="translate_to_target", prompt="Goodbye", answer="Adiaŭ"
    )
    is_correct, feedback = course_manager_instance.check_answer(exercise, "Hello")
    assert is_correct is False
    assert "Adiaŭ" in feedback


def test_check_answer_mcq_correct(course_manager_instance):
    options = [
        ExerciseOption(text="Kato", correct=True),
        ExerciseOption(text="Hundo", correct=False),
    ]
    exercise = Exercise(
        exercise_id="m1",
        type="multiple_choice_translation",
        source_word="Cat",
        options=options,
    )
    is_correct, feedback = course_manager_instance.check_answer(exercise, "kato")
    assert is_correct is True
    assert "Kato" in feedback


def test_check_answer_mcq_incorrect(course_manager_instance):
    options = [
        ExerciseOption(text="Kato", correct=True),
        ExerciseOption(text="Hundo", correct=False),
    ]
    exercise = Exercise(
        exercise_id="m2",
        type="multiple_choice_translation",
        source_word="Cat",
        options=options,
    )
    is_correct, feedback = course_manager_instance.check_answer(exercise, "hundo")
    assert is_correct is False
    assert "Kato" in feedback


def test_check_answer_fib_correct(course_manager_instance):
    exercise = Exercise(
        exercise_id="f1",
        type="fill_in_the_blank",
        sentence_template="Mi __BLANK__ feliĉa.",
        correct_option="estas",
        options=[
            ExerciseOption(text="estas"),
            ExerciseOption(text="havas"),
        ],
    )
    is_correct, feedback = course_manager_instance.check_answer(exercise, "estas")
    assert is_correct is True
    assert "estas" in feedback


def test_get_lesson_and_exercise(
    course_manager_instance,
):
    lesson = course_manager_instance.get_lesson("tu1l1")
    assert lesson is not None
    assert lesson.title == "Test Lesson 1.1 (Translation)"

    exercises = course_manager_instance.get_exercises("tu1l1")
    assert len(exercises) == 2

    exercise = course_manager_instance.get_exercise("tu1l1", 0)
    assert exercise is not None
    assert exercise.prompt == "Hello"

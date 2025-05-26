import pytest
from application.core.course_manager import CourseManager
from application.core.models import Exercise, ExerciseOption # For creating mock exercises if needed

# Uses the sample_course_obj fixture from conftest.py
# Need to ensure CourseManager can be initialized with a Course object or path to manifest
# For simplicity, let's assume we test CourseManager after it has loaded a course.

@pytest.fixture
def course_manager_instance(sample_course_obj):
    # CourseManager loads from manifest path. To test its methods with a loaded course,
    # we'd need to point it to a manifest. Or, we can test its methods more directly
    # if we can inject a Course object or mock its loading.
    # For now, let's test `check_answer` with manually created Exercise objects.
    # A full CourseManager test would involve setting up a manifest in tmp_path.
    
    # Simpler: Create a dummy CourseManager and set its course and languages for testing check_answer
    manager = CourseManager(manifest_dir=".") # Dummy manifest_dir, won't load
    manager.course = sample_course_obj # Inject the loaded course
    manager.target_language = sample_course_obj.target_language
    manager.source_language = sample_course_obj.source_language
    return manager

def test_check_answer_translate_correct(course_manager_instance):
    exercise = Exercise(exercise_id="t1", type="translate_to_target", prompt="Hello", answer="Saluton")
    is_correct, feedback = course_manager_instance.check_answer(exercise, "saluton")
    assert is_correct is True
    assert "Saluton" in feedback

def test_check_answer_translate_incorrect(course_manager_instance):
    exercise = Exercise(exercise_id="t2", type="translate_to_target", prompt="Goodbye", answer="Adiaŭ")
    is_correct, feedback = course_manager_instance.check_answer(exercise, "Hello")
    assert is_correct is False
    assert "Adiaŭ" in feedback

def test_check_answer_mcq_correct(course_manager_instance):
    options = [
        ExerciseOption(text="Kato", correct=True),
        ExerciseOption(text="Hundo", correct=False)
    ]
    exercise = Exercise(exercise_id="m1", type="multiple_choice_translation", source_word="Cat", options=options)
    is_correct, feedback = course_manager_instance.check_answer(exercise, "kato") # User answer is text
    assert is_correct is True
    assert "Kato" in feedback

def test_check_answer_mcq_incorrect(course_manager_instance):
    options = [
        ExerciseOption(text="Kato", correct=True),
        ExerciseOption(text="Hundo", correct=False)
    ]
    exercise = Exercise(exercise_id="m2", type="multiple_choice_translation", source_word="Cat", options=options)
    is_correct, feedback = course_manager_instance.check_answer(exercise, "hundo")
    assert is_correct is False
    assert "Kato" in feedback


def test_check_answer_fib_correct(course_manager_instance):
    exercise = Exercise(
        exercise_id="f1", type="fill_in_the_blank",
        sentence_template="Mi __BLANK__ feliĉa.",
        correct_option="estas",
        options=[ExerciseOption(text="estas"), ExerciseOption(text="havas")] # Simplified for test
    )
    is_correct, feedback = course_manager_instance.check_answer(exercise, "estas")
    assert is_correct is True
    assert "estas" in feedback

def test_get_lesson_and_exercise(course_manager_instance): # Uses injected sample_course_obj
    lesson = course_manager_instance.get_lesson("tu1l1")
    assert lesson is not None
    assert lesson.title == "Test Lesson 1.1 (Translation)"
    
    exercises = course_manager_instance.get_exercises("tu1l1")
    assert len(exercises) == 2
    
    exercise = course_manager_instance.get_exercise("tu1l1", 0)
    assert exercise is not None
    assert exercise.prompt == "Hello"
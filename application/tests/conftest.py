import pytest
import os
import yaml
from core.models import Course, Unit, Lesson, Exercise, ExerciseOption, GlossaryEntry
from core.course_manager import CourseManager
from core.progress_manager import ProgressManager

@pytest.fixture
def sample_course_data():
    """Provides a sample in-memory Course object for testing."""
    ex1 = Exercise(exercise_id="u1l1_ex1", type="translate_to_target", prompt="Hello", answer="Xin chào")
    ex2 = Exercise(
        exercise_id="u1l1_ex2",
        type="multiple_choice_translation",
        source_word="cat",
        options=[
            ExerciseOption(text="con chó", correct=False),
            ExerciseOption(text="con mèo", correct=True),
        ]
    )
    ex3 = Exercise(exercise_id="u1l2_ex1", type="sentence_jumble", words=["Tôi", "ăn", "táo"], answer="Tôi ăn táo")
    
    lesson1 = Lesson(lesson_id="u1l1", title="Greetings", exercises=[ex1, ex2])
    lesson2 = Lesson(lesson_id="u1l2", title="Sentences", exercises=[ex3])
    unit1 = Unit(unit_id="unit1", title="Basics", lessons=[lesson1, lesson2])

    course = Course(
        course_id="test_course_v1",
        title="Test Course",
        target_language="Vietnamese",
        source_language="English",
        version="1.0.0",
        units=[unit1]
    )
    return course

@pytest.fixture
def temp_course_files(tmp_path, sample_course_data):
    """Creates temporary YAML files for a course and returns the manifest path."""
    course_dir = tmp_path / "test_course"
    course_dir.mkdir()

    # --- Create manifest.yaml ---
    manifest_data = {
        "course_id": sample_course_data.course_id,
        "course_title": sample_course_data.title,
        "version": sample_course_data.version,
        "target_language": sample_course_data.target_language,
        "source_language": sample_course_data.source_language,
        "content_file": "content.yaml",
        "glossary_file": "glossary.yaml"
    }
    manifest_path = course_dir / "manifest.yaml"
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(manifest_data, f)

    # --- Create content.yaml ---
    content_data = sample_course_data.to_dict()
    content_path = course_dir / "content.yaml"
    with open(content_path, "w", encoding="utf-8") as f:
        yaml.dump(content_data, f)
        
    # --- Create glossary.yaml ---
    glossary_data = [
        {"word": "Xin chào", "translation": "Hello"},
        {"word": "Cảm ơn", "translation": "Thank you"},
    ]
    glossary_path = course_dir / "glossary.yaml"
    with open(glossary_path, "w", encoding="utf-8") as f:
        yaml.dump(glossary_data, f)

    return str(manifest_path)

@pytest.fixture
def course_manager(temp_course_files):
    """Provides an initialized CourseManager instance."""
    return CourseManager(manifest_path=temp_course_files)

@pytest.fixture
def progress_manager(course_manager, tmp_path):
    """Provides an initialized ProgressManager instance in a temporary directory."""
    # Point QStandardPaths to our temp dir for this test
    os.environ['XDG_DATA_HOME'] = str(tmp_path)
    return ProgressManager(course_id=course_manager.course.course_id)
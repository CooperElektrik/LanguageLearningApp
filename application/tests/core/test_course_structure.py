import os
import yaml
from core import course_loader, glossary_loader, yaml_serializer
from core.models import Course, GlossaryEntry

def test_load_manifest_success(temp_course_files):
    """Tests that a valid manifest file is loaded correctly."""
    manifest_data = course_loader.load_manifest(temp_course_files)
    assert manifest_data is not None
    assert manifest_data["course_id"] == "test_course_v1"
    assert manifest_data["course_title"] == "Test Course"

def test_load_manifest_not_found():
    """Tests that loading a non-existent manifest returns None."""
    manifest_data = course_loader.load_manifest("non_existent_file.yaml")
    assert manifest_data is None

def test_load_course_content_success(temp_course_files):
    """Tests that a valid course content file is parsed into model objects."""
    manifest_data = course_loader.load_manifest(temp_course_files)
    content_path = os.path.join(os.path.dirname(temp_course_files), manifest_data["content_file"])
    
    course = course_loader.load_course_content(
        content_filepath=content_path,
        course_id=manifest_data["course_id"],
        course_title=manifest_data["course_title"],
        target_lang=manifest_data["target_language"],
        source_lang=manifest_data["source_language"],
        version=manifest_data["version"]
    )
    
    assert isinstance(course, Course)
    assert len(course.units) == 1
    assert course.units[0].title == "Basics"
    assert len(course.units[0].lessons) == 2
    assert len(course.units[0].lessons[0].exercises) == 2
    assert course.units[0].lessons[0].exercises[0].type == "translate_to_target"

def test_load_glossary_success(temp_course_files):
    """Tests loading a valid glossary file."""
    manifest_data = course_loader.load_manifest(temp_course_files)
    glossary_path = os.path.join(os.path.dirname(temp_course_files), manifest_data["glossary_file"])
    
    glossary = glossary_loader.load_glossary(glossary_path)
    assert len(glossary) == 2
    assert isinstance(glossary[0], GlossaryEntry)
    assert glossary[0].word == "Xin chào"

def test_round_trip_serialization(sample_course_data, tmp_path):
    """Tests that saving a course and reloading it results in the same structure."""
    save_path = tmp_path / "round_trip_course.yaml"
    
    # Save the course object to YAML
    assert yaml_serializer.save_course_to_yaml(sample_course_data, str(save_path))
    
    # Reload it
    with open(save_path, 'r', encoding='utf-8') as f:
        reloaded_data = yaml.safe_load(f)
        
    # Basic structural assertions
    assert "units" in reloaded_data
    assert len(reloaded_data["units"]) == len(sample_course_data.units)
    assert reloaded_data["units"][0]["title"] == sample_course_data.units[0].title
    assert len(reloaded_data["units"][0]["lessons"][0]["exercises"]) == 2
    assert reloaded_data["units"][0]["lessons"][0]["exercises"][0]["type"] == "translate_to_target"
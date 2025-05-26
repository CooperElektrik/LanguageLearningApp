import pytest
import os
from application.core.course_loader import load_manifest, load_course_content

def test_load_valid_manifest(valid_manifest_path):
    manifest_data = load_manifest(valid_manifest_path)
    assert manifest_data is not None
    assert manifest_data["course_id"] == "test_course_001"
    assert manifest_data["content_file"] == "test_course_valid.yaml"

def test_load_invalid_manifest_structure(invalid_manifest_path, caplog):
    # caplog is a pytest fixture to capture log output
    manifest_data = load_manifest(invalid_manifest_path)
    # The loader itself handles logging errors, it might return None or a partially filled dict
    # Depending on strictness, we might expect None or check logs
    # Our current loader logs an error and returns None if parsing fails or essential fields are missing.
    # Here, it's syntactically valid YAML but missing fields; our loader might not catch this as an error
    # if we are only checking YAML syntax. The validator would catch missing fields.
    # Let's assume the loader is for syntax and basic structure.
    # The provided invalid_manifest.yaml will load as a dict.
    assert manifest_data is not None
    assert "course_id" not in manifest_data # Example check

def test_load_nonexistent_manifest(tmp_path, caplog):
    non_existent_path = os.path.join(tmp_path, "does_not_exist.yaml")
    manifest_data = load_manifest(non_existent_path)
    assert manifest_data is None
    assert f"Manifest file not found: {non_existent_path}" in caplog.text

def test_load_valid_course_content(valid_manifest_path, valid_course_content_path):
    # This test implicitly uses the valid_manifest_path to get details for course obj
    manifest_data = load_manifest(valid_manifest_path)
    assert manifest_data is not None
    
    course = load_course_content(
        content_filepath=valid_course_content_path, # Ensure this path is correct relative to manifest
        course_id=manifest_data["course_id"],
        course_title=manifest_data["course_title"],
        target_lang=manifest_data["target_language"],
        source_lang=manifest_data["source_language"],
        version=manifest_data["version"]
    )
    assert course is not None
    assert course.course_id == "test_course_001"
    assert len(course.units) == 2
    assert course.units[0].title == "Test Unit 1"
    assert len(course.units[0].lessons[0].exercises) > 0

def test_load_invalid_course_content_structure(invalid_course_content_path, caplog):
    # For this test, we need some minimal manifest data
    # Even if the content file itself is bad.
    course = load_course_content(
        content_filepath=invalid_course_content_path,
        course_id="test_bad", course_title="Test Bad",
        target_lang="tl", source_lang="sl", version="1"
    )
    assert course is None # Expecting None because 'units' key is missing
    assert "is empty or 'units' key is missing" in caplog.text # Check for specific log message
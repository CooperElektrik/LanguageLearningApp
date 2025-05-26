# Updated tests/conftest.py (with sys.path modification at the top)

import sys
import os
import uuid

from application.core.progress_manager import ProgressManager

# Ensure the project root (parent of 'application', 'tools', 'tests') is on sys.path
# This allows imports like 'from application.core...' from test files and conftest.py itself.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    # print(f"[DEBUG conftest.py] Added to sys.path: {project_root}") # For debugging

import pytest # Now import pytest and other modules
import yaml
import shutil
from typing import Dict, Any

from application.core.models import Course, Unit, Lesson, Exercise, ExerciseOption
from application.core.course_loader import load_manifest as app_load_manifest
from application.core.course_loader import load_course_content as app_load_course_content

# ... (rest of the fixtures as previously defined) ...
@pytest.fixture
def tests_data_dir():
    """Returns the path to the tests/data directory."""
    return os.path.join(os.path.dirname(__file__), "data")

@pytest.fixture
def valid_manifest_path(tests_data_dir):
    return os.path.join(tests_data_dir, "test_manifest_valid.yaml")

@pytest.fixture
def valid_course_content_path(tests_data_dir):
    return os.path.join(tests_data_dir, "test_course_valid.yaml")
    
@pytest.fixture
def invalid_manifest_path(tests_data_dir):
    return os.path.join(tests_data_dir, "test_manifest_invalid.yaml")

@pytest.fixture
def invalid_course_content_path(tests_data_dir):
    return os.path.join(tests_data_dir, "test_course_invalid_structure.yaml")

@pytest.fixture
def sample_course_obj(valid_manifest_path) -> Course:
    """Loads a valid sample Course object for testing."""
    manifest_data = app_load_manifest(valid_manifest_path)
    assert manifest_data is not None
    # Assuming content_file is relative to the manifest's directory for this test fixture
    content_filepath = os.path.join(os.path.dirname(valid_manifest_path), manifest_data["content_file"])
    
    course = app_load_course_content(
        content_filepath=content_filepath,
        course_id=manifest_data["course_id"],
        course_title=manifest_data["course_title"],
        target_lang=manifest_data["target_language"],
        source_lang=manifest_data["source_language"],
        version=manifest_data["version"],
        author=manifest_data.get("author"),
        description=manifest_data.get("description")
    )
    assert course is not None
    return course

@pytest.fixture
def progress_manager_instance(tmp_path):
    course_id = f"test_course_{uuid.uuid4().hex}"
    pm_data_dir = tmp_path / "pm_test_data_dir" 
    return ProgressManager(course_id=course_id, data_dir=str(pm_data_dir))
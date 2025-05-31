import pytest
import os
import shutil
import yaml
from application.core.glossary_loader import load_glossary
from application.core.models import GlossaryEntry
from application.core.course_manager import CourseManager
from application.core import yaml_serializer


@pytest.fixture
def valid_glossary_path(tests_data_dir):
    return os.path.join(tests_data_dir, "glossary_valid.yaml")

@pytest.fixture
def empty_glossary_path(tmp_path):
    # Create an empty YAML file for testing purposes
    empty_file = tmp_path / "empty_glossary.yaml"
    empty_file.touch()
    return str(empty_file)

@pytest.fixture
def malformed_glossary_path(tmp_path):
    malformed_content = """
- word: Valid Entry
  translation: Valid Translation
- Invalid Entry: No list structure
"""
    malformed_file = tmp_path / "malformed_glossary.yaml"
    malformed_file.write_text(malformed_content)
    return str(malformed_file)


def test_load_valid_glossary(valid_glossary_path):
    glossary = load_glossary(valid_glossary_path)
    assert isinstance(glossary, list)
    assert len(glossary) == 3
    assert all(isinstance(entry, GlossaryEntry) for entry in glossary)
    
    entry1 = glossary[0]
    assert entry1.word == "Saluton"
    assert entry1.translation == "Hello"
    assert entry1.part_of_speech == "interj."
    assert entry1.example_sentence == "Saluton, kiel vi fartas?"
    assert entry1.audio_file == "assets/audio/saluton.mp3"

    entry2 = glossary[1]
    assert entry2.word == "Hundo"
    assert entry2.translation == "Dog"
    assert entry2.example_sentence == "Mi havas grandan hundon."
    assert entry2.part_of_speech == "n." # Check optional field

def test_load_nonexistent_glossary(tmp_path):
    non_existent_path = os.path.join(tmp_path, "non_existent_glossary.yaml")
    glossary = load_glossary(non_existent_path)
    assert isinstance(glossary, list)
    assert len(glossary) == 0

def test_load_empty_glossary_file(empty_glossary_path):
    glossary = load_glossary(empty_glossary_path)
    assert isinstance(glossary, list)
    assert len(glossary) == 0

def test_load_malformed_glossary_structure(malformed_glossary_path):
    glossary = load_glossary(malformed_glossary_path)
    assert isinstance(glossary, list)
    # It should still parse valid entries and skip malformed ones, so length should be 1
    assert len(glossary) == 1 
    assert glossary[0].word == "Valid Entry"


def test_course_manager_loads_glossary(manifest_with_glossary_and_content):
    # Re-initialize CourseManager to ensure manifest is read fresh from temp path
    cm = CourseManager(manifest_path=manifest_with_glossary_and_content)
    
    assert cm.course is not None
    assert cm.get_glossary_entries() is not None
    assert len(cm.get_glossary_entries()) > 0
    assert cm.get_glossary_entries()[0].word == "Saluton"

def test_course_manager_loads_no_glossary_if_not_specified(tmp_path):
    # Create a manifest without a glossary_file entry
    manifest_content = """
course_id: no_glossary_course
course_title: No Glossary Course
target_language: Test
source_language: English
content_file: dummy_content.yaml
version: 1.0
"""
    manifest_path = tmp_path / "manifest_no_glossary.yaml"
    manifest_path.write_text(manifest_content)
    dummy_content_path = tmp_path / "dummy_content.yaml"
    dummy_content_path.write_text("units: []")
    
    cm = CourseManager(manifest_path=str(manifest_path))
    
    assert cm.course is not None
    assert len(cm.get_glossary_entries()) == 0

@pytest.fixture
def manifest_with_glossary_and_content(tmp_path, tests_data_dir):
    # Copy valid manifest and content to tmp_path for isolation
    valid_manifest_src = os.path.join(tests_data_dir, "test_manifest_valid.yaml")
    valid_content_src = os.path.join(tests_data_dir, "test_course_valid.yaml")
    valid_glossary_src = os.path.join(tests_data_dir, "glossary_valid.yaml") # Ensure this is in tests/data

    # Rename test_manifest_valid.yaml to manifest.yaml to match default expectations or CourseManager direct path
    manifest_target_path = tmp_path / "test_manifest_valid.yaml" # Keep original name for clarity in test
    content_target_path = tmp_path / "test_course_valid.yaml"
    glossary_target_path = tmp_path / "glossary_valid.yaml"

    shutil.copy(valid_manifest_src, manifest_target_path)
    shutil.copy(valid_content_src, content_target_path)
    shutil.copy(valid_glossary_src, glossary_target_path)

    # Return the path to the copied manifest
    return str(manifest_target_path)

def test_save_glossary_to_yaml(tmp_path):
    """Test saving a list of GlossaryEntry objects to a YAML file."""
    output_filepath = tmp_path / "saved_glossary.yaml"
    
    entries_to_save = [
        GlossaryEntry(word="TestWord1", translation="TestTranslation1", part_of_speech="n."),
        GlossaryEntry(word="TestWord2", translation="TestTranslation2", example_sentence="Example."),
    ]

    success = yaml_serializer.save_glossary_to_yaml(entries_to_save, str(output_filepath))
    assert success is True
    assert os.path.exists(output_filepath)

    # Load and verify content
    with open(output_filepath, "r", encoding="utf-8") as f:
        loaded_data = yaml.safe_load(f)

    assert isinstance(loaded_data, list)
    assert len(loaded_data) == 2
    assert loaded_data[0]["word"] == "TestWord1"
    assert loaded_data[1]["translation"] == "TestTranslation2"
    assert "part_of_speech" in loaded_data[0]
    assert "example_sentence" in loaded_data[1]
    assert "notes" not in loaded_data[0] # Verify None fields are not saved
import yaml
import logging
from typing import Dict, Any, List
from .models import Course, Unit, Lesson, Exercise, ExerciseOption, GlossaryEntry

logger = logging.getLogger(__name__)


def course_to_yaml_data(course: Course) -> Dict[str, Any]:
    """
    Converts a Course object hierarchy into a dictionary structure suitable for
    dumping as the main course content YAML file.
    Delegates serialization to the models' to_dict() and to_content_dict() methods.
    """
    # The Course model's to_dict() method is designed to return the top-level
    # dictionary structure for the content file (e.g., {"units": [...]}).
    return course.to_dict()


def manifest_to_yaml_data(manifest_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns the manifest data as is, suitable for YAML dumping.
    This function simply passes through the dictionary data.
    """
    return manifest_data


def save_course_to_yaml(course: Course, filepath: str):
    """Saves a Course object to a YAML file."""
    logger.info(f"Attempting to save course content to {filepath}")
    try:
        yaml_data = course_to_yaml_data(course)
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_data, f, indent=2, sort_keys=False, allow_unicode=True)
        logger.info(f"Course content saved successfully to {filepath}")
        return True
    except IOError as e:
        logger.error(f"Error writing course content file {filepath}: {e}")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while saving course content {filepath}: {e}"
        )
    return False


def save_manifest_to_yaml(manifest_data: Dict[str, Any], filepath: str):
    """Saves manifest data to a YAML file."""
    logger.info(f"Attempting to save manifest to {filepath}")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                manifest_data, f, indent=2, sort_keys=False, allow_unicode=True
            )
        logger.info(f"Manifest saved successfully to {filepath}")
        return True
    except IOError as e:
        logger.error(f"Error writing manifest file {filepath}: {e}")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while saving manifest {filepath}: {e}"
        )
    return False


def save_glossary_to_yaml(glossary_entries: List[GlossaryEntry], filepath: str):
    """Saves a list of GlossaryEntry objects to a YAML file."""
    glossary_data_to_save = [entry.to_dict() for entry in glossary_entries]
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                glossary_data_to_save, f, indent=2, sort_keys=False, allow_unicode=True
            )
        logger.info(f"Glossary saved successfully to {filepath}")
        return True
    except IOError as e:
        logger.error(f"Error writing glossary file {filepath}: {e}")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while saving glossary {filepath}: {e}"
        )
    return False

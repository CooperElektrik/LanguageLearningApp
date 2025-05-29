import yaml
import os
import logging
from typing import Dict, Any, Optional, Tuple
import uuid

try:
    from core.models import Course, Unit, Lesson, Exercise, ExerciseOption
except ImportError:
    logging.warning(
        "Could not import models directly. Ensure application/core is on sys.path for standalone testing."
    )

    class Course:
        pass

    class Unit:
        pass

    class Lesson:
        pass

    class Exercise:
        pass

    class ExerciseOption:
        pass


logger = logging.getLogger(__name__)


def load_manifest(manifest_path: str) -> Optional[Dict[str, Any]]:
    """Loads the course manifest YAML file."""
    if not os.path.exists(manifest_path):
        logger.info(f"Manifest file not found at {manifest_path}.")
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f)
        logger.info(f"Manifest loaded successfully from {manifest_path}")
        return manifest_data
    except yaml.YAMLError as e:
        logger.error(f"Error parsing manifest YAML file {manifest_path}: {e}")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while loading manifest {manifest_path}: {e}"
        )
    return None


def save_manifest(manifest_data: Dict[str, Any], manifest_path: str):
    """Saves the course manifest YAML file."""
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(manifest_data, f, indent=2, sort_keys=False)
        logger.info(f"Manifest saved successfully to {manifest_path}")
        return True
    except IOError as e:
        logger.error(f"Error writing manifest file {manifest_path}: {e}")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while saving manifest {manifest_path}: {e}"
        )
    return False


def _parse_exercise_data_to_model(
    ex_data: Dict[str, Any], lesson_id: str, index: int
) -> Exercise:
    """Helper to parse raw exercise dict to Exercise model."""
    options_list = []
    if "options" in ex_data and isinstance(ex_data["options"], list):
        for opt_data in ex_data["options"]:
            if isinstance(opt_data, dict):
                options_list.append(
                    ExerciseOption(
                        text=opt_data["text"], correct=opt_data.get("correct", False)
                    )
                )
            elif isinstance(opt_data, str):
                options_list.append(
                    ExerciseOption(
                        text=opt_data,
                        correct=(opt_data == ex_data.get("correct_option")),
                    )
                )

    return Exercise(
        exercise_id=f"{lesson_id}_ex{index}_{uuid.uuid4().hex[:4]}",
        type=ex_data.get("type", "unknown"),
        prompt=ex_data.get("prompt"),
        answer=ex_data.get("answer"),
        source_word=ex_data.get("source_word"),
        options=options_list,
        sentence_template=ex_data.get("sentence_template"),
        correct_option=ex_data.get("correct_option"),
        translation_hint=ex_data.get("translation_hint"),
        raw_data=ex_data,
    )


def load_course_content_from_yaml(
    content_filepath: str, manifest_data: Dict[str, Any]
) -> Optional[Course]:
    """Loads and parses the course content YAML file into a Course object."""
    if not os.path.exists(content_filepath):
        logger.info(f"Course content file not found at {content_filepath}.")
        return None
    try:
        with open(content_filepath, "r", encoding="utf-8") as f:
            raw_course_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing course content YAML file {content_filepath}: {e}")
        return None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred loading course content {content_filepath}: {e}"
        )
        return None

    if not raw_course_data or "units" not in raw_course_data:
        logger.error(
            f"Course content file {content_filepath} is empty or 'units' key is missing."
        )
        return None

    course = Course(
        course_id=manifest_data.get("course_id", str(uuid.uuid4())),
        title=manifest_data.get("course_title", "New Course"),
        target_language=manifest_data.get("target_language", "Target Language"),
        source_language=manifest_data.get("source_language", "Source Language"),
        version=manifest_data.get("version", "1.0.0"),
        author=manifest_data.get("author"),
        description=manifest_data.get("description"),
        content_file=os.path.basename(content_filepath),
    )

    for unit_data in raw_course_data.get("units", []):
        unit_obj = Unit(
            unit_id=unit_data.get("unit_id", str(uuid.uuid4())),
            title=unit_data.get("title", ""),
        )
        for lesson_data in unit_data.get("lessons", []):
            lesson_obj = Lesson(
                lesson_id=lesson_data.get("lesson_id", str(uuid.uuid4())),
                title=lesson_data.get("title", ""),
                unit_id=unit_obj.unit_id,
            )
            for i, ex_data in enumerate(lesson_data.get("exercises", [])):
                exercise_obj = _parse_exercise_data_to_model(
                    ex_data, lesson_obj.lesson_id, i
                )
                lesson_obj.exercises.append(exercise_obj)
            unit_obj.lessons.append(lesson_obj)
        course.units.append(unit_obj)

    logger.info(f"Course content for '{course.title}' loaded successfully.")
    return course


def save_course_content_to_yaml(course: Course, content_filepath: str):
    """Saves the Course object back to a YAML file."""
    try:
        course_data_to_save = course.to_dict()
        with open(content_filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(course_data_to_save, f, indent=2, sort_keys=False)
        logger.info(f"Course content saved successfully to {content_filepath}")
        return True
    except IOError as e:
        logger.error(f"Error writing course content file {content_filepath}: {e}")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while saving course content {content_filepath}: {e}"
        )
    return False


def create_new_course() -> Tuple[Dict[str, Any], Course]:
    """Creates a new empty course manifest and content object."""
    new_course_id = str(uuid.uuid4())
    new_content_filename = f"course_{new_course_id[:8]}.yaml"

    manifest = {
        "course_id": new_course_id,
        "course_title": "New LL Course",
        "target_language": "Target Language",
        "source_language": "Source Language",
        "content_file": new_content_filename,
        "version": "1.0.0",
        "author": "New Author",
        "description": "A newly created language course.",
    }

    course_obj = Course(
        course_id=new_course_id,
        title="New LL Course",
        target_language="Target Language",
        source_language="Source Language",
        version="1.0.0",
        author="New Author",
        description="A newly created language course.",
        content_file=new_content_filename,
        units=[],
    )
    return manifest, course_obj

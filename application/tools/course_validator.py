import sys
import os
import argparse
import logging
import yaml
from typing import List, Dict, Any, Optional

current_script_dir = os.path.dirname(os.path.abspath(__file__))
application_root_dir = os.path.abspath(os.path.join(current_script_dir, ".."))

if application_root_dir not in sys.path:
    sys.path.insert(0, application_root_dir)

try:
    from core.models import Course, Unit, Lesson, Exercise, ExerciseOption
    from core.course_loader import load_manifest as app_load_manifest
    from core.course_loader import load_course_content as app_load_course_content
except ImportError as e:
    print(f"CRITICAL: course_validator.py - Cannot import core modules: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _collect_error(errors_list: List[str], message: str, path_prefix: str = ""):
    """Collects an error message with a path prefix."""
    full_message = f"{path_prefix}{message}" if path_prefix else message
    errors_list.append(full_message)


def _validate_exercise_translation_internal(
    exercise: Exercise, path_prefix: str, errors_list: List[str]
):
    if (
        not exercise.prompt
        or not isinstance(exercise.prompt, str)
        or not exercise.prompt.strip()
    ):
        _collect_error(
            errors_list, "Missing or empty 'prompt' (must be a string).", path_prefix
        )
    if (
        not exercise.answer
        or not isinstance(exercise.answer, str)
        or not exercise.answer.strip()
    ):
        _collect_error(
            errors_list, "Missing or empty 'answer' (must be a string).", path_prefix
        )


def _validate_exercise_mcq_internal(
    exercise: Exercise, path_prefix: str, errors_list: List[str]
):
    if (
        not exercise.source_word
        or not isinstance(exercise.source_word, str)
        or not exercise.source_word.strip()
    ):
        _collect_error(
            errors_list,
            "Missing or empty 'source_word' (must be a string).",
            path_prefix,
        )

    if (
        not exercise.options
        or not isinstance(exercise.options, list)
        or len(exercise.options) == 0
    ):
        _collect_error(
            errors_list, "Missing, empty, or invalid 'options' list.", path_prefix
        )
        return

    correct_count = 0
    for i, option in enumerate(exercise.options):
        option_path = f"{path_prefix}Option #{i+1} ('{option.text[:20] if hasattr(option, 'text') else 'N/A'}...'): "
        if (
            not hasattr(option, "text")
            or not isinstance(option.text, str)
            or not option.text.strip()
        ):
            _collect_error(
                errors_list, "Missing or empty 'text' for option.", option_path
            )
        if not hasattr(option, "correct") or not isinstance(option.correct, bool):
            _collect_error(
                errors_list,
                "Missing or invalid 'correct' flag (must be boolean) for option.",
                option_path,
            )
        if hasattr(option, "correct") and option.correct:
            correct_count += 1

    if correct_count == 0:
        _collect_error(errors_list, "No option marked as correct.", path_prefix)
    elif correct_count > 1:
        _collect_error(
            errors_list,
            f"Multiple options ({correct_count}) marked as correct. Only one should be.",
            path_prefix,
        )


def _validate_exercise_fib_internal(
    exercise: Exercise, path_prefix: str, errors_list: List[str]
):
    if (
        not exercise.sentence_template
        or not isinstance(exercise.sentence_template, str)
        or not exercise.sentence_template.strip()
    ):
        _collect_error(
            errors_list,
            "Missing or empty 'sentence_template' (must be a string).",
            path_prefix,
        )
    elif "__BLANK__" not in exercise.sentence_template:
        _collect_error(
            errors_list,
            "Warning: 'sentence_template' does not contain '__BLANK__' placeholder (recommended).",
            path_prefix,
        )

    if (
        not exercise.correct_option
        or not isinstance(exercise.correct_option, str)
        or not exercise.correct_option.strip()
    ):
        _collect_error(
            errors_list,
            "Missing or empty 'correct_option' (must be a string).",
            path_prefix,
        )

    if (
        not exercise.options
        or not isinstance(exercise.options, list)
        or len(exercise.options) == 0
    ):
        _collect_error(
            errors_list,
            "Missing, empty, or invalid 'options' list for blank choices.",
            path_prefix,
        )
        return

    option_texts = [
        opt.text
        for opt in exercise.options
        if hasattr(opt, "text") and opt.text.strip()
    ]
    if (
        exercise.correct_option
        and exercise.correct_option.strip()
        and exercise.correct_option.strip() not in option_texts
    ):
        _collect_error(
            errors_list,
            f"'correct_option' ('{exercise.correct_option}') not found in the provided 'options' list texts.",
            path_prefix,
        )

    if (
        not exercise.translation_hint
        or not isinstance(exercise.translation_hint, str)
        or not exercise.translation_hint.strip()
    ):
        _collect_error(
            errors_list,
            "Missing or empty 'translation_hint' (must be a string).",
            path_prefix,
        )


def _validate_exercise_internal(
    exercise: Exercise,
    index: int,
    lesson_path_prefix: str,
    errors_list: List[str],
    course_manifest_base_dir: str,
):
    """Validates a single exercise."""
    path_prefix = f"{lesson_path_prefix}Exercise #{index+1} (Type: {exercise.type if hasattr(exercise, 'type') else 'N/A'}): "

    if (
        not hasattr(exercise, "type")
        or not isinstance(exercise.type, str)
        or not exercise.type.strip()
    ):
        _collect_error(errors_list, "Missing or empty 'type' field.", path_prefix)
        return

    if hasattr(exercise, "audio_file") and exercise.audio_file:
        if not isinstance(exercise.audio_file, str):
            _collect_error(
                errors_list, "'audio_file' field must be a string path.", path_prefix
            )
        else:
            full_audio_path = os.path.join(
                course_manifest_base_dir, exercise.audio_file
            )
            if not os.path.exists(full_audio_path):
                _collect_error(
                    errors_list,
                    f"Audio file '{exercise.audio_file}' not found at resolved path '{full_audio_path}'.",
                    path_prefix,
                )

    if hasattr(exercise, "image_file") and exercise.image_file:
        if not isinstance(exercise.image_file, str):
            _collect_error(
                errors_list, "'image_file' field must be a string path.", path_prefix
            )
        else:
            full_image_path = os.path.join(
                course_manifest_base_dir, exercise.image_file
            )
            if not os.path.exists(full_image_path):
                _collect_error(
                    errors_list,
                    f"Image file '{exercise.image_file}' not found at resolved path '{full_image_path}'.",
                    path_prefix,
                )

    valid_types = [
        "translate_to_target",
        "translate_to_source",
        "multiple_choice_translation",
        "fill_in_the_blank",
    ]
    if exercise.type not in valid_types:
        _collect_error(
            errors_list,
            f"Invalid exercise type '{exercise.type}'. Must be one of {valid_types}.",
            path_prefix,
        )
        return

    if exercise.type in ["translate_to_target", "translate_to_source"]:
        _validate_exercise_translation_internal(exercise, path_prefix, errors_list)
    elif exercise.type == "multiple_choice_translation":
        _validate_exercise_mcq_internal(exercise, path_prefix, errors_list)
    elif exercise.type == "fill_in_the_blank":
        _validate_exercise_fib_internal(exercise, path_prefix, errors_list)


def _validate_lesson_internal(
    lesson: Lesson,
    unit_path_prefix: str,
    errors_list: List[str],
    course_manifest_base_dir: str,
):
    """Validates a single lesson."""
    path_prefix = f"{unit_path_prefix}Lesson '{lesson.lesson_id}' ('{lesson.title}'): "
    if (
        not hasattr(lesson, "lesson_id")
        or not isinstance(lesson.lesson_id, str)
        or not lesson.lesson_id.strip()
    ):
        _collect_error(errors_list, "Missing or empty 'lesson_id'.", path_prefix)
    if (
        not hasattr(lesson, "title")
        or not isinstance(lesson.title, str)
        or not lesson.title.strip()
    ):
        _collect_error(errors_list, "Missing or empty 'title'.", path_prefix)

    if not hasattr(lesson, "exercises") or not isinstance(lesson.exercises, list):
        _collect_error(errors_list, "Missing or invalid 'exercises' list.", path_prefix)
        return

    if not lesson.exercises:
        _collect_error(errors_list, "Warning: Contains no exercises.", path_prefix)

    for i, exercise in enumerate(lesson.exercises):
        _validate_exercise_internal(
            exercise, i, path_prefix, errors_list, course_manifest_base_dir
        )


def _validate_unit_internal(
    unit: Unit,
    course_path_prefix: str,
    errors_list: List[str],
    course_manifest_base_dir: str,
):
    """Validates a single unit."""
    path_prefix = f"{course_path_prefix}Unit '{unit.unit_id}' ('{unit.title}'): "
    if (
        not hasattr(unit, "unit_id")
        or not isinstance(unit.unit_id, str)
        or not unit.unit_id.strip()
    ):
        _collect_error(errors_list, "Missing or empty 'unit_id'.", path_prefix)
    if (
        not hasattr(unit, "title")
        or not isinstance(unit.title, str)
        or not unit.title.strip()
    ):
        _collect_error(errors_list, "Missing or empty 'title'.", path_prefix)

    if not hasattr(unit, "lessons") or not isinstance(unit.lessons, list):
        _collect_error(errors_list, "Missing or invalid 'lessons' list.", path_prefix)
        return

    if not unit.lessons:
        _collect_error(errors_list, "Warning: Contains no lessons.", path_prefix)

    lesson_ids_in_unit = set()
    for lesson in unit.lessons:
        if not hasattr(lesson, "lesson_id") or not isinstance(lesson.lesson_id, str):
            _collect_error(
                errors_list,
                "Lesson has invalid or missing lesson_id, cannot check for duplicates.",
                path_prefix,
            )
        elif lesson.lesson_id in lesson_ids_in_unit:
            _collect_error(
                errors_list,
                f"Duplicate lesson_id '{lesson.lesson_id}' found within this unit.",
                path_prefix,
            )
        lesson_ids_in_unit.add(lesson.lesson_id)
        _validate_lesson_internal(
            lesson, path_prefix, errors_list, course_manifest_base_dir
        )


def perform_manifest_validation(
    manifest_data: Dict[str, Any], manifest_path: str
) -> List[str]:
    """Validates the loaded manifest data, returning a list of errors."""
    errors = []
    required_fields = [
        "course_id",
        "course_title",
        "target_language",
        "source_language",
        "content_file",
    ]
    for field in required_fields:
        if (
            field not in manifest_data
            or not manifest_data[field]
            or (
                isinstance(manifest_data[field], str)
                and not manifest_data[field].strip()
            )
        ):
            _collect_error(
                errors, f"Manifest missing or empty required field: '{field}'"
            )

    if "content_file" in manifest_data and manifest_data["content_file"]:
        content_filepath = os.path.join(
            os.path.dirname(manifest_path), manifest_data["content_file"]
        )
        if not os.path.exists(content_filepath):
            _collect_error(
                errors,
                f"Manifest 'content_file' points to a non-existent file: '{content_filepath}' (relative to manifest location)",
            )
    return errors


def perform_course_content_validation(
    course: Course, course_manifest_base_dir: str
) -> List[str]:
    """Validates the main course content object, returning a list of errors."""
    errors = []
    path_prefix = f"Course '{course.title}': "

    if not course or not hasattr(course, "units") or not isinstance(course.units, list):
        _collect_error(
            errors, "Course object is invalid or has no 'units' list.", path_prefix
        )
        return errors

    if not course.units:
        _collect_error(errors, "Warning: Course contains no units.", path_prefix)

    unit_ids_in_course = set()
    for unit in course.units:
        if not hasattr(unit, "unit_id") or not isinstance(unit.unit_id, str):
            _collect_error(
                errors,
                "Unit has invalid or missing unit_id, cannot check for duplicates.",
                path_prefix,
            )
        elif unit.unit_id in unit_ids_in_course:
            _collect_error(
                errors,
                f"Duplicate unit_id '{unit.unit_id}' found within the course.",
                path_prefix,
            )
        unit_ids_in_course.add(unit.unit_id)
        _validate_unit_internal(unit, path_prefix, errors, course_manifest_base_dir)

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate LL course content YAML files."
    )
    parser.add_argument(
        "manifest_file", help="Path to the manifest.yaml file for the course."
    )
    args = parser.parse_args()

    current_errors: List[str] = []

    logger.info(f"Starting validation for manifest: {args.manifest_file}")

    if not os.path.exists(args.manifest_file):
        logger.error(f"Manifest file not found: {args.manifest_file}")
        sys.exit(1)

    manifest_data = app_load_manifest(args.manifest_file)
    if not manifest_data:
        _collect_error(
            current_errors,
            "Failed to load or parse manifest. See previous logs for details.",
            "",
        )
    else:
        manifest_validation_errors = perform_manifest_validation(
            manifest_data, args.manifest_file
        )
        current_errors.extend(manifest_validation_errors)

    course_obj: Optional[Course] = None
    course_content_actual_base_dir = None

    if (
        manifest_data
        and "content_file" in manifest_data
        and manifest_data["content_file"]
    ):
        manifest_dir = os.path.dirname(os.path.abspath(args.manifest_file))
        content_filename = manifest_data["content_file"]
        content_filepath = os.path.join(manifest_dir, manifest_data["content_file"])
        course_content_actual_base_dir = os.path.dirname(content_filepath)

        if os.path.exists(content_filepath):
            course_obj = app_load_course_content(
                content_filepath=content_filepath,
                course_id=manifest_data.get("course_id", "unknown"),
                course_title=manifest_data.get("course_title", "unknown"),
                target_lang=manifest_data.get("target_language", "unknown"),
                source_lang=manifest_data.get("source_language", "unknown"),
                version=manifest_data.get("version", "unknown"),
                author=manifest_data.get("author"),
                description=manifest_data.get("description"),
            )
            if course_obj and course_content_actual_base_dir:
                content_validation_errors = perform_course_content_validation(
                    course_obj, course_content_actual_base_dir
                )
                current_errors.extend(content_validation_errors)
            if not course_obj:
                _collect_error(
                    current_errors,
                    f"Failed to load or parse course content file: {content_filepath}. See previous logs.",
                    "",
                )
            else:
                content_validation_errors = perform_course_content_validation(
                    course_obj, course_content_actual_base_dir
                )
                current_errors.extend(content_validation_errors)
        else:
            pass
    elif manifest_data:
        _collect_error(
            current_errors,
            "Manifest is missing 'content_file' or it is empty; cannot validate course content.",
            "",
        )

    if not current_errors:
        logger.info("---------------------------------------------")
        logger.info("Validation PASSED. No errors found.")
        logger.info("---------------------------------------------")
        sys.exit(0)
    else:
        logger.info("---------------------------------------------")
        logger.error(f"Validation FAILED. Found {len(current_errors)} error(s):")
        for i, err in enumerate(current_errors):
            logger.error(f"  {i+1}. {err}")
        logger.info("---------------------------------------------")
        sys.exit(1)


if __name__ == "__main__":
    main()

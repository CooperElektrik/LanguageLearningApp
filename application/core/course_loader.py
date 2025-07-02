import yaml
import os
import logging
import random
from typing import Dict, Any, Optional, List

from .models import Course, Unit, Lesson, Exercise, ExerciseOption

logger = logging.getLogger(__name__)


def _validate_asset_path(
    asset_path: Optional[str], course_base_dir: str, pool_base_dir: str
) -> Optional[str]:
    """
    Checks if an asset exists in the course or shared pool directories and returns the valid path.
    """
    if not asset_path:
        return None

    # Construct full paths
    course_asset_path = os.path.join(course_base_dir, asset_path)
    if os.path.exists(course_asset_path):
        return course_asset_path

    pool_asset_path = os.path.join(pool_base_dir, asset_path)
    if os.path.exists(pool_asset_path):
        return pool_asset_path

    logger.warning(
        f"Asset not found: '{asset_path}'."
    )
    return None


def load_manifest(manifest_path: str) -> Optional[Dict[str, Any]]:
    """Loads the course manifest YAML file."""
    logger.debug(f"Attempting to load manifest from: {manifest_path}")
    if not os.path.exists(manifest_path):
        logger.error(f"Manifest file not found: {manifest_path}")
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


def _parse_exercise_options(
    options_data: Any,
    correct_option_text: Optional[str],
    course_base_dir: str,
    pool_base_dir: str,
) -> List[ExerciseOption]:
    """Helper to parse options data into a list of ExerciseOption objects."""
    logger.debug(
        f"Parsing exercise options: {options_data}, correct_option_text: {correct_option_text}"
    )
    parsed_options = []
    if isinstance(options_data, list):
        if all(isinstance(opt, dict) for opt in options_data):
            # Format: [{"text": "Option A", "image_file": "path/to/image.png", "correct": true}]
            for opt in options_data:
                image_file = opt.get("image_file")
                validated_image_path = _validate_asset_path(
                    image_file, course_base_dir, pool_base_dir
                )
                parsed_options.append(
                    ExerciseOption(
                        text=opt.get("text"),
                        image_file=validated_image_path or image_file,
                        correct=opt.get("correct", False),
                    )
                )
            logger.debug(f"Parsed options (dict format): {parsed_options}")
        elif all(isinstance(opt, str) for opt in options_data):
            # Format: ["Option A", "Option B", "Option C"]
            if correct_option_text is None:
                logger.warning(
                    f"Simple options list provided {options_data} but 'correct_option' is missing. Options might not be correctly marked as correct."
                )
            parsed_options = [
                ExerciseOption(text=opt, correct=(opt == correct_option_text))
                for opt in options_data
            ]
            random.shuffle(parsed_options)
            logger.debug(f"Parsed options (list format): {parsed_options}")
    else:
        logger.warning(
            f"Invalid options data format: {options_data}. Expected a list. Returning empty options."
        )
    return parsed_options


def _parse_exercise(
    exercise_data: Dict[str, Any],
    lesson_id: str,
    index: int,
    target_language: str,
    source_language: str,
    course_base_dir: str,
    pool_base_dir: str,
) -> Optional[Exercise]:
    """Parses a single exercise entry from YAML data into an Exercise object."""
    ex_id = f"{lesson_id}_ex{index}"
    ex_type = exercise_data.get("type")
    logger.debug(f"Attempting to parse exercise {ex_id} of type '{ex_type}'.")

    if not ex_type:
        logger.warning(f"Skipping exercise {ex_id}: 'type' field is missing.")
        return None

    title = exercise_data.get("title")
    prompt = exercise_data.get("prompt")
    answer = exercise_data.get("answer")
    source_word = exercise_data.get("source_word")
    sentence_template = exercise_data.get("sentence_template")
    correct_option = exercise_data.get("correct_option")
    translation_hint = exercise_data.get("translation_hint")
    audio_file = exercise_data.get("audio_file")
    image_file = exercise_data.get("image_file")
    words_data = exercise_data.get("words")
    explanation_text = exercise_data.get("explanation")
    target_pron_text = exercise_data.get("target_pronunciation_text")
    allowed_lev_dist = exercise_data.get("allowed_levenshtein_distance")

    validated_audio_path = _validate_asset_path(
        audio_file, course_base_dir, pool_base_dir
    )
    validated_image_path = _validate_asset_path(
        image_file, course_base_dir, pool_base_dir
    )

    options: List[ExerciseOption] = []
    if ex_type in [
        "multiple_choice_translation",
        "fill_in_the_blank",
        "image_association",
        "listen_and_select",
    ]:
        options = _parse_exercise_options(
            exercise_data.get("options", []),
            correct_option,
            course_base_dir,
            pool_base_dir,
        )
        if not options:
            logger.warning(f"No valid options parsed for {ex_type} exercise {ex_id}.")

    # Basic validation for essential fields based on type
    if ex_type in ["translate_to_target", "translate_to_source", "dictation"] and (
        prompt is None or answer is None
    ):
        logger.warning(
            f"Skipping {ex_type} exercise {ex_id}: 'prompt' or 'answer' is missing."
        )
        return None
    elif ex_type in [
        "multiple_choice_translation",
        "image_association",
        "listen_and_select",
    ] and (not options):
        logger.warning(
            f"Skipping {ex_type} exercise {ex_id}: 'options' are missing/empty."
        )
        return None
    elif ex_type == "fill_in_the_blank" and (
        sentence_template is None or correct_option is None or not options
    ):
        logger.warning(
            f"Skipping {ex_type} exercise {ex_id}: 'sentence_template', 'correct_option' or 'options' missing/empty."
        )
        return None
    elif ex_type == "sentence_jumble" and (not words_data or answer is None):
        logger.warning(
            f"Skipping {ex_type} exercise {ex_id}: 'words' or 'answer' is missing/empty."
        )
        return None
    elif ex_type == "context_block" and prompt is None:
        logger.warning(
            f"Skipping {ex_type} exercise {ex_id}: 'prompt' content is missing."
        )
        return None
    elif ex_type == "pronunciation_practice" and target_pron_text is None:
        logger.warning(
            f"Skipping {ex_type} exercise {ex_id}: 'target_pronunciation_text' is missing."
        )
        return None

    return Exercise(
        exercise_id=ex_id,
        type=ex_type,
        title=title,
        prompt=prompt,
        answer=answer,
        source_word=source_word,
        options=options,
        sentence_template=sentence_template,
        correct_option=correct_option,
        translation_hint=translation_hint,
        audio_file=validated_audio_path or audio_file,
        image_file=validated_image_path or image_file,
        words=words_data if isinstance(words_data, list) else None,
        explanation=explanation_text,
        target_pronunciation_text=target_pron_text,
        allowed_levenshtein_distance=allowed_lev_dist,
        raw_data=exercise_data,
    )


def load_course_content(
    content_filepath: str,
    course_id: str,
    course_title: str,
    target_lang: str,
    source_lang: str,
    version: str,
    author: Optional[str] = None,
    description: Optional[str] = None,
    image_file: Optional[str] = None,
    course_base_dir: Optional[str] = None,
    pool_base_dir: Optional[str] = None,
) -> Optional[Course]:
    """Loads and parses the course content YAML file into a Course object."""
    logger.debug(f"Attempting to load course content from: {content_filepath}")
    if not os.path.exists(content_filepath):
        logger.error(f"Course content file not found: {content_filepath}")
        return None
    try:
        with open(content_filepath, "r", encoding="utf-8") as f:
            raw_course_data = yaml.safe_load(f)
        logger.info(f"Successfully loaded raw course data from {content_filepath}")
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
            f"Course content file {content_filepath} is empty or 'units' key is missing. Cannot load course."
        )
        return None

    validated_image_path = _validate_asset_path(
        image_file, course_base_dir, pool_base_dir
    )

    course = Course(
        course_id=course_id,
        title=course_title,
        target_language=target_lang,
        source_language=source_lang,
        version=version,
        author=author,
        description=description,
        image_file=validated_image_path or image_file,
        content_file=os.path.basename(content_filepath),
    )
    logger.debug(f"Initialized Course object for '{course_title}' (ID: {course_id})")

    for unit_data in raw_course_data.get("units", []):
        unit_id = unit_data.get("unit_id")
        unit_title = unit_data.get("title")
        if not unit_id or not unit_title:
            logger.warning(
                f"Skipping malformed unit: {unit_data}. Missing unit_id or title."
            )
            continue
        unit_obj = Unit(unit_id=unit_id, title=unit_title)
        logger.debug(f"Parsed unit '{unit_title}' (ID: {unit_id})")

        for lesson_data in unit_data.get("lessons", []):
            lesson_id = lesson_data.get("lesson_id")
            lesson_title = lesson_data.get("title")
            if not lesson_id or not lesson_title:
                logger.warning(
                    f"Skipping malformed lesson in unit {unit_id}: {lesson_data}. Missing lesson_id or title."
                )
                continue
            lesson_obj = Lesson(
                lesson_id=lesson_id,
                title=lesson_title,
                unit_id=unit_obj.unit_id,
            )
            logger.debug(
                f"Parsed lesson '{lesson_title}' (ID: {lesson_id}) in unit {unit_id}"
            )
            for i, ex_data in enumerate(lesson_data.get("exercises", [])):
                exercise_obj = _parse_exercise(
                    ex_data,
                    lesson_obj.lesson_id,
                    i,
                    target_lang,
                    source_lang,
                    course_base_dir,
                    pool_base_dir,
                )
                if exercise_obj:
                    lesson_obj.exercises.append(exercise_obj)
                    logger.debug(
                        f"Added exercise {exercise_obj.exercise_id} to lesson {lesson_id}"
                    )
                else:
                    logger.warning(
                        f"Failed to parse exercise at index {i} in lesson {lesson_id}. Skipping."
                    )
            unit_obj.lessons.append(lesson_obj)
            logger.debug(f"Added lesson {lesson_id} to unit {unit_id}")
        course.units.append(unit_obj)
        logger.debug(f"Added unit {unit_id} to course {course_id}")

    logger.info(
        f"Course '{course_title}' loaded successfully with {len(course.units)} units and {sum(len(u.lessons) for u in course.units)} lessons."
    )
    return course


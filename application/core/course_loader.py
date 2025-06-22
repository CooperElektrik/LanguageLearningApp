import yaml
import os
import logging
import random
from typing import Dict, Any, Optional, List

from .models import Course, Unit, Lesson, Exercise, ExerciseOption

logger = logging.getLogger(__name__)


def load_manifest(manifest_path: str) -> Optional[Dict[str, Any]]:
    """Loads the course manifest YAML file."""
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
    options_data: Any, correct_option_text: Optional[str] = None
) -> List[ExerciseOption]:
    """Helper to parse options data into a list of ExerciseOption objects."""
    parsed_options = []
    if isinstance(options_data, list):
        if all(isinstance(opt, dict) for opt in options_data):
            # Format: [{"text": "Option A", "correct": true}]
            parsed_options = [
                ExerciseOption(text=opt["text"], correct=opt.get("correct", False))
                for opt in options_data
            ]
        elif all(isinstance(opt, str) for opt in options_data):
            # Format: ["Option A", "Option B", "Option C"]
            if correct_option_text is None:
                logger.warning(
                    f"Simple options list provided {options_data} but 'correct_option' is missing."
                )
            parsed_options = [
                ExerciseOption(text=opt, correct=(opt == correct_option_text))
                for opt in options_data
            ]
            random.shuffle(parsed_options)
    else:
        logger.warning(f"Invalid options data format: {options_data}. Expected a list.")
    return parsed_options


def _parse_exercise(
    exercise_data: Dict[str, Any],
    lesson_id: str,
    index: int,
    target_language: str,
    source_language: str,
) -> Optional[Exercise]:
    """Parses a single exercise entry from YAML data into an Exercise object."""
    ex_id = f"{lesson_id}_ex{index}"
    ex_type = exercise_data.get("type")

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

    options: List[ExerciseOption] = []
    if ex_type in [
        "multiple_choice_translation",
        "fill_in_the_blank",
        "image_association",
        "listen_and_select",
    ]:
        options = _parse_exercise_options(
            exercise_data.get("options", []), correct_option
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
        audio_file=audio_file,
        image_file=image_file,
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
) -> Optional[Course]:
    """Loads and parses the course content YAML file into a Course object."""
    if not os.path.exists(content_filepath):
        logger.error(f"Course content file not found: {content_filepath}")
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
        course_id=course_id,
        title=course_title,
        target_language=target_lang,
        source_language=source_lang,
        version=version,
        author=author,
        description=description,
        content_file=os.path.basename(content_filepath),
    )

    for unit_data in raw_course_data.get("units", []):
        unit_id = unit_data.get("unit_id")
        unit_title = unit_data.get("title")
        if not unit_id or not unit_title:
            logger.warning(
                f"Skipping malformed unit: {unit_data}. Missing unit_id or title."
            )
            continue
        unit_obj = Unit(unit_id=unit_id, title=unit_title)

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
            for i, ex_data in enumerate(lesson_data.get("exercises", [])):
                exercise_obj = _parse_exercise(
                    ex_data, lesson_obj.lesson_id, i, target_lang, source_lang
                )
                if exercise_obj:
                    lesson_obj.exercises.append(exercise_obj)
                else:
                    logger.warning(
                        f"Failed to parse exercise at index {i} in lesson {lesson_id}. Skipping."
                    )
            unit_obj.lessons.append(lesson_obj)
        course.units.append(unit_obj)

    logger.info(
        f"Course '{course_title}' loaded successfully with {len(course.units)} units."
    )
    return course

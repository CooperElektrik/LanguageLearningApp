import yaml
import os
import logging
import random
from typing import Dict, Any, Optional
from .models import Course, Unit, Lesson, Exercise, ExerciseOption

logger = logging.getLogger(__name__)


def load_manifest(manifest_path: str) -> Optional[Dict[str, Any]]:
    """Loads the course manifest YAML file."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f)
        logger.info(f"Manifest loaded successfully from {manifest_path}")
        return manifest_data
    except FileNotFoundError:
        logger.error(f"Manifest file not found: {manifest_path}")
    except yaml.YAMLError as e:
        logger.error(f"Error parsing manifest YAML file {manifest_path}: {e}")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while loading manifest {manifest_path}: {e}"
        )
    return None


def _parse_exercise(
    exercise_data: Dict[str, Any],
    lesson_id: str,
    index: int,
    target_language: str,
    source_language: str,
) -> Exercise:
    """Parses a single exercise entry from YAML data into an Exercise object."""
    ex_id = f"{lesson_id}_ex{index}"
    ex_type = exercise_data.get("type", "unknown")

    prompt = exercise_data.get("prompt")
    answer = exercise_data.get("answer")
    source_word = exercise_data.get("source_word")

    options_data = exercise_data.get("options", [])
    parsed_options = []
    if ex_type == "multiple_choice_translation" or ex_type == "fill_in_the_blank":
        if isinstance(options_data, list) and all(
            isinstance(opt, dict) for opt in options_data
        ):
            parsed_options = [
                ExerciseOption(text=opt["text"], correct=opt.get("correct", False))
                for opt in options_data
            ]
        elif isinstance(options_data, list) and all(
            isinstance(opt, str) for opt in options_data
        ):
            correct_opt_text = exercise_data.get("correct_option")
            parsed_options = [
                ExerciseOption(text=opt, correct=(opt == correct_opt_text))
                for opt in options_data
            ]
            random.shuffle(parsed_options)

    if ex_type == "multiple_choice_translation" and source_word:
        prompt = f"Choose the {target_language} translation for: '{source_word}' ({source_language})"

    audio_file = exercise_data.get("audio_file")
    image_file = exercise_data.get("image_file")

    return Exercise(
        exercise_id=ex_id,
        type=ex_type,
        prompt=prompt,
        answer=answer,
        source_word=source_word,
        options=parsed_options,
        sentence_template=exercise_data.get("sentence_template"),
        correct_option=exercise_data.get("correct_option"),
        translation_hint=exercise_data.get("translation_hint"),
        audio_file=audio_file,
        image_file=image_file,
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
    try:
        with open(content_filepath, "r", encoding="utf-8") as f:
            raw_course_data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Course content file not found: {content_filepath}")
        return None
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
        unit_obj = Unit(unit_id=unit_data["unit_id"], title=unit_data["title"])
        for lesson_data in unit_data.get("lessons", []):
            lesson_obj = Lesson(
                lesson_id=lesson_data["lesson_id"],
                title=lesson_data["title"],
                unit_id=unit_obj.unit_id,
            )
            for i, ex_data in enumerate(lesson_data.get("exercises", [])):
                exercise_obj = _parse_exercise(
                    ex_data, lesson_obj.lesson_id, i, target_lang, source_lang
                )
                lesson_obj.exercises.append(exercise_obj)
            unit_obj.lessons.append(lesson_obj)
        course.units.append(unit_obj)

    logger.info(
        f"Course '{course_title}' loaded successfully with {len(course.units)} units."
    )
    return course

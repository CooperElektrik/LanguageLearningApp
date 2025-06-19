import sys
import os
import argparse
import logging
import csv
import yaml
import uuid
from typing import List, Dict, Any, Optional, Tuple

current_script_dir = os.path.dirname(os.path.abspath(__file__))
application_root_dir = os.path.abspath(os.path.join(current_script_dir, ".."))

if application_root_dir not in sys.path:
    sys.path.insert(0, application_root_dir)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_existing_course_data(yaml_filepath: str) -> Dict[str, Any]:
    """Loads existing course data from a YAML file into a dictionary format."""
    if os.path.exists(yaml_filepath):
        try:
            with open(yaml_filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "units" in data and isinstance(data["units"], list):
                    return data
                else:
                    logger.warning(
                        f"Existing YAML file '{yaml_filepath}' is not in the expected format (missing 'units' list). Starting with new structure."
                    )
                    return {"units": []}
        except yaml.YAMLError as e:
            logger.error(
                f"Error parsing existing YAML file '{yaml_filepath}': {e}. Starting with new structure."
            )
            return {"units": []}
        except Exception as e:
            logger.error(
                f"Unexpected error loading '{yaml_filepath}': {e}. Starting with new structure."
            )
            return {"units": []}
    return {"units": []}


def save_course_data(course_data: Dict[str, Any], yaml_filepath: str):
    """Saves the course data (dictionary format) to a YAML file."""
    try:
        with open(yaml_filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                course_data, f, indent=2, sort_keys=False, allow_unicode=True
            )
        logger.info(f"Course data saved successfully to '{yaml_filepath}'.")
    except Exception as e:
        logger.error(f"Error saving course data to '{yaml_filepath}': {e}")


def find_or_create_unit(
    course_data: Dict[str, Any],
    unit_id: str,
    unit_title: Optional[str],
    messages: List[str],
) -> Optional[Dict[str, Any]]:
    """Finds an existing unit by ID or creates a new one if title is provided."""
    for unit in course_data["units"]:
        if unit.get("unit_id") == unit_id:
            messages.append(
                f"Found existing unit: ID='{unit_id}', Title='{unit.get('title', 'N/A')}'"
            )
            return unit

    if unit_title and unit_title.strip():
        new_unit = {"unit_id": unit_id, "title": unit_title.strip(), "lessons": []}
        course_data["units"].append(new_unit)
        messages.append(f"Created new unit: ID='{unit_id}', Title='{unit_title}'")
        return new_unit
    else:
        messages.append(
            f"ERROR: Unit with ID '{unit_id}' not found and no --unit_title provided to create it."
        )
        return None


def find_or_create_lesson(
    unit_data: Dict[str, Any],
    lesson_id: str,
    lesson_title: Optional[str],
    messages: List[str],
) -> Optional[Dict[str, Any]]:
    """Finds an existing lesson by ID within a unit or creates a new one if title is provided."""
    for lesson in unit_data.get("lessons", []):
        if lesson.get("lesson_id") == lesson_id:
            messages.append(
                f"Found existing lesson: ID='{lesson_id}', Title='{lesson.get('title', 'N/A')}' in Unit '{unit_data.get('unit_id')}'"
            )
            return lesson

    if lesson_title and lesson_title.strip():
        new_lesson = {
            "lesson_id": lesson_id,
            "title": lesson_title.strip(),
            "exercises": [],
        }
        if "lessons" not in unit_data:
            unit_data["lessons"] = []
        unit_data["lessons"].append(new_lesson)
        messages.append(
            f"Created new lesson: ID='{lesson_id}', Title='{lesson_title}' in Unit '{unit_data.get('unit_id')}'"
        )
        return new_lesson
    else:
        messages.append(
            f"ERROR: Lesson with ID '{lesson_id}' not found in Unit '{unit_data.get('unit_id')}' and no --lesson_title provided to create it."
        )
        return None


def _process_translation_csv_internal(
    csv_reader_instance,
    target_lesson_dict: Dict[str, Any],
    exercise_type: str,
    prompt_col: str,
    answer_col: str,
    messages: List[str],
    audio_file_col: str = None,
) -> int:
    count = 0
    for row_num, row in enumerate(csv_reader_instance):
        prompt = row.get(prompt_col)
        answer = row.get(answer_col)

        if not prompt or not answer:
            messages.append(
                f"Warning: Skipping CSV row {row_num + 1}: Missing '{prompt_col}' or '{answer_col}'."
            )
            continue

        exercise_data = {"type": exercise_type, "prompt": prompt, "answer": answer}
        target_lesson_dict["exercises"].append(exercise_data)
        count += 1

        # Handle dictation audio files
        if exercise_type == "dictation":
            audio_file = row.get(audio_file_col)  # Use the passed audio_file_col
            if audio_file:
                exercise_data["audio_file"] = audio_file
    messages.append(
        f"Info: Added {count} '{exercise_type}' exercises to Lesson '{target_lesson_dict.get('lesson_id')}'."
    )
    return count


def _process_mcq_csv_internal(
    csv_reader_instance,
    target_lesson_dict: Dict[str, Any],
    source_word_col: str,
    correct_option_col: str,
    incorrect_options_cols: List[str],
    messages: List[str],
) -> int:
    count = 0
    for row_num, row in enumerate(csv_reader_instance):
        source_word = row.get(source_word_col)
        correct_option_text = row.get(correct_option_col)

        if not source_word or not correct_option_text:
            messages.append(
                f"Warning: Skipping CSV row {row_num + 1}: Missing '{source_word_col}' or '{correct_option_col}'."
            )
            continue

        options = [{"text": correct_option_text, "correct": True}]

        has_incorrect = False
        for col_name in incorrect_options_cols:
            incorrect_text = row.get(col_name)
            if incorrect_text:
                options.append({"text": incorrect_text, "correct": False})
                has_incorrect = True

        if not has_incorrect:
            messages.append(
                f"Warning: Skipping CSV row {row_num + 1} for source_word '{source_word}': No incorrect options provided/found from columns: {incorrect_options_cols}."
            )
            continue

        exercise_data = {
            "type": "multiple_choice_translation",
            "source_word": source_word,
            "options": options,
        }
        target_lesson_dict["exercises"].append(exercise_data)
        count += 1
    messages.append(
        f"Info: Added {count} 'multiple_choice_translation' exercises to Lesson '{target_lesson_dict.get('lesson_id')}'."
    )
    return count


def _process_association_csv_internal(
    csv_reader_instance,
    target_lesson_dict: Dict[str, Any],
    exercise_type: str,
    prompt_col: str,
    asset_col: str,  # 'image_file' or 'audio_file'
    correct_option_col: str,
    incorrect_options_cols: List[str],
    messages: List[str],
) -> int:
    count = 0
    for row_num, row in enumerate(csv_reader_instance):
        prompt = row.get(prompt_col)
        asset_path = row.get(asset_col)
        correct_option_text = row.get(correct_option_col)

        if not all(
            [prompt, correct_option_text]
        ):  # Asset path can be optional for prompt
            messages.append(
                f"Warning: Skipping row {row_num + 1}, missing prompt or correct_option data."
            )
            continue

        options = [{"text": correct_option_text, "correct": True}]
        incorrects = [row.get(col) for col in incorrect_options_cols if row.get(col)]
        if (
            not incorrects
        ):  # Allow association with only one correct option if no incorrects are provided
            messages.append(
                f"Info: Row {row_num + 1} for '{prompt}' has no incorrect options from columns: {incorrect_options_cols}."
            )

        for inc_opt in incorrects:
            options.append({"text": inc_opt, "correct": False})

        exercise_data = {"type": exercise_type, "prompt": prompt, "options": options}
        if exercise_type == "image_association" and asset_path:
            exercise_data["image_file"] = asset_path
        elif exercise_type == "listen_and_select" and asset_path:
            exercise_data["audio_file"] = asset_path

        target_lesson_dict["exercises"].append(exercise_data)
        count += 1
    messages.append(f"Info: Added {count} '{exercise_type}' exercises.")
    return count


def _process_jumble_csv_internal(
    csv_reader_instance,
    target_lesson_dict: Dict[str, Any],
    prompt_col: str,
    words_col: str,
    answer_col: str,
    messages: List[str],
) -> int:
    count = 0
    for row_num, row in enumerate(csv_reader_instance):
        prompt = row.get(prompt_col)  # Prompt can be optional for jumble
        words_str = row.get(words_col)
        answer = row.get(answer_col)

        if not all([words_str, answer]):
            messages.append(
                f"Warning: Skipping row {row_num + 1}, missing 'words' or 'answer' for jumble."
            )
            continue

        exercise_data = {
            "type": "sentence_jumble",
            "words": words_str.split(),
            "answer": answer,
        }
        if prompt:
            exercise_data["prompt"] = prompt
        target_lesson_dict["exercises"].append(exercise_data)
        count += 1
    messages.append(f"Info: Added {count} 'sentence_jumble' exercises.")
    return count


def _process_context_csv_internal(
    csv_reader_instance,
    target_lesson_dict: Dict[str, Any],
    title_col: str,
    prompt_col: str,
    messages: List[str],
) -> int:
    count = 0
    for row_num, row in enumerate(csv_reader_instance):
        exercise_data = {
            "type": "context_block",
            "title": row.get(title_col),
            "prompt": row.get(prompt_col),
        }
        if not exercise_data["prompt"]:  # Prompt (content) is essential
            messages.append(
                f"Warning: Skipping row {row_num + 1} for context_block, missing content/prompt."
            )
            continue
        target_lesson_dict["exercises"].append(exercise_data)
        count += 1
    messages.append(f"Info: Added {count} 'context_block' slides.")
    return count


def import_csv_data(
    csv_filepath: str,
    existing_course_data: Dict[str, Any],
    exercise_type: str,
    unit_id: str,
    unit_title: Optional[str],
    lesson_id: str,
    lesson_title: Optional[str],
    prompt_col: str = "prompt",
    answer_col: str = "answer",
    source_word_col: str = "source_word",
    correct_option_col: str = "correct_option",
    audio_file_col: str = "audio_file",  # Added for dictation
    image_file_col: str = "image_file",  # Added for image_association
    words_col: str = "words",  # Added for sentence_jumble
    title_col: str = "title",  # Added for context_block
    incorrect_options_cols: Optional[List[str]] = None,
    incorrect_options_prefix: str = "incorrect_option_",
) -> Tuple[bool, List[str]]:
    messages = []
    success = True

    target_unit = find_or_create_unit(
        existing_course_data, unit_id, unit_title, messages
    )
    if not target_unit:
        return False, messages

    target_lesson = find_or_create_lesson(
        target_unit, lesson_id, lesson_title, messages
    )
    if not target_lesson:
        return False, messages

    if "exercises" not in target_lesson:
        target_lesson["exercises"] = []

    try:
        with open(csv_filepath, mode="r", encoding="utf-8-sig") as csvfile:
            reader = list(csv.DictReader(csvfile))

            if not reader:
                messages.append(
                    "Error: CSV file is empty or could not be read as dictionary."
                )
                return False, messages

            fieldnames = reader[0].keys() if reader else []

            if exercise_type in [
                "translate_to_target",
                "translate_to_source",
                "dictation",
            ]:
                required_cols = [prompt_col, answer_col]
                if exercise_type == "dictation" and audio_file_col not in fieldnames:
                    messages.append(
                        f"Warning: For 'dictation', '{audio_file_col}' column is recommended but not found. Proceeding without audio if not present in rows."
                    )

                if not all(col in fieldnames for col in required_cols):
                    messages.append(
                        f"Error: CSV missing required columns for {exercise_type}: {', '.join(required_cols)}. Found: {list(fieldnames)}"
                    )
                    return False, messages
                _process_translation_csv_internal(
                    reader,
                    target_lesson,
                    exercise_type,
                    prompt_col,
                    answer_col,
                    messages,
                    # Pass audio_file_col for dictation
                    audio_file_col if exercise_type == "dictation" else None,
                )

            elif exercise_type == "multiple_choice_translation":
                actual_incorrect_cols = []
                if incorrect_options_cols:
                    actual_incorrect_cols = [
                        col for col in incorrect_options_cols if col in fieldnames
                    ]
                else:
                    actual_incorrect_cols = [
                        fn
                        for fn in fieldnames
                        if fn.startswith(incorrect_options_prefix)
                        and fn != incorrect_options_prefix
                    ]

                required_mcq_cols = [source_word_col, correct_option_col]
                missing_mcq_cols = [
                    col for col in required_mcq_cols if col not in fieldnames
                ]
                if missing_mcq_cols:
                    messages.append(
                        f"Error: CSV missing required columns for MCQ: {missing_mcq_cols}. Found fieldnames: {list(fieldnames)}"
                    )
                    return False, messages
                if not actual_incorrect_cols:
                    messages.append(
                        f"Error: No incorrect option columns found. Specify via --incorrect_options_cols or ensure columns match --incorrect_options_prefix ('{incorrect_options_prefix}'). Found fieldnames: {list(fieldnames)}"
                    )
                    return False, messages

                _process_mcq_csv_internal(
                    reader,
                    target_lesson,
                    source_word_col,
                    correct_option_col,
                    actual_incorrect_cols,
                    messages,
                )
            elif exercise_type == "image_association":
                required_cols = [prompt_col, image_file_col, correct_option_col]
                if not all(
                    col in fieldnames for col in [prompt_col, correct_option_col]
                ):  # image_file_col can be optional
                    messages.append(
                        f"Error: CSV missing required columns for image_association: '{prompt_col}', '{correct_option_col}'. Found: {list(fieldnames)}"
                    )
                    return False, messages
                if image_file_col not in fieldnames:
                    messages.append(
                        f"Warning: For 'image_association', '{image_file_col}' column not found. Exercises will be created without images if not present in rows."
                    )
                _process_association_csv_internal(
                    reader,
                    target_lesson,
                    exercise_type,
                    prompt_col,
                    image_file_col,
                    correct_option_col,
                    incorrect_options_cols or [],
                    messages,  # Pass empty list if None
                )
            elif exercise_type == "listen_and_select":
                required_cols = [prompt_col, audio_file_col, correct_option_col]
                if not all(
                    col in fieldnames for col in [prompt_col, correct_option_col]
                ):  # audio_file_col can be optional
                    messages.append(
                        f"Error: CSV missing required columns for listen_and_select: '{prompt_col}', '{correct_option_col}'. Found: {list(fieldnames)}"
                    )
                    return False, messages
                if audio_file_col not in fieldnames:
                    messages.append(
                        f"Warning: For 'listen_and_select', '{audio_file_col}' column not found. Exercises will be created without audio if not present in rows."
                    )
                _process_association_csv_internal(
                    reader,
                    target_lesson,
                    exercise_type,
                    prompt_col,
                    audio_file_col,
                    correct_option_col,
                    incorrect_options_cols or [],
                    messages,  # Pass empty list if None
                )
            elif exercise_type == "sentence_jumble":
                required_cols = [words_col, answer_col]  # prompt_col is optional
                if not all(col in fieldnames for col in required_cols):
                    messages.append(
                        f"Error: CSV missing required columns for sentence_jumble: '{words_col}', '{answer_col}'. Found: {list(fieldnames)}"
                    )
                    return False, messages
                if prompt_col not in fieldnames:
                    messages.append(
                        f"Warning: For 'sentence_jumble', '{prompt_col}' column not found. Exercises will be created without prompts if not present in rows."
                    )
                _process_jumble_csv_internal(
                    reader, target_lesson, prompt_col, words_col, answer_col, messages
                )

            elif exercise_type == "context_block":
                required_cols = [prompt_col]  # title_col is optional
                if prompt_col not in fieldnames:  # Prompt (content) is essential
                    messages.append(
                        f"Error: CSV missing required column for context_block: '{prompt_col}'. Found: {list(fieldnames)}"
                    )
                    return False, messages
                _process_context_csv_internal(
                    reader, target_lesson, title_col, prompt_col, messages
                )
            else:
                messages.append(
                    f"Error: Unsupported exercise type for CSV import: {exercise_type}"
                )
                return False, messages

    except FileNotFoundError:
        messages.append(f"Error: CSV file not found: '{csv_filepath}'")
        return False, messages
    except Exception as e:
        messages.append(
            f"Fatal Error: An unexpected error occurred while processing the CSV file: {e}"
        )
        return False, messages

    messages.insert(0, "CSV import process initiated.")
    return success, messages


def main():
    parser = argparse.ArgumentParser(
        description="Import exercises from CSV into a LL course content YAML file."
    )
    parser.add_argument("csv_file", help="Path to the input CSV file.")
    parser.add_argument(
        "--output_yaml",
        required=True,
        help="Path to the course content YAML file to create or update.",
    )

    parser.add_argument(
        "--exercise_type",
        required=True,
        choices=[
            "translate_to_target",
            "translate_to_source",
            "dictation",
            "multiple_choice_translation",
            "image_association",
            "listen_and_select",
            "sentence_jumble",
            "context_block",
        ],
        help="Type of exercises to generate.",
    )

    parser.add_argument(
        "--unit_id",
        required=True,
        help="ID of the unit to add exercises to (e.g., 'unit1').",
    )
    parser.add_argument(
        "--unit_title",
        help="Title for the unit if it needs to be created (required if --unit_id is new).",
    )

    parser.add_argument(
        "--lesson_id",
        required=True,
        help="ID of the lesson to add exercises to (e.g., 'u1l1').",
    )
    parser.add_argument(
        "--lesson_title",
        help="Title for the lesson if it needs to be created (required if --lesson_id is new).",
    )

    parser.add_argument(
        "--prompt_col",
        default="prompt",
        help="CSV column name for prompt/source text (for translation/MCQ). Default: 'prompt'",
    )
    parser.add_argument(
        "--answer_col",
        default="answer",
        help="CSV column name for the correct answer (for translation types). Default: 'answer'",
    )
    parser.add_argument(
        "--source_word_col",
        default="source_word",
        help="CSV column name for source word (for MCQ). Default: 'source_word'",
    )
    parser.add_argument(
        "--correct_option_col",
        default="correct_option",
        help="CSV column name for the correct MC option text. Default: 'correct_option'",
    )
    parser.add_argument(
        "--incorrect_options_cols",
        type=lambda s: [item.strip() for item in s.split(",")],
        help="Comma-separated CSV column names for incorrect MC option texts (e.g., 'incorr1,incorr2').",
    )
    parser.add_argument(
        "--incorrect_options_prefix",
        default="incorrect_option_",
        help="Prefix for CSV columns containing incorrect MC option texts (e.g., 'incorrect_option_1', 'incorrect_option_2'). Default: 'incorrect_option_'. This is used if --incorrect_options_cols is not provided.",
    )
    parser.add_argument(
        "--audio_file_col",
        default="audio_file",
        help="CSV column name for audio file path (for dictation, listen_and_select). Default: 'audio_file'",
    )
    parser.add_argument(
        "--image_file_col",
        default="image_file",
        help="CSV column name for image file path (for image_association). Default: 'image_file'",
    )
    parser.add_argument(
        "--words_col",
        default="words",
        help="CSV column name for space-separated words (for sentence_jumble). Default: 'words'",
    )
    parser.add_argument(
        "--title_col",
        default="title",
        help="CSV column name for the title (for context_block). Default: 'title'",
    )

    args = parser.parse_args()

    logger.info(f"Starting CSV import: '{args.csv_file}' into '{args.output_yaml}'")

    course_data_dict = load_existing_course_data(args.output_yaml)

    success, messages = import_csv_data(
        csv_filepath=args.csv_file,
        existing_course_data=course_data_dict,
        exercise_type=args.exercise_type,
        unit_id=args.unit_id,
        unit_title=args.unit_title,
        lesson_id=args.lesson_id,
        lesson_title=args.lesson_title,
        prompt_col=args.prompt_col,
        answer_col=args.answer_col,
        source_word_col=args.source_word_col,
        correct_option_col=args.correct_option_col,
        audio_file_col=args.audio_file_col,
        image_file_col=args.image_file_col,
        words_col=args.words_col,
        title_col=args.title_col,
        incorrect_options_cols=args.incorrect_options_cols,
        incorrect_options_prefix=args.incorrect_options_prefix,
    )

    if success:
        save_course_data(course_data_dict, args.output_yaml)

    for msg in messages:
        logger.info(msg)

    if success:
        logger.info("CSV import process completed successfully.")
        sys.exit(0)
    else:
        logger.error("CSV import process failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()

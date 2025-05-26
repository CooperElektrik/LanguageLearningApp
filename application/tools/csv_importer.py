import sys
import os
import argparse
import logging
import csv
import yaml
import uuid
from typing import List, Dict, Any, Optional, Tuple

# --- Setup sys.path to find 'core' module from the 'application' directory ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
application_root_dir = os.path.abspath(os.path.join(current_script_dir, '..'))

if application_root_dir not in sys.path:
    sys.path.insert(0, application_root_dir)

# --- Logging Configuration (used by CLI, GUI will use its own display) ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions (used by both CLI and GUI functions) ---

def load_existing_course_data(yaml_filepath: str) -> Dict[str, Any]:
    """Loads existing course data from a YAML file into a dictionary format."""
    if os.path.exists(yaml_filepath):
        try:
            with open(yaml_filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and 'units' in data and isinstance(data['units'], list):
                    return data
                else:
                    logger.warning(f"Existing YAML file '{yaml_filepath}' is not in the expected format (missing 'units' list). Starting with new structure.")
                    return {'units': []}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing existing YAML file '{yaml_filepath}': {e}. Starting with new structure.")
            return {'units': []}
        except Exception as e:
            logger.error(f"Unexpected error loading '{yaml_filepath}': {e}. Starting with new structure.")
            return {'units': []}
    return {'units': []}

def save_course_data(course_data: Dict[str, Any], yaml_filepath: str):
    """Saves the course data (dictionary format) to a YAML file."""
    try:
        with open(yaml_filepath, 'w', encoding='utf-8') as f:
            yaml.safe_dump(course_data, f, indent=2, sort_keys=False, allow_unicode=True)
        logger.info(f"Course data saved successfully to '{yaml_filepath}'.")
    except Exception as e:
        logger.error(f"Error saving course data to '{yaml_filepath}': {e}")

def find_or_create_unit(course_data: Dict[str, Any], unit_id: str, unit_title: Optional[str], messages: List[str]) -> Optional[Dict[str, Any]]:
    """Finds an existing unit by ID or creates a new one if title is provided."""
    for unit in course_data['units']:
        if unit.get('unit_id') == unit_id:
            messages.append(f"Found existing unit: ID='{unit_id}', Title='{unit.get('title', 'N/A')}'")
            return unit
    
    if unit_title and unit_title.strip():
        new_unit = {
            'unit_id': unit_id,
            'title': unit_title.strip(),
            'lessons': []
        }
        course_data['units'].append(new_unit)
        messages.append(f"Created new unit: ID='{unit_id}', Title='{unit_title}'")
        return new_unit
    else:
        messages.append(f"ERROR: Unit with ID '{unit_id}' not found and no --unit_title provided to create it.")
        return None

def find_or_create_lesson(unit_data: Dict[str, Any], lesson_id: str, lesson_title: Optional[str], messages: List[str]) -> Optional[Dict[str, Any]]:
    """Finds an existing lesson by ID within a unit or creates a new one if title is provided."""
    for lesson in unit_data.get('lessons', []):
        if lesson.get('lesson_id') == lesson_id:
            messages.append(f"Found existing lesson: ID='{lesson_id}', Title='{lesson.get('title', 'N/A')}' in Unit '{unit_data.get('unit_id')}'")
            return lesson
            
    if lesson_title and lesson_title.strip():
        new_lesson = {
            'lesson_id': lesson_id,
            'title': lesson_title.strip(),
            'exercises': []
        }
        if 'lessons' not in unit_data:
            unit_data['lessons'] = [] # Defensive check
        unit_data['lessons'].append(new_lesson)
        messages.append(f"Created new lesson: ID='{lesson_id}', Title='{lesson_title}' in Unit '{unit_data.get('unit_id')}'")
        return new_lesson
    else:
        messages.append(f"ERROR: Lesson with ID '{lesson_id}' not found in Unit '{unit_data.get('unit_id')}' and no --lesson_title provided to create it.")
        return None

# --- CSV Processing Functions (now for GUI and return messages) ---

def _process_translation_csv_internal(csv_reader_instance, target_lesson_dict: Dict[str, Any], 
                                    exercise_type: str, prompt_col: str, answer_col: str, 
                                    messages: List[str]) -> int:
    count = 0
    for row_num, row in enumerate(csv_reader_instance):
        prompt = row.get(prompt_col)
        answer = row.get(answer_col)

        if not prompt or not answer:
            messages.append(f"Warning: Skipping CSV row {row_num + 1}: Missing '{prompt_col}' or '{answer_col}'.")
            continue
        
        exercise_data = {
            'type': exercise_type,
            'prompt': prompt,
            'answer': answer
        }
        target_lesson_dict['exercises'].append(exercise_data)
        count += 1
    messages.append(f"Info: Added {count} '{exercise_type}' exercises to Lesson '{target_lesson_dict.get('lesson_id')}'.")
    return count


def _process_mcq_csv_internal(csv_reader_instance, target_lesson_dict: Dict[str, Any], 
                              source_word_col: str, correct_option_col: str, incorrect_options_cols: List[str], 
                              messages: List[str]) -> int:
    count = 0
    for row_num, row in enumerate(csv_reader_instance):
        source_word = row.get(source_word_col)
        correct_option_text = row.get(correct_option_col)

        if not source_word or not correct_option_text:
            messages.append(f"Warning: Skipping CSV row {row_num + 1}: Missing '{source_word_col}' or '{correct_option_col}'.")
            continue

        options = [{'text': correct_option_text, 'correct': True}]
        
        has_incorrect = False
        for col_name in incorrect_options_cols:
            incorrect_text = row.get(col_name)
            if incorrect_text: # Only add if text is present
                options.append({'text': incorrect_text, 'correct': False})
                has_incorrect = True
        
        if not has_incorrect:
            messages.append(f"Warning: Skipping CSV row {row_num + 1} for source_word '{source_word}': No incorrect options provided/found from columns: {incorrect_options_cols}.")
            continue
        
        exercise_data = {
            'type': 'multiple_choice_translation',
            'source_word': source_word,
            'options': options
        }
        target_lesson_dict['exercises'].append(exercise_data)
        count += 1
    messages.append(f"Info: Added {count} 'multiple_choice_translation' exercises to Lesson '{target_lesson_dict.get('lesson_id')}'.")
    return count


# --- New Callable Function for Editor ---

def import_csv_data(
        csv_filepath: str,
        existing_course_data: Dict[str, Any], # This is the mutable course data dict to be modified
        exercise_type: str,
        unit_id: str, unit_title: Optional[str],
        lesson_id: str, lesson_title: Optional[str],
        prompt_col: str = "prompt", answer_col: str = "answer", # Defaults
        source_word_col: str = "source_word", correct_option_col: str = "correct_option",
        incorrect_options_cols: Optional[List[str]] = None, # Explicit list of column names
        incorrect_options_prefix: str = "incorrect_option_" # Prefix to auto-detect
    ) -> Tuple[bool, List[str]]: # Returns (success_flag, messages_list)
    """
    Imports exercise data from a CSV file into the provided course data dictionary.
    Modifies existing_course_data in place.
    """
    messages = []
    success = True

    target_unit = find_or_create_unit(existing_course_data, unit_id, unit_title, messages)
    if not target_unit:
        return False, messages # Error already added by find_or_create_unit

    target_lesson = find_or_create_lesson(target_unit, lesson_id, lesson_title, messages)
    if not target_lesson:
        return False, messages # Error already added

    if 'exercises' not in target_lesson:
        target_lesson['exercises'] = [] # Ensure list exists

    try:
        with open(csv_filepath, mode='r', encoding='utf-8-sig') as csvfile:
            reader = list(csv.DictReader(csvfile)) # Read all into list of dicts for simplicity and re-readability
            
            if not reader:
                messages.append("Error: CSV file is empty or could not be read as dictionary.")
                return False, messages

            fieldnames = reader[0].keys() if reader else []

            if exercise_type in ["translate_to_target", "translate_to_source"]:
                if prompt_col not in fieldnames or answer_col not in fieldnames:
                    messages.append(f"Error: CSV missing required columns for translation: '{prompt_col}' or '{answer_col}'. Found: {list(fieldnames)}")
                    return False, messages
                _process_translation_csv_internal(reader, target_lesson, exercise_type, prompt_col, answer_col, messages)
            
            elif exercise_type == "multiple_choice_translation":
                actual_incorrect_cols = []
                if incorrect_options_cols:
                    actual_incorrect_cols = [col for col in incorrect_options_cols if col in fieldnames]
                else: # Use prefix to auto-detect
                    actual_incorrect_cols = [fn for fn in fieldnames if fn.startswith(incorrect_options_prefix) and fn != incorrect_options_prefix]
                
                required_mcq_cols = [source_word_col, correct_option_col]
                missing_mcq_cols = [col for col in required_mcq_cols if col not in fieldnames]
                if missing_mcq_cols:
                    messages.append(f"Error: CSV missing required columns for MCQ: {missing_mcq_cols}. Found fieldnames: {list(fieldnames)}")
                    return False, messages
                if not actual_incorrect_cols:
                    messages.append(f"Error: No incorrect option columns found. Specify via --incorrect_options_cols or ensure columns match --incorrect_options_prefix ('{incorrect_options_prefix}'). Found fieldnames: {list(fieldnames)}")
                    return False, messages

                _process_mcq_csv_internal(reader, target_lesson, source_word_col, correct_option_col, actual_incorrect_cols, messages)
            else:
                messages.append(f"Error: Unsupported exercise type for CSV import: {exercise_type}")
                return False, messages
                
    except FileNotFoundError:
        messages.append(f"Error: CSV file not found: '{csv_filepath}'")
        return False, messages
    except Exception as e:
        messages.append(f"Fatal Error: An unexpected error occurred while processing the CSV file: {e}")
        return False, messages
        
    messages.insert(0, "CSV import process initiated.") # General status message
    return success, messages


# --- Original Main Function (kept for CLI compatibility) ---
def main():
    parser = argparse.ArgumentParser(description="Import exercises from CSV into a LinguaLearn course content YAML file.")
    parser.add_argument("csv_file", help="Path to the input CSV file.")
    parser.add_argument("--output_yaml", required=True, help="Path to the course content YAML file to create or update.")
    
    parser.add_argument("--exercise_type", required=True, 
                        choices=["translate_to_target", "translate_to_source", "multiple_choice_translation"],
                        help="Type of exercises to generate.")
    
    parser.add_argument("--unit_id", required=True, help="ID of the unit to add exercises to (e.g., 'unit1').")
    parser.add_argument("--unit_title", help="Title for the unit if it needs to be created (required if --unit_id is new).")
    
    parser.add_argument("--lesson_id", required=True, help="ID of the lesson to add exercises to (e.g., 'u1l1').")
    parser.add_argument("--lesson_title", help="Title for the lesson if it needs to be created (required if --lesson_id is new).")

    parser.add_argument("--prompt_col", default="prompt", help="CSV column name for prompt/source text (for translation/MCQ). Default: 'prompt'")
    parser.add_argument("--answer_col", default="answer", help="CSV column name for the correct answer (for translation types). Default: 'answer'")
    parser.add_argument("--source_word_col", default="source_word", help="CSV column name for source word (for MCQ). Default: 'source_word'")
    parser.add_argument("--correct_option_col", default="correct_option", help="CSV column name for the correct MC option text. Default: 'correct_option'")
    parser.add_argument("--incorrect_options_cols", type=lambda s: [item.strip() for item in s.split(',')],
                        help="Comma-separated CSV column names for incorrect MC option texts (e.g., 'incorr1,incorr2').")
    parser.add_argument("--incorrect_options_prefix", default="incorrect_option_", 
                        help="Prefix for CSV columns containing incorrect MC option texts (e.g., 'incorrect_option_1', 'incorrect_option_2'). Default: 'incorrect_option_'. This is used if --incorrect_options_cols is not provided.")

    args = parser.parse_args()

    logger.info(f"Starting CSV import: '{args.csv_file}' into '{args.output_yaml}'")

    # 1. Load existing course data or initialize new
    course_data_dict = load_existing_course_data(args.output_yaml)
    
    # 2. Perform import logic
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
        incorrect_options_cols=args.incorrect_options_cols,
        incorrect_options_prefix=args.incorrect_options_prefix
    )

    # 3. Save updated course data if import was successful
    if success:
        save_course_data(course_data_dict, args.output_yaml)
    
    # 4. Report results
    for msg in messages:
        logger.info(msg) # Log messages collected during the process

    if success:
        logger.info("CSV import process completed successfully.")
        sys.exit(0)
    else:
        logger.error("CSV import process failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
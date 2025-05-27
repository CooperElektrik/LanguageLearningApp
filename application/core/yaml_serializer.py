import yaml
from typing import Dict, Any, List
from .models import Course, Unit, Lesson, Exercise, ExerciseOption

def course_to_yaml_data(course: Course) -> Dict[str, Any]:
    """Converts a Course object hierarchy into a dictionary structure suitable for YAML dumping."""
    data = {"units": []}
    for unit in course.units:
        unit_data = {"unit_id": unit.unit_id, "title": unit.title, "lessons": []}
        for lesson in unit.lessons:
            lesson_data = {"lesson_id": lesson.lesson_id, "title": lesson.title, "exercises": []}
            for exercise in lesson.exercises:
                ex_raw = {"type": exercise.type}
                
                # Add common fields based on exercise type
                if exercise.type in ["translate_to_target", "translate_to_source"]:
                    ex_raw["prompt"] = exercise.prompt
                    ex_raw["answer"] = exercise.answer
                    ex_raw["audio_file"] = exercise.audio_file
                elif exercise.type == "multiple_choice_translation":
                    ex_raw["source_word"] = exercise.source_word
                    ex_raw["options"] = [{"text": opt.text, "correct": opt.correct} for opt in exercise.options]
                elif exercise.type == "fill_in_the_blank":
                    ex_raw["sentence_template"] = exercise.sentence_template
                    ex_raw["correct_option"] = exercise.correct_option
                    # For FIB, options in YAML are just text strings, not objects
                    ex_raw["options"] = [opt.text for opt in exercise.options] 
                    ex_raw["translation_hint"] = exercise.translation_hint
                
                lesson_data["exercises"].append(ex_raw)
            unit_data["lessons"].append(lesson_data)
        data["units"].append(unit_data)
    return data

def manifest_to_yaml_data(manifest_data: Dict[str, Any]) -> Dict[str, Any]:
    """Returns the manifest data as is, suitable for YAML dumping."""
    return manifest_data

def save_course_to_yaml(course: Course, filepath: str):
    """Saves a Course object to a YAML file."""
    yaml_data = course_to_yaml_data(course)
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(yaml_data, f, indent=2, sort_keys=False, allow_unicode=True)

def save_manifest_to_yaml(manifest_data: Dict[str, Any], filepath: str):
    """Saves manifest data to a YAML file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(manifest_data, f, indent=2, sort_keys=False, allow_unicode=True)
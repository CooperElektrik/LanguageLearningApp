from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class ExerciseOption:
    text: str
    correct: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Converts the ExerciseOption object to a dictionary."""
        # Only include 'correct' if it's True, to keep YAML/JSON clean for options
        # This is fine for simple booleans, but for complex fields, avoid conditional logic.
        data = {"text": self.text}
        if self.correct:
            data["correct"] = self.correct
        return data


@dataclass
class Exercise:
    exercise_id: str
    type: str

    prompt: Optional[str] = None
    answer: Optional[str] = None # For translation exercises

    source_word: Optional[str] = None # For MCQ translation
    options: List[ExerciseOption] = field(default_factory=list) # For MCQ/FIB

    sentence_template: Optional[str] = None # For FIB
    correct_option: Optional[str] = None # For FIB and simple MCQ options
    translation_hint: Optional[str] = None # For FIB

    audio_file: Optional[str] = None # Relative path to audio for pronunciation
    image_file: Optional[str] = None # Relative path to image for visual exercises

    # SRS related fields managed by ProgressManager
    last_reviewed: Optional[datetime] = field(default=None, repr=False)
    next_review_due: Optional[datetime] = field(default=None, repr=False)
    interval_days: int = field(default=0)
    ease_factor: float = field(default=2.5)
    repetitions: int = field(default=0)
    correct_in_a_row: int = field(default=0)

    # Stores original raw data, useful for round-tripping in editors
    raw_data: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Exercise object to a dictionary for progress saving.
        Includes all SRS fields and exercise-specific content fields.
        None values are typically excluded by asdict by default.
        """
        data = asdict(self)

        # Convert datetime objects to ISO format strings for serialization
        if data.get("last_reviewed") is not None and isinstance(data["last_reviewed"], datetime):
            data["last_reviewed"] = data["last_reviewed"].isoformat()
        if data.get("next_review_due") is not None and isinstance(data["next_review_due"], datetime):
            data["next_review_due"] = data["next_review_due"].isoformat()

        # Convert ExerciseOption objects in 'options' list
        if "options" in data and data["options"]:
            data["options"] = [opt.to_dict() for opt in self.options]
        
        # Remove fields that are not part of basic content, but for internal tracking
        # 'raw_data' is already excluded by repr=False but good to be explicit for clarity
        data.pop("raw_data", None) # Ensure raw_data is not serialized in progress
        data.pop("exercise_id", None) # exercise_id is the key in progress data, not an attribute to save

        # Clean up None values and empty lists from the final dictionary
        # This will remove fields that are not relevant to a specific exercise type
        # For example, a 'translate' exercise won't have 'options'
        cleaned_data = {k: v for k, v in data.items() if v is not None and not (isinstance(v, list) and not v)}
        
        return cleaned_data

    def to_content_dict(self) -> Dict[str, Any]:
        """
        Converts the Exercise object to a dictionary suitable for saving to the
        course content YAML file. This excludes SRS-specific fields and internal IDs.
        It focuses on the definitional content of the exercise.
        """
        data = {
            "type": self.type,
        }

        # Add fields based on exercise type
        if self.type in ["translate_to_target", "translate_to_source"]:
            if self.prompt is not None: data["prompt"] = self.prompt
            if self.answer is not None: data["answer"] = self.answer
        elif self.type == "multiple_choice_translation":
            if self.source_word is not None: data["source_word"] = self.source_word
            if self.options: data["options"] = [opt.to_dict() for opt in self.options]
        elif self.type == "fill_in_the_blank":
            if self.sentence_template is not None: data["sentence_template"] = self.sentence_template
            if self.correct_option is not None: data["correct_option"] = self.correct_option
            if self.options: data["options"] = [opt.text for opt in self.options] # FIB options are just text
            if self.translation_hint is not None: data["translation_hint"] = self.translation_hint
        
        # Common optional fields
        if self.audio_file is not None: data["audio_file"] = self.audio_file
        if self.image_file is not None: data["image_file"] = self.image_file
        
        return data


@dataclass
class Lesson:
    lesson_id: str
    title: str
    exercises: List[Exercise] = field(default_factory=list)
    unit_id: Optional[str] = None # For internal linking, not part of lesson's own YAML structure

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Lesson object to a dictionary for content saving."""
        data = {
            "lesson_id": self.lesson_id,
            "title": self.title,
            "exercises": [ex.to_content_dict() for ex in self.exercises], # Use to_content_dict
        }
        return data


@dataclass
class Unit:
    unit_id: str
    title: str
    lessons: List[Lesson] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Unit object to a dictionary for content saving."""
        data = {
            "unit_id": self.unit_id,
            "title": self.title,
            "lessons": [lesson.to_dict() for lesson in self.lessons],
        }
        return data


@dataclass
class Course:
    course_id: str
    title: str
    target_language: str
    source_language: str
    version: str
    author: Optional[str] = None
    description: Optional[str] = None
    units: List[Unit] = field(default_factory=list)
    content_file: Optional[str] = None # Name of the content file this course was loaded from

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Course object to a dictionary for content saving (its 'units' part)."""
        return {"units": [unit.to_dict() for unit in self.units]}

@dataclass
class GlossaryEntry:
    word: str
    translation: str
    part_of_speech: Optional[str] = None
    example_sentence: Optional[str] = None
    notes: Optional[str] = None
    audio_file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the GlossaryEntry object to a dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

@dataclass
class ExerciseOption:
    text: str
    correct: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Exercise:
    exercise_id: str # Unique ID for this exercise (e.g., lesson_id + index)
    type: str  # "translate_to_target", "translate_to_source", "multiple_choice_translation", "fill_in_the_blank"
    
    # Common fields (some might be None depending on type)
    prompt: Optional[str] = None  # For translation types, this is the text to translate.
    answer: Optional[str] = None  # Correct answer for translation types.
    
    # Type-specific fields
    source_word: Optional[str] = None # For multiple_choice_translation
    options: List[ExerciseOption] = field(default_factory=list) # For multiple_choice, fill_in_the_blank (shuffled options)
    
    sentence_template: Optional[str] = None # For fill_in_the_blank (e.g., "Mi __BLANK__ feliĉa.")
    correct_option: Optional[str] = None    # For fill_in_the_blank (the word that fills the blank)
    translation_hint: Optional[str] = None  # For fill_in_the_blank

    audio_file: Optional[str] = None # Relative path to audio file (e.g., "sounds/hello.mp3")
    image_file: Optional[str] = None # Relative path to image file (e.g., "images/cat.png")

    # Internal data for convenience after loading (not saved back to YAML)
    raw_data: Dict[str, Any] = field(default_factory=dict) 

    def to_dict(self) -> Dict[str, Any]:
        # Convert dataclass to dict, filtering out None values, empty lists, and internal 'raw_data'/'exercise_id'
        data = {k: v for k, v in asdict(self).items() if v is not None and v != [] and k not in ['raw_data', 'exercise_id']}
        
        # Special handling for options if they are dataclasses (convert to dicts)
        if 'options' in data:
            data['options'] = [opt.to_dict() for opt in self.options]

        return data

@dataclass
class Lesson:
    lesson_id: str
    title: str
    exercises: List[Exercise] = field(default_factory=list)
    unit_id: Optional[str] = None # Reference back to the unit (not saved to YAML)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if 'exercises' in data:
            data['exercises'] = [ex.to_dict() for ex in self.exercises]
        if 'unit_id' in data: # internal use, not part of YAML structure
            del data['unit_id']
        return data

@dataclass
class Unit:
    unit_id: str
    title: str
    lessons: List[Lesson] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if 'lessons' in data:
            data['lessons'] = [lesson.to_dict() for lesson in self.lessons]
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
    content_file: Optional[str] = None # This is for the manifest, not directly in course content YAML

    def to_dict(self) -> Dict[str, Any]:
        # The course content YAML only contains the 'units' list, not the manifest details.
        # This method is primarily used to prepare the 'units' list for dumping.
        return {'units': [unit.to_dict() for unit in self.units]}
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime

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

    last_reviewed: Optional[datetime] = field(default=None, repr=False) # Don't include in default repr
    next_review_due: Optional[datetime] = field(default=None, repr=False)
    interval_days: int = field(default=0) # Current SRS interval
    ease_factor: float = field(default=2.5) # Part of SM-2 algorithm
    repetitions: int = field(default=0) # Number of times reviewed
    correct_in_a_row: int = field(default=0) # Consecutive correct answers for this item

    # Internal data for convenience after loading (not saved back to YAML)
    raw_data: Dict[str, Any] = field(default_factory=dict) 

    def to_dict(self) -> Dict[str, Any]:
        # Existing to_dict logic...
        # Need to handle datetime serialization if saving to JSON.
        # YAML handles datetime objects fine.
        # For JSON, you'd convert datetime to isoformat string.
        data = {
            k: v for k, v in asdict(self).items() 
            if v is not None and 
               (v != [] if isinstance(v, list) else True) and # Check for empty list only if it's a list
               k not in ['raw_data', 'exercise_id']
        }
        if 'options' in data and data['options']: # ensure options exist and not empty before list comp
            data['options'] = [opt.to_dict() for opt in self.options]
        
        srs_fields_to_save = ['last_reviewed', 'next_review_due', 'interval_days', 'ease_factor', 'repetitions', 'correct_in_a_row']
        for srs_field in srs_fields_to_save:
            value = getattr(self, srs_field)
            if value is not None: # Only save if not None (or not default for int/float if desired)
                if isinstance(value, datetime):
                    data[srs_field] = value.isoformat() # Store as ISO string in YAML too for consistency
                elif srs_field in ['interval_days', 'repetitions', 'correct_in_a_row'] and value == 0 and srs_field != 'repetitions': # Don't save default 0 unless it's 'repetitions'
                    if srs_field in data: del data[srs_field] # Remove if it's default 0
                elif srs_field == 'ease_factor' and value == 2.5:
                     if srs_field in data: del data[srs_field] # Remove if it's default 2.5
                else:
                    data[srs_field] = value # Add/keep if not default or explicitly set
            elif srs_field in data: # Remove if None was explicitly set by asdict
                del data[srs_field]

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
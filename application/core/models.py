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
    exercise_id: str
    type: str

    prompt: Optional[str] = None
    answer: Optional[str] = None

    source_word: Optional[str] = None
    options: List[ExerciseOption] = field(default_factory=list)

    sentence_template: Optional[str] = None
    correct_option: Optional[str] = None
    translation_hint: Optional[str] = None

    audio_file: Optional[str] = None
    image_file: Optional[str] = None

    last_reviewed: Optional[datetime] = field(default=None, repr=False)
    next_review_due: Optional[datetime] = field(default=None, repr=False)
    interval_days: int = field(default=0)
    ease_factor: float = field(default=2.5)
    repetitions: int = field(default=0)
    correct_in_a_row: int = field(default=0)

    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            k: v
            for k, v in asdict(self).items()
            if v is not None
            and (v != [] if isinstance(v, list) else True)
            and k not in ["raw_data", "exercise_id"]
        }
        if "options" in data and data["options"]:
            data["options"] = [opt.to_dict() for opt in self.options]

        srs_fields_to_save = [
            "last_reviewed",
            "next_review_due",
            "interval_days",
            "ease_factor",
            "repetitions",
            "correct_in_a_row",
        ]
        for srs_field in srs_fields_to_save:
            value = getattr(self, srs_field)
            if value is not None:
                if isinstance(value, datetime):
                    data[srs_field] = value.isoformat()
                elif (
                    srs_field in ["interval_days", "repetitions", "correct_in_a_row"]
                    and value == 0
                    and srs_field != "repetitions"
                ):
                    if srs_field in data:
                        del data[srs_field]
                elif srs_field == "ease_factor" and value == 2.5:
                    if srs_field in data:
                        del data[srs_field]
                else:
                    data[srs_field] = value
            elif srs_field in data:
                del data[srs_field]

        return data


@dataclass
class Lesson:
    lesson_id: str
    title: str
    exercises: List[Exercise] = field(default_factory=list)
    unit_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if "exercises" in data:
            data["exercises"] = [ex.to_dict() for ex in self.exercises]
        if "unit_id" in data:
            del data["unit_id"]
        return data


@dataclass
class Unit:
    unit_id: str
    title: str
    lessons: List[Lesson] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if "lessons" in data:
            data["lessons"] = [lesson.to_dict() for lesson in self.lessons]
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
    content_file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"units": [unit.to_dict() for unit in self.units]}

@dataclass
class GlossaryEntry:
    word: str
    translation: str
    part_of_speech: Optional[str] = None # e.g., "n.", "v.", "adj."
    example_sentence: Optional[str] = None
    notes: Optional[str] = None
    audio_file: Optional[str] = None # Relative path to audio file for pronunciation

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
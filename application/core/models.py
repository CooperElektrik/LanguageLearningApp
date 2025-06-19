from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class ExerciseOption:
    text: str
    correct: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Converts the ExerciseOption object to a dictionary."""
        data = {"text": self.text}
        if self.correct:
            data["correct"] = self.correct
        return data


@dataclass
class Exercise:
    exercise_id: str
    type: str

    title: Optional[str] = None  # For context_block or any other exercise
    prompt: Optional[str] = None
    answer: Optional[str] = None

    source_word: Optional[str] = None
    options: List[ExerciseOption] = field(default_factory=list)

    sentence_template: Optional[str] = None
    correct_option: Optional[str] = None
    translation_hint: Optional[str] = None

    audio_file: Optional[str] = None
    image_file: Optional[str] = None

    explanation: Optional[str] = None

    words: Optional[List[str]] = None

    last_reviewed: Optional[datetime] = field(default=None, repr=False)
    next_review_due: Optional[datetime] = field(default=None, repr=False)
    interval_days: int = field(default=0)
    ease_factor: float = field(default=2.5)
    repetitions: int = field(default=0)
    correct_in_a_row: int = field(default=0)

    raw_data: Dict[str, Any] = field(default_factory=dict, repr=False)

    def has_hint(self) -> bool:
        """Checks if the exercise has a non-empty translation hint."""
        return bool(self.translation_hint and self.translation_hint.strip())

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Exercise object to a dictionary for progress saving.
        """
        data = asdict(self)

        if data.get("last_reviewed") is not None and isinstance(
            data["last_reviewed"], datetime
        ):
            data["last_reviewed"] = data["last_reviewed"].isoformat()
        if data.get("next_review_due") is not None and isinstance(
            data["next_review_due"], datetime
        ):
            data["next_review_due"] = data["next_review_due"].isoformat()

        if "options" in data and data["options"]:
            data["options"] = [opt.to_dict() for opt in self.options]

        data.pop("raw_data", None)
        data.pop("exercise_id", None)

        cleaned_data = {
            k: v
            for k, v in data.items()
            if v is not None and not (isinstance(v, list) and not v)
        }

        return cleaned_data

    def to_content_dict(self) -> Dict[str, Any]:
        """
        Converts the Exercise object to a dictionary suitable for saving to the
        course content YAML file.
        """
        data = {
            "type": self.type,
        }

        # Add title if it exists, for any type
        if self.title is not None:
            data["title"] = self.title

        if self.type in ["translate_to_target", "translate_to_source", "dictation"]:
            if self.prompt is not None:
                data["prompt"] = self.prompt
            if self.answer is not None:
                data["answer"] = self.answer
        elif self.type in [
            "multiple_choice_translation",
            "image_association",
            "listen_and_select",
        ]:
            if self.prompt is not None:
                data["prompt"] = self.prompt
            if self.source_word is not None:
                data["source_word"] = self.source_word
            if self.options:
                data["options"] = [opt.to_dict() for opt in self.options]
        elif self.type == "fill_in_the_blank":
            if self.sentence_template is not None:
                data["sentence_template"] = self.sentence_template
            if self.correct_option is not None:
                data["correct_option"] = self.correct_option
            if self.options:
                data["options"] = [opt.text for opt in self.options]
            if self.translation_hint is not None:
                data["translation_hint"] = self.translation_hint
        elif self.type == "sentence_jumble":
            if self.prompt is not None:
                data["prompt"] = self.prompt
            if self.words:
                data["words"] = self.words
            if self.answer is not None:
                data["answer"] = self.answer
        elif self.type == "context_block":
            if self.prompt is not None:
                data["prompt"] = self.prompt

        if self.audio_file is not None:
            data["audio_file"] = self.audio_file
        if self.image_file is not None:
            data["image_file"] = self.image_file

        if self.explanation is not None:
            data["explanation"] = self.explanation

        return data


@dataclass
class Lesson:
    lesson_id: str
    title: str
    exercises: List[Exercise] = field(default_factory=list)
    unit_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Lesson object to a dictionary for content saving."""
        data = {
            "lesson_id": self.lesson_id,
            "title": self.title,
            "exercises": [ex.to_content_dict() for ex in self.exercises],
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
    content_file: Optional[str] = None

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

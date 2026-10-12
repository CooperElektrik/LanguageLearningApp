from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExerciseOption:
    text: str | None = None
    image_file: str | None = None
    correct: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Converts the ExerciseOption object to a dictionary."""
        data = {}
        if self.text:
            data["text"] = self.text
        if self.image_file:
            data["image_file"] = self.image_file
        if self.correct:
            data["correct"] = self.correct
        return data


@dataclass
class Exercise:
    exercise_id: str
    type: str

    title: str | None = None  # For context_block or any other exercise
    prompt: str | None = None
    answer: str | None = None

    source_word: str | None = None
    options: list[ExerciseOption] = field(default_factory=list)

    sentence_template: str | None = None
    correct_option: str | None = None
    translation_hint: str | None = None

    audio_file: str | None = None
    image_file: str | None = None

    explanation: str | None = None

    target_pronunciation_text: str | None = None

    allowed_levenshtein_distance: int | None = None

    words: list[str] | None = None

    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)

    # NOTE: Spaced-repetition state (ease factor, intervals, due dates, ...) is
    # intentionally NOT stored on this model.  Exercises are immutable course
    # content; all SRS state lives in ProgressManager, keyed by exercise_id.

    def has_hint(self) -> bool:
        """Checks if the exercise has a non-empty translation hint."""
        return bool(self.translation_hint and self.translation_hint.strip())

    def to_content_dict(self) -> dict[str, Any]:
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
        elif self.type == "context_block" or self.type == "pronunciation_practice":
            if self.prompt is not None:
                data["prompt"] = self.prompt
        if self.audio_file is not None:
            data["audio_file"] = self.audio_file
        if self.image_file is not None:
            data["image_file"] = self.image_file
        if self.explanation is not None:
            data["explanation"] = self.explanation
        if self.allowed_levenshtein_distance is not None:
            data["allowed_levenshtein_distance"] = self.allowed_levenshtein_distance

        return data


@dataclass
class Lesson:
    lesson_id: str
    title: str
    exercises: list[Exercise] = field(default_factory=list)
    unit_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
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
    lessons: list[Lesson] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
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
    author: str | None = None
    description: str | None = None
    image_file: str | None = None
    units: list[Unit] = field(default_factory=list)
    content_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converts the Course object to a dictionary for content saving (its 'units' part)."""
        return {"units": [unit.to_dict() for unit in self.units]}


@dataclass
class GlossaryEntry:
    word: str
    translation: str
    part_of_speech: str | None = None
    example_sentence: str | None = None
    notes: str | None = None
    audio_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converts the GlossaryEntry object to a dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}

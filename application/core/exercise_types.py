"""Single source of truth for the exercise types supported by the application.

Historically the type list was re-declared in nine different places (the model
layer, the loader, ``CourseManager``, the runtime widgets, the editor window,
the CSV importer/dialog and the validator).  The copies drifted apart, which is
how the validator ended up rejecting ``pronunciation_practice`` and the CSV
importer silently lacked ``fill_in_the_blank`` support.

Centralising the names here keeps every layer in agreement.  Anything that only
needs "the list of types" should import from this module rather than re-typing
the literals.
"""

from enum import Enum


class ExerciseType(str, Enum):
    """Canonical exercise type identifiers.

    Inheriting from :class:`str` means members compare equal to their raw string
    value, so existing code that stores/reads plain strings keeps working.
    """

    TRANSLATE_TO_TARGET = "translate_to_target"
    TRANSLATE_TO_SOURCE = "translate_to_source"
    MULTIPLE_CHOICE_TRANSLATION = "multiple_choice_translation"
    FILL_IN_THE_BLANK = "fill_in_the_blank"
    DICTATION = "dictation"
    IMAGE_ASSOCIATION = "image_association"
    LISTEN_AND_SELECT = "listen_and_select"
    SENTENCE_JUMBLE = "sentence_jumble"
    CONTEXT_BLOCK = "context_block"
    PRONUNCIATION_PRACTICE = "pronunciation_practice"


# Ordered list used by UIs (menus/combos) so the presentation order is stable.
ALL_EXERCISE_TYPES: list[str] = [t.value for t in ExerciseType]

# The set every layer must accept.  Used by the validator and the loader.
VALID_EXERCISE_TYPES: list[str] = list(ALL_EXERCISE_TYPES)

# Types that have an editor + CSV importer and can therefore be created from
# scratch in the course editor (everything except pronunciation_practice, whose
# exercises are authored by recording rather than by hand).
CREATABLE_EXERCISE_TYPES: list[str] = [
    ExerciseType.TRANSLATE_TO_TARGET.value,
    ExerciseType.TRANSLATE_TO_SOURCE.value,
    ExerciseType.DICTATION.value,
    ExerciseType.MULTIPLE_CHOICE_TRANSLATION.value,
    ExerciseType.FILL_IN_THE_BLANK.value,
    ExerciseType.IMAGE_ASSOCIATION.value,
    ExerciseType.LISTEN_AND_SELECT.value,
    ExerciseType.SENTENCE_JUMBLE.value,
    ExerciseType.CONTEXT_BLOCK.value,
]

# Types that the CSV importer can turn rows into (same set for now).
CSV_IMPORTABLE_TYPES: list[str] = list(CREATABLE_EXERCISE_TYPES)

# Types whose ``options`` are serialised as ``[{"text": ..., "correct": ...}]``.
DICT_OPTION_TYPES = frozenset(
    {
        ExerciseType.MULTIPLE_CHOICE_TRANSLATION.value,
        ExerciseType.IMAGE_ASSOCIATION.value,
        ExerciseType.LISTEN_AND_SELECT.value,
    }
)

__all__ = [
    "ALL_EXERCISE_TYPES",
    "CREATABLE_EXERCISE_TYPES",
    "CSV_IMPORTABLE_TYPES",
    "DICT_OPTION_TYPES",
    "VALID_EXERCISE_TYPES",
    "ExerciseType",
]

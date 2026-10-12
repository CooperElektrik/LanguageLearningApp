"""The exercise-type list is a single source of truth.

These tests guard against the drift that produced two real bugs: the validator
rejected ``pronunciation_practice`` and the CSV importer had no
``fill_in_the_blank`` handling.
"""

from core.exercise_types import (
    ALL_EXERCISE_TYPES,
    CREATABLE_EXERCISE_TYPES,
    CSV_IMPORTABLE_TYPES,
    DICT_OPTION_TYPES,
    VALID_EXERCISE_TYPES,
    ExerciseType,
)


def test_all_types_are_unique():
    assert len(ALL_EXERCISE_TYPES) == len(set(ALL_EXERCISE_TYPES))


def test_enum_values_match_the_list():
    assert set(ALL_EXERCISE_TYPES) == {t.value for t in ExerciseType}


def test_pronunciation_is_valid_but_not_creatable():
    assert ExerciseType.PRONUNCIATION_PRACTICE.value in VALID_EXERCISE_TYPES
    assert ExerciseType.PRONUNCIATION_PRACTICE.value not in CREATABLE_EXERCISE_TYPES


def test_fill_in_the_blank_is_csv_importable():
    assert ExerciseType.FILL_IN_THE_BLANK.value in CSV_IMPORTABLE_TYPES


def test_creatable_and_csv_importable_are_subsets_of_valid():
    assert set(CREATABLE_EXERCISE_TYPES) <= set(VALID_EXERCISE_TYPES)
    assert set(CSV_IMPORTABLE_TYPES) <= set(VALID_EXERCISE_TYPES)


def test_dict_option_types_are_valid():
    assert DICT_OPTION_TYPES <= set(VALID_EXERCISE_TYPES)


def test_enum_members_compare_equal_to_raw_strings():
    assert ExerciseType.TRANSLATE_TO_TARGET == "translate_to_target"

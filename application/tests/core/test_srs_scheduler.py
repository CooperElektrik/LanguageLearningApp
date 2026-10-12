"""The SM-2 update was extracted into a pure function; pin its behaviour."""

from datetime import datetime

from core.progress_manager import (
    SM2_DEFAULT_EASE_FACTOR,
    SM2_MIN_EASE_FACTOR,
    apply_sm2_review,
    default_srs_record,
)

NOW = datetime(2026, 1, 1, 12, 0, 0)


def test_default_record_shape():
    record = default_srs_record()
    assert record["ease_factor"] == SM2_DEFAULT_EASE_FACTOR
    assert record["repetitions"] == 0
    assert record["interval_days"] == 0
    assert record["is_initially_learned"] is False


def test_first_successful_review_schedules_one_day():
    record = apply_sm2_review(default_srs_record(), 4, now=NOW)
    assert record["repetitions"] == 1
    assert record["interval_days"] == 1
    assert record["is_initially_learned"] is True
    assert record["last_reviewed"] == NOW
    assert record["next_review_due"] == datetime(2026, 1, 2, 12, 0, 0)


def test_second_successful_review_schedules_six_days():
    record = apply_sm2_review(default_srs_record(), 4, now=NOW)
    record = apply_sm2_review(record, 4, now=NOW)
    assert record["repetitions"] == 2
    assert record["interval_days"] == 6


def test_incorrect_review_resets_and_lowers_ease():
    record = apply_sm2_review(default_srs_record(), 5, now=NOW)
    ease_before = record["ease_factor"]
    record = apply_sm2_review(record, 0, now=NOW)
    assert record["repetitions"] == 0
    assert record["correct_in_a_row"] == 0
    assert record["interval_days"] == 0
    assert record["ease_factor"] < ease_before


def test_ease_factor_never_drops_below_floor():
    record = default_srs_record()
    for _ in range(50):
        apply_sm2_review(record, 0, now=NOW)
    assert record["ease_factor"] == SM2_MIN_EASE_FACTOR


def test_review_does_not_mutate_shared_state_semantically():
    # The function is pure w.r.t. the clock, so two identical records stay equal.
    a = apply_sm2_review(default_srs_record(), 4, now=NOW)
    b = apply_sm2_review(default_srs_record(), 4, now=NOW)
    assert a == b

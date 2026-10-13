"""
application/tests/core/test_diff_utils.py

Tests for diff_utils character and word-level HTML diff generation.
"""

from application.core.diff_utils import (
    format_feedback_card,
    generate_diff_html,
    strip_accents_and_case,
)


def test_strip_accents_and_case():
    assert strip_accents_and_case("Café") == "cafe"
    assert strip_accents_and_case("Xin Chào") == "xin chao"
    assert strip_accents_and_case("Bonjour") == "bonjour"


def test_generate_diff_html_exact_match():
    html = generate_diff_html("Hello World", "Hello World")
    assert "Hello World" in html
    assert "color: #2e7d32" in html


def test_generate_diff_html_empty_actual():
    html = generate_diff_html("Expected Text", "")
    assert "Expected:" in html
    assert "Expected Text" in html


def test_generate_diff_html_accent_difference():
    # Accent difference should trigger close match styling
    html = generate_diff_html("Xin chào", "Xin chao")
    assert "border-bottom: 2px dashed" in html or "title=" in html


def test_generate_diff_html_incorrect_spelling():
    html = generate_diff_html("banana", "babana")
    assert "line-through" in html


def test_format_feedback_card():
    # Exact match
    card = format_feedback_card(True, False, "hello", "hello")
    assert "Correct: hello" in card

    # Close match
    card_close = format_feedback_card(True, True, "Xin chào", "Xin chao")
    assert "Accepted (close match)" in card_close
    assert "Comparison:" in card_close

    # Incorrect
    card_wrong = format_feedback_card(
        False, False, "apple", "orange", explanation="An apple is a red fruit"
    )
    assert "Incorrect" in card_wrong
    assert "apple" in card_wrong
    assert "orange" in card_wrong
    assert "Explanation:" in card_wrong

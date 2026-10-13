"""
application/core/diff_utils.py

Provides character and word-level diff utilities for learner answer feedback.
Generates rich HTML diff markup with color-coding for correct, close, missing,
and extra characters/words.
"""

import difflib
import html
import re
import unicodedata


def strip_accents_and_case(text: str) -> str:
    """Removes diacritics and converts to lowercase for accent-insensitive comparison."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def generate_diff_html(expected: str, actual: str, for_speech: bool = False) -> str:
    """
    Generates an HTML snippet comparing ``actual`` (user input) against ``expected``.
    
    Styling:
    - Exact matches: Green text
    - Close matches (e.g. missing diacritics or capitalization): Amber/Yellow badge
    - Missing expected characters/words: Strikethrough red/rose badge
    - Erroneous / extra characters/words: Red badge
    """
    if not actual:
        return (
            f'<div style="margin-top: 4px;">'
            f'<span style="color: #c62828; font-weight: bold;">Expected:</span> '
            f'<span style="color: #2e7d32; font-weight: bold;">{html.escape(expected)}</span>'
            f'</div>'
        )

    expected_clean = expected.strip()
    actual_clean = actual.strip()

    if expected_clean == actual_clean:
        return (
            f'<span style="color: #2e7d32; font-weight: bold;">'
            f'{html.escape(actual_clean)}</span>'
        )

    # If the strings have spaces, perform word-level diff with character-level sub-diff
    expected_words = re.findall(r"\S+|\s+", expected_clean)
    actual_words = re.findall(r"\S+|\s+", actual_clean)

    matcher = difflib.SequenceMatcher(None, expected_clean, actual_clean)
    similarity = matcher.ratio()

    # For sentence or phrase comparisons, character-level sequence matching
    diff_parts = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        exp_chunk = html.escape(expected_clean[i1:i2])
        act_chunk = html.escape(actual_clean[j1:j2])

        if tag == "equal":
            diff_parts.append(
                f'<span style="color: #2e7d32; font-weight: 600;">{act_chunk}</span>'
            )
        elif tag == "replace":
            # Check if this is just an accent or case difference
            clean_exp = strip_accents_and_case(expected_clean[i1:i2])
            clean_act = strip_accents_and_case(actual_clean[j1:j2])
            if clean_exp == clean_act:
                # Close match / diacritic mismatch
                diff_parts.append(
                    f'<span style="background-color: #fff3e0; color: #e65100; border-bottom: 2px dashed #f57c00; font-weight: 600; padding: 1px 3px; border-radius: 3px;" title="Check accents/casing. Expected: {exp_chunk}">{act_chunk}</span>'
                )
            else:
                diff_parts.append(
                    f'<span style="background-color: #ffebee; color: #c62828; text-decoration: line-through; padding: 1px 3px; border-radius: 3px;">{act_chunk}</span>'
                    f'<span style="background-color: #e8f5e9; color: #1b5e20; font-weight: bold; padding: 1px 3px; border-radius: 3px; margin-left: 2px;">{exp_chunk}</span>'
                )
        elif tag == "delete":
            # Expected had something user omitted
            diff_parts.append(
                f'<span style="background-color: #e8f5e9; color: #1b5e20; font-weight: bold; padding: 1px 3px; border-radius: 3px;" title="Missing text">{exp_chunk}</span>'
            )
        elif tag == "insert":
            # User added unexpected text
            diff_parts.append(
                f'<span style="background-color: #ffebee; color: #c62828; text-decoration: line-through; padding: 1px 3px; border-radius: 3px;" title="Extra text">{act_chunk}</span>'
            )

    diff_html = "".join(diff_parts).replace("\n", "<br>")
    return diff_html


def format_feedback_card(
    is_correct: bool,
    is_close_match: bool,
    expected: str,
    actual: str,
    explanation: str = "",
) -> str:
    """
    Renders an HTML card for exercise feedback labels.
    Retains standard text patterns like 'Correct: ...' for backward compatibility.
    """
    expected_esc = html.escape(expected)
    actual_esc = html.escape(actual)

    if is_correct and not is_close_match:
        status_badge = '<span style="color: #2e7d32; font-weight: bold; font-size: 14px;">✓ Correct: {0}</span>'.format(expected_esc)
        return status_badge

    diff_markup = generate_diff_html(expected, actual)

    if is_correct and is_close_match:
        header = f'<span style="color: #e65100; font-weight: bold; font-size: 14px;">~ Accepted (close match). Correct: {expected_esc}. You wrote: {actual_esc}</span>'
        diff_view = f'<div style="margin-top: 4px; font-size: 13px;"><b>Comparison:</b> {diff_markup}</div>'
        return f"{header}<br>{diff_view}"

    # Incorrect
    header = f'<span style="color: #c62828; font-weight: bold; font-size: 14px;">✗ Incorrect. Correct: {expected_esc}. You wrote: {actual_esc}</span>'
    diff_view = f'<div style="margin-top: 4px; font-size: 13px;"><b>Correction:</b> {diff_markup}</div>'

    if explanation:
        exp_markup = f'<div style="margin-top: 6px; color: #555566; font-style: italic;"><b>Explanation:</b> {html.escape(explanation)}</div>'
        return f"{header}<br>{diff_view}{exp_markup}"

    return f"{header}<br>{diff_view}"

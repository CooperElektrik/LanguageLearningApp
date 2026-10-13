"""
application/tests/core/test_ui_overhaul.py

Tests verifying UI/UX overhaul components:
- Retention statistics in ProgressManager
- AudioLevelMeter PCM processing
- ValidationIssue backwards compatibility & structure
- CourseTreeWidget type and asset badges
"""

import math
import struct

from PySide6.QtWidgets import QApplication

from application.core.models import Exercise
from application.core.progress_manager import ProgressManager
from application.tools.course_validator import ValidationIssue
from application.tools.widgets.course_tree_widget import CourseTreeWidget
from application.ui.widgets.audio_level_meter import AudioLevelMeter


def test_validation_issue_str_compatibility():
    issue = ValidationIssue(
        "Invalid audio path",
        severity="error",
        unit_id="u1",
        lesson_id="l1",
        exercise_id="ex1",
        field="audio_file",
    )
    # Must behave as a string
    assert isinstance(issue, str)
    assert "Invalid audio path" in issue
    assert str(issue) == "Invalid audio path"

    # Must preserve attributes
    assert issue.severity == "error"
    assert issue.unit_id == "u1"
    assert issue.lesson_id == "l1"
    assert issue.exercise_id == "ex1"
    assert issue.field == "audio_file"


def test_course_tree_widget_badges():
    assert CourseTreeWidget.get_exercise_type_badge("multiple_choice_translation") == "[MCQ]"
    assert CourseTreeWidget.get_exercise_type_badge("translate_to_target") == "[TRANS→]"
    assert CourseTreeWidget.get_exercise_type_badge("fill_in_the_blank") == "[FIB]"
    assert CourseTreeWidget.get_exercise_type_badge("dictation") == "[DICT]"

    ex = Exercise(
        exercise_id="ex1",
        type="dictation",
        prompt="Test",
        audio_file="audio.mp3",
        image_file="img.png",
    )
    badges = CourseTreeWidget.get_asset_badges(ex)
    assert "[AUDIO]" in badges
    assert "[IMAGE]" in badges

    ex_no_assets = Exercise(exercise_id="ex2", type="mcq", prompt="Test")
    assert CourseTreeWidget.get_asset_badges(ex_no_assets) == ""


def test_audio_level_meter_pcm_processing():
    # Silent audio (zeros)
    silent_pcm = struct.pack("<1024h", *([0] * 1024))
    assert AudioLevelMeter.calculate_pcm_level(silent_pcm) == 0.0

    # Loud audio (sine wave near full scale)
    samples = [int(math.sin(2 * math.pi * 440 * (i / 1024.0)) * 25000) for i in range(1024)]
    loud_pcm = struct.pack("<1024h", *samples)
    loud_level = AudioLevelMeter.calculate_pcm_level(loud_pcm)
    assert loud_level > 0.4

    # Widget level processing
    app = QApplication.instance()
    if not app:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication([])

    meter = AudioLevelMeter()
    assert meter._current_level == 0.0
    meter.process_pcm_bytes(silent_pcm)
    assert meter._target_level == 0.0
    meter.process_pcm_bytes(loud_pcm)
    assert meter._target_level > 0.4
    assert meter._peak_level >= meter._target_level


def test_progress_manager_retention_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "application.core.progress_manager.QStandardPaths.writableLocation",
        lambda _: str(tmp_path),
    )
    pm = ProgressManager("test_course_retention")

    ex1 = Exercise(exercise_id="ex1", type="mcq", prompt="P1")
    ex2 = Exercise(exercise_id="ex2", type="mcq", prompt="P2")
    exercises = [ex1, ex2]

    # No reviews initially
    stats = pm.get_retention_stats(exercises)
    assert stats["total_exercises"] == 2
    assert stats["learned_count"] == 0
    assert stats["mastered_count"] == 0
    assert stats["average_retention"] == 0.0

    # Review ex1 with high quality score (4)
    pm.update_exercise_srs_data("ex1", is_correct=True, xp_awarded=10, quality_score_sm2=4)
    # Review ex1 a second time
    pm.update_exercise_srs_data("ex1", is_correct=True, xp_awarded=10, quality_score_sm2=4)

    stats2 = pm.get_retention_stats(exercises)
    assert stats2["learned_count"] == 1
    assert stats2["mastered_count"] == 1
    assert stats2["average_retention"] >= 95.0

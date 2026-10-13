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

from PySide6.QtCore import Qt
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


def test_inspector_header_widget():
    app = QApplication.instance()
    if not app:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication([])

    from application.tools.widgets.inspector_header_widget import InspectorHeaderWidget

    header = InspectorHeaderWidget()
    header.set_context(
        entity_type="Unit",
        breadcrumb_parts=["German Course", "Unit 1"],
        title="Unit 1: Basics",
        is_dirty=False,
        has_error=False,
    )
    assert header.badge_label.text() == "[UNIT]"
    assert header.breadcrumb_label.text() == "German Course › Unit 1"
    assert header.title_label.text() == "Unit 1: Basics"
    assert "Saved" in header.status_label.text()

    # Dirty status
    header.set_context(
        entity_type="Lesson",
        breadcrumb_parts=["German Course", "Unit 1", "Lesson 1"],
        title="Lesson 1: Greetings",
        is_dirty=True,
    )
    assert header.badge_label.text() == "[LESSON]"
    assert "Unsaved Changes" in header.status_label.text()

    # Error status
    header.set_context(
        entity_type="Exercise",
        breadcrumb_parts=["German Course", "Unit 1", "Lesson 1", "MCQ"],
        title="Question 1",
        has_error=True,
    )
    assert "Validation Issue" in header.status_label.text()


def test_unit_and_lesson_editors():
    app = QApplication.instance()
    if not app:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication([])

    from application.core.models import Lesson, Unit
    from application.tools.widgets.lesson_editor_widget import LessonEditorWidget
    from application.tools.widgets.unit_editor_widget import UnitEditorWidget

    # Unit Editor
    unit = Unit(unit_id="u_001", title="Original Unit Title")
    unit_editor = UnitEditorWidget()
    unit_editor.load_unit(unit)

    assert unit_editor.unit_id_edit.text() == "u_001"
    assert unit_editor.unit_title_edit.text() == "Original Unit Title"

    changed_signals = []
    unit_editor.data_changed.connect(lambda: changed_signals.append("data"))
    unit_editor.title_changed.connect(lambda t: changed_signals.append(f"title:{t}"))

    unit_editor.unit_title_edit.setText("Updated Unit Title")
    assert unit.title == "Updated Unit Title"
    assert "data" in changed_signals
    assert "title:Updated Unit Title" in changed_signals

    assert unit_editor.focus_field("title") is True
    assert unit_editor.focus_field("unit_id") is True

    unit_editor.revert()
    assert unit_editor.unit_title_edit.text() == "Updated Unit Title"

    # Lesson Editor
    lesson = Lesson(lesson_id="l_001", title="Original Lesson Title", unit_id="u_001")
    lesson_editor = LessonEditorWidget()
    lesson_editor.load_lesson(lesson)

    assert lesson_editor.lesson_id_edit.text() == "l_001"
    assert lesson_editor.lesson_title_edit.text() == "Original Lesson Title"
    assert lesson_editor.parent_unit_id_edit.text() == "u_001"

    lesson_signals = []
    lesson_editor.data_changed.connect(lambda: lesson_signals.append("data"))
    lesson_editor.title_changed.connect(lambda t: lesson_signals.append(f"title:{t}"))

    lesson_editor.lesson_title_edit.setText("Updated Lesson Title")
    assert lesson.title == "Updated Lesson Title"
    assert "data" in lesson_signals
    assert "title:Updated Lesson Title" in lesson_signals

    assert lesson_editor.focus_field("title") is True
    assert lesson_editor.focus_field("lesson_id") is True


def test_editor_window_architecture():
    app = QApplication.instance()
    if not app:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication([])

    from application.core.models import Course, Exercise, Lesson, Unit
    from application.tools.editor_window import EditorWindow

    win = EditorWindow()
    # Populate test course structure
    c = Course(
        course_id="c1",
        title="Test Course",
        source_language="en",
        target_language="de",
        version="1.0",
        units=[
            Unit(
                unit_id="u1",
                title="Unit 1",
                lessons=[
                    Lesson(
                        lesson_id="l1",
                        title="Lesson 1",
                        unit_id="u1",
                        exercises=[
                            Exercise(
                                exercise_id="ex1",
                                type="multiple_choice_translation",
                                prompt="Choose the right word",
                                source_word="Hello",
                                options=[],
                            )
                        ],
                    )
                ],
            )
        ],
    )
    win.course_data = c
    win.manifest_data = {
        "course_id": "c1",
        "course_title": "Test Course",
        "source_language": "en",
        "target_language": "de",
    }
    win.update_tree_view()

    # 1. 2-Pane Master Splitter
    assert hasattr(win, "master_splitter")
    assert win.master_splitter.count() == 2
    assert win.master_splitter.widget(0).objectName() == "LeftNavPane"
    assert win.master_splitter.widget(1).objectName() == "CenterInspectorPane"

    # Backward compatibility aliases
    assert win.splitter is win.master_splitter
    assert win.three_pane_splitter is win.master_splitter

    # 2. Dock Widgets
    assert hasattr(win, "preview_dock")
    assert hasattr(win, "asset_dock")
    assert hasattr(win, "problems_dock")
    assert win.preview_dock.objectName() == "LivePreviewDock"
    assert win.asset_dock.objectName() == "AssetHubDock"
    assert win.problems_dock.objectName() == "ProblemsDock"

    # 3. Inspector Scroll Area
    assert hasattr(win, "inspector_scroll_area")
    assert win.inspector_scroll_area.widgetResizable() is True

    # 4. Root Items in Tree
    assert win.tree_widget.topLevelItemCount() == 3  # Course Settings, Glossary, Unit 1
    item0 = win.tree_widget.topLevelItem(0)
    item1 = win.tree_widget.topLevelItem(1)
    item2 = win.tree_widget.topLevelItem(2)

    assert item0.data(0, Qt.UserRole)["type"] == "manifest"
    assert "Course Settings" in item0.text(0)
    assert item1.data(0, Qt.UserRole)["type"] == "glossary"
    assert "Glossary" in item1.text(0)
    assert isinstance(item2.data(0, Qt.UserRole), Unit)
    assert item2.text(0) == "Unit 1"

    # Verify no pseudo items (+ Add Lesson..., + Add Exercise...) in tree
    assert item2.childCount() == 1  # only Lesson 1
    lesson_item = item2.child(0)
    assert isinstance(lesson_item.data(0, Qt.UserRole), Lesson)
    assert lesson_item.childCount() == 1  # only ex1
    ex_item = lesson_item.child(0)
    assert isinstance(ex_item.data(0, Qt.UserRole), Exercise)

    # 5. Header Toolbar and Reorder buttons
    assert hasattr(win, "add_item_btn")
    assert hasattr(win, "move_up_btn")
    assert hasattr(win, "move_down_btn")
    assert hasattr(win, "expand_all_button")
    assert hasattr(win, "collapse_all_button")

    # 6. Selecting items updates InspectorHeaderWidget
    win.tree_widget.setCurrentItem(item0)
    assert win.inspector_header.badge_label.text() == "[SETTINGS]"

    win.tree_widget.setCurrentItem(item1)
    assert win.inspector_header.badge_label.text() == "[GLOSSARY]"

    win.tree_widget.setCurrentItem(item2)
    assert win.inspector_header.badge_label.text() == "[UNIT]"
    assert win.inspector_header.title_label.text() == "Unit 1"

    win.tree_widget.setCurrentItem(lesson_item)
    assert win.inspector_header.badge_label.text() == "[LESSON]"
    assert win.inspector_header.title_label.text() == "Lesson 1"

    win.tree_widget.setCurrentItem(ex_item)
    assert "MCQ" in win.inspector_header.badge_label.text() or "MULTIPLE" in win.inspector_header.badge_label.text()

    # 7. Navigation action additions
    target_unit = c.units[0]
    initial_lessons_count = len(target_unit.lessons)
    win.tree_widget.setCurrentItem(item2)
    win._add_lesson_from_nav()
    assert len(target_unit.lessons) == initial_lessons_count + 1

    # Cleanup
    win._set_dirty_state(False)
    win.close()

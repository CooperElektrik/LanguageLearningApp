"""
application/tests/core/test_ui_components_modular.py

Unit tests for standalone, modular UI components refactored to eliminate hackjobs:
- FlowLayout
- WordChip and TokenBankWidget
- OptionCardWidget and OptionGroupWidget
- AchievementCardWidget
- OptionsListEditorWidget
- AudioRecordingController
- PronunciationFeedbackView
- ExercisePreviewWidget & MockCourseManager
- Refactored ExerciseWidgets (SentenceJumble, ButtonOption, ContextBlock, Pronunciation)
- MainWindow dock and learning stack architecture
"""

import os
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout

from application.core.models import Exercise, ExerciseOption
from application.core.progress_manager import Achievement
from application.ui.widgets.flow_layout import FlowLayout
from application.ui.widgets.token_bank_widget import TokenBankWidget, WordChip
from application.ui.widgets.option_card_widget import OptionCardWidget, OptionGroupWidget
from application.ui.widgets.achievement_card_widget import AchievementCardWidget
from application.tools.widgets.options_list_editor_widget import OptionsListEditorWidget
from application.ui.widgets.audio_recording_controller import AudioRecordingController
from application.ui.widgets.pronunciation_feedback_view import PronunciationFeedbackView
from application.tools.widgets.exercise_preview_widget import (
    ExercisePreviewWidget,
    MockCourseManager,
)
from application.tools.widgets.live_preview_pane import LivePreviewPane
from application.tools.dialogs.exercise_preview_dialog import ExercisePreviewDialog
from application.ui.widgets.exercise_widgets import (
    SentenceJumbleExerciseWidget,
    ButtonOptionExerciseWidget,
    ContextBlockWidget,
    PronunciationExerciseWidget,
)


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


# ==============================================================================
# 1. FlowLayout Tests
# ==============================================================================
def test_flow_layout_basic(qapp):
    container = QWidget()
    layout = FlowLayout(container, margin=5, h_spacing=10, v_spacing=10)
    assert layout.count() == 0

    btn1 = QPushButton("One")
    btn2 = QPushButton("Two")
    btn3 = QPushButton("Three")

    layout.addWidget(btn1)
    layout.addWidget(btn2)
    layout.addWidget(btn3)

    assert layout.count() == 3
    assert layout.itemAt(0).widget() is btn1
    assert layout.itemAt(1).widget() is btn2
    assert layout.itemAt(2).widget() is btn3

    # Size hint should be positive
    hint = layout.sizeHint()
    assert hint.width() > 0
    assert hint.height() > 0

    # Minimum size should be valid
    min_size = layout.minimumSize()
    assert min_size.width() >= 0
    assert min_size.height() >= 0

    # Take an item
    taken = layout.takeAt(1)
    assert taken.widget() is btn2
    assert layout.count() == 2

    # Cleanup
    container.deleteLater()


# ==============================================================================
# 2. WordChip & TokenBankWidget Tests
# ==============================================================================
def test_token_bank_widget(qapp):
    words = ["I", "like", "apples", "and", "apples"]
    bank = TokenBankWidget(words=words)

    # 5 tokens created with unique IDs despite duplicate words
    assert len(bank._tokens) == 5
    assert len(bank._bank_chips) == 5
    assert len(bank._sentence_tokens) == 0
    assert bank.get_sentence() == ""

    # Add first token
    bank.add_token_to_sentence(0)
    assert len(bank._sentence_tokens) == 1
    assert bank.get_words() == [bank._tokens[0].text]
    assert not bank._bank_chips[0].isEnabled()

    # Add second token
    bank.add_token_to_sentence(1)
    assert len(bank._sentence_tokens) == 2
    assert bank.get_words() == [bank._tokens[0].text, bank._tokens[1].text]

    # Remove first token from sentence
    bank.remove_token_from_sentence(0)
    assert len(bank._sentence_tokens) == 1
    assert bank._bank_chips[0].isEnabled()

    # Reset returns all to bank
    bank.reset()
    assert len(bank._sentence_tokens) == 0
    assert bank.get_sentence() == ""

    # Clear removes all
    bank.clear()
    assert len(bank._tokens) == 0

    bank.deleteLater()


# ==============================================================================
# 3. OptionCardWidget & OptionGroupWidget Tests
# ==============================================================================
def test_option_card_and_group(qapp):
    card = OptionCardWidget(index=0, text="Option A", is_checkable=True)
    assert card.text() == "Option A"
    assert card.index == 0
    assert not card.isChecked()

    # Card click emission
    emitted = []
    card.clicked.connect(lambda: emitted.append(True))
    card.click()
    assert emitted == [True]
    assert card.isChecked()

    # Group widget
    group = OptionGroupWidget()
    group_emitted = []
    group.option_selected.connect(lambda idx: group_emitted.append(idx))

    options = [
        ExerciseOption(text="Red"),
        ExerciseOption(text="Green"),
        ExerciseOption(text="Blue"),
    ]
    group.set_options(options)
    assert len(group.buttons()) == 3
    assert group.get_selected_index() == -1

    # Select by index
    group.select_index(1)
    assert group.get_selected_index() == 1
    assert group.buttons()[1].isChecked()
    assert not group.buttons()[0].isChecked()

    # Number key
    group.handle_number_key(Qt.Key.Key_3)
    assert group.get_selected_index() == 2
    assert group.buttons()[2].isChecked()

    # Clear selection
    group.clear_selection()
    assert group.get_selected_index() == -1

    card.deleteLater()
    group.deleteLater()


# ==============================================================================
# 4. AchievementCardWidget Tests
# ==============================================================================
def test_achievement_card_widget(qapp):
    card = AchievementCardWidget(
        title="Week Warrior",
        description="Study for 7 consecutive days",
        is_unlocked=True,
        icon_filename="flame.png",
    )
    assert card.objectName() == "achievement_frame"
    assert "Week Warrior" in card.title_label.text()
    assert "Study for 7" in card.desc_label.text()
    assert card._is_unlocked is True

    # Test toggling unlocked state
    card.set_unlocked(False)
    assert card._is_unlocked is False

    card.deleteLater()


# ==============================================================================
# 5. OptionsListEditorWidget Tests
# ==============================================================================
def test_options_list_editor_widget(qapp):
    editor = OptionsListEditorWidget(heading="Choice Options", mode="mcq")
    assert editor.get_options() == []

    initial_options = [
        ExerciseOption(text="Apple", correct=True),
        ExerciseOption(text="Orange", correct=False),
    ]
    editor.load_options(initial_options)
    result = editor.get_options()
    assert len(result) == 2
    assert result[0].text == "Apple"
    assert result[0].correct is True
    assert result[1].text == "Orange"
    assert result[1].correct is False

    is_valid, msg = editor.validate()
    assert is_valid is True

    # Test FIB mode
    fib_editor = OptionsListEditorWidget(heading="FIB Options", mode="fib")
    fib_editor.load_options([
        ExerciseOption(text="cat", correct=False),
        ExerciseOption(text="dog", correct=False),
    ])
    fib_editor.set_target_blank_word("cat")
    is_valid, _ = fib_editor.validate()
    assert is_valid is True

    editor.deleteLater()
    fib_editor.deleteLater()


# ==============================================================================
# 6. AudioRecordingController Tests
# ==============================================================================
def test_audio_recording_controller(qapp):
    controller = AudioRecordingController()
    assert not controller.is_recording()

    errors = []
    controller.error_occurred.connect(lambda msg: errors.append(msg))

    started = controller.start_recording()
    if not started:
        assert len(errors) >= 1
    else:
        assert controller.is_recording() is True
        controller.stop_recording()
        assert not controller.is_recording()

    controller._cleanup_temp_file()
    controller.deleteLater()


# ==============================================================================
# 7. PronunciationFeedbackView Tests
# ==============================================================================
def test_pronunciation_feedback_view(qapp):
    feedback_view = PronunciationFeedbackView()
    assert feedback_view.objectName() == "pronunciation_feedback_group"

    feedback_view.display_results(
        target_text="Bonjour",
        transcribed_text="Bonjour",
        words=[{"word": "Bonjour", "confidence": 0.95}],
        engine="TestEngine",
        is_final=True,
    )
    assert feedback_view.feedback_browser.toPlainText() != ""
    assert feedback_view.try_again_button.isVisible()
    assert feedback_view.submit_button.isVisible()

    # Reset
    feedback_view.reset_view()
    assert feedback_view.feedback_browser.toPlainText() == ""

    feedback_view.deleteLater()


# ==============================================================================
# 8. ExercisePreviewWidget & Subclasses Tests
# ==============================================================================
def test_exercise_preview_widget(qapp):
    mock_mgr = MockCourseManager(
        manifest={"course_title": "Test Course", "target_language": "es"}
    )
    assert mock_mgr.get_course_title() == "Test Course"

    preview = ExercisePreviewWidget()
    ex = Exercise(
        exercise_id="mcq1",
        type="multiple_choice_translation",
        prompt="Select the Spanish word for 'cat'",
        options=[
            ExerciseOption(text="el gato", correct=True),
            ExerciseOption(text="el perro", correct=False),
        ],
    )
    preview.update_preview(ex)
    assert preview.current_exercise is ex
    assert preview.current_preview_widget is not None

    # Test LivePreviewPane wrapper
    pane = LivePreviewPane()
    pane.update_preview(ex)
    assert pane.current_exercise is ex

    # Test ExercisePreviewDialog
    dialog = ExercisePreviewDialog(ex, course_manager=mock_mgr)
    assert dialog.exercise is ex
    assert dialog.preview_widget.current_exercise is ex

    preview.deleteLater()
    pane.deleteLater()
    dialog.deleteLater()


# ==============================================================================
# 9. Refactored Exercise Widgets Tests
# ==============================================================================
def test_sentence_jumble_exercise_widget(qapp):
    ex = Exercise(
        exercise_id="jumble1",
        type="sentence_jumble",
        prompt="Arrange the words",
        words=["The", "cat", "sat"],
        answer="The cat sat",
    )
    mock_mgr = MockCourseManager()
    widget = SentenceJumbleExerciseWidget(ex, mock_mgr)
    assert len(widget.token_bank._tokens) == 3
    assert widget.get_answer() == ""

    # Move words into sentence by matching token text
    word_map = {t.text: t.token_id for t in widget.token_bank._tokens}
    for word in ["The", "cat", "sat"]:
        widget.token_bank.add_token_to_sentence(word_map[word])

    assert len(widget.token_bank._sentence_tokens) == 3
    assert widget.get_answer() == "The cat sat"
    assert widget.current_sentence_words == ["The", "cat", "sat"]

    # Clear answer
    widget.clear_input()
    assert len(widget.token_bank._sentence_tokens) == 0
    assert widget.get_answer() == ""

    widget.deleteLater()


def test_button_option_exercise_widget(qapp):
    ex = Exercise(
        exercise_id="btn_mcq",
        type="multiple_choice_translation",
        prompt="Select the correct word",
        options=[
            ExerciseOption(text="Uno", correct=True),
            ExerciseOption(text="Dos", correct=False),
            ExerciseOption(text="Tres", correct=False),
        ],
    )
    mock_mgr = MockCourseManager()
    widget = ButtonOptionExerciseWidget(ex, mock_mgr)
    assert hasattr(widget, "options_group")
    assert len(widget.options_group.buttons()) == 3
    assert widget.get_answer() == ""

    # Select second option
    widget.option_group.select_index(1)
    assert widget.get_answer() == "1"

    widget.clear_input()
    assert widget.get_answer() == ""

    widget.deleteLater()


def test_context_block_widget(qapp):
    ex = Exercise(
        exercise_id="ctx1",
        type="context_block",
        prompt="Read this story",
        raw_data={"content": "# A story\nOnce upon a time..."},
    )
    mock_mgr = MockCourseManager()
    widget = ContextBlockWidget(ex, mock_mgr)
    assert widget.has_integrated_submission is True
    assert widget.is_interactive_exercise is False

    # Check Continue button emission
    submitted = []
    widget.answer_submitted.connect(lambda ans: submitted.append(ans))
    widget.continue_button.click()
    assert len(submitted) == 1
    assert submitted[0] == "completed"

    widget.deleteLater()


def test_pronunciation_exercise_widget(qapp):
    from unittest.mock import MagicMock
    mock_stt = MagicMock()
    ex = Exercise(
        exercise_id="pron1",
        type="pronunciation",
        prompt="Say 'bonjour'",
        target_pronunciation_text="bonjour",
    )
    mock_mgr = MockCourseManager()
    widget = PronunciationExerciseWidget(ex, mock_mgr, mock_stt)
    assert widget.recording_controller is not None
    assert widget.feedback_view is not None
    # Backward compatibility aliases
    assert widget.feedback_group is widget.feedback_view
    assert widget.feedback_browser is widget.feedback_view.feedback_browser
    assert widget.try_again_button is widget.feedback_view.try_again_button
    assert widget.submit_feedback_button is widget.feedback_view.submit_button

    widget.deleteLater()


# ==============================================================================
# 10. MainWindow Architecture Tests
# ==============================================================================
def test_main_window_dock_and_learning_architecture(qapp, tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from application.core.progress_manager import ProgressManager
    from application.ui.main_window import MainWindow

    monkeypatch.setattr(
        "application.core.progress_manager.QStandardPaths.writableLocation",
        lambda _: str(tmp_path),
    )
    monkeypatch.setattr(
        MainWindow, "_check_and_show_initial_setup", lambda self: None
    )
    monkeypatch.setattr(
        MainWindow, "_check_and_show_onboarding", lambda self: None
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.information", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.warning", lambda *args, **kwargs: None
    )

    mock_stt = MagicMock()
    win = MainWindow(stt_manager=mock_stt)
    # Initially at selection screen
    assert win.learning_widget is None
    assert win.navigation_dock_widget is None
    assert win.progress_dock_widget is None

    # Simulate entering learning mode
    mock_mgr = MockCourseManager(
        manifest={"course_title": "Test Architecture", "course_id": "test_arch_1"}
    )
    win.course_manager = mock_mgr
    win.progress_manager = ProgressManager("test_arch_1")
    win._setup_learning_ui()

    # Docks must be hosted directly on MainWindow (not a nested QMainWindow)
    assert win.navigation_dock_widget is not None
    assert win.navigation_dock_widget.parent() is win
    assert win.progress_dock_widget is not None
    assert win.progress_dock_widget.parent() is win

    # Learning widget should be the stacked central view
    assert win.learning_widget is not None
    assert win.learning_widget.parent() is win.main_stack

    # Test start_lesson hides nav dock
    assert not win.navigation_dock_widget.isHidden()
    win.start_lesson("lesson_1")
    assert win.navigation_dock_widget.isHidden() is True

    # Test show_course_overview shows nav dock again
    win.show_course_overview()
    assert not win.navigation_dock_widget.isHidden()

    # Test start_review_session hides nav dock when exercises are due
    rev_ex = Exercise(exercise_id="rev1", type="multiple_choice_translation", prompt="Test")
    mock_mgr.get_all_exercises = lambda: [rev_ex]
    win.progress_manager.get_due_exercises = lambda *args, **kwargs: [rev_ex]

    win.start_review_session()
    assert win.navigation_dock_widget.isHidden() is True

    # Return to selection screen cleans up docks
    win._clear_dynamic_widgets()
    assert win.learning_widget is None
    assert win.navigation_dock_widget is None
    assert win.progress_dock_widget is None

    win.close()
    win.deleteLater()

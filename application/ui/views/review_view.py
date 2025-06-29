import logging
from enum import Enum, auto

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QStyle,
    QWidget,
    QVBoxLayout,
    QDialog,
)
from PySide6.QtCore import Signal, QTimer, Qt, QSettings, QEvent

from typing import List, Optional

import settings
import utils
from core.models import Exercise
from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from core.stt_manager import STTManager
from ui.views.base_exercise_player_view import BaseExercisePlayerView
from ui.widgets.exercise_widgets import TranslationExerciseWidget
from ..dialogs.glossary_detail_dialog import GlossaryDetailDialog
from ..dialogs.glossary_lookup_dialog import GlossaryLookupDialog
from PySide6.QtGui import QKeyEvent  # Added for keyPressEvent

logger = logging.getLogger(__name__)


class ReviewState(Enum):  # Specific to ReviewView's state machine
    INITIAL_LOAD = auto()  # View is first loaded or reset
    ASKING_QUESTION = auto()  # Displaying an exercise, awaiting submission
    ANSWER_SUBMITTED = auto()  # Answer processed, feedback shown, waiting for rating
    SESSION_ENDED = auto()  # All exercises done, session concluded


class ReviewView(BaseExercisePlayerView):  # Inherit from BaseExercisePlayerView
    review_session_finished = Signal()

    DEFAULT_REVIEW_LIMIT = 20

    def __init__(
        self,
        course_manager: CourseManager,
        progress_manager: ProgressManager,
        stt_manager: STTManager,
        parent=None,
    ):
        super().__init__(course_manager, progress_manager, stt_manager, parent)

        self.exercises_in_session: List[Exercise] = []
        self.current_exercise_index: int = -1
        self.total_exercises_in_session: int = 0

        self._current_session_name_for_retranslation: str = (
            "Review Session"  # For retranslation
        )
        self._last_submission_was_correct: bool = False
        self.view_state: ReviewState = ReviewState.INITIAL_LOAD

        self._setup_specific_ui()
        self.reset_view()

    def _setup_specific_ui(self):
        """Sets up UI elements specific to ReviewView, like its top bar and action buttons."""

        # Populate Top Bar (defined in Base)
        self.back_button = QPushButton(self.tr("← Back to Overview"))
        self.back_button.setObjectName("back_button_review")
        self.back_button.clicked.connect(self._handle_back_to_overview)
        self.top_bar_layout.addWidget(self.back_button)

        self.session_title_label = QLabel(self.tr("Review Session"))
        self.session_title_label.setObjectName("session_title_label")
        self.session_title_label.setAlignment(Qt.AlignCenter)
        self.top_bar_layout.addWidget(self.session_title_label, 1)

        # Configure Progress Bar (already added in Base)
        self.progress_bar.setFormat(self.tr("Review Progress: %v / %m"))

        # Populate Action Buttons Area (defined in Base)
        review_action_layout = QVBoxLayout()
        review_action_layout.setContentsMargins(0, 0, 0, 0)

        # Control Buttons (Submit, Show Answer, Toggle Notes)
        self.control_buttons_widget = QWidget()
        control_buttons_layout = QHBoxLayout(self.control_buttons_widget)
        control_buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.toggle_notes_button = QPushButton()
        self.toggle_notes_button.setObjectName("toggle_notes_button_review")
        self.toggle_notes_button.setCheckable(True)
        self.toggle_notes_button.toggled.connect(self._toggle_notes_panel)
        control_buttons_layout.addWidget(self.toggle_notes_button)

        self.toggle_hint_button = QPushButton(self.tr("Show Hint"))
        self.toggle_hint_button.setObjectName("toggle_hint_button_review")
        self.toggle_hint_button.setCheckable(False)
        self.toggle_hint_button.clicked.connect(self._toggle_hint_visibility_manually)
        control_buttons_layout.addWidget(self.toggle_hint_button)

        self.lookup_button = QPushButton(self.tr("Lookup..."))
        self.lookup_button.setObjectName("lookup_button_review")
        self.lookup_button.clicked.connect(self._handle_lookup_word)
        control_buttons_layout.addWidget(self.lookup_button)

        control_buttons_layout.addStretch(1)

        self.submit_button = QPushButton(self.tr("Submit Answer"))
        self.submit_button.setObjectName("submit_button_review")
        self.submit_button.clicked.connect(self._handle_user_submission_from_button)
        control_buttons_layout.addWidget(self.submit_button)

        self.show_answer_button = QPushButton(self.tr("Show Answer"))
        self.show_answer_button.setObjectName("show_answer_button_review")
        self.show_answer_button.clicked.connect(self._handle_show_answer)
        control_buttons_layout.addWidget(self.show_answer_button)
        review_action_layout.addWidget(self.control_buttons_widget)

        # Rating Buttons
        self.rating_buttons_widget = QWidget()
        rating_buttons_layout = QHBoxLayout(self.rating_buttons_widget)
        rating_buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.rating_button_again = QPushButton(self.tr("Again (1)"))
        self.rating_button_again.setObjectName("rating_again_button")
        self.rating_button_again.clicked.connect(lambda: self._handle_rating(0))

        self.rating_button_hard = QPushButton(self.tr("Hard (2)"))
        self.rating_button_hard.setObjectName("rating_hard_button")
        self.rating_button_hard.clicked.connect(lambda: self._handle_rating(3))

        self.rating_button_good = QPushButton(self.tr("Good (3)"))
        self.rating_button_good.setObjectName("rating_good_button")
        self.rating_button_good.clicked.connect(lambda: self._handle_rating(4))

        self.rating_button_easy = QPushButton(self.tr("Easy (4)"))
        self.rating_button_easy.setObjectName("rating_easy_button")
        self.rating_button_easy.clicked.connect(lambda: self._handle_rating(5))

        rating_buttons_layout.addStretch(1)
        rating_buttons_layout.addWidget(self.rating_button_again)
        rating_buttons_layout.addWidget(self.rating_button_hard)
        rating_buttons_layout.addWidget(self.rating_button_good)
        rating_buttons_layout.addWidget(self.rating_button_easy)
        rating_buttons_layout.addStretch(1)
        review_action_layout.addWidget(self.rating_buttons_widget)

        self.action_buttons_layout_container.addLayout(review_action_layout)

        self._update_button_states()

    def _update_button_states(self):
        """Updates visibility and enabled state of buttons based on view_state."""
        is_asking = self.view_state == ReviewState.ASKING_QUESTION
        is_submitted_or_shown = self.view_state == ReviewState.ANSWER_SUBMITTED
        is_session_ended = self.view_state == ReviewState.SESSION_ENDED
        is_initial = self.view_state == ReviewState.INITIAL_LOAD

        self.control_buttons_widget.setVisible(is_asking)
        self.submit_button.setEnabled(is_asking)
        self.show_answer_button.setEnabled(is_asking)

        self.rating_buttons_widget.setVisible(is_submitted_or_shown)
        self.rating_button_again.setEnabled(is_submitted_or_shown)
        self.rating_button_hard.setEnabled(is_submitted_or_shown)
        self.rating_button_good.setEnabled(is_submitted_or_shown)
        self.rating_button_easy.setEnabled(is_submitted_or_shown)

        self.toggle_notes_button.setEnabled(not is_session_ended and not is_initial)
        self.lookup_button.setEnabled(not is_session_ended and not is_initial)

        can_show_hint = (
            is_asking
            and self.current_exercise_obj
            and self.current_exercise_obj.has_hint()
        )
        self.toggle_hint_button.setVisible(can_show_hint)
        if logger.isEnabledFor(logging.DEBUG):  # Conditional logging
            logger.debug(
                f"_update_button_states (ReviewView): can_show_hint={can_show_hint}, "
                f"hint_label.isVisible()={self.hint_label.isVisible() if hasattr(self, 'hint_label') else 'N/A'}, "
                f"is_asking={is_asking}, current_exercise_obj exists={bool(self.current_exercise_obj)}"
            )
        if can_show_hint:
            self.toggle_hint_button.setText(
                self.tr("Hide Hint")
                if self.hint_label.isVisible()
                else self.tr("Show Hint")
            )

        if is_submitted_or_shown:
            if self._last_submission_was_correct:
                self.rating_button_good.setFocus()
            else:
                self.rating_button_again.setFocus()
        elif is_asking and self.current_exercise_widget:
            self.current_exercise_widget.set_focus_on_input()

    def start_review_session(
        self,
        exercises: Optional[List[Exercise]] = None,
        session_name: str = "Review Session",
    ):
        super()._save_current_note()
        self._current_session_name_for_retranslation = (
            session_name  # Store for retranslation
        )
        self.reset_view()

        if exercises is not None:
            self.exercises_in_session = exercises[: self.DEFAULT_REVIEW_LIMIT]
        else:  # Default behavior: get due exercises
            self.exercises_in_session = self.progress_manager.get_due_exercises(
                self.course_manager.get_all_exercises(), limit=self.DEFAULT_REVIEW_LIMIT
            )

        self.total_exercises_in_session = len(self.exercises_in_session)

        if self.total_exercises_in_session == 0:
            QMessageBox.information(
                self,
                self.tr("Review Session"),
                self.tr("No exercises to review in this session!"),
            )
            self.view_state = ReviewState.SESSION_ENDED
            self._update_button_states()
            self.back_to_overview_signal.emit()
            return

        self.current_exercise_index = 0
        self.session_title_label.setText(
            self.tr("{0} ({1} exercises)").format(
                self.tr(session_name), self.total_exercises_in_session
            )
        )
        self.progress_bar.setRange(0, self.total_exercises_in_session)
        self.progress_bar.setValue(0)

        self._load_next_review_exercise()

    def _load_next_review_exercise(self):
        super()._save_current_note()
        self.feedback_label.setText("")  # Clear feedback label
        # self._toggle_hint_visibility(force_show=False) # Done by _load_exercise_widget in base

        self.feedback_label.setText("")
        self.feedback_label.setStyleSheet("")

        if self.current_exercise_index >= self.total_exercises_in_session:
            self._finish_review_session()
            return

        exercise_to_load = self.exercises_in_session[self.current_exercise_index]

        if super()._load_exercise_widget(exercise_to_load):
            if self.current_exercise_widget:
                self.current_exercise_widget.answer_submitted.connect(
                    self._handle_user_submission_from_widget
                )

            self._check_and_auto_show_hint()  # Auto-show from base class
            # Button states (including hint button text) updated at the end of this method
            self.view_state = ReviewState.ASKING_QUESTION
        else:
            self.feedback_label.setText(
                self.tr("Error loading exercise. Please rate to continue.")
            )
            self.feedback_label.setStyleSheet("color: red;")
            self.view_state = ReviewState.ANSWER_SUBMITTED

        # Defer button state update to ensure UI changes (like hint visibility) are processed
        QTimer.singleShot(0, self._update_button_states)

    def _toggle_hint_visibility_manually(self):
        """Handles manual click on the Show/Hide Hint button."""
        if self.current_exercise_obj and self.current_exercise_obj.has_hint():
            super()._toggle_hint_visibility()  # Call base class method
            self.toggle_hint_button.setText(
                self.tr("Hide Hint")
                if self.hint_label.isVisible()
                else self.tr("Show Hint")
            )

    def _handle_user_submission_from_button(self):
        if (
            self.current_exercise_widget
            and self.view_state == ReviewState.ASKING_QUESTION
        ):
            user_answer = self.current_exercise_widget.get_answer()
            self._process_submission(user_answer, was_shown=False)

    def _handle_user_submission_from_widget(self, user_answer: str):
        if self.view_state == ReviewState.ASKING_QUESTION:
            self._process_submission(user_answer, was_shown=False)

    def _process_submission(self, user_answer: str, was_shown: bool):
        if (
            not self.current_exercise_obj
            or self.view_state != ReviewState.ASKING_QUESTION
        ):
            return
        self._toggle_hint_visibility(force_show=False)  # Hide hint on submission

        if not user_answer.strip() and isinstance(
            self.current_exercise_widget, TranslationExerciseWidget
        ):
            self.feedback_label.setText(self.tr("Please provide an answer."))
            self.feedback_label.setStyleSheet("color: orange;")
            return

        is_correct, feedback_text = self.course_manager.check_answer(
            self.current_exercise_obj, user_answer
        )

        self.feedback_label.setText(feedback_text)
        self.feedback_label.setStyleSheet(
            "color: green;" if is_correct else "color: red;"
        )
        utils.play_sound(
            settings.SOUND_FILE_CORRECT if is_correct else settings.SOUND_FILE_INCORRECT
        )

        if not is_correct and self.current_exercise_obj.explanation:
            current_feedback = self.feedback_label.text()
            self.feedback_label.setText(
                current_feedback
                + self.tr("\n\nExplanation: {0}").format(
                    self.current_exercise_obj.explanation
                )
            )

        self._last_submission_was_correct = is_correct
        self.view_state = ReviewState.ANSWER_SUBMITTED
        self._update_button_states()

    def _handle_show_answer(self):
        if (
            not self.current_exercise_obj
            or self.view_state != ReviewState.ASKING_QUESTION
        ):
            return
        self._toggle_hint_visibility(force_show=False)  # Hide hint when answer is shown

        correct_answer_for_display = "N/A"
        if self.current_exercise_obj.type in [
            "translate_to_target",
            "translate_to_source",
        ]:
            correct_answer_for_display = self.current_exercise_obj.answer
        elif self.current_exercise_obj.type in [
            "multiple_choice_translation",
            "image_association",
            "listen_and_select",
        ]:
            correct_option = next(
                (opt for opt in self.current_exercise_obj.options if opt.correct), None
            )
            if correct_option:
                correct_answer_for_display = correct_option.text
        elif self.current_exercise_obj.type == "fill_in_the_blank":
            correct_answer_for_display = self.current_exercise_obj.correct_option

        feedback_message = self.tr("Correct answer: {0}").format(
            correct_answer_for_display or "N/A"
        )
        if self.current_exercise_obj.explanation:
            feedback_message += self.tr("\n\nExplanation: {0}").format(
                self.current_exercise_obj.explanation
            )

        self.feedback_label.setText(feedback_message)
        self.feedback_label.setStyleSheet("color: blue;")

        self._last_submission_was_correct = False
        self.view_state = ReviewState.ANSWER_SUBMITTED
        self._update_button_states()

    def _handle_rating(self, quality_score_sm2: int):  # 0, 3, 4, 5
        if (
            not self.current_exercise_obj
            or self.view_state != ReviewState.ANSWER_SUBMITTED
        ):
            return

        xp_awarded_for_review = (
            10 if quality_score_sm2 >= 3 else (5 if quality_score_sm2 >= 1 else 0)
        )

        self.progress_manager.update_exercise_srs_data(
            self.current_exercise_obj.exercise_id,
            is_correct=(quality_score_sm2 >= 3),
            xp_awarded=xp_awarded_for_review,
            quality_score_sm2=quality_score_sm2,
        )

        self.current_exercise_index += 1
        self.progress_bar.setValue(self.current_exercise_index)
        self._load_next_review_exercise()

    def _finish_review_session(self):
        self.view_state = ReviewState.SESSION_ENDED
        self._update_button_states()
        super()._save_current_note()
        utils.play_sound(settings.SOUND_FILE_COMPLETE)
        QMessageBox.information(
            self,
            self.tr("Review Session Complete"),
            self.tr(
                "You've completed this review session! Total exercises: {0}"
            ).format(self.total_exercises_in_session),
        )
        self.review_session_finished.emit()

    def reset_view(self):
        super().reset_view()

        self.current_exercise_index = -1
        self.exercises_in_session = []
        self.total_exercises_in_session = 0
        self._last_submission_was_correct = False

        self.session_title_label.setText(self.tr("Review Session"))
        self.progress_bar.setFormat(self.tr("Review Progress: %v / %m"))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.view_state = ReviewState.INITIAL_LOAD
        self._update_button_states()

    def _handle_lookup_word(self):
        """Opens a dialog to search for a word in the glossary."""
        if not self.course_manager.get_glossary_entries():
            QMessageBox.information(
                self,
                self.tr("Glossary Empty"),
                self.tr("No glossary entries available for this course."),
            )
            return

        dialog = GlossaryLookupDialog(self.course_manager.get_glossary_entries(), self)
        result = dialog.exec()

        if result == QDialog.Accepted:
            found_entry = dialog.get_selected_entry()
            if found_entry:
                dialog = GlossaryDetailDialog(found_entry, self.course_manager, self)
                dialog.exec()

    def keyPressEvent(self, event: QKeyEvent):
        """Handles keyboard shortcuts specific to ReviewView, like rating."""
        if self.view_state == ReviewState.ANSWER_SUBMITTED:
            key_map = {
                Qt.Key_1: 0,  # Again
                Qt.Key_2: 3,  # Hard
                Qt.Key_3: 4,  # Good
                Qt.Key_4: 5,  # Easy
            }
            if event.key() in key_map:
                if (
                    self.rating_buttons_widget.isVisible()
                ):  # Ensure rating buttons are active
                    quality_score = key_map[event.key()]
                    logger.debug(
                        f"Rating key '{event.text()}' pressed, calling _handle_rating({quality_score})"
                    )
                    self._handle_rating(quality_score)
                    event.accept()
                    return

        # Pass unhandled events to the base class (for Ctrl+H, Ctrl+N)
        super().keyPressEvent(event)

    # Note: changeEvent for retranslation is already in the base class and inherited.

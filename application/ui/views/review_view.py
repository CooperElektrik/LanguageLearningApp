import logging
from enum import Enum, auto

from PySide6.QtWidgets import (
    QLabel, QPushButton, QHBoxLayout, QMessageBox, QStyle, QWidget, QVBoxLayout
)
from PySide6.QtCore import Signal, QTimer, Qt

from typing import List, Optional

from core.models import Exercise
from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.views.base_exercise_player_view import BaseExercisePlayerView
from ui.widgets.exercise_widgets import TranslationExerciseWidget

logger = logging.getLogger(__name__)

class ReviewState(Enum): # Specific to ReviewView's state machine
    INITIAL_LOAD = auto()       # View is first loaded or reset
    ASKING_QUESTION = auto()    # Displaying an exercise, awaiting submission
    ANSWER_SUBMITTED = auto()   # Answer processed, feedback shown, waiting for rating
    SESSION_ENDED = auto()      # All exercises done, session concluded


class ReviewView(BaseExercisePlayerView): # Inherit from BaseExercisePlayerView
    review_session_finished = Signal()

    DEFAULT_REVIEW_LIMIT = 20

    def __init__(
        self,
        course_manager: CourseManager,
        progress_manager: ProgressManager,
        parent=None,
    ):
        super().__init__(course_manager, progress_manager, parent)

        self.due_exercises: List[Exercise] = []
        self.current_exercise_index: int = -1
        self.total_exercises_in_session: int = 0
        
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
        # Create a QVBoxLayout to hold control buttons AND rating buttons
        review_action_layout = QVBoxLayout()
        review_action_layout.setContentsMargins(0,0,0,0)

        # Control Buttons (Submit, Show Answer, Toggle Notes)
        self.control_buttons_widget = QWidget() # Container for control buttons
        control_buttons_layout = QHBoxLayout(self.control_buttons_widget)
        control_buttons_layout.setContentsMargins(0,0,0,0) # No internal margins for this sub-layout

        self.toggle_notes_button = QPushButton() # Expected by Base's notes logic
        self.toggle_notes_button.setObjectName("toggle_notes_button_review")
        self.toggle_notes_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.toggle_notes_button.setToolTip(self.tr("Show/Hide Notes"))
        self.toggle_notes_button.setCheckable(True)
        self.toggle_notes_button.toggled.connect(self._toggle_notes_panel) # Connect to Base's method
        control_buttons_layout.addWidget(self.toggle_notes_button)
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
        self.rating_buttons_widget = QWidget() # Container for rating buttons
        rating_buttons_layout = QHBoxLayout(self.rating_buttons_widget)
        rating_buttons_layout.setContentsMargins(0,0,0,0) # No internal margins for this sub-layout

        self.rating_button_again = QPushButton(self.tr("Again (0)"))
        self.rating_button_again.setObjectName("rating_again_button")
        self.rating_button_again.clicked.connect(lambda: self._handle_rating(0))
        
        self.rating_button_hard = QPushButton(self.tr("Hard (1)"))
        self.rating_button_hard.setObjectName("rating_hard_button")
        self.rating_button_hard.clicked.connect(lambda: self._handle_rating(1))
        
        self.rating_button_good = QPushButton(self.tr("Good (2)"))
        self.rating_button_good.setObjectName("rating_good_button")
        self.rating_button_good.clicked.connect(lambda: self._handle_rating(2))
        
        self.rating_button_easy = QPushButton(self.tr("Easy (3)"))
        self.rating_button_easy.setObjectName("rating_easy_button")
        self.rating_button_easy.clicked.connect(lambda: self._handle_rating(3))

        rating_buttons_layout.addStretch(1)
        rating_buttons_layout.addWidget(self.rating_button_again)
        rating_buttons_layout.addWidget(self.rating_button_hard)
        rating_buttons_layout.addWidget(self.rating_button_good)
        rating_buttons_layout.addWidget(self.rating_button_easy)
        rating_buttons_layout.addStretch(1)
        review_action_layout.addWidget(self.rating_buttons_widget)
        
        # Add this new layout to the container provided by the base class
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
        # Rating buttons are generally always enabled when visible, unless specific logic applies
        self.rating_button_again.setEnabled(is_submitted_or_shown)
        self.rating_button_hard.setEnabled(is_submitted_or_shown)
        self.rating_button_good.setEnabled(is_submitted_or_shown)
        self.rating_button_easy.setEnabled(is_submitted_or_shown)

        self.toggle_notes_button.setEnabled(not is_session_ended and not is_initial)

        if is_submitted_or_shown:
            if self._last_submission_was_correct:
                self.rating_button_good.setFocus()
            else:
                self.rating_button_again.setFocus()
        elif is_asking and self.current_exercise_widget:
            self.current_exercise_widget.set_focus_on_input()


    def start_review_session(self, review_limit: Optional[int] = None):
        if review_limit is None:
            review_limit = self.DEFAULT_REVIEW_LIMIT
            
        super()._save_current_note() # Save note from any previously viewed exercise
        self.reset_view() # Prepare for new session

        self.due_exercises = self.progress_manager.get_due_exercises(
            self.course_manager.get_all_exercises(), limit=review_limit
        )
        self.total_exercises_in_session = len(self.due_exercises)

        if self.total_exercises_in_session == 0:
            QMessageBox.information(
                self,
                self.tr("Review Session"),
                self.tr("No exercises are due for review right now! Keep up the good work!"),
            )
            self.view_state = ReviewState.SESSION_ENDED
            self._update_button_states()
            self.back_to_overview_signal.emit() # Go back if nothing to review
            return

        self.current_exercise_index = 0
        self.session_title_label.setText(
            self.tr("Review Session ({0} exercises)").format(self.total_exercises_in_session)
        )
        self.progress_bar.setRange(0, self.total_exercises_in_session)
        self.progress_bar.setValue(0)
        
        self._load_next_review_exercise()


    def _load_next_review_exercise(self):
        super()._save_current_note() # Save previous note
        
        self.feedback_label.setText("")
        self.feedback_label.setStyleSheet("") # Clear feedback style
        
        if self.current_exercise_index >= self.total_exercises_in_session:
            self._finish_review_session()
            return

        exercise_to_load = self.due_exercises[self.current_exercise_index]
        
        # Use base class method to load the widget and notes
        if super()._load_exercise_widget(exercise_to_load): # This also sets self.current_exercise_obj
            # Connect signals for the newly loaded widget
            if self.current_exercise_widget:
                 self.current_exercise_widget.answer_submitted.connect(self._handle_user_submission_from_widget)
            self.view_state = ReviewState.ASKING_QUESTION
        else: # Widget loading failed (e.g., unsupported type)
            self.feedback_label.setText(self.tr("Error loading exercise. Please rate to continue."))
            self.feedback_label.setStyleSheet("color: red;")
            self.view_state = ReviewState.ANSWER_SUBMITTED # Allow to proceed
        
        self._update_button_states() # This will set focus


    def _handle_user_submission_from_button(self):
        if self.current_exercise_widget and self.view_state == ReviewState.ASKING_QUESTION:
            user_answer = self.current_exercise_widget.get_answer()
            self._process_submission(user_answer, was_shown=False)


    def _handle_user_submission_from_widget(self, user_answer: str):
        if self.view_state == ReviewState.ASKING_QUESTION:
            self._process_submission(user_answer, was_shown=False)


    def _process_submission(self, user_answer: str, was_shown: bool):
        if not self.current_exercise_obj or self.view_state != ReviewState.ASKING_QUESTION:
            return

        if not user_answer.strip() and isinstance(self.current_exercise_widget, TranslationExerciseWidget):
            self.feedback_label.setText(self.tr("Please provide an answer."))
            self.feedback_label.setStyleSheet("color: orange;")
            return # Don't change state, let user retry

        is_correct, feedback_text = self.course_manager.check_answer(
            self.current_exercise_obj, user_answer
        )

        self.feedback_label.setText(feedback_text)
        self.feedback_label.setStyleSheet("color: green;" if is_correct else "color: red;")
        
        self._last_submission_was_correct = is_correct
        self.view_state = ReviewState.ANSWER_SUBMITTED
        self._update_button_states()


    def _handle_show_answer(self):
        if not self.current_exercise_obj or self.view_state != ReviewState.ASKING_QUESTION:
            return

        correct_answer_for_display = self.tr("Could not retrieve answer.")
        if self.current_exercise_obj.type in ["translate_to_target", "translate_to_source"]:
            correct_answer_for_display = self.current_exercise_obj.answer
        elif self.current_exercise_obj.type == "multiple_choice_translation":
            correct_option = next((opt for opt in self.current_exercise_obj.options if opt.correct), None)
            if correct_option: correct_answer_for_display = correct_option.text
        elif self.current_exercise_obj.type == "fill_in_the_blank":
            correct_answer_for_display = self.current_exercise_obj.correct_option

        self.feedback_label.setText(self.tr("Correct answer: {0}").format(correct_answer_for_display or "N/A"))
        self.feedback_label.setStyleSheet("color: blue;") # Different color for revealed answer

        self._last_submission_was_correct = False # User didn't answer correctly
        self.view_state = ReviewState.ANSWER_SUBMITTED # Transition to rating state
        self._update_button_states()


    def _handle_rating(self, quality_score_frontend: int): # 0:Again, 1:Hard, 2:Good, 3:Easy
        if not self.current_exercise_obj or self.view_state != ReviewState.ANSWER_SUBMITTED:
            return

        sm2_quality_map = {0: 0, 1: 3, 2: 4, 3: 5} # Map frontend rating to SM-2 quality (0-5)
        sm2_quality = sm2_quality_map.get(quality_score_frontend, 0)

        # Award XP
        xp_awarded_for_review = 10 if sm2_quality >= 3 else (5 if sm2_quality >=1 else 0)

        # Update SRS data for this exercise
        self.progress_manager.update_exercise_srs_data(
            self.current_exercise_obj.exercise_id,
            is_correct=(sm2_quality >= 3), # Correct enough for SRS progression means SM2 quality 3 or higher
            xp_awarded=xp_awarded_for_review,
            quality_score_sm2=sm2_quality,
        )

        self.current_exercise_index += 1
        self.progress_bar.setValue(self.current_exercise_index)
        self._load_next_review_exercise()


    def _finish_review_session(self):
        self.view_state = ReviewState.SESSION_ENDED
        self._update_button_states()
        super()._save_current_note() # Save note for the last exercise if any
        QMessageBox.information(
            self,
            self.tr("Review Session Complete"),
            self.tr("You've completed this review session! Total exercises: {0}").format(self.total_exercises_in_session),
        )
        self.review_session_finished.emit()
        # back_to_overview_signal is emitted by _handle_back_to_overview if user clicks back.


    def reset_view(self):
        super().reset_view() # Call base class reset first
        
        self.current_exercise_index = -1
        self.due_exercises = []
        self.total_exercises_in_session = 0
        self._last_submission_was_correct = False
        
        self.session_title_label.setText(self.tr("Review Session"))
        self.progress_bar.setFormat(self.tr("Review Progress: %v / %m"))
        self.progress_bar.setRange(0, 100) # Reset to default range
        self.progress_bar.setValue(0)

        self.view_state = ReviewState.INITIAL_LOAD
        self._update_button_states() # Update buttons for the reset state
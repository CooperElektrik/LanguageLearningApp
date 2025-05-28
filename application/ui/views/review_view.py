import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QFrame, QProgressBar, QMessageBox)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from typing import List, Optional

# Ensure core models and managers are accessible
try:
    from core.models import Exercise, Lesson, Unit # Lesson, Unit for context if needed
    from core.course_manager import CourseManager # For getting formatted prompts, context
    from core.progress_manager import ProgressManager # For SRS updates and getting due exercises
    from ui.widgets.exercise_widgets import (
        TranslationExerciseWidget, MultipleChoiceExerciseWidget, 
        FillInTheBlankExerciseWidget, BaseExerciseWidget
    )
except ImportError as e:
    logging.error(f"ReviewView: Critical import failed: {e}")
    # Fallback dummy classes to prevent hard crash during development if imports are missing
    class Exercise: pass
    class CourseManager: pass
    class ProgressManager: pass
    class BaseExerciseWidget: pass
    class TranslationExerciseWidget(BaseExerciseWidget): pass
    class MultipleChoiceExerciseWidget(BaseExerciseWidget): pass
    class FillInTheBlankExerciseWidget(BaseExerciseWidget): pass


logger = logging.getLogger(__name__)

class ReviewView(QWidget):
    review_session_finished = Signal() # Emits when the review session is done
    back_to_overview_signal = Signal() # To return to main overview

    def __init__(self, course_manager: CourseManager, progress_manager: ProgressManager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        self.due_exercises: List[Exercise] = [] # List of exercises for this session
        self.current_exercise_index: int = -1
        self.current_exercise_widget: Optional[BaseExerciseWidget] = None
        self.total_exercises_in_session: int = 0
        self.current_exercise_obj: Optional[Exercise] = None # Store the current Exercise object

        self.user_just_submitted = False # Flag to manage button states after submission
        self.user_just_showed_answer = False # Flag to manage buttons after showing answer

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Top bar for session title and back button
        top_bar_layout = QHBoxLayout()
        self.back_button = QPushButton("← Back to Lessons")
        self.back_button.clicked.connect(self.back_to_overview_signal.emit)
        top_bar_layout.addWidget(self.back_button)
        
        self.session_title_label = QLabel("Review Session")
        self.session_title_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.session_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_bar_layout.addWidget(self.session_title_label, 1)
        main_layout.addLayout(top_bar_layout)

        # Progress Bar for session
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Review Progress: %v / %m")
        main_layout.addWidget(self.progress_bar)

        # Exercise Area (container for dynamic widget)
        self.exercise_area_container = QFrame()
        self.exercise_area_layout = QVBoxLayout(self.exercise_area_container)
        main_layout.addWidget(self.exercise_area_container, 1)

        # Feedback Label
        self.feedback_label = QLabel("")
        self.feedback_label.setFont(QFont("Arial", 12))
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setWordWrap(True)
        main_layout.addWidget(self.feedback_label)

        # Action Buttons (Submit, Show Answer, Rating)
        self.action_buttons_layout = QVBoxLayout() # Use vertical for main buttons then horizontal for rating
        
        # --- Submission/Reveal Buttons ---
        self.submit_show_layout = QHBoxLayout()
        self.submit_button = QPushButton("Submit Answer")
        self.submit_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.submit_button.clicked.connect(self._handle_user_submission_from_button)
        self.submit_show_layout.addWidget(self.submit_button)

        self.show_answer_button = QPushButton("Show Answer")
        self.show_answer_button.setFont(QFont("Arial", 12))
        self.show_answer_button.clicked.connect(self._handle_show_answer)
        self.submit_show_layout.addWidget(self.show_answer_button)
        self.submit_show_layout.addStretch(1) # Push to left

        self.action_buttons_layout.addLayout(self.submit_show_layout)

        # --- Rating Buttons (Initially hidden) ---
        self.rating_buttons_layout = QHBoxLayout()
        self.rating_button_again = QPushButton("Again (0)")
        self.rating_button_again.clicked.connect(lambda: self._handle_rating(0))
        self.rating_button_hard = QPushButton("Hard (1)")
        self.rating_button_hard.clicked.connect(lambda: self._handle_rating(1))
        self.rating_button_good = QPushButton("Good (2)")
        self.rating_button_good.clicked.connect(lambda: self._handle_rating(2))
        self.rating_button_easy = QPushButton("Easy (3)")
        self.rating_button_easy.clicked.connect(lambda: self._handle_rating(3))

        self.rating_buttons_layout.addStretch(1)
        self.rating_buttons_layout.addWidget(self.rating_button_again)
        self.rating_buttons_layout.addWidget(self.rating_button_hard)
        self.rating_buttons_layout.addWidget(self.rating_button_good)
        self.rating_buttons_layout.addWidget(self.rating_button_easy)
        self.rating_buttons_layout.addStretch(1)

        self.action_buttons_layout.addLayout(self.rating_buttons_layout)
        main_layout.addLayout(self.action_buttons_layout)

        self._set_button_states(initial=True) # Set initial button states

    def _set_button_states(self, initial=False, after_submission=False, after_show_answer=False):
        if initial:
            self.submit_button.setVisible(True)
            self.show_answer_button.setVisible(True)
            self.submit_button.setEnabled(True)
            self.show_answer_button.setEnabled(True)
            self.rating_button_again.setVisible(False)
            self.rating_button_hard.setVisible(False)
            self.rating_button_good.setVisible(False)
            self.rating_button_easy.setVisible(False)
        elif after_submission or after_show_answer:
            self.submit_button.setVisible(False)
            self.show_answer_button.setVisible(False)
            self.submit_button.setEnabled(False)
            self.show_answer_button.setEnabled(False)
            
            # Show rating buttons
            self.rating_button_again.setVisible(True)
            self.rating_button_hard.setVisible(True)
            self.rating_button_good.setVisible(True)
            self.rating_button_easy.setVisible(True)
            # Enable rating buttons
            self.rating_button_again.setEnabled(True)
            self.rating_button_hard.setEnabled(True)
            self.rating_button_good.setEnabled(True)
            self.rating_button_easy.setEnabled(True)
        else: # After rating, ready for next exercise
            self.submit_button.setVisible(False) # Will be hidden for next
            self.show_answer_button.setVisible(False)
            self.submit_button.setEnabled(False) # Will be disabled
            self.show_answer_button.setEnabled(False)
            
            self.rating_button_again.setVisible(False) # Hide rating buttons
            self.rating_button_hard.setVisible(False)
            self.rating_button_good.setVisible(False)
            self.rating_button_easy.setVisible(False)
            self.rating_button_again.setEnabled(False) # Disable rating buttons
            self.rating_button_hard.setEnabled(False)
            self.rating_button_good.setEnabled(False)
            self.rating_button_easy.setEnabled(False)


    def start_review_session(self, review_limit: int = 20):
        self.due_exercises = self.progress_manager.get_due_exercises(
            self.course_manager.get_all_exercises(), # CourseManager needs this helper
            limit=review_limit
        )
        self.current_exercise_index = 0
        self.total_exercises_in_session = len(self.due_exercises)

        if self.total_exercises_in_session == 0:
            QMessageBox.information(self, "Review Session", "No exercises are due for review right now! Keep up the good work!")
            self.back_to_overview_signal.emit()
            return

        self.session_title_label.setText(f"Review Session ({self.total_exercises_in_session} exercises)")
        self.progress_bar.setRange(0, self.total_exercises_in_session)
        self.progress_bar.setValue(0)
        
        self._load_current_exercise()

    def _clear_exercise_area(self):
        if self.current_exercise_widget:
            self.current_exercise_widget.answer_submitted.disconnect() # Disconnect old signal
            self.current_exercise_widget.deleteLater()
            self.current_exercise_widget = None
        self.feedback_label.setText("")

    def _load_current_exercise(self):
        self._clear_exercise_area()
        self._set_button_states(initial=True) # Reset button states for new exercise

        if self.current_exercise_index >= self.total_exercises_in_session:
            self._finish_review_session()
            return

        self.current_exercise_obj = self.due_exercises[self.current_exercise_index]
        
        # Instantiate correct ExerciseWidget
        if self.current_exercise_obj.type == "translate_to_target" or self.current_exercise_obj.type == "translate_to_source":
            self.current_exercise_widget = TranslationExerciseWidget(self.current_exercise_obj, self.course_manager)
        elif self.current_exercise_obj.type == "multiple_choice_translation":
            self.current_exercise_widget = MultipleChoiceExerciseWidget(self.current_exercise_obj, self.course_manager)
        elif self.current_exercise_obj.type == "fill_in_the_blank":
            self.current_exercise_widget = FillInTheBlankExerciseWidget(self.current_exercise_obj, self.course_manager)
        else:
            self.feedback_label.setText(f"Unsupported exercise type: {self.current_exercise_obj.type}")
            self._set_button_states(initial=False) # Disable buttons if unsupported type
            return

        self.exercise_area_layout.addWidget(self.current_exercise_widget)
        self.current_exercise_widget.answer_submitted.connect(self._handle_user_submission_from_widget) # Connect user input signal
        self.current_exercise_widget.set_focus_on_input()

        self.progress_bar.setValue(self.current_exercise_index) # Update progress bar

    def _handle_user_submission_from_button(self):
        if self.current_exercise_widget and self.submit_button.isEnabled():
            user_answer = self.current_exercise_widget.get_answer()
            self._handle_user_submission_from_widget(user_answer)

    def _handle_user_submission_from_widget(self, user_answer: str):
        if not self.current_exercise_obj or not self.current_exercise_widget:
            return

        # Basic input validation for text-based inputs
        if not user_answer.strip() and isinstance(self.current_exercise_widget, TranslationExerciseWidget):
            self.feedback_label.setText("Please provide an answer.")
            self.feedback_label.setStyleSheet("color: orange;")
            return

        is_correct, feedback_text = self.course_manager.check_answer(self.current_exercise_obj, user_answer)

        self.feedback_label.setText(feedback_text)
        self.feedback_label.setStyleSheet("color: green;" if is_correct else "color: red;")
        
        self.current_exercise_widget.clear_input() 
        self._set_button_states(after_submission=True)

        # Store correctness to update SRS later (when rating is given)
        self._last_submission_was_correct = is_correct

    def _handle_show_answer(self):
        if not self.current_exercise_obj:
            return

        # Get correct answer for display
        correct_answer_for_display = "Could not retrieve answer."
        if self.current_exercise_obj.type in ["translate_to_target", "translate_to_source"]:
            correct_answer_for_display = self.current_exercise_obj.answer
        elif self.current_exercise_obj.type == "multiple_choice_translation":
            correct_option = next((opt for opt in self.current_exercise_obj.options if opt.correct), None)
            if correct_option: correct_answer_for_display = correct_option.text
        elif self.current_exercise_obj.type == "fill_in_the_blank":
            correct_answer_for_display = self.current_exercise_obj.correct_option
            
        self.feedback_label.setText(f"Correct answer: {correct_answer_for_display}")
        self.feedback_label.setStyleSheet("color: orange;") # Skipped/Revealed color

        self._set_button_states(after_show_answer=True) # Show rating buttons
        self._last_submission_was_correct = False # Treat showing answer as incorrect for SRS
        self.show_answer_button.setEnabled(False) # Disable after showing

    def _handle_rating(self, quality_score: int):
        # quality_score: 0=Again, 1=Hard, 2=Good, 3=Easy
        # Update SRS using is_correct status from submission, and quality from button.
        # For simplicity in initial SRS, we'll map rating directly to SM-2 quality (0-5)
        # 0 (Again): SM-2 quality 0-2 (incorrect)
        # 1 (Hard): SM-2 quality 3 (correct but hard)
        # 2 (Good): SM-2 quality 4 (correct, remembered)
        # 3 (Easy): SM-2 quality 5 (correct, very easy)
        
        # Map our 0-3 rating to SM-2's 0-5 scale
        sm2_quality_map = {0: 0, 1: 3, 2: 4, 3: 5}
        sm2_quality = sm2_quality_map.get(quality_score, 0) # Default to 0 (again)

        # Award XP for good ratings (corresponding to SM-2 quality 3,4,5)
        xp_awarded_for_review = 10 if sm2_quality >= 3 else 0 # No XP for "Again" or "Hard" in some systems

        self.progress_manager.update_exercise_srs_data(
            self.current_exercise_obj.exercise_id, 
            is_correct=(sm2_quality >= 3), # Is this considered a "correct" run?
            xp_awarded=xp_awarded_for_review,
            quality_score_sm2=sm2_quality # Pass the granular quality to SRS algo
        )
        
        self.current_exercise_index += 1
        self.progress_bar.setValue(self.current_exercise_index) # Advance progress bar visually
        self._load_current_exercise() # Load next exercise or finish session

    def _finish_review_session(self):
        QMessageBox.information(self, "Review Session", f"You've completed this review session! Total exercises: {self.total_exercises_in_session}")
        self.review_session_finished.emit() # Signal that session is done
        self.back_to_overview_signal.emit() # Return to overview

    def reset_view(self):
        """Resets the view state for a new session."""
        self._clear_exercise_area()
        self._set_button_states(initial=True)
        self.feedback_label.setText("")
        self.progress_bar.setValue(0)
        self.current_exercise_index = -1
        self.due_exercises = []
        self.current_exercise_obj = None
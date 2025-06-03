import logging
from enum import Enum, auto

from PySide6.QtWidgets import (
    QLabel, QPushButton, QHBoxLayout, QMessageBox, QStyle, QWidget
)
from PySide6.QtCore import Signal, Qt

from typing import Optional

from core.models import Lesson, Exercise
from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from ui.views.base_exercise_player_view import BaseExercisePlayerView
from ui.widgets.exercise_widgets import EXERCISE_WIDGET_MAP # For direct use of the map

logger = logging.getLogger(__name__)

# State machine for the LessonView
class LessonViewState(Enum):
    INITIAL_LOAD = auto()       # View is first loaded or reset
    ASKING_QUESTION = auto()    # Displaying an exercise, awaiting submission
    ANSWER_SUBMITTED = auto()   # Answer processed, feedback shown (correct or incorrect)
    LESSON_COMPLETED = auto()   # All exercises in the lesson are done


class LessonView(BaseExercisePlayerView): # Inherit from the new base class
    lesson_completed_signal = Signal(str) # Emits lesson_id on completion

    def __init__(self, course_manager: CourseManager, progress_manager: ProgressManager, parent: Optional[QWidget] = None):
        # Call the base class constructor first. This sets up common UI and managers.
        super().__init__(course_manager, progress_manager, parent)

        # LessonView-specific instance variables
        self.current_lesson: Optional[Lesson] = None
        self.current_exercise_index: int = -1
        self.total_exercises_in_lesson: int = 0
        # self.current_exercise_obj and self.current_exercise_widget are managed by BaseExercisePlayerView

        self.view_state: LessonViewState = LessonViewState.INITIAL_LOAD
        
        # Setup UI elements specific to LessonView
        self._setup_specific_ui()
        
        # Reset view to its initial state, which also calls the base reset
        self.reset_view()


    def _setup_specific_ui(self):
        """Sets up UI elements unique to LessonView, complementing the base class's UI."""
        
        # --- Top Bar (Populated into self.top_bar_layout from Base) ---
        self.back_button = QPushButton(self.tr("← Back to Lessons"))
        self.back_button.setObjectName("back_button_lesson")
        # Connect to the base class's _handle_back_to_overview for common behavior
        self.back_button.clicked.connect(self._handle_back_to_overview)
        self.top_bar_layout.addWidget(self.back_button)

        self.lesson_title_label = QLabel(self.tr("Lesson Title"))
        self.lesson_title_label.setObjectName("lesson_title_label")
        self.lesson_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.top_bar_layout.addWidget(self.lesson_title_label, 1) # Add with stretch


        # --- Progress Bar Configuration (Configuring self.progress_bar from Base) ---
        self.progress_bar.setFormat(self.tr("%v / %m Steps"))


        # --- Action Buttons Area (Populated into self.action_buttons_layout_container from Base) ---
        # Create a horizontal layout for LessonView's specific buttons
        lesson_action_buttons_layout = QHBoxLayout()

        # Toggle Notes Button (used by base class notes logic)
        self.toggle_notes_button = QPushButton()
        self.toggle_notes_button.setObjectName("toggle_notes_button_lesson")
        self.toggle_notes_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.toggle_notes_button.setToolTip(self.tr("Show/Hide Notes"))
        self.toggle_notes_button.setCheckable(True)
        # Connect to the base class's _toggle_notes_panel method
        self.toggle_notes_button.toggled.connect(self._toggle_notes_panel)
        lesson_action_buttons_layout.addWidget(self.toggle_notes_button)
        
        lesson_action_buttons_layout.addStretch(1) # Pushes main buttons to the right

        # Skip Button
        self.skip_button = QPushButton(self.tr("Skip"))
        self.skip_button.setObjectName("skip_button_lesson")
        self.skip_button.clicked.connect(self._handle_skip_exercise)
        lesson_action_buttons_layout.addWidget(self.skip_button)

        # Submit Button
        self.submit_button = QPushButton(self.tr("Submit"))
        self.submit_button.setObjectName("submit_button_lesson")
        self.submit_button.clicked.connect(self._handle_submit_button_click)
        lesson_action_buttons_layout.addWidget(self.submit_button)

        # Next/Continue Button
        self.next_button = QPushButton(self.tr("Continue")) # Initial text
        self.next_button.setObjectName("next_button_lesson")
        self.next_button.clicked.connect(self._handle_next_action_click)
        lesson_action_buttons_layout.addWidget(self.next_button)
        
        # Add this specific layout to the base class's container
        self.action_buttons_layout_container.addLayout(lesson_action_buttons_layout)
        
        # Initial update of button states based on view state
        self._update_button_states()


    def _update_button_states(self):
        """Manages visibility and enabled state of LessonView-specific buttons based on current state."""
        # Determine visibility and enabled state based on LessonViewState
        is_asking = self.view_state == LessonViewState.ASKING_QUESTION
        is_submitted = self.view_state == LessonViewState.ANSWER_SUBMITTED
        is_completed = self.view_state == LessonViewState.LESSON_COMPLETED
        is_initial = self.view_state == LessonViewState.INITIAL_LOAD # For toggle notes button init

        self.submit_button.setVisible(is_asking)
        self.submit_button.setEnabled(is_asking)
        
        self.skip_button.setVisible(is_asking)
        self.skip_button.setEnabled(is_asking)

        self.next_button.setVisible(is_submitted or is_completed)
        self.next_button.setEnabled(is_submitted or is_completed)

        # Toggle notes button is enabled unless the lesson is completed or not yet started
        self.toggle_notes_button.setEnabled(not (is_completed or is_initial))

        # Update next_button text and set focus
        if is_submitted:
            if self.current_exercise_index + 1 >= self.total_exercises_in_lesson:
                self.next_button.setText(self.tr("Finish Lesson 🎉"))
            else:
                self.next_button.setText(self.tr("Next Exercise →"))
            self.next_button.setFocus()
        elif is_completed:
            self.next_button.setText(self.tr("Back to Overview"))
            self.next_button.setFocus()
        
        # Set focus on the exercise input if in asking state and widget exists
        if is_asking and self.current_exercise_widget:
            self.current_exercise_widget.set_focus_on_input()


    # _handle_back_to_overview is inherited from BaseExercisePlayerView,
    # and calls _save_current_note and reset_view.

    def start_lesson(self, lesson_id: str):
        """Initiates a new lesson session."""
        self.reset_view() # Ensure view is clean before starting a new lesson
        
        self.current_lesson = self.course_manager.get_lesson(lesson_id)

        if not self.current_lesson:
            logger.error(f"Could not load lesson with ID: {lesson_id}")
            self.feedback_label.setText(self.tr("Error: Could not load lesson data."))
            self.feedback_label.setStyleSheet("color: red;")
            self.view_state = LessonViewState.INITIAL_LOAD # Stay in initial state
            self._update_button_states()
            return

        self.lesson_title_label.setText(self.current_lesson.title)
        self.current_exercise_index = 0
        self.total_exercises_in_lesson = len(self.current_lesson.exercises)
        
        # Configure progress bar from base class
        self.progress_bar.setRange(0, self.total_exercises_in_lesson)
        self.progress_bar.setValue(0)
        
        self._load_next_exercise_in_lesson()


    def _load_next_exercise_in_lesson(self):
        """Loads the next exercise in the current lesson, or finishes the lesson."""
        # Ensure any notes from the previous exercise are saved before loading a new one.
        # This is handled by _load_exercise_widget via _save_current_note().
        self._save_current_note() # Explicitly save notes for the *previous* exercise (if any)

        # Check if all exercises in the lesson are completed
        if self.current_exercise_index >= self.total_exercises_in_lesson:
            self._finish_lesson()
            return

        exercise_to_load = self.current_lesson.exercises[self.current_exercise_index]
        
        # Use the base class method to load the exercise widget
        if super()._load_exercise_widget(exercise_to_load): # This also sets self.current_exercise_obj
            # Connect the answer_submitted signal from the new widget to our handler
            if self.current_exercise_widget:
                self.current_exercise_widget.answer_submitted.connect(self._handle_submit_answer_from_widget)
            
            self.progress_bar.setValue(self.current_exercise_index) # Update progress bar (0-indexed)
            self.view_state = LessonViewState.ASKING_QUESTION
        else:
            # If _load_exercise_widget failed (e.g., unsupported exercise type),
            # provide feedback and allow user to proceed.
            self.feedback_label.setText(self.tr("Error loading exercise. Skipping."))
            self.feedback_label.setStyleSheet("color: red;")
            self.view_state = LessonViewState.ANSWER_SUBMITTED # Allows "Next" button
        
        self._update_button_states() # Update buttons based on new state and set focus


    def _handle_submit_button_click(self):
        """Handles the 'Submit' button click."""
        if self.current_exercise_widget and self.view_state == LessonViewState.ASKING_QUESTION:
            user_answer = self.current_exercise_widget.get_answer()
            self._process_answer(user_answer, was_skipped=False)

    def _handle_submit_answer_from_widget(self, answer_text: str):
        """Handles submission triggered by pressing Enter in the exercise widget."""
        if self.view_state == LessonViewState.ASKING_QUESTION:
            self._process_answer(answer_text, was_skipped=False)


    def _process_answer(self, user_answer: str, was_skipped: bool):
        """Processes the user's answer or a skipped exercise."""
        # self.current_exercise_obj is set by BaseExercisePlayerView._load_exercise_widget
        if not self.current_exercise_obj:
            logger.error("_process_answer called with no current_exercise_obj available.")
            return

        is_correct = False
        feedback_text_display = ""
        xp_to_award = 0
        quality_score_for_srs = 0 # Default SM-2 (0-5)

        if was_skipped:
            # Determine correct answer for display if skipped
            correct_answer_for_display = self.tr("N/A")
            if self.current_exercise_obj.type in ["translate_to_target", "translate_to_source"]:
                correct_answer_for_display = self.current_exercise_obj.answer
            elif self.current_exercise_obj.type == "multiple_choice_translation":
                correct_option = next((opt for opt in self.current_exercise_obj.options if opt.correct), None)
                if correct_option: correct_answer_for_display = correct_option.text
            elif self.current_exercise_obj.type == "fill_in_the_blank":
                correct_answer_for_display = self.current_exercise_obj.correct_option
            
            feedback_text_display = self.tr("Skipped. Correct answer: {0}").format(correct_answer_for_display or self.tr("N/A"))
            self.feedback_label.setStyleSheet("color: orange;")
            is_correct = False # Skipped is treated as incorrect for SRS progression
            quality_score_for_srs = 0 # Lowest quality for SM-2
        else:
            # --- Answer Input Validation ---
            # For non-MCQ/FIB exercises, ensure input is not empty
            if (not user_answer.strip() and 
                self.current_exercise_widget and
                self.current_exercise_widget.exercise.type not in ["multiple_choice_translation", "fill_in_the_blank"]):
                self.feedback_label.setText(self.tr("Please provide an answer."))
                self.feedback_label.setStyleSheet("color: orange;")
                return # Stay in ASKING_QUESTION state, don't update progress or SRS

            # --- Check Answer with CourseManager ---
            is_correct, feedback_text_display = self.course_manager.check_answer(
                self.current_exercise_obj, user_answer
            )
            self.feedback_label.setStyleSheet("color: green;" if is_correct else "color: red;")
            
            # --- Determine XP and SM-2 Quality ---
            if is_correct:
                xp_to_award = 10 # Default XP for a correct lesson exercise
                quality_score_for_srs = 4 # Assume 'Good' for SM-2 (0-5)
            else:
                xp_to_award = 0 # No XP for incorrect answer
                quality_score_for_srs = 1 # Treat as 'Hard' or 'Incorrect' for SM-2
                if self.current_exercise_widget:
                    self.current_exercise_widget.clear_input() # Clear input for incorrect answer


        # --- Update UI and Progress ---
        self.feedback_label.setText(feedback_text_display)
        
        # Update SRS data and XP via ProgressManager
        self.progress_manager.update_exercise_srs_data(
            self.current_exercise_obj.exercise_id,
            is_correct=is_correct,
            xp_awarded=xp_to_award,
            quality_score_sm2=quality_score_for_srs
        )
        
        # Advance progress bar (even for incorrect/skipped, it's a step in the lesson)
        self.progress_bar.setValue(self.current_exercise_index + 1)
        
        # Transition to ANSWER_SUBMITTED state and update buttons
        self.view_state = LessonViewState.ANSWER_SUBMITTED
        self._update_button_states() # This will show "Next Exercise" or "Finish Lesson"


    def _handle_next_action_click(self):
        """Handles the 'Next Exercise' or 'Back to Overview' button click."""
        if self.view_state == LessonViewState.LESSON_COMPLETED:
            # If lesson is completed, clicking 'Next' means go back to overview
            super()._handle_back_to_overview() # Calls base handler for save and reset
        elif self.view_state == LessonViewState.ANSWER_SUBMITTED:
            # If an answer was just submitted, load the next exercise
            self.current_exercise_index += 1
            self._load_next_exercise_in_lesson()


    def _handle_skip_exercise(self):
        """Handles the 'Skip Exercise' button click."""
        if not self.current_lesson or self.view_state != LessonViewState.ASKING_QUESTION:
            return

        reply = QMessageBox.question(
            self,
            self.tr("Skip Exercise"),
            self.tr("Are you sure you want to skip this exercise? It will be marked for earlier review."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No # Default button for safety
        )
        if reply == QMessageBox.StandardButton.No:
            return
        
        # Process the skip, treating it as an incorrect answer
        self._process_answer(user_answer="", was_skipped=True)


    def _finish_lesson(self):
        """Actions to perform when the entire lesson is completed."""
        self._save_current_note() # Ensure notes for the last exercise are saved
        
        self.feedback_label.setText(self.tr("Lesson '{0}' completed!").format(self.current_lesson.title if self.current_lesson else ""))
        self.feedback_label.setStyleSheet("color: blue;")
        
        super()._clear_exercise_area() # Clear out the last exercise widget from display
        self.current_exercise_obj = None # Explicitly clear the current exercise reference for this view
        
        self.view_state = LessonViewState.LESSON_COMPLETED
        self._update_button_states() # This will change the "Next" button text to "Back to Overview"
        
        # Emit signal that the lesson is completed
        if self.current_lesson:
            self.lesson_completed_signal.emit(self.current_lesson.lesson_id)


    def reset_view(self):
        """
        Resets LessonView to its initial state.
        Overrides the base class reset to include LessonView-specific elements.
        """
        super().reset_view() # Call the base class's reset method first
        
        # Reset LessonView-specific variables
        self.current_lesson = None
        self.current_exercise_index = -1
        self.total_exercises_in_lesson = 0
        # self.current_exercise_obj is already handled by super().reset_view()

        # Reset LessonView-specific UI elements
        self.lesson_title_label.setText(self.tr("Lesson")) # Reset title to generic
        self.progress_bar.setFormat(self.tr("%v / %m Steps")) # Ensure format is correct
        self.progress_bar.setRange(0,100) # Reset range for a cleaner look if not active
        self.progress_bar.setValue(0) # Reset value

        # Reset view state and update buttons accordingly
        self.view_state = LessonViewState.INITIAL_LOAD
        self._update_button_states()


    # --- Notes Panel Methods (Highly similar to ReviewView, candidate for base class) ---
    def _toggle_notes_panel(self, checked: bool):
        """Toggles the visibility of the notes panel."""
        self.notes_group_box.setVisible(checked)
        if checked:
            self.notes_text_edit.setFocus() # Set focus when showing
        else:
            self._save_current_note() # Save notes when panel is hidden
        self._update_notes_button_indicator() # Update icon based on note presence

    def _save_current_note(self):
        """Saves the current note for the active exercise to progress manager."""
        self.notes_save_timer.stop() # Stop pending debounced save
        if self.current_exercise_obj: # Only save if an exercise is active
            note_content = self.notes_text_edit.toPlainText().strip()
            self.progress_manager.save_exercise_note(self.current_exercise_obj.exercise_id, note_content)
            self._update_notes_button_indicator() # Update button icon

    def _update_notes_button_indicator(self):
        """Updates the icon and tooltip of the toggle notes button based on whether a note exists."""
        has_note = False
        if self.current_exercise_obj:
            note_content = self.progress_manager.get_exercise_note(self.current_exercise_obj.exercise_id)
            if note_content and note_content.strip():
                has_note = True
        
        icon_to_use = QStyle.StandardPixmap.SP_FileDialogDetailedView if has_note else QStyle.StandardPixmap.SP_FileIcon
        tooltip_text = self.tr("Edit Notes") if has_note else self.tr("Add Notes")
        
        self.toggle_notes_button.setIcon(self.style().standardIcon(icon_to_use))
        self.toggle_notes_button.setToolTip(tooltip_text)
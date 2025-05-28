from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, 
                               QFrame, QProgressBar, QMessageBox)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from core.models import Lesson, Exercise
from ui.widgets.exercise_widgets import (TranslationExerciseWidget, 
                                         MultipleChoiceExerciseWidget, 
                                         FillInTheBlankExerciseWidget,
                                         BaseExerciseWidget) # Assuming core and ui are accessible

class LessonView(QWidget):
    lesson_completed_signal = Signal(str) # Emits lesson_id
    back_to_overview_signal = Signal()

    def __init__(self, course_manager, progress_manager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        self.current_lesson: Lesson = None
        self.current_exercise_index: int = -1
        self.current_exercise_widget: BaseExerciseWidget = None
        self.total_exercises_in_lesson: int = 0

        self.main_layout = QVBoxLayout(self)

        # Top bar for lesson title and back button
        top_bar_layout = QHBoxLayout()
        self.back_button = QPushButton("← Back to Lessons")
        self.back_button.clicked.connect(self.back_to_overview_signal.emit)
        top_bar_layout.addWidget(self.back_button)
        
        self.lesson_title_label = QLabel("Lesson Title")
        self.lesson_title_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.lesson_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_bar_layout.addWidget(self.lesson_title_label, 1) # Stretch factor
        self.main_layout.addLayout(top_bar_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFormat("%v / %m Steps")
        self.main_layout.addWidget(self.progress_bar)

        # Exercise Area (placeholder for dynamic widget)
        self.exercise_area_container = QFrame() # Use a container for easy clearing
        self.exercise_area_layout = QVBoxLayout(self.exercise_area_container)
        self.main_layout.addWidget(self.exercise_area_container, 1) # Stretch factor for exercise area

        # Feedback Label
        self.feedback_label = QLabel("")
        self.feedback_label.setFont(QFont("Arial", 12))
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setWordWrap(True)
        self.main_layout.addWidget(self.feedback_label)

        # Action Buttons
        self.action_buttons_layout = QHBoxLayout()
        self.submit_button = QPushButton("Submit Answer")
        self.submit_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.submit_button.clicked.connect(self._handle_submit_answer)
        
        self.next_button = QPushButton("Continue") # Text changes to "Finish Lesson"
        self.next_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.next_button.clicked.connect(self._handle_next_action)

        self.skip_button = QPushButton("Skip Exercise")
        self.skip_button.setFont(QFont("Arial", 10))
        self.skip_button.clicked.connect(self._handle_skip_exercise)
        
        self.action_buttons_layout.addWidget(self.submit_button)
        self.action_buttons_layout.addWidget(self.next_button)
        self.action_buttons_layout.addWidget(self.skip_button)
        self.main_layout.addLayout(self.action_buttons_layout)

    def start_lesson(self, lesson_id: str):
        self.current_lesson = self.course_manager.get_lesson(lesson_id)
        if not self.current_lesson:
            # Handle error: lesson not found
            self.feedback_label.setText("Error: Could not load lesson.")
            self.submit_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        self.lesson_title_label.setText(self.current_lesson.title)
        self.current_exercise_index = 0
        self.total_exercises_in_lesson = len(self.current_lesson.exercises)
        self.progress_bar.setRange(0, self.total_exercises_in_lesson)
        self.progress_bar.setValue(0)
        
        self._load_current_exercise()

    def _clear_exercise_area(self):
        while self.exercise_area_layout.count():
            child = self.exercise_area_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.current_exercise_widget = None

    def _load_current_exercise(self):
        self._clear_exercise_area()
        self.feedback_label.setText("")
        self.submit_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.next_button.setVisible(False) # Hide until answer is submitted and correct

        if self.current_exercise_index >= self.total_exercises_in_lesson:
            self._finish_lesson()
            return

        exercise = self.current_lesson.exercises[self.current_exercise_index]
        
        if exercise.type == "translate_to_target" or exercise.type == "translate_to_source":
            self.current_exercise_widget = TranslationExerciseWidget(exercise, self.course_manager)
        elif exercise.type == "multiple_choice_translation":
            self.current_exercise_widget = MultipleChoiceExerciseWidget(exercise, self.course_manager)
        elif exercise.type == "fill_in_the_blank":
            self.current_exercise_widget = FillInTheBlankExerciseWidget(exercise, self.course_manager)
        else:
            self.feedback_label.setText(f"Unsupported exercise type: {exercise.type}")
            self.submit_button.setEnabled(False)
            return

        if self.current_exercise_widget:
            self.exercise_area_layout.addWidget(self.current_exercise_widget)
            self.current_exercise_widget.answer_submitted.connect(self._handle_submit_answer_from_widget)
            self.current_exercise_widget.set_focus_on_input() # Set focus to input field

        self.progress_bar.setValue(self.current_exercise_index)
        self.submit_button.setText("Submit Answer") # Reset button text

    def _handle_submit_answer_from_widget(self, answer_text: str):
        """Slot for when an exercise widget emits an answer via its own mechanism (e.g. radio click)"""
        if self.submit_button.isEnabled(): # Only process if submission is active
            self._process_answer(answer_text)

    def _handle_submit_answer(self):
        """Slot for the main Submit button click."""
        if not self.current_exercise_widget:
            return
        user_answer = self.current_exercise_widget.get_answer()
        self._process_answer(user_answer)
        
    def _process_answer(self, user_answer: str):
        if not user_answer and not self.current_exercise_widget.exercise.type.startswith("multiple_choice"): # MC/FIB can have direct submission
            self.feedback_label.setText("Please provide an answer.")
            self.feedback_label.setStyleSheet("color: orange;")
            return

        exercise = self.current_lesson.exercises[self.current_exercise_index]
        is_correct, feedback_text = self.course_manager.check_answer(exercise, user_answer)

        self.feedback_label.setText(feedback_text)
        if is_correct:
            self.feedback_label.setStyleSheet("color: green;")
            self.progress_bar.setValue(self.current_exercise_index + 1) # Visually mark as done
            self.submit_button.setEnabled(False) # Disable submit after correct answer
            self.next_button.setVisible(True)
            if self.current_exercise_index + 1 >= self.total_exercises_in_lesson:
                self.next_button.setText("Finish Lesson 🎉")
            else:
                self.next_button.setText("Next Exercise →")
            self.next_button.setFocus()
        else:
            self.feedback_label.setStyleSheet("color: red;")
            if self.current_exercise_widget: # Allow re-try by clearing input
                self.current_exercise_widget.clear_input()
                self.current_exercise_widget.set_focus_on_input()


    def _handle_next_action(self):
        self.current_exercise_index += 1
        self._load_current_exercise() # This will call _finish_lesson if no more exercises

    def _handle_skip_exercise(self):
        if not self.current_lesson or self.current_exercise_index < 0 or \
        self.current_exercise_index >= self.total_exercises_in_lesson:
            return

        reply = QMessageBox.question(self, "Skip Exercise", 
                                    "Are you sure you want to skip this exercise? You won't get points for it.",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return

        exercise = self.current_lesson.exercises[self.current_exercise_index]
        
        # Get correct answer for display (similar to _process_answer)
        _, correct_answer_display_text = self.course_manager.check_answer(exercise, "!@#INVALID_ANSWER_FOR_SKIPPING#@!") 
        # The check_answer method usually returns tuple (is_correct, feedback_text).
        # We need the feedback text part that reveals the answer.
        # A more direct way to get the answer might be better if check_answer has side effects.
        # Assuming check_answer is safe to call like this or we have another way to get display_answer.
        
        # Let's refine getting the correct answer:
        correct_answer_for_display = "Could not retrieve answer." # Default
        if exercise.type in ["translate_to_target", "translate_to_source"]:
            correct_answer_for_display = exercise.answer
        elif exercise.type == "multiple_choice_translation":
            correct_option = next((opt for opt in exercise.options if opt.correct), None)
            if correct_option: correct_answer_for_display = correct_option.text
        elif exercise.type == "fill_in_the_blank":
            correct_answer_for_display = exercise.correct_option
            
        self.feedback_label.setText(f"Skipped. The correct answer was: {correct_answer_for_display}")
        self.feedback_label.setStyleSheet("color: orange;") # Skipped color

        self.progress_bar.setValue(self.current_exercise_index + 1) # Visually advance
        
        self.submit_button.setEnabled(False)
        self.skip_button.setEnabled(False) # Disable skip too once skipped
        self.next_button.setVisible(True)
        if self.current_exercise_index + 1 >= self.total_exercises_in_lesson:
            self.next_button.setText("Finish Lesson 🎉")
        else:
            self.next_button.setText("Next Exercise →")
        self.next_button.setFocus()
        
        # We don't actually call _handle_next_action immediately here, as that increments the index again.
        # The next_button click will handle moving to the next exercise.
        # The state is now: exercise "answered" (skipped), show next_button.


    def _finish_lesson(self):
        self.feedback_label.setText(f"Lesson '{self.current_lesson.title}' completed!")
        self.feedback_label.setStyleSheet("color: blue;")
        self.progress_manager.mark_lesson_completed(self.current_lesson.lesson_id)
        
        self._clear_exercise_area() # Clear out the last exercise widget
        
        # Instead of a next button, show a summary or a specific "Return to Overview" button
        self.submit_button.setVisible(False)
        self.next_button.setText("Back to Course Overview")
        self.next_button.setVisible(True)
        self.next_button.clicked.disconnect() # Remove previous connection
        self.next_button.clicked.connect(self.back_to_overview_signal.emit) # New connection
        
        self.lesson_completed_signal.emit(self.current_lesson.lesson_id)
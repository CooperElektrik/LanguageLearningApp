from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QFrame,
    QProgressBar,
    QMessageBox,
    QStyle,
    QGroupBox,
    QTextEdit
)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont, QIcon

from core.models import Lesson, Exercise
from ui.widgets.exercise_widgets import (
    TranslationExerciseWidget,
    MultipleChoiceExerciseWidget,
    FillInTheBlankExerciseWidget,
    BaseExerciseWidget,
)

from typing import Optional
import logging

logger = logging.getLogger(__name__)

class LessonView(QWidget):
    lesson_completed_signal = Signal(str)
    back_to_overview_signal = Signal()

    def __init__(self, course_manager, progress_manager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        self.current_lesson: Lesson = None
        self.current_exercise_index: int = -1
        self.current_exercise_widget: BaseExerciseWidget = None
        self.total_exercises_in_lesson: int = 0
        self.current_exercise_obj: Optional[Exercise] = None # To store current exercise for notes

        self.main_layout = QVBoxLayout(self)

        top_bar_layout = QHBoxLayout()
        self.back_button = QPushButton(self.tr("← Back to Lessons"))
        self.back_button.clicked.connect(self._handle_back_to_overview)
        top_bar_layout.addWidget(self.back_button)

        self.lesson_title_label = QLabel(self.tr("Lesson Title"))
        self.lesson_title_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.lesson_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_bar_layout.addWidget(self.lesson_title_label, 1)
        self.main_layout.addLayout(top_bar_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFormat(self.tr("%v / %m Steps"))
        self.main_layout.addWidget(self.progress_bar)

        self.exercise_area_container = QFrame()
        self.exercise_area_layout = QVBoxLayout(self.exercise_area_container)
        self.main_layout.addWidget(self.exercise_area_container, 1)

        self.notes_group_box = QGroupBox(self.tr("My Notes"))
        self.notes_group_box.setVisible(False) # Initially hidden
        notes_layout = QVBoxLayout(self.notes_group_box)
        
        self.notes_text_edit = QTextEdit()
        self.notes_text_edit.setPlaceholderText(self.tr("Type your personal notes for this exercise here..."))
        # Debounce saving notes to avoid saving on every keystroke
        self.notes_save_timer = QTimer(self)
        self.notes_save_timer.setSingleShot(True)
        self.notes_save_timer.setInterval(1500) # Save 1.5 seconds after last edit
        self.notes_save_timer.timeout.connect(self._save_current_note)
        self.notes_text_edit.textChanged.connect(self.notes_save_timer.start) # Restart timer on change
        
        notes_layout.addWidget(self.notes_text_edit)
        self.main_layout.addWidget(self.notes_group_box)

        self.feedback_label = QLabel("")
        self.feedback_label.setFont(QFont("Arial", 12))
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setWordWrap(True)
        self.main_layout.addWidget(self.feedback_label)

        self.action_buttons_layout = QHBoxLayout()

        self.toggle_notes_button = QPushButton()
        self.toggle_notes_button.setIcon(self.style().standardIcon(QStyle.SP_FileIcon)) # Placeholder icon
        self.toggle_notes_button.setToolTip(self.tr("Show/Hide Notes"))
        self.toggle_notes_button.setCheckable(True)
        self.toggle_notes_button.toggled.connect(self._toggle_notes_panel)
        self.action_buttons_layout.addWidget(self.toggle_notes_button)
        self.action_buttons_layout.addStretch(1) # Push other buttons to the right

        self.submit_button = QPushButton(self.tr("Submit Answer"))
        self.submit_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.submit_button.clicked.connect(self._handle_submit_answer)

        self.next_button = QPushButton(self.tr("Continue"))
        self.next_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.next_button.clicked.connect(self._handle_next_action)

        self.skip_button = QPushButton(self.tr("Skip Exercise"))
        self.skip_button.setFont(QFont("Arial", 10))
        self.skip_button.clicked.connect(self._handle_skip_exercise)

        self.action_buttons_layout.addWidget(self.submit_button)
        self.action_buttons_layout.addWidget(self.next_button)
        self.action_buttons_layout.addWidget(self.skip_button)
        self.main_layout.addLayout(self.action_buttons_layout)

    def _handle_back_to_overview(self):
        """Handles saving notes before going back."""
        self._save_current_note() # Ensure latest note is saved
        self.back_to_overview_signal.emit()

    def start_lesson(self, lesson_id: str):
        self.current_lesson = self.course_manager.get_lesson(lesson_id)
        if not self.current_lesson:
            self.feedback_label.setText(self.tr("Error: Could not load lesson."))
            self.submit_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        self.lesson_title_label.setText(self.current_lesson.title)
        self.current_exercise_index = 0
        self.total_exercises_in_lesson = len(self.current_lesson.exercises)
        self.progress_bar.setRange(0, self.total_exercises_in_lesson)
        self.progress_bar.setValue(0)
        self.current_exercise_obj = None

        self._load_current_exercise()

    def _clear_exercise_area(self):
        while self.exercise_area_layout.count():
            child = self.exercise_area_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.current_exercise_widget = None
        self.current_exercise_obj = None

    def _load_current_exercise(self):
        self._save_current_note() # Save note for the *previous* exercise before loading new one
        self._clear_exercise_area()
        self.feedback_label.setText("")
        self.submit_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.next_button.setVisible(False)
        self.toggle_notes_button.setChecked(False) # Ensure notes panel is hidden initially
        self.notes_group_box.setVisible(False)

        if self.current_exercise_index >= self.total_exercises_in_lesson:
            self._finish_lesson()
            return

        self.current_exercise_obj = self.current_lesson.exercises[self.current_exercise_index]
        exercise = self.current_exercise_obj

        if (
            exercise.type == "translate_to_target"
            or exercise.type == "translate_to_source"
        ):
            self.current_exercise_widget = TranslationExerciseWidget(
                exercise, self.course_manager
            )
        elif exercise.type == "multiple_choice_translation":
            self.current_exercise_widget = MultipleChoiceExerciseWidget(
                exercise, self.course_manager
            )
        elif exercise.type == "fill_in_the_blank":
            self.current_exercise_widget = FillInTheBlankExerciseWidget(
                exercise, self.course_manager
            )
        else:
            self.feedback_label.setText(self.tr("Unsupported exercise type: {0}").format(exercise.type))
            self.submit_button.setEnabled(False)
            return

        if self.current_exercise_widget:
            self.exercise_area_layout.addWidget(self.current_exercise_widget)
            self.current_exercise_widget.answer_submitted.connect(
                self._handle_submit_answer_from_widget
            )
            self.current_exercise_widget.set_focus_on_input()

            note_text = self.progress_manager.get_exercise_note(exercise.exercise_id)
            self.notes_text_edit.blockSignals(True) # Prevent textChanged during programmatic set
            self.notes_text_edit.setPlainText(note_text or "")
            self.notes_text_edit.blockSignals(False)
            self._update_notes_button_indicator() # Update button icon based on note presence

        self.progress_bar.setValue(self.current_exercise_index)
        self.submit_button.setText(self.tr("Submit Answer"))

    def _toggle_notes_panel(self, checked: bool):
        self.notes_group_box.setVisible(checked)
        if not checked: # Panel is being hidden
            self._save_current_note() # Explicitly save
        else: # Panel is being shown
            self.notes_text_edit.setFocus()
        self._update_notes_button_indicator()


    def _save_current_note(self):
        self.notes_save_timer.stop() # Stop any pending debounced save
        if self.current_exercise_obj:
            note_content = self.notes_text_edit.toPlainText()
            self.progress_manager.save_exercise_note(self.current_exercise_obj.exercise_id, note_content)
            self._update_notes_button_indicator()
            logger.info(f"Saved note for exercise {self.current_exercise_obj.exercise_id}: {note_content}")
            
    def _update_notes_button_indicator(self):
        if self.current_exercise_obj:
            has_note = bool(self.progress_manager.get_exercise_note(self.current_exercise_obj.exercise_id))
            if has_note:
                self.toggle_notes_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView)) # Example: "document with content" icon
                self.toggle_notes_button.setToolTip(self.tr("Edit Notes"))
            else:
                self.toggle_notes_button.setIcon(self.style().standardIcon(QStyle.SP_FileIcon)) # Example: "empty document" icon
                self.toggle_notes_button.setToolTip(self.tr("Add Notes"))

    def _handle_submit_answer_from_widget(self, answer_text: str):
        if self.submit_button.isEnabled():
            self._process_answer(answer_text)

    def _handle_submit_answer(self):
        if not self.current_exercise_widget:
            return
        user_answer = self.current_exercise_widget.get_answer()
        self._process_answer(user_answer)

    def _process_answer(self, user_answer: str):
        if (
            not user_answer.strip()
            and not self.current_exercise_widget.exercise.type.startswith(
                "multiple_choice"
            )
            and not self.current_exercise_widget.exercise.type.startswith(
                "fill_in_the_blank"
            )
        ):
            self.feedback_label.setText(self.tr("Please provide an answer."))
            self.feedback_label.setStyleSheet("color: orange;")
            return

        exercise = self.current_lesson.exercises[self.current_exercise_index]
        is_correct, feedback_text = self.course_manager.check_answer(
            exercise, user_answer
        )

        self.feedback_label.setText(feedback_text)
        xp_to_award = 10 # Default XP for a lesson exercise
        if is_correct:
            self.feedback_label.setStyleSheet("color: green;")
            self.progress_bar.setValue(self.current_exercise_index + 1)
            self.submit_button.setEnabled(False)
            self.skip_button.setEnabled(False) # Disable skip once answered correctly
            self.next_button.setVisible(True)
            if self.current_exercise_index + 1 >= self.total_exercises_in_lesson:
                self.next_button.setText(self.tr("Finish Lesson 🎉"))
            else:
                self.next_button.setText(self.tr("Next Exercise →"))
            self.next_button.setFocus()

            quality_score_for_srs = 4 # Assume 'Good' (SM-2 scale 0-5)
            self.progress_manager.update_exercise_srs_data(
                exercise.exercise_id,
                is_correct=True,
                xp_awarded=xp_to_award,
                quality_score_sm2=quality_score_for_srs
            )
        else:
            self.feedback_label.setStyleSheet("color: red;")
            if self.current_exercise_widget:
                self.current_exercise_widget.clear_input()
                self.current_exercise_widget.set_focus_on_input()
            
            # For incorrect answers, quality score should be low (e.g., 0-2)
            quality_score_for_srs = 1 # Example: Treat as difficult/barely recall
            self.progress_manager.update_exercise_srs_data(
                exercise.exercise_id,
                is_correct=False,
                xp_awarded=0, # No XP for incorrect answer
                quality_score_sm2=quality_score_for_srs
            )

    def _handle_next_action(self):
        self.current_exercise_index += 1
        self._load_current_exercise()

    def _handle_skip_exercise(self):
        if (
            not self.current_lesson
            or self.current_exercise_index < 0
            or self.current_exercise_index >= self.total_exercises_in_lesson
        ):
            return

        reply = QMessageBox.question(
            self,
            self.tr("Skip Exercise"),
            self.tr("Are you sure you want to skip this exercise? You won't get points for it."),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.No:
            return

        exercise = self.current_lesson.exercises[self.current_exercise_index]

        correct_answer_for_display = self.tr("Could not retrieve answer.")
        if exercise.type in ["translate_to_target", "translate_to_source"]:
            correct_answer_for_display = exercise.answer
        elif exercise.type == "multiple_choice_translation":
            correct_option = next(
                (opt for opt in exercise.options if opt.correct), None
            )
            if correct_option:
                correct_answer_for_display = correct_option.text
        elif exercise.type == "fill_in_the_blank":
            correct_answer_for_display = exercise.correct_option

        self.feedback_label.setText(
            self.tr("Skipped. The correct answer was: {0}").format(correct_answer_for_display)
        )
        self.feedback_label.setStyleSheet("color: orange;")

        self.progress_bar.setValue(self.current_exercise_index + 1)

        self.progress_manager.update_exercise_srs_data(
            exercise.exercise_id,
            is_correct=False, # Skipped is treated as incorrect for SRS progression
            xp_awarded=0,
            quality_score_sm2=0 # Lowest quality for SM-2, ensuring it comes up for review soon
        )

        self.submit_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.next_button.setVisible(True)
        if self.current_exercise_index + 1 >= self.total_exercises_in_lesson:
            self.next_button.setText(self.tr("Finish Lesson 🎉"))
        else:
            self.next_button.setText(self.tr("Next Exercise →"))
        self.next_button.setFocus()

    def _finish_lesson(self):
        self._save_current_note() # Save note for the last exercise in the lesson
        self.feedback_label.setText(self.tr("Lesson '{0}' completed!").format(self.current_lesson.title))
        self.feedback_label.setStyleSheet("color: blue;")
        
        self._clear_exercise_area()

        self.submit_button.setVisible(False)
        self.next_button.setText(self.tr("Back to Course Overview"))
        self.next_button.setVisible(True)
        try:
            self.next_button.clicked.disconnect()
        except TypeError:
            pass
        self.next_button.clicked.connect(self.back_to_overview_signal.emit)

        self.lesson_completed_signal.emit(self.current_lesson.lesson_id)
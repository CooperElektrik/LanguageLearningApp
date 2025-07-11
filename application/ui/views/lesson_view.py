import logging
from enum import Enum, auto

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QStyle,
    QWidget,
    QDialog,
)
from PySide6.QtCore import Signal, Qt, QSettings, QTimer, QEvent

from typing import Optional, List

import settings
import utils
from core.models import Lesson, Exercise
from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from core.stt_manager import STTManager
from ui.views.base_exercise_player_view import BaseExercisePlayerView
from ..dialogs.glossary_detail_dialog import GlossaryDetailDialog
from ..dialogs.glossary_lookup_dialog import GlossaryLookupDialog
from PySide6.QtGui import QKeyEvent  # Added for keyPressEvent

logger = logging.getLogger(__name__)


# State machine for the LessonView
class LessonViewState(Enum):
    INITIAL_LOAD = auto()  # View is first loaded or reset
    ASKING_QUESTION = auto()  # Displaying an exercise, awaiting submission
    ANSWER_SUBMITTED = auto()  # Answer processed, feedback shown (correct or incorrect)
    REVIEWING_MISTAKES = auto()  # Special round for incorrect items
    LESSON_COMPLETED = auto()  # All exercises in the lesson are done


class LessonView(BaseExercisePlayerView):  # Inherit from the new base class
    lesson_completed_signal = Signal(str)  # Emits lesson_id on completion

    def __init__(
        self,
        course_manager: CourseManager,
        progress_manager: ProgressManager,
        stt_manager: STTManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(course_manager, progress_manager, stt_manager, parent)

        self.current_lesson: Optional[Lesson] = None
        self.exercises_in_session: List[Exercise] = []
        self.mistakes_queue: List[Exercise] = []
        self.current_exercise_index: int = -1
        self.total_exercises_in_lesson: int = 0
        self.lesson_start_index: int = 0 # New attribute to store where the lesson started

        self.view_state: LessonViewState = LessonViewState.INITIAL_LOAD

        self._setup_specific_ui()
        self.reset_view()

    def _setup_specific_ui(self):
        """Sets up UI elements unique to LessonView, complementing the base class's UI."""

        self.back_button = QPushButton(self.tr("← Back to Lessons"))
        self.back_button.setObjectName("back_button_lesson")
        self.back_button.clicked.connect(self._handle_back_to_overview)
        self.top_bar_layout.addWidget(self.back_button)

        self.lesson_title_label = QLabel(self.tr("Lesson Title"))
        self.lesson_title_label.setObjectName("lesson_title_label")
        self.lesson_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.top_bar_layout.addWidget(self.lesson_title_label, 1)

        self.progress_bar.setFormat(self.tr("%v / %m Steps"))

        lesson_action_buttons_layout = QHBoxLayout()

        self.toggle_notes_button = QPushButton()
        self.toggle_notes_button.setObjectName("toggle_notes_button_lesson")
        self.toggle_notes_button.setCheckable(True)
        self.toggle_notes_button.toggled.connect(self._toggle_notes_panel)
        lesson_action_buttons_layout.addWidget(self.toggle_notes_button)

        self.toggle_hint_button = QPushButton(self.tr("Show Hint"))
        self.toggle_hint_button.setObjectName("toggle_hint_button_lesson")
        self.toggle_hint_button.setCheckable(
            False
        )  # Behavior is to toggle, not stay pressed
        self.toggle_hint_button.clicked.connect(self._toggle_hint_visibility_manually)
        lesson_action_buttons_layout.addWidget(self.toggle_hint_button)

        self.lookup_button = QPushButton(self.tr("Lookup..."))
        self.lookup_button.setObjectName("lookup_button_lesson")
        self.lookup_button.clicked.connect(self._handle_lookup_word)
        lesson_action_buttons_layout.addWidget(self.lookup_button)

        lesson_action_buttons_layout.addStretch(1)

        self.skip_button = QPushButton(self.tr("Skip"))
        self.skip_button.setObjectName("skip_button_lesson")
        self.skip_button.clicked.connect(self._handle_skip_exercise)
        lesson_action_buttons_layout.addWidget(self.skip_button)

        self.submit_button = QPushButton(self.tr("Submit"))
        self.submit_button.setObjectName("submit_button_lesson")
        self.submit_button.clicked.connect(self._handle_submit_button_click)
        lesson_action_buttons_layout.addWidget(self.submit_button)

        self.next_button = QPushButton(self.tr("Continue"))
        self.next_button.setObjectName("next_button_lesson")
        self.next_button.clicked.connect(self._handle_next_action_click)
        lesson_action_buttons_layout.addWidget(self.next_button)

        self.action_buttons_layout_container.addLayout(lesson_action_buttons_layout)

        self._update_button_states()

    def _update_button_states(self):
        """Manages visibility and enabled state of LessonView-specific buttons based on current state."""
        is_asking = self.view_state in [
            LessonViewState.ASKING_QUESTION,
            LessonViewState.REVIEWING_MISTAKES,
        ]
        is_submitted = self.view_state == LessonViewState.ANSWER_SUBMITTED
        is_completed = self.view_state == LessonViewState.LESSON_COMPLETED
        is_initial = self.view_state == LessonViewState.INITIAL_LOAD

        self.submit_button.setVisible(is_asking)
        # Hide the main submit button for widgets that have their own
        if (
            is_asking
            and self.current_exercise_obj
            and self.current_exercise_obj.type == "context_block"
        ):
            self.submit_button.setVisible(False)
        self.submit_button.setEnabled(is_asking)

        self.skip_button.setVisible(
            is_asking and self.view_state != LessonViewState.REVIEWING_MISTAKES
        )
        self.skip_button.setEnabled(
            is_asking and self.view_state != LessonViewState.REVIEWING_MISTAKES
        )

        self.next_button.setVisible(is_submitted or is_completed)
        self.next_button.setEnabled(is_submitted or is_completed)

        self.toggle_notes_button.setEnabled(not (is_completed or is_initial))
        self.lookup_button.setEnabled(not (is_completed or is_initial))

        can_show_hint = (
            is_asking
            and self.current_exercise_obj
            and self.current_exercise_obj.has_hint()
        )
        self.toggle_hint_button.setVisible(can_show_hint)
        if logger.isEnabledFor(logging.DEBUG):  # Conditional logging
            logger.debug(
                f"_update_button_states (LessonView): can_show_hint={can_show_hint}, "
                f"hint_label.isVisible()={self.hint_label.isVisible() if hasattr(self, 'hint_label') else 'N/A'}, "
                f"is_asking={is_asking}, current_exercise_obj exists={bool(self.current_exercise_obj)}"
            )
        if can_show_hint:
            self.toggle_hint_button.setText(
                self.tr("Hide Hint")
                if self.hint_label.isVisible()
                else self.tr("Show Hint")
            )

        if is_submitted:
            if self.current_exercise_index + 1 >= len(self.exercises_in_session):
                if (
                    self.view_state == LessonViewState.REVIEWING_MISTAKES
                    or not self.mistakes_queue
                ):
                    self.next_button.setText(self.tr("Finish Lesson 🎉"))
                else:
                    self.next_button.setText(self.tr("Review Mistakes →"))
            else:
                self.next_button.setText(self.tr("Next Exercise →"))
            self.next_button.setFocus()
        elif is_completed:
            self.next_button.setText(self.tr("Back to Overview"))
            self.next_button.setFocus()

        if is_asking and self.current_exercise_widget:
            self.current_exercise_widget.set_focus_on_input()

    def start_lesson(self, lesson_id: str):
        """Initiates a new lesson session."""
        self.reset_view()

        self.current_lesson = self.course_manager.get_lesson(lesson_id)

        if not self.current_lesson:
            logger.error(f"Could not load lesson with ID: {lesson_id}")
            self.feedback_label.setText(self.tr("Error: Could not load lesson data."))
            self.feedback_label.setStyleSheet("color: red;")
            self.view_state = LessonViewState.INITIAL_LOAD
            self._update_button_states()
            return

        self.exercises_in_session = self.current_lesson.exercises
        self.lesson_title_label.setText(self.current_lesson.title)

        # Determine resume behavior based on settings
        q_settings = QSettings()
        resume_behavior = q_settings.value(
            settings.QSETTINGS_KEY_LESSON_RESUME_BEHAVIOR,
            settings.LESSON_RESUME_BEHAVIOR_DEFAULT,
            type=str,
        )

        last_index = self.progress_manager.get_lesson_progress(self.current_lesson.lesson_id)
        
        should_resume = False
        if last_index is not None and 0 <= last_index < len(self.exercises_in_session):
            if resume_behavior == settings.LESSON_RESUME_ALWAYS_RESUME:
                should_resume = True
            elif resume_behavior == settings.LESSON_RESUME_ALWAYS_RESTART:
                should_resume = False # Explicitly restart
            elif resume_behavior == settings.LESSON_RESUME_PROMPT:
                reply = QMessageBox.question(
                    self,
                    self.tr("Resume Lesson?"),
                    self.tr(f"You have unfinished progress in this lesson.\n" 
                            f"Would you like to resume from where you left off (Exercise {last_index + 1} of {len(self.exercises_in_session)})?\n\n"
                            f"Click 'Yes' to resume, 'No' to restart from the beginning."),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                should_resume = (reply == QMessageBox.StandardButton.Yes)

        if should_resume:
            self.current_exercise_index = last_index
            logger.info(f"Resuming lesson '{self.current_lesson.title}' from exercise index {self.current_exercise_index}")
        else:
            self.current_exercise_index = 0
            # If restarting, clear previous progress for this lesson
            if last_index is not None:
                self.progress_manager.set_lesson_progress(self.current_lesson.lesson_id, 0)
            logger.info(f"Starting lesson '{self.current_lesson.title}' from the beginning.")

        self.lesson_start_index = self.current_exercise_index # Store where this session started
        self.total_exercises_in_lesson = len(self.exercises_in_session)

        self.progress_bar.setRange(0, self.total_exercises_in_lesson - self.lesson_start_index)
        self.progress_bar.setValue(0)

        self._load_next_exercise_in_lesson()

    def _load_next_exercise_in_lesson(self):
        """Loads the next exercise in the current session, or finishes the lesson."""
        self._save_current_note()
        if self.current_lesson:
            self.progress_manager.set_lesson_progress(self.current_lesson.lesson_id, self.current_exercise_index)
        self.feedback_label.setText("")  # Clear feedback label
        # self._toggle_hint_visibility(force_show=False) # Done by _load_exercise_widget in base
        self.feedback_label.setStyleSheet("")

        if self.current_exercise_index >= len(self.exercises_in_session):
            if (
                self.view_state == LessonViewState.REVIEWING_MISTAKES
                or not self.mistakes_queue
            ):
                self._finish_lesson()
            else:
                self._start_mistake_review()
            return

        exercise_to_load = self.exercises_in_session[self.current_exercise_index]

        if super()._load_exercise_widget(exercise_to_load):
            if self.current_exercise_widget:
                self.current_exercise_widget.answer_submitted.connect(
                    self._handle_submit_answer_from_widget
                )

            self._check_and_auto_show_hint()  # Auto-show from base class
            # Button states (including hint button text) updated at the end of this method

            if self.view_state != LessonViewState.REVIEWING_MISTAKES:
                self.progress_bar.setValue(self.current_exercise_index - self.lesson_start_index)
            self.view_state = (
                LessonViewState.ASKING_QUESTION
                if self.view_state != LessonViewState.REVIEWING_MISTAKES
                else LessonViewState.REVIEWING_MISTAKES
            )
        else:
            self.feedback_label.setText(self.tr("Error loading exercise. Skipping."))
            self.feedback_label.setStyleSheet("color: red;")
            self.view_state = LessonViewState.ANSWER_SUBMITTED

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

    def _handle_submit_button_click(self):
        """Handles the 'Submit' button click."""
        if self.current_exercise_widget and self.view_state in [
            LessonViewState.ASKING_QUESTION,
            LessonViewState.REVIEWING_MISTAKES,
        ]:
            user_answer = self.current_exercise_widget.get_answer()
            self._process_answer(user_answer, was_skipped=False)

    def _handle_submit_answer_from_widget(self, answer_text: str):
        """Handles submission triggered by pressing Enter in the exercise widget."""
        if self.view_state in [
            LessonViewState.ASKING_QUESTION,
            LessonViewState.REVIEWING_MISTAKES,
        ]:
            self._process_answer(answer_text, was_skipped=False)

    def _process_answer(self, user_answer: str, was_skipped: bool):
        """Processes the user's answer or a skipped exercise."""
        if not self.current_exercise_obj:
            return
        self._toggle_hint_visibility(force_show=False)  # Hide hint on submission/skip

        is_correct = False
        feedback_text_display = ""
        xp_to_award = 0
        quality_score_for_srs = 0

        if was_skipped:
            correct_answer_display_part = (
                self.current_exercise_obj.answer
                or self.current_exercise_obj.correct_option
                or "N/A"
            )
            feedback_text_display = self.tr("Skipped. Correct answer: {0}").format(
                correct_answer_display_part
            )
            self.feedback_label.setStyleSheet("color: orange;")
            is_correct = False
            quality_score_for_srs = 0
            if self.current_exercise_obj.explanation:
                feedback_text_display += self.tr("\n\nExplanation: {0}").format(
                    self.current_exercise_obj.explanation
                )
        else:
            if not user_answer.strip() and self.current_exercise_obj.type in [
                "translate_to_target",
                "dictation",
            ]:
                self.feedback_label.setText(self.tr("Please provide an answer."))
                self.feedback_label.setStyleSheet("color: orange;")
                return

            is_correct, feedback_text_display = self.course_manager.check_answer(
                self.current_exercise_obj, user_answer
            )
            self.feedback_label.setStyleSheet(
                "color: green;" if is_correct else "color: red;"
            )
            utils.play_sound(
                settings.SOUND_FILE_CORRECT
                if is_correct
                else settings.SOUND_FILE_INCORRECT
            )

            if is_correct:
                xp_to_award = 10
                quality_score_for_srs = 4
                # If it was a mistake, remove it from the list
                if (
                    self.view_state == LessonViewState.REVIEWING_MISTAKES
                    and self.current_exercise_obj in self.mistakes_queue
                ):
                    self.mistakes_queue.remove(self.current_exercise_obj)
            else:
                xp_to_award = 0
                quality_score_for_srs = 1
                if self.current_exercise_widget:
                    self.current_exercise_widget.clear_input()
                # Add to mistakes queue if it's the first time seeing it in this lesson
                if (
                    self.view_state == LessonViewState.ASKING_QUESTION
                    and self.current_exercise_obj not in self.mistakes_queue
                ):
                    self.mistakes_queue.append(self.current_exercise_obj)
                if self.current_exercise_obj.explanation:
                    feedback_text_display += self.tr("\n\nExplanation: {0}").format(
                        self.current_exercise_obj.explanation
                    )

        self.feedback_label.setText(feedback_text_display)

        self.progress_manager.update_exercise_srs_data(
            self.current_exercise_obj.exercise_id,
            is_correct=is_correct,
            xp_awarded=xp_to_award,
            quality_score_sm2=quality_score_for_srs,
        )

        if self.view_state != LessonViewState.REVIEWING_MISTAKES:
            self.progress_bar.setValue(self.current_exercise_index + 1)

        self.view_state = LessonViewState.ANSWER_SUBMITTED
        self._update_button_states()

    def _handle_next_action_click(self):
        """Handles the 'Next Exercise' or 'Back to Overview' button click."""
        if self.view_state == LessonViewState.LESSON_COMPLETED:
            super()._handle_back_to_overview()
        elif self.view_state == LessonViewState.ANSWER_SUBMITTED:
            self.current_exercise_index += 1
            self._load_next_exercise_in_lesson()

    def _handle_skip_exercise(self):
        """Handles the 'Skip Exercise' button click."""
        if self.view_state != LessonViewState.ASKING_QUESTION:
            return

        reply = QMessageBox.question(
            self,
            self.tr("Skip Exercise"),
            self.tr(
                "Are you sure you want to skip this exercise? It will be marked for earlier review."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # self._toggle_hint_visibility(force_show=False) # Already handled by _process_answer
            self._process_answer(user_answer="", was_skipped=True)

    def _start_mistake_review(self):
        """Initiates the mistake review round at the end of a lesson."""
        logger.info(
            f"Starting mistake review round with {len(self.mistakes_queue)} items."
        )
        self.view_state = LessonViewState.REVIEWING_MISTAKES
        self.exercises_in_session = self.mistakes_queue
        self.current_exercise_index = 0

        self.lesson_title_label.setText(self.tr("Reviewing Mistakes"))
        self.feedback_label.setText(
            self.tr("Let's go over the exercises you had trouble with.")
        )
        self.feedback_label.setStyleSheet("")

        self._load_next_exercise_in_lesson()

    def _finish_lesson(self):
        """Actions to perform when the entire lesson is completed."""
        self._save_current_note()
        if self.current_lesson:
            # Clear lesson progress upon completion
            self.progress_manager.set_lesson_progress(self.current_lesson.lesson_id, 0)
        utils.play_sound(settings.SOUND_FILE_COMPLETE)

        self.feedback_label.setText(
            self.tr("Lesson '{0}' completed!").format(
                self.current_lesson.title if self.current_lesson else ""
            )
        )
        self.feedback_label.setStyleSheet("color: blue;")

        super()._clear_exercise_area()
        self.current_exercise_obj = None

        self.view_state = LessonViewState.LESSON_COMPLETED
        self._update_button_states()

        if self.current_lesson:
            self.lesson_completed_signal.emit(self.current_lesson.lesson_id)

    def reset_view(self):
        """Resets LessonView to its initial state."""
        super().reset_view()

        self.current_lesson = None
        self.exercises_in_session = []
        self.mistakes_queue = []
        self.current_exercise_index = -1
        self.total_exercises_in_lesson = 0

        self.lesson_title_label.setText(self.tr("Lesson"))
        self.progress_bar.setFormat(self.tr("%v / %m Steps"))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.view_state = LessonViewState.INITIAL_LOAD
        self._update_button_states()

    def _handle_lookup_word(self):
        """Opens a dialog to search for a word in the glossary."""
        if not self.course_manager.get_glossary_entries():
            QMessageBox.information(
                self,
                self.tr("Glossary Empty"),
                self.tr("No glossary entries for this course."),
            )
            return

        dialog = GlossaryLookupDialog(self.course_manager.get_glossary_entries(), self)
        result = dialog.exec()

        if result == QDialog.Accepted:
            found_entry = dialog.get_selected_entry()

        if found_entry:
            dialog = GlossaryDetailDialog(found_entry, self.course_manager, self)
            dialog.exec()

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        super().retranslateUi()  # Call base class retranslate

        self.back_button.setText(self.tr("← Back to Lessons"))
        self.lesson_title_label.setText(
            self.tr("Lesson Title")
            if not self.current_lesson
            else self.current_lesson.title
        )  # Keep current title if lesson loaded

        self.progress_bar.setFormat(self.tr("%v / %m Steps"))

        # toggle_notes_button text is set by icon and tooltip in base
        # self.toggle_hint_button text is updated in _update_button_states
        self.lookup_button.setText(self.tr("Lookup..."))
        self.skip_button.setText(self.tr("Skip"))
        self.submit_button.setText(self.tr("Submit"))
        # self.next_button text is updated in _update_button_states

        # Update texts that depend on state
        self._update_button_states()

        if self.view_state == LessonViewState.REVIEWING_MISTAKES:
            self.lesson_title_label.setText(self.tr("Reviewing Mistakes"))

        logger.debug("LessonView retranslated.")

    def keyPressEvent(self, event: QKeyEvent):
        """Handles keyboard shortcuts specific to LessonView."""
        # Add any lesson-specific shortcuts here if needed in the future
        # For now, just pass to base for common shortcuts like Ctrl+H, Ctrl+N
        super().keyPressEvent(event)

import logging
from enum import (
    Enum,
    auto,
)  # For generic state if needed, or subclasses define their own
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QProgressBar,
    QMessageBox,
    QGroupBox,
    QTextEdit,
    QStyle,
)
from PySide6.QtCore import Signal, Qt, QTimer, QSettings, QEvent
from typing import Optional, Type, Dict  # For EXERCISE_WIDGET_MAP type hint

from core.models import Exercise
from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from core.stt_manager import STTManager
from ui.widgets.exercise_widgets import BaseExerciseWidget, EXERCISE_WIDGET_MAP
import settings as app_settings  # For QSettings keys
from PySide6.QtGui import QKeyEvent  # Added for keyPressEvent

logger = logging.getLogger(__name__)


class BaseExercisePlayerView(QWidget):
    """
    A base class for views that present exercises to the user one by one,
    including features like an exercise display area, feedback, and a notes panel.
    Subclasses (LessonView, ReviewView) will implement specific control logic
    and progression.
    """

    back_to_overview_signal = Signal()  # Common signal

    NOTES_SAVE_INTERVAL_MS = 1500

    def __init__(
        self,
        course_manager: CourseManager,
        progress_manager: ProgressManager,
        stt_manager: STTManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager
        self.stt_manager = stt_manager

        self.current_exercise_obj: Optional[Exercise] = None
        self.current_exercise_widget: Optional[BaseExerciseWidget] = None

        self._setup_common_ui()

    def _setup_common_ui(self):
        """Sets up UI elements common to all exercise player views."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setObjectName(f"{self.__class__.__name__}_main_layout")

        # Top Bar: Subclasses will populate this (e.g., Back button, Title)
        self.top_bar_layout = QHBoxLayout()
        self.main_layout.addLayout(self.top_bar_layout)

        # Progress Bar: Subclasses will configure range and value
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName(f"{self.__class__.__name__}_progress_bar")
        self.progress_bar.setTextVisible(True)  # Default, can be overridden
        self.main_layout.addWidget(self.progress_bar)

        # Exercise Area
        self.exercise_area_container = QFrame()
        self.exercise_area_container.setObjectName(
            f"{self.__class__.__name__}_exercise_area_container"
        )
        self.exercise_area_layout = QVBoxLayout(self.exercise_area_container)
        self.main_layout.addWidget(self.exercise_area_container, 1)  # Stretch

        # Hint Label (initially hidden)
        self.hint_label = QLabel("")
        self.hint_label.setObjectName(f"{self.__class__.__name__}_hint_label")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setWordWrap(True)
        self.hint_label.setVisible(False)  # Start hidden
        self.main_layout.addWidget(self.hint_label)  # Add it before notes or feedback

        # Notes Panel
        self.notes_group_box = QGroupBox(self.tr("My Notes"))
        self.notes_group_box.setObjectName(f"{self.__class__.__name__}_notes_groupbox")
        self.notes_group_box.setVisible(False)
        notes_layout = QVBoxLayout(self.notes_group_box)

        self.notes_text_edit = QTextEdit()
        self.notes_text_edit.setObjectName(f"{self.__class__.__name__}_notes_text_edit")
        self.notes_text_edit.setPlaceholderText(
            self.tr("Type your personal notes for this exercise here...")
        )

        self.notes_save_timer = QTimer(self)
        self.notes_save_timer.setSingleShot(True)
        self.notes_save_timer.setInterval(self.NOTES_SAVE_INTERVAL_MS)
        self.notes_save_timer.timeout.connect(self._save_current_note)
        self.notes_text_edit.textChanged.connect(self.notes_save_timer.start)
        notes_layout.addWidget(self.notes_text_edit)
        self.main_layout.addWidget(self.notes_group_box)

        # Feedback Label
        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName(f"{self.__class__.__name__}_feedback_label")
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setWordWrap(True)
        self.main_layout.addWidget(self.feedback_label)

        # Action Buttons Area: Subclasses will populate this with specific buttons
        self.action_buttons_layout_container = (
            QVBoxLayout()
        )  # Or QHBoxLayout based on subclass needs
        self.main_layout.addLayout(self.action_buttons_layout_container)

    def _clear_exercise_area(self):
        """Clears the current exercise widget and related data."""
        if self.current_exercise_widget:
            self.current_exercise_widget.stop_media()
            # Attempt to disconnect signals robustly
            try:
                # Assuming a common signal name 'answer_submitted' from BaseExerciseWidget
                # If signal names differ, this needs to be more generic or handled by subclass
                if hasattr(self.current_exercise_widget, "answer_submitted"):
                    self.current_exercise_widget.answer_submitted.disconnect()
            except (TypeError, RuntimeError) as e:
                logger.debug(f"Error disconnecting signal during clear: {e}")
                pass  # Signal might not have been connected or widget already deleting
            self.current_exercise_widget.deleteLater()
        if self.hint_label:  # Clear and hide hint
            self._toggle_hint_visibility(force_show=False)
            self.current_exercise_widget = None

    def _load_exercise_widget(self, exercise: Exercise) -> bool:
        """
        Loads the appropriate widget for the given exercise.
        Returns True if successful, False otherwise.
        """
        self._clear_exercise_area()  # Clear previous widget first
        self.current_exercise_obj = exercise  # Set current exercise context
        self._toggle_hint_visibility(force_show=False)  # Ensure previous hint is hidden

        widget_class = EXERCISE_WIDGET_MAP.get(exercise.type)
        if widget_class:
            if exercise.type == "pronunciation_practice":
                self.current_exercise_widget = widget_class(
                    exercise,
                    self.course_manager,
                    self.stt_manager,
                    self.exercise_area_container,  # Parent to container
                )
            else:
                self.current_exercise_widget = widget_class(
                    exercise,
                    self.course_manager,
                    self.exercise_area_container,  # Parent to container
                )
            # Trigger autoplay after the widget is created and added to the layout
            self.current_exercise_widget.trigger_autoplay_audio()

            self.exercise_area_layout.addWidget(self.current_exercise_widget)

            # Subclasses will connect to self.current_exercise_widget.answer_submitted
            # Example: self.current_exercise_widget.answer_submitted.connect(self._some_handler)

            # Load notes for the new exercise
            note_text = self.progress_manager.get_exercise_note(exercise.exercise_id)
            self.notes_text_edit.blockSignals(True)
            self.notes_text_edit.setPlainText(note_text or "")
            self.notes_text_edit.blockSignals(False)
            self._update_notes_button_indicator()  # Update based on newly loaded note

            return True
        else:
            error_msg = self.tr("Unsupported exercise type: {0}").format(exercise.type)
            logger.error(error_msg + f" (Exercise ID: {exercise.exercise_id})")
            self.feedback_label.setText(error_msg)
            self.feedback_label.setStyleSheet("color: red;")
            self.current_exercise_obj = None  # Clear if widget fails to load
            return False

    def _toggle_hint_visibility(self, force_show: Optional[bool] = None):
        """
        Toggles or sets the visibility of the hint label.
        This method is intended to be called by subclasses or internal logic.
        """
        if not self.hint_label:  # Should not happen if _setup_common_ui ran
            logger.error("Hint label not initialized in BaseExercisePlayerView.")
            return

        if not self.current_exercise_obj or not self.current_exercise_obj.has_hint():
            self.hint_label.setText("")
            self.hint_label.setVisible(False)
            return

        if force_show is not None:
            new_visibility = force_show
        else:
            new_visibility = not self.hint_label.isVisible()

        if new_visibility:
            self.hint_label.setText(
                self.tr("Hint: {0}").format(self.current_exercise_obj.translation_hint)
            )
        else:
            self.hint_label.setText("")  # Clear text when hiding
        self.hint_label.setVisible(new_visibility)

    def _check_and_auto_show_hint(self):
        """Checks user preference and auto-shows hint if enabled and not already visible."""
        q_settings = QSettings()
        autoshow_enabled = q_settings.value(
            app_settings.QSETTINGS_KEY_AUTOSHOW_HINTS,
            app_settings.AUTOSHOW_HINTS_DEFAULT,
            type=bool,
        )
        if (
            autoshow_enabled
            and self.current_exercise_obj
            and self.current_exercise_obj.has_hint()
            and not self.hint_label.isVisible()
        ):
            self._toggle_hint_visibility(force_show=True)
            logger.info(
                "Hint automatically shown for the current exercise based on user setting."
            )

    # --- Notes Panel Methods (Common Logic) ---
    def _toggle_notes_panel(self, checked: bool):
        self.notes_group_box.setVisible(checked)
        if checked:
            self.notes_text_edit.setFocus()
        else:  # Panel is being hidden
            self._save_current_note()  # Explicitly save
        self._update_notes_button_indicator()

    def _save_current_note(self):
        self.notes_save_timer.stop()  # Stop any pending debounced save
        if self.current_exercise_obj:  # Only save if an exercise is currently loaded
            note_content = self.notes_text_edit.toPlainText().strip()
            self.progress_manager.save_exercise_note(
                self.current_exercise_obj.exercise_id, note_content
            )
            self._update_notes_button_indicator()  # Update button icon based on saved note presence
            logger.debug(
                f"Note saved for exercise ID: {self.current_exercise_obj.exercise_id}"
            )

    def _update_notes_button_indicator(self):
        """Updates the toggle notes button icon and tooltip based on note presence."""
        has_note = False
        if self.current_exercise_obj:
            note_content = self.progress_manager.get_exercise_note(
                self.current_exercise_obj.exercise_id
            )
            if (
                note_content and note_content.strip()
            ):  # Check if note is not just whitespace
                has_note = True

        # This assumes the subclass creates self.toggle_notes_button
        if hasattr(self, "toggle_notes_button") and self.toggle_notes_button:
            icon_to_use = (
                QStyle.StandardPixmap.SP_FileDialogDetailedView
                if has_note
                else QStyle.StandardPixmap.SP_FileIcon
            )
            tooltip_text = self.tr("Edit Notes") if has_note else self.tr("Add Notes")

            self.toggle_notes_button.setIcon(self.style().standardIcon(icon_to_use))
            self.toggle_notes_button.setToolTip(tooltip_text)
        else:
            logger.debug(
                "_update_notes_button_indicator called but toggle_notes_button not found."
            )

    # --- Abstract or Overridable Methods for Subclasses ---
    def _handle_back_to_overview(self):
        """Default implementation for handling 'back to overview' action."""
        self._save_current_note()  # Ensure notes are saved
        self.reset_view()  # Clean up the view
        self.back_to_overview_signal.emit()

    def reset_view(self):
        """
        Resets the view to its initial state.
        Subclasses should override to reset their specific state and UI elements.
        """
        logger.debug(f"Resetting view: {self.__class__.__name__}")
        self._clear_exercise_area()
        self.current_exercise_obj = None

        self.feedback_label.setText("")
        self.feedback_label.setStyleSheet("")

        self._toggle_hint_visibility(force_show=False)  # Hide any visible hint
        self.notes_text_edit.clear()
        if (
            hasattr(self, "toggle_notes_button") and self.toggle_notes_button
        ):  # Check if button exists
            self.toggle_notes_button.setChecked(
                False
            )  # Hides notes panel if connected to _toggle_notes_panel
        self.notes_group_box.setVisible(False)  # Ensure hidden

        # Subclasses should reset their specific progress indicators (e.g., progress bar, titles)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("")  # Subclass should set its own format

    # Subclasses will need to implement/override:
    # - How they populate self.top_bar_layout
    # - How they populate self.action_buttons_layout_container
    # - Their specific state management (Enum and _update_button_states methods)
    # - Their exercise loading and progression logic (e.g., start_session(), _load_next_exercise())
    # - How they connect to self.current_exercise_widget.answer_submitted

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        """Retranslates common UI elements in the base player view."""
        self.notes_group_box.setTitle(self.tr("My Notes"))
        self.notes_text_edit.setPlaceholderText(
            self.tr("Type your personal notes for this exercise here...")
        )

        # If hint is visible, retranslate it
        if (
            self.hint_label.isVisible()
            and self.current_exercise_obj
            and self.current_exercise_obj.has_hint()
        ):
            self.hint_label.setText(
                self.tr("Hint: {0}").format(self.current_exercise_obj.translation_hint)
            )

        self._update_notes_button_indicator()  # This uses self.tr() for tooltips
        logger.debug(f"{self.__class__.__name__} common elements retranslated.")

    def keyPressEvent(self, event: QKeyEvent):
        """Handles common keyboard shortcuts for the exercise player."""
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_H:
                # Check if the specific view (LessonView or ReviewView) has this button
                if (
                    hasattr(self, "toggle_hint_button")
                    and self.toggle_hint_button
                    and self.toggle_hint_button.isVisible()
                ):
                    self.toggle_hint_button.click()  # Simulate a click to ensure all logic (text change etc.) runs
                    event.accept()
                    return
            elif event.key() == Qt.Key_N:
                # Check if the specific view has this button
                if hasattr(self, "toggle_notes_button") and self.toggle_notes_button:
                    self.toggle_notes_button.setChecked(
                        not self.toggle_notes_button.isChecked()
                    )
                    event.accept()
                    return
        super().keyPressEvent(
            event
        )  # Pass to parent or for further processing if not handled

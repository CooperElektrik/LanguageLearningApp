import logging
import os
import sys
from typing import Any, Dict, Optional, Type

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QButtonGroup,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import Signal, QUrl, Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import utils

from core.models import Exercise
from core.course_manager import (
    PROMPT_KEY_DEFAULT,
    PROMPT_KEY_FIB,
    PROMPT_KEY_MCQ_TRANSLATION,
    PROMPT_KEY_TRANSLATE_TO_SOURCE,
    PROMPT_KEY_TRANSLATE_TO_TARGET,
)

logger = logging.getLogger(__name__)

class BaseExerciseWidget(QWidget):
    answer_submitted = Signal(str) # Emits the selected/entered answer text

    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(parent)
        self.exercise = exercise
        self.course_manager = course_manager
        # Determine asset base directory more robustly
        # Prefer manifest directory, fall back to content directory.
        self.assets_base_dir = self.course_manager.get_course_manifest_directory()
        if not self.assets_base_dir:
            self.assets_base_dir = self.course_manager.get_course_content_directory()
            if self.assets_base_dir:
                logger.warning(
                    "Asset base directory derived from content directory. Manifest directory is preferred."
                )
            else:
                logger.error(f"Could not determine asset base directory for exercise {self.exercise.exercise_id}. Assets may fail to load.")
        
        self.layout = QVBoxLayout(self)
        self.prompt_label = QLabel()
        self.prompt_label.setObjectName("prompt_label")
        self.prompt_label.setWordWrap(True)
        self.layout.addWidget(self.prompt_label)

        self.image_label = QLabel()
        self.image_label.setObjectName("image_label")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMaximumWidth(380) # Adjusted for typical layout
        self.image_label.setMaximumHeight(280)
        self.image_label.setScaledContents(False) # Important for aspect ratio
        self._setup_image() # Helper for image loading
        self.layout.addWidget(self.image_label, alignment=Qt.AlignCenter)
        
        self._media_player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None


    def _setup_image(self):
        if self.exercise.image_file and self.assets_base_dir:
            # Construct path using utils.get_resource_path relative to the assets_base_dir
            # This requires careful thought: get_resource_path is from app root.
            # Assets for courses are relative to the course itself.
            # So, assets_base_dir should be an absolute path.
            full_image_path = os.path.join(self.assets_base_dir, self.exercise.image_file)
            
            if os.path.exists(full_image_path):
                pixmap = QPixmap(full_image_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        self.image_label.maximumWidth(),
                        self.image_label.maximumHeight(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    self.image_label.setPixmap(scaled_pixmap)
                    self.image_label.setVisible(True)
                else:
                    logger.warning(f"Failed to load image (pixmap is null): {full_image_path}")
                    self.image_label.setVisible(False)
            else:
                logger.warning(f"Image file not found: {full_image_path}")
                self.image_label.setVisible(False)
        else:
            self.image_label.setVisible(False)

    def _init_audio_player(self):
        """Initializes QMediaPlayer and QAudioOutput if not already done."""
        if self._media_player is None:
            self._media_player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._media_player.setAudioOutput(self._audio_output)
            # Connect error signals for better debugging
            self._media_player.errorOccurred.connect(self._handle_media_error)

    def _handle_media_error(self, error: QMediaPlayer.Error, error_string: str):
        logger.error(f"QMediaPlayer Error ({error}): {error_string}")
        # Avoid showing QMessageBox directly from here if this widget is reused in non-interactive contexts
        # Signals could be used to propagate error to parent view if UI feedback is needed.

    def _play_audio_file(self, relative_audio_path: str):
        """Plays an audio file specified by a path relative to assets_base_dir."""
        if not relative_audio_path or not self.assets_base_dir:
            logger.warning("Audio file path or assets base directory is missing.")
            return

        self._init_audio_player() # Ensure player is initialized

        full_audio_path = os.path.join(self.assets_base_dir, relative_audio_path)

        if os.path.exists(full_audio_path):
            self._media_player.setSource(QUrl.fromLocalFile(full_audio_path))
            # Check media player status before playing
            if self._media_player.mediaStatus() == QMediaPlayer.NoMedia and self._media_player.error() != QMediaPlayer.NoError:
                 logger.error(f"Error setting media source for {full_audio_path}: {self._media_player.errorString()}")
                 QMessageBox.warning(
                    self,
                    self.tr("Audio Error"),
                    self.tr("Cannot prepare audio: {0}").format(self._media_player.errorString()),
                 )
                 return

            self._media_player.play()
            if self._media_player.playbackState() == QMediaPlayer.PlayingState:
                logger.info(f"Playing audio: {full_audio_path}")
            elif self._media_player.error() != QMediaPlayer.NoError: # Check error after play attempt
                 logger.error(f"Error playing audio {full_audio_path}: {self._media_player.errorString()}")
                 QMessageBox.warning(
                    self,
                    self.tr("Audio Error"),
                    self.tr("Cannot play audio: {0}").format(self._media_player.errorString()),
                 )

        else:
            logger.error(f"Audio file not found: {full_audio_path}")
            QMessageBox.warning(
                self,
                self.tr("Audio Error"),
                self.tr("Audio file not found: {0}\n\nCheck course assets and paths.").format(relative_audio_path),
            )

    def _format_prompt_from_data(self, prompt_data: Dict[str, Any]) -> str:
        """Helper to format the prompt using tr() and arguments from prompt_data."""
        template_key = prompt_data.get("template_key", PROMPT_KEY_DEFAULT)
        args = prompt_data.get("args", [])
        
        # Templates are defined using Python's %s style placeholders.
        # self.tr() will fetch the translated template string.
        # Note: The order and number of %s placeholders in the translated string
        # in the .ts file MUST match the number of arguments provided.
        
        template_str_map = {
            PROMPT_KEY_TRANSLATE_TO_TARGET: self.tr("Translate to %s: \"%s\""),
            PROMPT_KEY_TRANSLATE_TO_SOURCE: self.tr("Translate to %s: \"%s\""),
            PROMPT_KEY_MCQ_TRANSLATION: self.tr("Choose the %s translation for: \"%s\" (%s)"),
            PROMPT_KEY_FIB: self.tr("%s (Hint: %s)"),
            PROMPT_KEY_DEFAULT: self.tr("Exercise Prompt: %s") if args else self.tr("Exercise Prompt")
        }

        template_str = template_str_map.get(template_key)
        
        if template_str is None: # Fallback for unknown key
            logger.warning(f"Unknown prompt template key: {template_key}. Using generic fallback.")
            template_str = self.tr("Exercise: %s") if args else self.tr("Exercise")

        formatted_string = template_str
        if args:
            str_args = tuple(str(arg) for arg in args)
            try:
                formatted_string = template_str % str_args
            except TypeError:
                logger.error(
                    f"String formatting error for template key '{template_key}'. "
                    f"Template (translated): '{template_str}', Args: {str_args}. "
                    "Ensure placeholder count in translation matches argument count."
                )
                # Fallback: Append args to avoid crash, though translation might be broken
                formatted_string = f"{template_str} ({', '.join(str_args)})"
        
        return formatted_string

    def get_answer(self) -> str:
        raise NotImplementedError("Subclasses must implement get_answer")

    def clear_input(self):
        raise NotImplementedError("Subclasses must implement clear_input")

    def set_focus_on_input(self):
        """Sets focus to the primary input element of the exercise."""
        pass # Subclasses should implement if they have an input element

    def stop_media(self):
        """Stops any playing media."""
        if self._media_player and self._media_player.playbackState() == QMediaPlayer.PlayingState:
            self._media_player.stop()


class TranslationExerciseWidget(BaseExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)

        prompt_data = self.course_manager.get_formatted_prompt_data(self.exercise)
        formatted_prompt = self._format_prompt_from_data(prompt_data)
        self.prompt_label.setText(formatted_prompt)

        if self.exercise.audio_file:
            self.play_audio_button = QPushButton(self.tr("🔊 Play Audio"))
            self.play_audio_button.setObjectName("play_audio_button")
            self.play_audio_button.clicked.connect(
                lambda: self._play_audio_file(self.exercise.audio_file)
            )
            # Insert button after prompt_label or image_label, depending on which is visible
            insert_index = self.layout.indexOf(self.prompt_label) + 1
            if self.image_label.isVisible():
                insert_index = self.layout.indexOf(self.image_label) + 1
            self.layout.insertWidget(insert_index, self.play_audio_button)


        self.answer_input = QLineEdit()
        self.answer_input.setObjectName("answer_input_text")
        # self.answer_input.setFont(QFont(settings.DEFAULT_FONT_FAMILY, settings.DEFAULT_FONT_SIZE_LARGE)) # Example: use settings
        self.layout.addWidget(self.answer_input)
        self.answer_input.returnPressed.connect(
            lambda: self.answer_submitted.emit(self.get_answer())
        )

    def get_answer(self) -> str:
        return self.answer_input.text()

    def clear_input(self):
        self.answer_input.clear()

    def set_focus_on_input(self):
        self.answer_input.setFocus()


class RadioButtonOptionExerciseWidget(BaseExerciseWidget):
    """
    Base class for exercises that present options as radio buttons (e.g., MCQ, some FIB).
    """
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        
        self.options_group = QButtonGroup(self)
        # self.options_group.setExclusive(True) # Default behavior

        options_layout = QVBoxLayout() # This layout will hold the radio buttons

        options_to_display = self.exercise.options
        if not options_to_display:
            logger.warning(f"No options found for option-based exercise: {self.exercise.exercise_id}")
            no_options_label = QLabel(self.tr("No options available for this exercise."))
            options_layout.addWidget(no_options_label)
        else:
            for i, option_obj in enumerate(options_to_display): # Assuming exercise.options are ExerciseOption objects
                rb = QRadioButton(option_obj.text)
                rb.setObjectName(f"option_radio_button_{i}")
                # rb.setFont(QFont(settings.DEFAULT_FONT_FAMILY, settings.DEFAULT_FONT_SIZE_LARGE)) # Use settings
                options_layout.addWidget(rb)
                self.options_group.addButton(rb, i) # Associate radio button with an ID (index)

        self.layout.addLayout(options_layout)
        
        # Emit signal when a button is clicked (often means answer is selected)
        self.options_group.buttonClicked.connect(
            lambda button: self.answer_submitted.emit(self.get_answer())
        )

    def get_answer(self) -> str:
        checked_button = self.options_group.checkedButton()
        return checked_button.text() if checked_button else ""

    def clear_input(self):
        checked_button = self.options_group.checkedButton()
        if checked_button:
            # Temporarily disable exclusive mode to uncheck
            self.options_group.setExclusive(False)
            checked_button.setChecked(False)
            self.options_group.setExclusive(True)

    def set_focus_on_input(self):
        if self.options_group.buttons():
            self.options_group.buttons()[0].setFocus()


class MultipleChoiceExerciseWidget(RadioButtonOptionExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        
        prompt_data = self.course_manager.get_formatted_prompt_data(self.exercise)
        formatted_prompt = self._format_prompt_from_data(prompt_data)
        self.prompt_label.setText(formatted_prompt)


class FillInTheBlankExerciseWidget(RadioButtonOptionExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)

        prompt_data = self.course_manager.get_formatted_prompt_data(self.exercise)
        formatted_prompt = self._format_prompt_from_data(prompt_data)
        self.prompt_label.setText(formatted_prompt)

EXERCISE_WIDGET_MAP: Dict[str, Type[BaseExerciseWidget]] = {
    "translate_to_target": TranslationExerciseWidget,
    "translate_to_source": TranslationExerciseWidget,
    "multiple_choice_translation": MultipleChoiceExerciseWidget,
    "fill_in_the_blank": FillInTheBlankExerciseWidget,
}

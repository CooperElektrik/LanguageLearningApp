import logging
import os
import sys
import random
from typing import Any, Dict, Optional, Type, List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QButtonGroup,
    QPushButton,
    QMessageBox,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QTextEdit,
)
from PySide6.QtCore import Signal, QUrl, Qt, QTimer, QSettings
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

try:
    from application.core.models import Exercise
    from application.core.course_manager import (
        PROMPT_KEY_DEFAULT,
        PROMPT_KEY_FIB,
        PROMPT_KEY_MCQ_TRANSLATION,
        PROMPT_KEY_TRANSLATE_TO_SOURCE,
        PROMPT_KEY_TRANSLATE_TO_TARGET,
        PROMPT_KEY_IMAGE_ASSOCIATION,
        PROMPT_KEY_LISTEN_SELECT,
        PROMPT_KEY_SENTENCE_JUMBLE,
        PROMPT_KEY_CONTEXT_BLOCK,
        PROMPT_KEY_DICTATION,
    )
    from application import settings as app_settings # For reading autoplay setting
except ImportError: # This makes Nuitka happy
    from core.models import Exercise
    from core.course_manager import (
        PROMPT_KEY_DEFAULT,
        PROMPT_KEY_FIB,
        PROMPT_KEY_MCQ_TRANSLATION,
        PROMPT_KEY_TRANSLATE_TO_SOURCE,
        PROMPT_KEY_TRANSLATE_TO_TARGET,
        PROMPT_KEY_IMAGE_ASSOCIATION,
        PROMPT_KEY_LISTEN_SELECT,
        PROMPT_KEY_SENTENCE_JUMBLE,
        PROMPT_KEY_CONTEXT_BLOCK,
        PROMPT_KEY_DICTATION,
    )
    import settings as app_settings # Fallback for Nuitka

logger = logging.getLogger(__name__)

class BaseExerciseWidget(QWidget):
    answer_submitted = Signal(str)

    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(parent)
        self.exercise = exercise
        self.course_manager = course_manager
        self.assets_base_dir = self.course_manager.get_course_manifest_directory()
        if not self.assets_base_dir:
            self.assets_base_dir = self.course_manager.get_course_content_directory()
        
        self.layout = QVBoxLayout(self)
        self.prompt_label = QLabel()
        self.prompt_label.setObjectName("prompt_label")
        self.prompt_label.setWordWrap(True)
        self.layout.addWidget(self.prompt_label)

        self.image_label = QLabel()
        self.image_label.setObjectName("image_label")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMaximumWidth(380)
        self.image_label.setMaximumHeight(280)
        self.image_label.setScaledContents(False)
        self._setup_image()
        self.layout.addWidget(self.image_label, alignment=Qt.AlignCenter)
        
        self._media_player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None


    def _setup_image(self):
        if self.exercise.image_file and self.assets_base_dir:
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
                    return        
            # self.image_label.setVisible(False)
            self.image_label.setText(f"Cannot load image: {self.exercise.image_file}")
            return
        self.image_label.setVisible(False)

    def _init_audio_player(self):
        """Initializes QMediaPlayer and QAudioOutput if not already done."""
        if self._media_player is None:
            self._media_player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._media_player.setAudioOutput(self._audio_output)
            self._media_player.errorOccurred.connect(self._handle_media_error)

    def _handle_media_error(self, error: QMediaPlayer.Error, error_string: str):
        logger.error(f"QMediaPlayer Error ({error}): {error_string}")

    def _play_audio_file(self, relative_audio_path: str):
        """Plays an audio file specified by a path relative to assets_base_dir."""
        if not relative_audio_path or not self.assets_base_dir:
            return

        self._init_audio_player()

        full_audio_path = os.path.join(self.assets_base_dir, relative_audio_path)

        if os.path.exists(full_audio_path):
            self._media_player.setSource(QUrl.fromLocalFile(full_audio_path))
            if self._media_player.mediaStatus() == QMediaPlayer.NoMedia and self._media_player.error() != QMediaPlayer.NoError:
                 logger.error(f"Error setting media source for {full_audio_path}: {self._media_player.errorString()}")
                 QMessageBox.warning(self, self.tr("Audio Error"), self.tr("Cannot prepare audio: {0}").format(self._media_player.errorString()))
                 return

            self._media_player.play()
        else:
            logger.error(f"Audio file not found: {full_audio_path}")
            QMessageBox.warning(self, self.tr("Audio Error"), self.tr("Audio file not found: {0}").format(relative_audio_path))

    def _format_prompt_from_data(self, prompt_data: Dict[str, Any]) -> str:
        """Helper to format the prompt using tr() and arguments from prompt_data."""
        template_key = prompt_data.get("template_key", PROMPT_KEY_DEFAULT)
        args = prompt_data.get("args", [])
        
        template_str_map = {
            PROMPT_KEY_TRANSLATE_TO_TARGET: self.tr("Translate to %s: \"%s\""),
            PROMPT_KEY_TRANSLATE_TO_SOURCE: self.tr("Translate to %s: \"%s\""),
            PROMPT_KEY_MCQ_TRANSLATION: self.tr("Choose the %s translation for: \"%s\" (%s)"),
            PROMPT_KEY_FIB: self.tr("%s (Hint: %s)"),
            PROMPT_KEY_DICTATION: self.tr("%s"),
            PROMPT_KEY_IMAGE_ASSOCIATION: self.tr("%s"),
            PROMPT_KEY_LISTEN_SELECT: self.tr("%s"),
            PROMPT_KEY_SENTENCE_JUMBLE: self.tr("%s"),
            PROMPT_KEY_CONTEXT_BLOCK: self.tr("%s"),
            PROMPT_KEY_DEFAULT: self.tr("Exercise Prompt: %s") if args else self.tr("Exercise Prompt")
        }

        template_str = template_str_map.get(template_key, "")
        
        formatted_string = template_str
        if args:
            str_args = tuple(str(arg) for arg in args)
            try:
                formatted_string = template_str % str_args
            except TypeError:
                logger.error(f"String formatting error for template key '{template_key}'.")
                formatted_string = f"{template_str} ({', '.join(str_args)})"
        
        return formatted_string

    def get_answer(self) -> str:
        raise NotImplementedError("Subclasses must implement get_answer")

    def clear_input(self):
        raise NotImplementedError("Subclasses must implement clear_input")

    def set_focus_on_input(self):
        pass

    def stop_media(self):
        if self._media_player and self._media_player.playbackState() == QMediaPlayer.PlayingState:
            self._media_player.stop()

    def trigger_autoplay_audio(self):
        """
        Checks the application settings and autoplays the exercise's audio
        if the feature is enabled and an audio file is associated with the exercise.
        """
        if not self.exercise or not self.exercise.audio_file:
            logger.debug(f"No audio file for exercise {self.exercise.exercise_id if self.exercise else 'N/A'}, skipping autoplay.")
            return

        q_settings = QSettings()
        autoplay_enabled = q_settings.value(
            app_settings.QSETTINGS_KEY_AUTOPLAY_AUDIO,
            app_settings.AUTOPLAY_AUDIO_DEFAULT,
            type=bool
        )

        if autoplay_enabled:
            logger.info(f"Autoplay enabled. Playing audio for exercise: {self.exercise.exercise_id}")
            self._play_audio_file(self.exercise.audio_file)


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
            insert_index = self.layout.indexOf(self.prompt_label) + 1
            if self.image_label.isVisible():
                insert_index = self.layout.indexOf(self.image_label) + 1
            self.layout.insertWidget(insert_index, self.play_audio_button)


        self.answer_input = QLineEdit()
        self.answer_input.setObjectName("answer_input_text")
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
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        
        self.options_group = QButtonGroup(self)
        options_layout = QVBoxLayout()

        options_to_display = self.exercise.options
        if not options_to_display:
            logger.warning(f"No options found for option-based exercise: {self.exercise.exercise_id}")
            options_layout.addWidget(QLabel(self.tr("No options available for this exercise.")))
        else:
            for i, option_obj in enumerate(options_to_display):
                rb = QRadioButton(option_obj.text)
                rb.setObjectName(f"option_radio_button_{i}")
                options_layout.addWidget(rb)
                self.options_group.addButton(rb, i)

        self.layout.addLayout(options_layout)
        self.options_group.buttonClicked.connect(
            lambda button: self.answer_submitted.emit(self.get_answer())
        )

    def get_answer(self) -> str:
        checked_button = self.options_group.checkedButton()
        return checked_button.text() if checked_button else ""

    def clear_input(self):
        checked_button = self.options_group.checkedButton()
        if checked_button:
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

class ListenSelectExerciseWidget(RadioButtonOptionExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        
        prompt_data = self.course_manager.get_formatted_prompt_data(self.exercise)
        formatted_prompt = self._format_prompt_from_data(prompt_data)
        self.prompt_label.setText(formatted_prompt)

        if self.exercise.audio_file:
            self.play_audio_button = QPushButton(self.tr("🔊 Play Audio"))
            self.play_audio_button.setObjectName("play_audio_button")
            self.play_audio_button.clicked.connect(lambda: self._play_audio_file(self.exercise.audio_file))
            insert_index = self.layout.indexOf(self.prompt_label) + 1
            self.layout.insertWidget(insert_index, self.play_audio_button)

class FillInTheBlankExerciseWidget(RadioButtonOptionExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        prompt_data = self.course_manager.get_formatted_prompt_data(self.exercise)
        formatted_prompt = self._format_prompt_from_data(prompt_data)
        self.prompt_label.setText(formatted_prompt)

class SentenceJumbleExerciseWidget(BaseExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        prompt_data = self.course_manager.get_formatted_prompt_data(self.exercise)
        self.prompt_label.setText(self._format_prompt_from_data(prompt_data))

        self.current_sentence_words: List[str] = []
        self.word_bank_buttons: List[QPushButton] = []

        self.sentence_display = QLabel(self.tr("Your sentence will appear here."))
        self.sentence_display.setObjectName("sentence_jumble_display")
        self.sentence_display.setWordWrap(True)
        self.layout.addWidget(self.sentence_display)

        separator = QFrame(); separator.setFrameShape(QFrame.Shape.HLine)
        self.layout.addWidget(separator)

        self.word_bank_layout = QGridLayout()
        self.layout.addLayout(self.word_bank_layout)
        self._setup_word_bank()

        self.submit_button = QPushButton(self.tr("Submit Sentence"))
        self.submit_button.clicked.connect(lambda: self.answer_submitted.emit(self.get_answer()))
        self.layout.addWidget(self.submit_button)

    def _setup_word_bank(self):
        words = list(self.exercise.words) if self.exercise.words else []
        random.shuffle(words)
        for i, word in enumerate(words):
            button = QPushButton(word)
            button.clicked.connect(lambda checked, w=word, b=button: self._add_word_to_sentence(w, b))
            self.word_bank_buttons.append(button)
            row, col = divmod(i, 4)
            self.word_bank_layout.addWidget(button, row, col)
        self._update_display()

    def _add_word_to_sentence(self, word: str, button: QPushButton):
        self.current_sentence_words.append(word)
        button.setEnabled(False)
        self._update_display()

    def _update_display(self):
        if self.current_sentence_words:
            self.sentence_display.setText(" ".join(self.current_sentence_words))
        else:
            self.sentence_display.setText(self.tr("Click words below to build your sentence."))

    def clear_input(self):
        self.current_sentence_words = []
        for btn in self.word_bank_buttons:
            btn.setEnabled(True)
        self._update_display()

    def get_answer(self) -> str:
        return " ".join(self.current_sentence_words)


class ContextBlockWidget(BaseExerciseWidget):
    """A widget to display text content, not as an interactive exercise."""
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        # Hide the default prompt label as we use a dedicated title and content area
        self.prompt_label.setVisible(False)

        if self.exercise.title:
            title_label = QLabel(self.exercise.title)
            title_label.setObjectName("context_title_label")
            self.layout.insertWidget(0, title_label)

        content_text = QTextEdit()
        content_text.setReadOnly(True)
        content_text.setMarkdown(self.exercise.prompt or "")
        self.layout.insertWidget(1, content_text)

        continue_button = QPushButton(self.tr("Continue"))
        continue_button.clicked.connect(lambda: self.answer_submitted.emit("completed"))
        self.layout.addWidget(continue_button)

    def get_answer(self) -> str:
        return "completed"
    
    def clear_input(self):
        pass # Nothing to clear

    def set_focus_on_input(self):
        # Focus the continue button by default
        self.findChild(QPushButton).setFocus()


EXERCISE_WIDGET_MAP: Dict[str, Type[BaseExerciseWidget]] = {
    "translate_to_target": TranslationExerciseWidget,
    "translate_to_source": TranslationExerciseWidget,
    "multiple_choice_translation": MultipleChoiceExerciseWidget,
    "fill_in_the_blank": FillInTheBlankExerciseWidget,
    "dictation": TranslationExerciseWidget,
    "image_association": MultipleChoiceExerciseWidget,
    "listen_and_select": ListenSelectExerciseWidget,
    "sentence_jumble": SentenceJumbleExerciseWidget,
    "context_block": ContextBlockWidget,
}
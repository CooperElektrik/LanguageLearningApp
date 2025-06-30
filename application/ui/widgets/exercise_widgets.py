import logging
import os
import sys
import random
import re
import markdown
import urllib.parse
import tempfile
import difflib
import time
from typing import Any, Dict, Optional, Type, List
import soundfile as sf
import numpy as np

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
    QTextBrowser,
    QGroupBox,
    QProgressBar,
    QSizePolicy,
)
from PySide6.QtCore import (
    Signal,
    QUrl,
    Qt,
    QTimer,
    QSettings,
    QThread,
    QByteArray,
    QIODevice,
    QBuffer,
    QSize,
)
from PySide6.QtGui import QFont, QPixmap, QKeyEvent, QPainter, QPainterPath  # Added QKeyEvent
from PySide6.QtMultimedia import (
    QMediaPlayer,
    QAudioOutput,
    QAudioSource,
    QAudioFormat,
    QMediaDevices,
    QAudioDevice,
)  # Import QAudioDevice

try:
    from application.core.models import Exercise
    from application.core.course_manager import (
        CourseManager,  # Import full class for type hinting
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
    from application.core.stt_manager import STTManager
    from application.core.whisper_engine import _TORCH_AVAILABLE, WhisperTranscriptionTask # For CUDA check and Whisper-specific task
    from application import settings as app_settings  # For reading autoplay setting
    from application.ui.dialogs.glossary_detail_dialog import (
        GlossaryDetailDialog,
    )  # Import for context block
except ImportError:  # This makes Nuitka happy
    from core.models import Exercise
    from core.course_manager import (
        CourseManager,
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
    from core.stt_manager import STTManager
    from core.whisper_engine import _TORCH_AVAILABLE, WhisperTranscriptionTask # For CUDA check and Whisper-specific task
    import settings as app_settings  # Fallback for Nuitka
    from ui.dialogs.glossary_detail_dialog import GlossaryDetailDialog

logger = logging.getLogger(__name__)

ICON_SIZE = QSize(256, 144)

def create_rounded_pixmap(original_pixmap: QPixmap, target_size: QSize, corner_radius: int = 15) -> QPixmap:
    """
    Scales, crops to a 16:9 ratio, and rounds the corners of a QPixmap.
    """
    # Define the target aspect ratio
    aspect_ratio = 16 / 9

    # Adjust the target size to fit the 16:9 aspect ratio
    target_width = target_size.width()
    target_height = int(target_width / aspect_ratio)
    final_size = QSize(target_width, target_height)

    # Scale the pixmap to fill the new target size while maintaining aspect ratio
    scaled_pixmap = original_pixmap.scaled(final_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)

    # Center-crop the scaled pixmap
    x = (scaled_pixmap.width() - final_size.width()) / 2
    y = (scaled_pixmap.height() - final_size.height()) / 2
    cropped_pixmap = scaled_pixmap.copy(x, y, final_size.width(), final_size.height())

    # Create a new pixmap with a transparent background to draw on
    rounded_pixmap = QPixmap(final_size)
    rounded_pixmap.fill(Qt.GlobalColor.transparent)

    # Use QPainter to draw the rounded rectangle
    painter = QPainter(rounded_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    path = QPainterPath()
    path.addRoundedRect(0, 0, final_size.width(), final_size.height(), corner_radius, corner_radius)

    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped_pixmap)
    painter.end()

    return rounded_pixmap

class BaseExerciseWidget(QWidget):
    answer_submitted = Signal(str)

    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(parent)
        self.exercise = exercise
        self.course_manager: CourseManager = course_manager
        self.assets_base_dir = self.course_manager.get_course_manifest_directory()
        if not self.assets_base_dir:
            self.assets_base_dir = self.course_manager.get_course_content_directory()

        self.layout = QVBoxLayout(self)
        self.prompt_label = QLabel()
        self.prompt_label.setObjectName("prompt_label")
        self.prompt_label.setWordWrap(True)
        self.prompt_label.setMinimumHeight(300)
        self.layout.addWidget(self.prompt_label)

        self.image_label = QLabel()
        self.image_label.setObjectName("image_label")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMaximumWidth(640)
        self.image_label.setMaximumHeight(99999)
        self.image_label.setScaledContents(False)
        self._setup_image()
        self.layout.addWidget(self.image_label, alignment=Qt.AlignCenter)
        self.image_label.setVisible(True)

        self._media_player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None

    def _setup_image(self):
        if self.exercise.image_file and self.assets_base_dir:
            full_image_path = os.path.join(
                self.assets_base_dir, self.exercise.image_file
            )

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
            if (
                self._media_player.mediaStatus() == QMediaPlayer.NoMedia
                and self._media_player.error() != QMediaPlayer.NoError
            ):
                logger.error(
                    f"Error setting media source for {full_audio_path}: {self._media_player.errorString()}"
                )
                QMessageBox.warning(
                    self,
                    self.tr("Audio Error"),
                    self.tr("Cannot prepare audio: {0}").format(
                        self._media_player.errorString()
                    ),
                )
                return

            self._media_player.play()
        else:
            logger.error(f"Audio file not found: {full_audio_path}")
            QMessageBox.warning(
                self,
                self.tr("Audio Error"),
                self.tr("Audio file not found: {0}").format(relative_audio_path),
            )

    def _format_prompt_from_data(self, prompt_data: Dict[str, Any]) -> str:
        """Helper to format the prompt using tr() and arguments from prompt_data."""
        template_key = prompt_data.get("template_key", PROMPT_KEY_DEFAULT)
        args = prompt_data.get("args", [])

        template_str_map = {
            PROMPT_KEY_TRANSLATE_TO_TARGET: self.tr('Translate to %s: "%s"'),
            PROMPT_KEY_TRANSLATE_TO_SOURCE: self.tr('Translate to %s: "%s"'),
            PROMPT_KEY_MCQ_TRANSLATION: self.tr(
                'Choose the %s translation for: "%s" (%s)'
            ),
            PROMPT_KEY_FIB: self.tr("%s (Hint: %s)"),
            PROMPT_KEY_DICTATION: self.tr("%s"),
            PROMPT_KEY_IMAGE_ASSOCIATION: self.tr("%s"),
            PROMPT_KEY_LISTEN_SELECT: self.tr("%s"),
            PROMPT_KEY_SENTENCE_JUMBLE: self.tr("%s"),
            PROMPT_KEY_CONTEXT_BLOCK: self.tr("%s"),
            PROMPT_KEY_DEFAULT: (
                self.tr("Exercise Prompt: %s") if args else self.tr("Exercise Prompt")
            ),
        }

        template_str = template_str_map.get(template_key, "")

        formatted_string = template_str
        if args:
            str_args = tuple(str(arg) for arg in args)
            try:
                formatted_string = template_str % str_args
            except TypeError:
                logger.error(
                    f"String formatting error for template key '{template_key}'."
                )
                formatted_string = f"{template_str} ({', '.join(str_args)})"

        return formatted_string

    def get_answer(self) -> str:
        raise NotImplementedError("Subclasses must implement get_answer")

    def clear_input(self):
        raise NotImplementedError("Subclasses must implement clear_input")

    def set_focus_on_input(self):
        pass

    def stop_media(self):
        if (
            self._media_player
            and self._media_player.playbackState() == QMediaPlayer.PlayingState
        ):
            self._media_player.stop()

    def trigger_autoplay_audio(self):
        """
        Checks the application settings and autoplays the exercise's audio
        if the feature is enabled and an audio file is associated with the exercise.
        """
        if not self.exercise or not self.exercise.audio_file:
            logger.debug(
                f"No audio file for exercise {self.exercise.exercise_id if self.exercise else 'N/A'}, skipping autoplay."
            )
            return

        q_settings = QSettings()
        autoplay_enabled = q_settings.value(
            app_settings.QSETTINGS_KEY_AUTOPLAY_AUDIO,
            app_settings.AUTOPLAY_AUDIO_DEFAULT,
            type=bool,
        )

        if autoplay_enabled:
            logger.info(
                f"Autoplay enabled. Playing audio for exercise: {self.exercise.exercise_id}"
            )
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


class ButtonOptionExerciseWidget(BaseExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)

        self.options_group = QButtonGroup(self)
        self.options_group.setExclusive(True)
        self.options_layout = QHBoxLayout()

        options_to_display = self.exercise.options
        if not options_to_display:
            logger.warning(
                f"No options found for option-based exercise: {self.exercise.exercise_id}"
            )
            no_options_label = QLabel(self.tr("No options available for this exercise."))
            self.options_layout.addWidget(no_options_label)
        else:
            for i, option_obj in enumerate(options_to_display):
                button = QPushButton()
                button.setObjectName(f"option_button_{i}")
                button.setCheckable(True)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                button.setFixedHeight(160)

                button_layout = QHBoxLayout(button)
                button_layout.setContentsMargins(10, 5, 10, 5)  # Add padding

                icon_label = QLabel()
                text_label = QLabel(option_obj.text)
                text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                if option_obj.image_file and self.assets_base_dir:
                    full_image_path = os.path.join(self.assets_base_dir, option_obj.image_file)
                    if os.path.exists(full_image_path):
                        pixmap = QPixmap(full_image_path)
                        if not pixmap.isNull():
                            rounded_pixmap = create_rounded_pixmap(pixmap, ICON_SIZE)
                            icon_label.setPixmap(rounded_pixmap)

                button_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignLeft)

                # Add a separator
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.VLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                button_layout.addWidget(separator)

                button_layout.addWidget(text_label, 1)

                self.options_layout.addWidget(button)
                self.options_group.addButton(button, i)

        self.layout.addLayout(self.options_layout)
        self.options_group.buttonClicked.connect(
            lambda button: self.answer_submitted.emit(self.get_answer())
        )

    def get_answer(self) -> str:
        checked_button = self.options_group.checkedButton()
        if checked_button:
            return str(self.options_group.id(checked_button))
        return ""

    def clear_input(self):
        checked_button = self.options_group.checkedButton()
        if checked_button:
            self.options_group.setExclusive(False)
            checked_button.setChecked(False)
            self.options_group.setExclusive(True)

    def set_focus_on_input(self):
        if self.options_group.buttons():
            self.options_group.buttons()[0].setFocus()

    def keyPressEvent(self, event: QKeyEvent):
        """Handles number key presses for selecting options."""
        key = event.key()
        key_to_index_map = {
            Qt.Key_1: 0, Qt.Key_2: 1, Qt.Key_3: 2,
            Qt.Key_4: 3, Qt.Key_5: 4, Qt.Key_6: 5,
            Qt.Key_7: 6, Qt.Key_8: 7, Qt.Key_9: 8,
        }

        if key in key_to_index_map:
            option_index = key_to_index_map[key]
            if 0 <= option_index < len(self.options_group.buttons()):
                button_to_select = self.options_group.buttons()[option_index]
                if button_to_select.isEnabled():
                    button_to_select.click()  # Simulate a click
                    logger.debug(
                        f"Option {option_index + 1} ('{button_to_select.text()}') selected via keyboard shortcut."
                    )
                    event.accept()
                    return
        super().keyPressEvent(event)


class RadioButtonOptionExerciseWidget(BaseExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)

        self.options_group = QButtonGroup(self)
        options_layout = QVBoxLayout()

        options_to_display = self.exercise.options
        if not options_to_display:
            logger.warning(
                f"No options found for option-based exercise: {self.exercise.exercise_id}"
            )
            options_layout.addWidget(
                QLabel(self.tr("No options available for this exercise."))
            )
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
        if checked_button:
            return str(self.options_group.id(checked_button))
        return ""

    def clear_input(self):
        checked_button = self.options_group.checkedButton()
        if checked_button:
            self.options_group.setExclusive(False)
            checked_button.setChecked(False)
            self.options_group.setExclusive(True)

    def set_focus_on_input(self):
        if self.options_group.buttons():
            self.options_group.buttons()[0].setFocus()

    def keyPressEvent(self, event: QKeyEvent):
        """Handles number key presses for selecting options."""
        key = event.key()
        # Map Qt.Key_1 to Qt.Key_9 to indices 0-8
        key_to_index_map = {
            Qt.Key_1: 0,
            Qt.Key_2: 1,
            Qt.Key_3: 2,
            Qt.Key_4: 3,
            Qt.Key_5: 4,
            Qt.Key_6: 5,
            Qt.Key_7: 6,
            Qt.Key_8: 7,
            Qt.Key_9: 8,
        }

        if key in key_to_index_map:
            option_index = key_to_index_map[key]
            if 0 <= option_index < len(self.options_group.buttons()):
                button_to_select = self.options_group.buttons()[option_index]
                if button_to_select.isEnabled():  # Only if the option is selectable
                    # Setting checked will trigger the QButtonGroup.buttonClicked signal
                    # which is already connected to self.answer_submitted
                    button_to_select.setChecked(True)
                    logger.debug(
                        f"Option {option_index + 1} ('{button_to_select.text()}') selected via keyboard shortcut."
                    )
                    event.accept()
                    return
        super().keyPressEvent(event)


class MultipleChoiceExerciseWidget(ButtonOptionExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        prompt_data = self.course_manager.get_formatted_prompt_data(self.exercise)
        formatted_prompt = self._format_prompt_from_data(prompt_data)
        self.prompt_label.setText(formatted_prompt)


class ListenSelectExerciseWidget(ButtonOptionExerciseWidget):
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
            self.layout.insertWidget(insert_index, self.play_audio_button)


class FillInTheBlankExerciseWidget(ButtonOptionExerciseWidget):
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

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        self.layout.addWidget(separator)

        self.word_bank_layout = QGridLayout()
        self.layout.addLayout(self.word_bank_layout)
        self._setup_word_bank()

        self.submit_button = QPushButton(self.tr("Submit Sentence"))
        self.submit_button.clicked.connect(
            lambda: self.answer_submitted.emit(self.get_answer())
        )
        self.layout.addWidget(self.submit_button)

    def _setup_word_bank(self):
        words = list(self.exercise.words) if self.exercise.words else []
        random.shuffle(words)
        for i, word in enumerate(words):
            button = QPushButton(word)
            button.clicked.connect(
                lambda checked, w=word, b=button: self._add_word_to_sentence(w, b)
            )
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
            self.sentence_display.setText(
                self.tr("Click words below to build your sentence.")
            )

    def clear_input(self):
        self.current_sentence_words = []
        for btn in self.word_bank_buttons:
            btn.setEnabled(True)
        self._update_display()

    def get_answer(self) -> str:
        return " ".join(self.current_sentence_words)


class ContextBlockWidget(BaseExerciseWidget):
    """A widget to display text content, not as an interactive exercise."""

    def __init__(self, exercise: Exercise, course_manager: CourseManager, parent=None):
        # TODO: fix the random pop-up that appears for a split second
        # Cause: init call
        super().__init__(exercise, course_manager, parent)
        # Hide the default prompt label as we use a dedicated title and content area
        self.prompt_label.setVisible(False)

        if self.exercise.title:
            title_label = QLabel(self.exercise.title)
            title_label.setObjectName("context_title_label")
            self.layout.insertWidget(0, title_label)

        # Clean the input slightly and prepare links
        cleaned_prompt = (self.exercise.prompt or "").strip()
        markdown_with_links = self._prepare_content_with_glossary_links(cleaned_prompt)

        # Use 'extra' for better Markdown parsing and 'nl2br' for newline handling
        html_content = markdown.markdown(
            markdown_with_links, extensions=["extra", "nl2br"]
        )
        logger.debug(f"ContextBlock Input MD: '''{markdown_with_links}'''")
        logger.debug(f"ContextBlock Output HTML: '''{html_content}'''")

        self.content_text = QTextBrowser()
        self.content_text.setReadOnly(True)
        self.content_text.setOpenLinks(False)
        self.content_text.anchorClicked.connect(self._handle_glossary_link_clicked)

        self.content_text.setHtml(html_content)
        self.layout.insertWidget(1, self.content_text)

        continue_button = QPushButton(self.tr("Continue"))
        continue_button.clicked.connect(lambda: self.answer_submitted.emit("completed"))
        self.layout.addWidget(continue_button)

    def _prepare_content_with_glossary_links(self, original_content: str) -> str:
        """
        Parses the content, finds words in the glossary, and wraps them in
        Markdown link format for the QTextBrowser to handle.
        """
        glossary_entries = self.course_manager.get_glossary_entries()
        if not glossary_entries:
            return original_content

        sorted_words = sorted(
            [e.word for e in glossary_entries if e.word], key=len, reverse=True
        )
        if not sorted_words:
            return original_content
        escaped_words = [re.escape(word) for word in sorted_words]
        pattern = r"\b(" + "|".join(escaped_words) + r")\b"

        def replace_with_link(match):
            word = match.group(1)
            encoded_word = urllib.parse.quote(word, encoding="utf-8", safe="")
            return f"[{word}](glossary:{encoded_word})"

        try:
            # We use re.sub with a function to perform the replacement
            linked_content = re.sub(
                pattern, replace_with_link, original_content, flags=re.IGNORECASE
            )
            return linked_content
        except re.error as e:
            logger.error(f"Regex error while creating glossary links: {e}")
            return original_content

    def _handle_glossary_link_clicked(self, url: QUrl):
        """Handles clicks on glossary:// links, opening a new detail dialog."""
        logger.debug(f"_handle_glossary_link_clicked called with url: {url.toString()}")
        if url.scheme() == "glossary":
            # For scheme:path, url.path() returns the path component.
            # QUrl automatically handles percent-decoding.
            decoded_word = url.path()

            if not decoded_word:
                logger.warning(
                    f"Glossary link clicked, but decoded word is empty. Original URL: {url.toString()}"
                )
                return

            logger.debug(
                f"Attempting to find glossary entry for decoded word: '{decoded_word}'"
            )
            entry = self.course_manager.get_glossary_entry_by_word(decoded_word)
            if entry:
                # Open a new dialog for the clicked entry
                new_dialog = GlossaryDetailDialog(
                    entry, self.course_manager, self.window()
                )
                new_dialog.exec()
            else:
                logger.warning(
                    f"Glossary link clicked for decoded word '{decoded_word}', but no entry found."
                )

    def get_answer(self) -> str:  # Ensure this method and others are correctly indented
        return "completed"

    def clear_input(self):  # Ensure this method and others are correctly indented
        pass  # Nothing to clear

    def set_focus_on_input(self):
        # Focus the continue button by default
        self.findChild(QPushButton).setFocus()


class PronunciationExerciseWidget(BaseExerciseWidget):
    transcription_started = Signal()
    transcription_ready = Signal(str)
    transcription_error = Signal(str)

    def __init__(
        self,
        exercise: Exercise,
        course_manager: CourseManager,
        stt_manager: STTManager,
        parent=None,
    ):
        super().__init__(exercise, course_manager, parent)
        self.stt_manager = stt_manager
        self._audio_recorder: Optional[QAudioSource] = None
        self._audio_buffer: Optional[QByteArray] = None
        self._qbuffer: Optional[QBuffer] = None
        self._temp_audio_file: Optional[tempfile.NamedTemporaryFile] = None
        self._is_recording = False
        self._last_transcription_text = ""

        # --- UI Setup ---
        self.target_text_label = QLabel(
            self.tr("Please pronounce: ") + f"{self.exercise.target_pronunciation_text}"
        )
        self.target_text_label.setObjectName("pronunciation_target_label")
        self.target_text_label.setWordWrap(True)
        self.layout.insertWidget(
            self.layout.indexOf(self.prompt_label) + 1, self.target_text_label
        )
        self.prompt_label.setVisible(False)

        if self.exercise.audio_file:
            self.play_ref_button = QPushButton(self.tr("🔊 Play Reference"))
            self.play_ref_button.clicked.connect(
                lambda: self._play_audio_file(self.exercise.audio_file)
            )
            self.layout.insertWidget(
                self.layout.indexOf(self.target_text_label) + 1, self.play_ref_button
            )

        # Action Buttons
        action_layout = QHBoxLayout()
        self.load_model_button = QPushButton()
        self.load_model_button.setObjectName("load_model_button")
        self.load_model_button.clicked.connect(self._handle_load_model_click)
        action_layout.addWidget(self.load_model_button)

        self.record_button = QPushButton(self.tr("🎤 Record"))
        self.record_button.setCheckable(True)
        self.record_button.toggled.connect(self._handle_record_toggle)
        action_layout.addWidget(self.record_button)
        self.layout.addLayout(action_layout)

        self.status_label = QLabel(self.tr("Tap record and speak clearly."))
        self.status_label.setObjectName("pronunciation_status_label")
        self.layout.addWidget(self.status_label)

        # --- Progress Bar for Model Loading ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        # --- Rich Feedback Area ---
        self.feedback_group = QGroupBox(self.tr("Transcription Feedback"))
        feedback_layout = QVBoxLayout(self.feedback_group)
        self.confidence_browser = QTextBrowser()
        self.confidence_browser.setOpenExternalLinks(False)
        self.diff_browser = QTextBrowser()
        self.diff_browser.setOpenExternalLinks(False)
        feedback_layout.addWidget(
            QLabel(self.tr("Your speech (colored by confidence):"))
        )
        feedback_layout.addWidget(self.confidence_browser)
        feedback_layout.addWidget(QLabel(self.tr("Comparison with target text:")))
        feedback_layout.addWidget(self.diff_browser)

        feedback_action_layout = QHBoxLayout()
        self.try_again_button = QPushButton(self.tr("🔄 Try Again"))
        self.try_again_button.clicked.connect(self.clear_input)
        self.submit_feedback_button = QPushButton(self.tr("Submit and Continue"))
        self.submit_feedback_button.clicked.connect(self._handle_submit_click)
        feedback_action_layout.addStretch(1)
        feedback_action_layout.addWidget(self.try_again_button)
        feedback_action_layout.addWidget(self.submit_feedback_button)
        feedback_action_layout.addStretch(1)
        feedback_layout.addLayout(feedback_action_layout)

        self.layout.addWidget(self.feedback_group)

        self.stt_manager.modelLoadingStarted.connect(self._on_model_loading_started)
        self.stt_manager.modelLoadingFinished.connect(
            self._on_model_loading_finished
        )
        self.stt_manager.modelUnloaded.connect(self._on_model_unloaded)

        self.submit_feedback_button.setVisible(False)
        self._update_ui_for_model_state()

    def _update_ui_for_model_state(self):
        selected_engine = self.stt_manager.get_selected_stt_engine()
        target_model_name = None
        
        if selected_engine == app_settings.STT_ENGINE_WHISPER:
            target_model_name = self.stt_manager.get_selected_whisper_model_name()
        elif selected_engine == app_settings.STT_ENGINE_VOSK:
            target_model_name = self.stt_manager.get_selected_vosk_model_path()

        loaded_model_name = self.stt_manager.get_loaded_model_name()
        is_loading = self.stt_manager.is_loading()

        self.feedback_group.setVisible(False)
        self.submit_feedback_button.setVisible(False)

        logger.debug(f"STT UI Update: selected_engine={selected_engine}, target_model_name='{target_model_name}', loaded_model_name='{loaded_model_name}', is_loading={is_loading}")

        if not target_model_name or target_model_name.lower() == "none":
            self.load_model_button.setVisible(False)
            self.record_button.setVisible(False)
            self.status_label.setText(
                self.tr(
                    "Please select an STT model in Settings to enable pronunciation practice."
                )
            )
        elif is_loading:
            self._on_model_loading_started(target_model_name)
        elif target_model_name == loaded_model_name:
            logger.debug(f"STT UI Update: Model '{target_model_name}' is loaded and matches target.")
            self.load_model_button.setVisible(False)
            self.record_button.setVisible(True)
            self.record_button.setEnabled(True)
            self.status_label.setText(self.tr("Tap record to speak."))
        else:
            logger.debug(f"STT UI Update: Target model '{target_model_name}' does not match loaded model '{loaded_model_name}'.")
            self.load_model_button.setText(
                self.tr("Load Model: {0}").format(target_model_name)
            )
            self.load_model_button.setVisible(True)
            self.load_model_button.setEnabled(True)
            self.record_button.setVisible(False)
            self.status_label.setText(self.tr("Model must be loaded before recording."))

    def _init_audio_recorder(self):
        if self._audio_recorder:
            return True
        q_settings = QSettings()
        preferred_device_id_str = q_settings.value(
            app_settings.QSETTINGS_KEY_AUDIO_INPUT_DEVICE,
            "",
            type=str,
        )
        selected_device_info: Optional[QAudioDevice] = None
        if preferred_device_id_str:
            for device in QMediaDevices.audioInputs():
                if device.id().toStdString() == preferred_device_id_str:
                    selected_device_info = device
                    logger.info(
                        f"Using preferred audio input device: {selected_device_info.description()}"
                    )
                    break
        if not selected_device_info:
            default_device_info = QMediaDevices.defaultAudioInput()
            if not default_device_info.isNull():
                selected_device_info = default_device_info
                logger.info(
                    f"Using system default audio input device: {selected_device_info.description()}"
                )
            else:
                self.status_label.setText(self.tr("No audio input device found!"))
                logger.error(
                    "No audio input device found (neither preferred nor default)."
                )
                self.record_button.setEnabled(False)
                return False
        if selected_device_info and not selected_device_info.isNull():
            audio_format = QAudioFormat()
            # Use the device's default sample rate for recording
            audio_format.setSampleRate(int(selected_device_info.maximumSampleRate()))
            audio_format.setChannelCount(1)
            audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self._audio_recorder = QAudioSource(
                selected_device_info, audio_format, self
            )
            return True
        else:
            self.status_label.setText(self.tr("No audio input device found!"))
            logger.error("No default audio input device found.")
            self.record_button.setEnabled(False)
            return False

    def _on_model_loading_started(self, model_name: str):
        self.record_button.setEnabled(False)
        self.load_model_button.setEnabled(False)
        self.load_model_button.setVisible(True)
        self.record_button.setVisible(False)
        self.status_label.setText(
            self.tr("Loading pronunciation model ({0})...").format(model_name)
        )
        self.progress_bar.setRange(0, 0)  # Set to indeterminate
        self.progress_bar.setVisible(True)

    def _on_model_loading_finished(self, model_name: str, success: bool):
        self.progress_bar.setVisible(False)
        self._update_ui_for_model_state()

    def _on_model_unloaded(self, model_name: str):
        self._update_ui_for_model_state()

    def _handle_load_model_click(self):
        self.stt_manager.load_model()

    def _handle_record_toggle(self, checked: bool):
        if checked:
            if not self._init_audio_recorder():
                self.record_button.setChecked(False)
                return
            self.confidence_browser.clear()
            self.diff_browser.clear()
            self.feedback_group.setVisible(False)
            self.status_label.setText(self.tr("Recording... Speak now!"))
            self.record_button.setText(self.tr("⏹️ Stop Recording"))
            if self._temp_audio_file:
                try:
                    if not self._temp_audio_file.closed:
                        self._temp_audio_file.close()
                    os.unlink(self._temp_audio_file.name)
                except Exception as e:
                    logger.warning(
                        f"Could not close/delete previous temp audio file '{self._temp_audio_file.name if self._temp_audio_file else 'N/A'}': {e}"
                    )
            self._temp_audio_file = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            )
            self._temp_audio_file.close()
            logger.debug(
                f"New temporary audio file for recording: {self._temp_audio_file.name}"
            )
            self._audio_buffer = QByteArray()
            self._qbuffer = QBuffer(self._audio_buffer, self)
            self._qbuffer.open(QIODevice.OpenModeFlag.WriteOnly)
            self._audio_recorder.start(self._qbuffer)
            self._is_recording = True
            logger.info(f"Audio recording started, writing to QBuffer.")
        else:
            if self._audio_recorder and self._is_recording:
                self._audio_recorder.stop()
                self._is_recording = False
                logger.info("Audio recording stopped.")
                self.status_label.setText(self.tr("Processing audio... Please wait."))
                self.record_button.setText(self.tr("🎤 Record"))
                self.record_button.setEnabled(False)
                if self._qbuffer and self._qbuffer.isOpen():
                    self._qbuffer.close()
                if self._temp_audio_file and self._audio_buffer:
                    try:
                        # Get the actual sample rate from the audio recorder's format
                        recorded_samplerate = self._audio_recorder.format().sampleRate()

                        # Save the recorded audio to a WAV file using soundfile
                        # soundfile automatically handles the sample width based on the data type
                        sf.write(
                            self._temp_audio_file.name,
                            np.frombuffer(self._audio_buffer.data(), dtype=np.int16),
                            recorded_samplerate,
                            format='WAV',
                            subtype='PCM_16'
                        )
                        logger.info(
                            f"Buffered raw PCM audio saved as WAV to {self._temp_audio_file.name} at {recorded_samplerate} Hz"
                        )
                        self._start_transcription(
                            self._temp_audio_file.name,
                            recorded_samplerate,
                            self.course_manager.target_language_code,
                        )
                    except Exception as e:
                        logger.error(
                            f"Error saving buffered audio to {self._temp_audio_file.name}: {e}"
                        )
                        self.status_label.setText(self.tr("Error saving audio."))
                        self.record_button.setEnabled(True)
                    finally:
                        self._audio_buffer = None
                        self._qbuffer = None
                else:
                    self.status_label.setText(self.tr("No audio data to process."))
                    self.record_button.setEnabled(True)

    def _start_transcription(
        self, audio_file_path: str, recorded_samplerate: int, language_code: str | None = None
    ):
        if not audio_file_path or not os.path.exists(audio_file_path):
            self.status_label.setText(
                self.tr("Error: Audio file for transcription not found.")
            )
            self.record_button.setEnabled(True)
            return
        task = self.stt_manager.transcribe_audio(
            audio_file_path, recorded_samplerate, self.exercise.exercise_id, language_code
        )
        if task:
            task.signals.finished.connect(self._on_transcription_finished)
            task.signals.error.connect(self._on_transcription_error)
        else:
            self.status_label.setText(
                self.tr("Transcription service not available or disabled.")
            )
            self.record_button.setEnabled(True)

    def _on_transcription_finished(self, exercise_id: str, result):
        logger.debug("Transcription finished.")
        if exercise_id != self.exercise.exercise_id:
            return

        full_text = ""
        confidence_html = ""

        if isinstance(result, str):  # VOSK result is a string
            full_text = result.strip()
            confidence_html = self.tr("VOSK does not provide word-level confidence. Transcribed text: {0}").format(full_text)
        else:  # Assume Whisper result (segments, info)
            segments = result
            all_words = []
            segment_list = list(segments)
            for segment in segment_list:
                full_text += segment.text
                if segment.words:
                    all_words.extend(segment.words)
            full_text = full_text.strip()
            confidence_html = self._generate_confidence_html(all_words)

        self.status_label.setText(
            self.tr("Transcription complete. Review your feedback below.")
        )
        self.confidence_browser.setHtml(confidence_html)
        target_text = self.exercise.target_pronunciation_text
        diff_html = self._generate_diff_html(target_text, full_text)
        self.diff_browser.setHtml(diff_html)
        self.transcription_ready.emit(full_text)
        self.record_button.setEnabled(True)
        self.feedback_group.setVisible(True)
        self.submit_feedback_button.setVisible(True)
        self._last_transcription_text = full_text

    def _handle_submit_click(self):
        self.answer_submitted.emit(self._last_transcription_text)
        self.submit_feedback_button.setEnabled(False)
        self.try_again_button.setEnabled(False)
        self.submit_feedback_button.setEnabled(False)

    def _generate_confidence_html(self, words: list) -> str:
        if not words:
            return f"{self.tr('No speech detected.')}"
        html_parts = []
        for word in words:
            prob = word.probability
            if prob > 0.9:
                color = "#006400"
            elif prob > 0.7:
                color = "#DAA520"
            elif prob > 0.5:
                color = "#FF8C00"
            else:
                color = "#DC143C"
            html_parts.append(f'<span style="color: {color};">{word.word}</span>')
        return "".join(html_parts)

    def _generate_diff_html(self, target_str: str, user_str: str) -> str:
        target_str_norm = self.course_manager._normalize_answer_for_comparison(
            target_str, for_pronunciation=True
        )
        user_str_norm = self.course_manager._normalize_answer_for_comparison(
            user_str, for_pronunciation=True
        )
        matcher = difflib.SequenceMatcher(
            None, target_str_norm.split(), user_str_norm.split()
        )
        html_parts = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                html_parts.append(" ".join(matcher.a[i1:i2]))
            else:
                if tag in ("delete", "replace"):
                    deleted_text = " ".join(matcher.a[i1:i2])
                    html_parts.append(
                        f'<span style="background-color: #ffdddd; text-decoration: line-through;">{deleted_text}</span>'
                    )
                if tag in ("insert", "replace"):
                    inserted_text = " ".join(matcher.b[j1:j2])
                    html_parts.append(
                        f'<span style="background-color: #ddffdd; font-weight: bold;">{inserted_text}</span>'
                    )
        return " ".join(html_parts)

    def _on_transcription_error(self, exercise_id: str, error_message: str):
        if exercise_id != self.exercise.exercise_id:
            return
        self.status_label.setText(
            self.tr("Transcription Error: {0}").format(error_message)
        )
        self.record_button.setEnabled(True)
        self.transcription_error.emit(error_message)

    def get_answer(self) -> str:
        return self._last_transcription_text

    def clear_input(self):
        self.feedback_group.setVisible(False)
        self.confidence_browser.clear()
        self.diff_browser.clear()
        self._update_ui_for_model_state()
        self.record_button.setChecked(False)

    def stop_media(self):
        super().stop_media()
        if self._is_recording and self._audio_recorder:
            self._audio_recorder.stop()
            self._is_recording = False
            logger.info("Recording stopped by stop_media call.")
        if self._temp_audio_file:
            try:
                if not self._temp_audio_file.closed:
                    self._temp_audio_file.close()
                if os.path.exists(self._temp_audio_file.name):
                    os.unlink(self._temp_audio_file.name)
            except Exception as e:
                logger.error(f"Error during temp file cleanup in stop_media: {e}")
            self._temp_audio_file = None
        if self._qbuffer and self._qbuffer.isOpen():
            self._qbuffer.close()
        self._qbuffer = None
        self._audio_buffer = None


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
    "pronunciation_practice": PronunciationExerciseWidget,
}

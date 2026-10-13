import difflib
import logging
import os
import random
import re
import tempfile
import urllib.parse
from typing import Any

import markdown
import numpy as np
import soundfile as sf
from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QSettings,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QKeyEvent, QPainter, QPainterPath, QPixmap  # Added QKeyEvent
from PySide6.QtMultimedia import (
    QAudioDevice,
    QAudioFormat,
    QAudioOutput,
    QAudioSource,
    QMediaDevices,
    QMediaPlayer,
)  # Import QAudioDevice
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

try:
    from application import settings as app_settings  # For reading autoplay setting
    from application.core.course_manager import (
        CourseManager,  # Import full class for type hinting
    )
    from application.core.models import Exercise
    from application.core.stt_common import TranscriptionResult
    from application.core.stt_manager import STTManager
    from application.ui.dialogs.glossary_detail_dialog import (
        GlossaryDetailDialog,
    )  # Import for context block
except ImportError:  # This makes Nuitka happy
    import settings as app_settings  # Fallback for Nuitka
    from core.course_manager import CourseManager
    from core.models import Exercise
    from ui.dialogs.glossary_detail_dialog import GlossaryDetailDialog

try:
    from application.ui.widgets.audio_level_meter import AudioLevelMeter
    from application.ui.widgets.option_card_widget import OptionCardWidget, OptionGroupWidget
    from application.ui.widgets.token_bank_widget import TokenBankWidget, WordChip
    from application.ui.widgets.audio_recording_controller import AudioRecordingController
    from application.ui.widgets.pronunciation_feedback_view import PronunciationFeedbackView
except ImportError:
    try:
        from ui.widgets.audio_level_meter import AudioLevelMeter
        from ui.widgets.option_card_widget import OptionCardWidget, OptionGroupWidget
        from ui.widgets.token_bank_widget import TokenBankWidget, WordChip
        from ui.widgets.audio_recording_controller import AudioRecordingController
        from ui.widgets.pronunciation_feedback_view import PronunciationFeedbackView
    except ImportError:
        from .audio_level_meter import AudioLevelMeter
        from .option_card_widget import OptionCardWidget, OptionGroupWidget
        from .token_bank_widget import TokenBankWidget, WordChip
        from .audio_recording_controller import AudioRecordingController
        from .pronunciation_feedback_view import PronunciationFeedbackView

logger = logging.getLogger(__name__)

ICON_SIZE = QSize(256, 144)


def create_rounded_pixmap(
    original_pixmap: QPixmap, target_size: QSize, corner_radius: int = 15
) -> QPixmap:
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
    scaled_pixmap = original_pixmap.scaled(
        final_size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )

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
        self.assets_base_dir = self.course_manager.get_asset_directory()
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
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMaximumWidth(640)
        self.image_label.setMaximumHeight(400)
        self.image_label.setScaledContents(False)
        self._setup_image()
        self.layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setVisible(True)

        self._media_player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None

    def _setup_image(self):
        if self.exercise.image_file and self.assets_base_dir:
            full_image_path = os.path.join(self.assets_base_dir, self.exercise.image_file)

            if os.path.exists(full_image_path):
                pixmap = QPixmap(full_image_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        self.image_label.maximumWidth(),
                        self.image_label.maximumHeight(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
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

        # Determine the course's base directory (where its manifest is)
        course_base_dir = self.course_manager.get_course_manifest_directory()
        if not course_base_dir:
            logger.error("Could not determine course base directory for audio playback.")
            QMessageBox.warning(
                self,
                self.tr("Audio Error"),
                self.tr("Could not determine course base directory for audio."),
            )
            return

        # First, try to find the audio file relative to the course's base directory
        full_audio_path = os.path.join(course_base_dir, relative_audio_path)

        # If not found, try the shared asset pool or other configured asset directory
        if not os.path.exists(full_audio_path):
            assets_base_dir = self.course_manager.get_asset_directory()
            if assets_base_dir:
                full_audio_path = os.path.join(assets_base_dir, relative_audio_path)
            else:
                logger.warning(
                    "Shared asset directory not found or configured, falling back to course base directory."
                )
                # If get_asset_directory also fails, we stick with the course_base_dir path
                # which was already constructed.

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
                    self.tr("Cannot prepare audio: {0}").format(self._media_player.errorString()),
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

    def _format_prompt_from_data(self, prompt_data: dict[str, Any]) -> str:
        """Helper to format the prompt using tr() and arguments from prompt_data."""
        return prompt_data.get("args", [""])[0]

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
            self.play_audio_button = QPushButton(self.tr("Play Audio"))
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

        self.option_group = OptionGroupWidget(self)
        self.option_group.set_options(self.exercise.options, self.assets_base_dir)
        self.layout.addWidget(self.option_group)

        self.option_group.option_selected.connect(
            lambda idx: self.answer_submitted.emit(self.get_answer())
        )

        # Backwards compatibility attributes
        self.options_group = self.option_group
        self.options_layout = self.option_group.grid_layout

    def get_answer(self) -> str:
        idx = self.option_group.get_selected_index()
        return str(idx) if idx >= 0 else ""

    def clear_input(self):
        self.option_group.clear_selection()

    def set_focus_on_input(self):
        self.option_group.set_focus_on_first()

    def keyPressEvent(self, event: QKeyEvent):
        """Handles number key presses for selecting options."""
        if self.option_group.handle_number_key(event.key()):
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
            self.play_audio_button = QPushButton(self.tr("Play Audio"))
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
        self.prompt_label.setText(
            self.tr("Fill in the blank: {0}").format(prompt_data.get("args", [""])[0])
        )


class SentenceJumbleExerciseWidget(BaseExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        prompt_data = self.course_manager.get_formatted_prompt_data(self.exercise)
        self.prompt_label.setText(self._format_prompt_from_data(prompt_data))

        self.token_bank = TokenBankWidget(words=self.exercise.words or [], parent=self)
        self.layout.addWidget(self.token_bank)

        self.submit_button = QPushButton(self.tr("Submit Sentence"))
        self.submit_button.clicked.connect(lambda: self.answer_submitted.emit(self.get_answer()))
        self.layout.addWidget(self.submit_button)

    @property
    def current_sentence_words(self) -> list[str]:
        return self.token_bank.get_words()

    def clear_input(self):
        self.token_bank.reset()

    def get_answer(self) -> str:
        return self.token_bank.get_sentence()


class ContextBlockWidget(BaseExerciseWidget):
    """A clean widget to display reading/context text content rather than an interactive quiz."""

    has_integrated_submission = True
    is_interactive_exercise = False

    def __init__(self, exercise: Exercise, course_manager: CourseManager, parent=None):
        super().__init__(exercise, course_manager, parent)
        # Remove the inherited 300px prompt label to prevent split-second layout jumps
        self.layout.removeWidget(self.prompt_label)
        self.prompt_label.deleteLater()
        self.prompt_label = QLabel()
        self.prompt_label.setVisible(False)

        if self.exercise.title:
            title_label = QLabel(self.exercise.title)
            title_label.setObjectName("context_title_label")
            self.layout.addWidget(title_label)

        cleaned_prompt = (self.exercise.prompt or "").strip()
        markdown_with_links = self._prepare_content_with_glossary_links(cleaned_prompt)

        html_content = markdown.markdown(markdown_with_links, extensions=["extra", "nl2br"])
        logger.debug(f"ContextBlock Input MD: '''{markdown_with_links}'''")
        logger.debug(f"ContextBlock Output HTML: '''{html_content}'''")

        self.content_text = QTextBrowser()
        self.content_text.setReadOnly(True)
        self.content_text.setOpenLinks(False)
        self.content_text.anchorClicked.connect(self._handle_glossary_link_clicked)
        self.content_text.setHtml(html_content)
        self.layout.addWidget(self.content_text, 1)

        self.continue_button = QPushButton(self.tr("Continue"))
        self.continue_button.clicked.connect(lambda: self.answer_submitted.emit("completed"))
        self.layout.addWidget(self.continue_button)

    def _prepare_content_with_glossary_links(self, original_content: str) -> str:
        glossary_entries = self.course_manager.get_glossary_entries()
        if not glossary_entries:
            return original_content

        sorted_words = sorted([e.word for e in glossary_entries if e.word], key=len, reverse=True)
        if not sorted_words:
            return original_content
        escaped_words = [re.escape(word) for word in sorted_words]
        pattern = r"\b(" + "|".join(escaped_words) + r")\b"

        def replace_with_link(match):
            word = match.group(1)
            encoded_word = urllib.parse.quote(word, encoding="utf-8", safe="")
            return f"[{word}](glossary:{encoded_word})"

        try:
            return re.sub(pattern, replace_with_link, original_content, flags=re.IGNORECASE)
        except re.error as e:
            logger.error(f"Regex error while creating glossary links: {e}")
            return original_content

    def _handle_glossary_link_clicked(self, url: QUrl):
        if url.scheme() == "glossary":
            decoded_word = url.path()
            if not decoded_word:
                return
            entry = self.course_manager.get_glossary_entry_by_word(decoded_word)
            if entry:
                new_dialog = GlossaryDetailDialog(entry, self.course_manager, self.window())
                new_dialog.exec()

    def get_answer(self) -> str:
        return "completed"

    def clear_input(self):
        pass

    def set_focus_on_input(self):
        if hasattr(self, "continue_button"):
            self.continue_button.setFocus()


class PronunciationExerciseWidget(BaseExerciseWidget):
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
        self._last_transcription_text = ""

        # Remove inherited prompt label
        self.prompt_label.setVisible(False)

        # UI Layout
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(20, 20, 20, 20)
        self.layout.addLayout(grid_layout)

        # 1. Target Text
        self.target_text_label = QLabel(self.exercise.target_pronunciation_text)
        self.target_text_label.setObjectName("pronunciation_target_label")
        self.target_text_label.setWordWrap(True)
        self.target_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(self.target_text_label, 0, 0, 1, 4)

        # 2. Play Reference Audio
        if self.exercise.audio_file:
            self.play_ref_button = QPushButton(self.tr("Play Reference"))
            self.play_ref_button.setObjectName("play_ref_button")
            self.play_ref_button.clicked.connect(
                lambda: self._play_audio_file(self.exercise.audio_file)
            )
            grid_layout.addWidget(self.play_ref_button, 1, 0, 1, 4, Qt.AlignmentFlag.AlignCenter)

        # 3. Record Button
        self.record_button = QPushButton("Record")
        self.record_button.setObjectName("record_button")
        self.record_button.setCheckable(True)
        self.record_button.toggled.connect(self._handle_record_toggle)
        self.record_button.setFixedSize(100, 100)
        grid_layout.addWidget(self.record_button, 2, 0, 1, 4, Qt.AlignmentFlag.AlignCenter)

        # 4. Level Meter
        self.level_meter = AudioLevelMeter(self)
        grid_layout.addWidget(self.level_meter, 3, 0, 1, 4, Qt.AlignmentFlag.AlignCenter)

        # 5. Status Label
        self.status_label = QLabel(self.tr("Tap the microphone to start recording."))
        self.status_label.setObjectName("pronunciation_status_label")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(self.status_label, 4, 0, 1, 4)

        # 6. Model Loading Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        grid_layout.addWidget(self.progress_bar, 5, 0, 1, 4)

        # 7. Dedicated Feedback View
        self.feedback_view = PronunciationFeedbackView(self)
        self.feedback_view.try_again_requested.connect(self.clear_input)
        self.feedback_view.submit_requested.connect(self._handle_submit_click)
        grid_layout.addWidget(self.feedback_view, 6, 0, 1, 4)

        # Backwards compatibility attributes
        self.feedback_group = self.feedback_view
        self.feedback_browser = self.feedback_view.feedback_browser
        self.try_again_button = self.feedback_view.try_again_button
        self.submit_feedback_button = self.feedback_view.submit_button

        # Controller for recording
        self._audio_controller = AudioRecordingController(self)
        self.recording_controller = self._audio_controller
        self._audio_controller.pcm_samples_available.connect(self.level_meter.process_pcm_bytes)
        self._audio_controller.recording_stopped.connect(self._on_recording_stopped)
        self._audio_controller.error_occurred.connect(self._on_recording_error)

        # STT Signals
        self.stt_manager.modelLoadingStarted.connect(self._on_model_loading_started)
        self.stt_manager.modelLoadingFinished.connect(self._on_model_loading_finished)
        self.stt_manager.modelUnloaded.connect(self._on_model_unloaded)

        self.feedback_view.setVisible(False)
        self._update_ui_for_model_state()

        if not self.stt_manager.get_loaded_model_name():
            self._handle_load_model_click()

    def _update_ui_for_model_state(self):
        selected_engine = self.stt_manager.get_selected_stt_engine()
        target_model_name = self.stt_manager.get_stt_model_name(selected_engine)
        loaded_model_name = self.stt_manager.get_loaded_model_name()
        is_loading = self.stt_manager.is_loading()

        self.feedback_view.setVisible(False)

        if not target_model_name or target_model_name.lower() == "none":
            self.record_button.setVisible(False)
            self.status_label.setText(
                self.tr("Please select a Whisper model in Settings to enable pronunciation practice.")
            )
        elif is_loading:
            self._on_model_loading_started(target_model_name)
        elif target_model_name == loaded_model_name:
            self.record_button.setVisible(True)
            self.record_button.setEnabled(True)
            self.status_label.setText(self.tr("Tap the microphone to start recording."))
        else:
            self.record_button.setVisible(False)
            self.status_label.setText(self.tr("Initializing speech model..."))
            self._handle_load_model_click()

    def _on_model_loading_started(self, model_name: str):
        self.record_button.setEnabled(False)
        self.record_button.setVisible(False)
        self.status_label.setText(
            self.tr("Loading pronunciation model ({0})...").format(model_name)
        )
        self.progress_bar.setRange(0, 0)
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
            self.feedback_view.reset()
            self.status_label.setText(self.tr("Recording... Speak now!"))
            self.record_button.setText("Stop")
            self.record_button.setProperty("recording", True)
            self.level_meter.set_recording(True)
            if not self._audio_controller.start_recording():
                self.record_button.setChecked(False)
                self.level_meter.set_recording(False)
        else:
            self.level_meter.set_recording(False)
            self.level_meter.set_level(0.0)
            self.status_label.setText(self.tr("Processing... Please wait."))
            self.record_button.setText("Record")
            self.record_button.setProperty("recording", False)
            self.record_button.setEnabled(False)
            self._audio_controller.stop_recording()

    def _on_recording_stopped(self, wav_path: str, samplerate: int):
        self._start_transcription(wav_path, samplerate, self.course_manager.target_language_code)

    def _on_recording_error(self, message: str):
        self.status_label.setText(message)
        self.record_button.setEnabled(True)
        self.record_button.setChecked(False)

    def _start_transcription(self, audio_file_path: str, recorded_samplerate: int, language_code: str | None = None):
        task = self.stt_manager.transcribe_audio(
            audio_file_path, recorded_samplerate, self.exercise.exercise_id, language_code
        )
        if task:
            task.signals.finished.connect(self._on_transcription_finished)
            task.signals.error.connect(self._on_transcription_error)
        else:
            self.status_label.setText(self.tr("Transcription service not available or disabled."))
            self.record_button.setEnabled(True)

    def _on_transcription_finished(self, exercise_id: str, result: TranscriptionResult):
        if exercise_id != self.exercise.exercise_id:
            return
        full_text = (result.text or "").strip()
        self._last_transcription_text = full_text
        self.status_label.setText(self.tr("Transcription complete. Review your feedback below."))
        self.record_button.setEnabled(True)

        self.feedback_view.display_results(
            target_text=self.exercise.target_pronunciation_text,
            transcribed_text=full_text,
            words=result.words,
            engine=result.engine,
            course_manager=self.course_manager,
        )

        self.transcription_ready.emit(full_text)

    def _on_transcription_error(self, exercise_id: str, error_message: str):
        if exercise_id != self.exercise.exercise_id:
            return
        self.status_label.setText(self.tr("Transcription Error: {0}").format(error_message))
        self.record_button.setEnabled(True)
        self.transcription_error.emit(error_message)

    def _handle_submit_click(self, text: str = ""):
        submission = text or self._last_transcription_text
        self.answer_submitted.emit(submission)
        self.submit_feedback_button.setEnabled(False)
        self.try_again_button.setEnabled(False)

    def get_answer(self) -> str:
        return self._last_transcription_text

    def clear_input(self):
        self.feedback_view.reset()
        self._update_ui_for_model_state()
        self.record_button.setChecked(False)

    def stop_media(self):
        super().stop_media()
        if hasattr(self, "level_meter"):
            self.level_meter.set_recording(False)
            self.level_meter.set_level(0.0)
        if hasattr(self, "_audio_controller"):
            self._audio_controller.cleanup()
        self._disconnect_stt_signals()

    def _disconnect_stt_signals(self):
        try:
            self.stt_manager.modelLoadingStarted.disconnect(self._on_model_loading_started)
        except (RuntimeError, TypeError):
            pass
        try:
            self.stt_manager.modelLoadingFinished.disconnect(self._on_model_loading_finished)
        except (RuntimeError, TypeError):
            pass
        try:
            self.stt_manager.modelUnloaded.disconnect(self._on_model_unloaded)
        except (RuntimeError, TypeError):
            pass

    def closeEvent(self, event):
        self._disconnect_stt_signals()
        super().closeEvent(event)


EXERCISE_WIDGET_MAP: dict[str, type[BaseExerciseWidget]] = {
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

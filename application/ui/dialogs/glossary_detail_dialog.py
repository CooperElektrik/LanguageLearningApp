import os
import logging
import re
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextBrowser,
    QFormLayout, QDialogButtonBox, QMessageBox, QFrame, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QUrl, QEvent
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from core.models import GlossaryEntry
from core.course_manager import CourseManager

from typing import Optional

logger = logging.getLogger(__name__)


class GlossaryDetailDialog(QDialog):
    def __init__(self, entry: GlossaryEntry, course_manager: CourseManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Glossary Entry: {0}").format(entry.word))
        self.setMinimumSize(500, 400)
        
        self.entry = entry
        self.course_manager = course_manager

        # Media player for audio
        self._media_player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None

        self._setup_ui()
        self._load_entry_data()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setObjectName("glossary_detail_dialog_main_layout")
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Word and Translation (placed directly in main_layout for prominence)
        self.word_label = QLabel()
        self.word_label.setObjectName("detail_word_label")
        # self.word_label.setFont(QFont("Arial", 18, QFont.Bold)) # To QSS
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.word_label)

        self.translation_label = QLabel()
        self.translation_label.setObjectName("detail_translation_label")
        # self.translation_label.setFont(QFont("Arial", 14)) # To QSS
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.translation_label)

        main_layout.addWidget(self._create_separator())

        # Scroll Area for the rest of the content (QFormLayout within)
        scroll_area = QScrollArea()
        scroll_area.setObjectName("detail_scroll_area")
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_widget.setObjectName("detail_content_widget")
        content_layout = QFormLayout(content_widget)
        content_layout.setObjectName("detail_content_form_layout")
        content_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        content_layout.setFormAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(10, 10, 10, 10)
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Part of Speech
        self.pos_label = QLabel()
        self.pos_label_title = QLabel(self.tr("Part of Speech:"))
        self.pos_label.setObjectName("detail_pos_label")
        content_layout.addRow(self.pos_label_title, self.pos_label)

        # Example Sentence
        self.example_sentence_text = QTextBrowser()
        self.example_sentence_title = QLabel(self.tr("Example Sentence:"))
        self.example_sentence_text.setObjectName("detail_example_text")
        self.example_sentence_text.setReadOnly(True)
        self.example_sentence_text.setFrameShape(QFrame.Shape.NoFrame)
        self.example_sentence_text.setMinimumHeight(80)
        self.example_sentence_text.setOpenLinks(False)
        self.example_sentence_text.anchorClicked.connect(self._handle_glossary_link_clicked)
        content_layout.addRow(self.example_sentence_title, self.example_sentence_text)

        # Notes
        self.notes_text = QTextBrowser()
        self.notes_text_title = QLabel(self.tr("Notes:"))
        self.notes_text.setObjectName("detail_notes_text")
        self.notes_text.setReadOnly(True)
        self.notes_text.setFrameShape(QFrame.Shape.NoFrame)
        self.notes_text.setMinimumHeight(80)
        content_layout.addRow(self.notes_text_title, self.notes_text)

        # Audio Playback
        audio_layout = QHBoxLayout()
        self.play_audio_button = QPushButton(self.tr("🔊 Play Audio"))
        self.play_audio_button.setObjectName("detail_play_audio_button")
        self.play_audio_button.clicked.connect(self._play_audio)
        audio_layout.addWidget(self.play_audio_button)
        audio_layout.addStretch(1)
        self.pronunciation_title = QLabel(self.tr("Pronunciation:"))
        content_layout.addRow(self.pronunciation_title, audio_layout)

        # OK Button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.setObjectName("detail_dialog_button_box")
        buttons.accepted.connect(self.accept)
        main_layout.addWidget(buttons)
    
    def _create_separator(self) -> QFrame:
        """Creates a horizontal separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("h_separator_detail")
        return separator

    def _create_interactive_glossary_text(self, text: str) -> str:
        """Processes text to find glossary words and wrap them in Markdown links."""
        if not text or not self.course_manager.glossary_map:
            return text

        parts = re.findall(r'(\w+|[^\w\s])', text)
        result_parts = []
        for part in parts:
            # Don't link the current entry's word to itself
            if part.lower() == self.entry.word.lower():
                result_parts.append(part)
                continue

            entry = self.course_manager.get_glossary_entry_by_word(part)
            if entry:
                link = f"[{part}](glossary://{part})"
                result_parts.append(link)
            else:
                result_parts.append(part)
        
        return " ".join(result_parts).replace(" .", ".").replace(" ,", ",").replace(" ?", "?").replace(" !", "!")

    def _load_entry_data(self):
        """Populates the UI fields with data from the GlossaryEntry."""
        self.word_label.setText(self.entry.word)
        self.translation_label.setText(self.entry.translation)
        self.pos_label.setText(self.entry.part_of_speech or self.tr("N/A"))

        if self.entry.example_sentence:
            interactive_example = self._create_interactive_glossary_text(self.entry.example_sentence)
            self.example_sentence_text.setMarkdown(interactive_example)
        else:
            self.example_sentence_text.setPlainText(self.tr("N/A"))

        self.notes_text.setPlainText(self.entry.notes or self.tr("N/A"))

        if not self.entry.audio_file:
            self.play_audio_button.setEnabled(False)
            self.play_audio_button.setText(self.tr("No Audio Available"))
        else:
            self.play_audio_button.setEnabled(True)
            self.play_audio_button.setText(self.tr("🔊 Play Audio"))

    def _handle_glossary_link_clicked(self, url: QUrl):
        """Handles clicks on glossary:// links, opening a new detail dialog."""
        if url.scheme() == "glossary":
            word = url.host()
            entry = self.course_manager.get_glossary_entry_by_word(word)
            if entry:
                # Open a new dialog for the clicked entry
                new_dialog = GlossaryDetailDialog(entry, self.course_manager, self.window())
                new_dialog.exec()
            else:
                logger.warning(f"Glossary link clicked for '{word}', but no entry found.")

    def _init_audio_player(self):
        """Initializes QMediaPlayer and QAudioOutput if not already done."""
        if self._media_player is None:
            self._media_player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._media_player.setAudioOutput(self._audio_output)
            self._media_player.errorOccurred.connect(self._handle_media_error)

    def _handle_media_error(self, error: QMediaPlayer.Error, error_string: str):
        logger.error(f"QMediaPlayer Error ({error}): {error_string}")
        # Optionally, show a more user-friendly message for critical errors
        QMessageBox.warning(
            self,
            self.tr("Audio Playback Error"),
            self.tr("An audio error occurred: {0}").format(error_string)
        )

    def _play_audio(self):
        """Plays the audio file associated with the glossary entry."""
        if not self.entry.audio_file:
            logger.debug("Attempted to play audio, but no audio_file specified.")
            return

        self._init_audio_player()

        # Determine the base directory for assets (manifest_dir is preferred)
        assets_base_dir = self.course_manager.get_course_manifest_directory()
        if not assets_base_dir:
            assets_base_dir = self.course_manager.get_course_content_directory()
            if not assets_base_dir:
                logger.error("Could not determine asset base directory for audio playback.")
                QMessageBox.warning(self, self.tr("Audio Error"), self.tr("Could not determine asset base directory for audio."))
                return
        
        full_audio_path = os.path.join(assets_base_dir, self.entry.audio_file)

        if os.path.exists(full_audio_path):
            self._media_player.setSource(QUrl.fromLocalFile(full_audio_path))
            
            # Check for errors after attempting to set the source
            if self._media_player.error() != QMediaPlayer.Error.NoError:
                error_string = self._media_player.errorString()
                logger.error(f"Error setting media source {full_audio_path}: {error_string}")
                QMessageBox.warning(self, self.tr("Audio Error"), self.tr("Cannot prepare audio: {0}").format(error_string))
                return

            self._media_player.play()

            # Check playback state and errors after attempting to play
            if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                logger.info(f"Playing glossary audio: {full_audio_path}")
            elif self._media_player.error() != QMediaPlayer.Error.NoError:
                error_string = self._media_player.errorString()
                logger.error(f"Error playing audio {full_audio_path}: {error_string}")
                QMessageBox.warning(self, self.tr("Audio Error"), self.tr("Cannot play audio: {0}").format(error_string))

        else:
            logger.error(f"Audio file not found: {full_audio_path} for entry '{self.entry.word}'")
            QMessageBox.warning(self, self.tr("Audio Error"), self.tr("Audio file not found at path:\n{0}\n\nPlease check course assets and paths.").format(full_audio_path))

    def closeEvent(self, event):
        """Stops any playing audio when the dialog is closed."""
        if self._media_player and self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.stop()
        super().closeEvent(event)

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.setWindowTitle(self.tr("Glossary Entry: {0}").format(self.entry.word))
        
        self.pos_label_title.setText(self.tr("Part of Speech:"))
        self.example_sentence_title.setText(self.tr("Example Sentence:"))
        self.notes_text_title.setText(self.tr("Notes:"))
        self.pronunciation_title.setText(self.tr("Pronunciation:"))

        # Reload data to update N/A texts and button text
        self._load_entry_data()
        
        # Standard buttons (OK) usually retranslate automatically.
        logger.debug("GlossaryDetailDialog retranslated.")
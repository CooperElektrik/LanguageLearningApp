import os
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QFormLayout, QDialogButtonBox, QMessageBox, QFrame, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from core.models import GlossaryEntry

logger = logging.getLogger(__name__)

class GlossaryDetailDialog(QDialog):
    def __init__(self, entry: GlossaryEntry, course_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Glossary Entry: {0}").format(entry.word))
        self.setMinimumSize(500, 400)
        
        self.entry = entry
        self.course_manager = course_manager

        self._setup_ui()
        self._load_entry_data()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Scroll Area for the content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QFormLayout(content_widget)
        content_layout.setLabelAlignment(Qt.AlignRight)
        content_layout.setFormAlignment(Qt.AlignHCenter | Qt.AlignTop)
        content_layout.setContentsMargins(10, 10, 10, 10)
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Word and Translation
        self.word_label = QLabel()
        self.word_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.word_label.setAlignment(Qt.AlignCenter)
        main_layout.insertWidget(0, self.word_label) # Insert at top

        self.translation_label = QLabel()
        self.translation_label.setFont(QFont("Arial", 14))
        self.translation_label.setAlignment(Qt.AlignCenter)
        main_layout.insertWidget(1, self.translation_label) # Insert below word

        main_layout.insertWidget(2, self._create_separator()) # Separator

        # Part of Speech
        self.pos_label = QLabel()
        content_layout.addRow(QLabel(self.tr("Part of Speech:")), self.pos_label)

        # Example Sentence
        self.example_sentence_text = QTextEdit()
        self.example_sentence_text.setReadOnly(True)
        self.example_sentence_text.setFrameShape(QFrame.NoFrame)
        self.example_sentence_text.setMinimumHeight(80)
        content_layout.addRow(QLabel(self.tr("Example Sentence:")), self.example_sentence_text)

        # Notes
        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setFrameShape(QFrame.NoFrame)
        self.notes_text.setMinimumHeight(80)
        content_layout.addRow(QLabel(self.tr("Notes:")), self.notes_text)

        # Audio Playback
        audio_layout = QHBoxLayout()
        self.play_audio_button = QPushButton(self.tr("🔊 Play Audio"))
        self.play_audio_button.clicked.connect(self._play_audio)
        audio_layout.addWidget(self.play_audio_button)
        audio_layout.addStretch(1)
        content_layout.addRow(QLabel(self.tr("Pronunciation:")), audio_layout)

        # OK Button
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        main_layout.addWidget(buttons)

        # Media player for audio
        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._media_player.setAudioOutput(self._audio_output)

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator

    def _load_entry_data(self):
        self.word_label.setText(self.entry.word)
        self.translation_label.setText(self.entry.translation)
        self.pos_label.setText(self.entry.part_of_speech or self.tr("N/A"))
        self.example_sentence_text.setPlainText(self.entry.example_sentence or self.tr("N/A"))
        self.notes_text.setPlainText(self.entry.notes or self.tr("N/A"))

        # Enable/disable audio button
        if not self.entry.audio_file:
            self.play_audio_button.setEnabled(False)
            self.play_audio_button.setText(self.tr("No Audio Available"))
        else:
            self.play_audio_button.setEnabled(True)
            self.play_audio_button.setText(self.tr("🔊 Play Audio"))

    def _play_audio(self):
        if self.entry.audio_file:
            assets_base_dir = self.course_manager.get_course_manifest_directory()
            if not assets_base_dir:
                assets_base_dir = self.course_manager.get_course_content_directory()
            
            if assets_base_dir:
                full_audio_path = os.path.join(assets_base_dir, self.entry.audio_file)
                if os.path.exists(full_audio_path):
                    self._media_player.setSource(QUrl.fromLocalFile(full_audio_path))
                    if self._media_player.error() == QMediaPlayer.NoError:
                        self._media_player.play()
                    else:
                        logger.error(f"Error setting media source {full_audio_path}: {self._media_player.errorString()}")
                        QMessageBox.warning(self, self.tr("Audio Error"), self.tr("Cannot play audio: {0}").format(self._media_player.errorString()))
                else:
                    logger.error(f"Audio file not found: {full_audio_path} for entry {self.entry.word}")
                    QMessageBox.warning(self, self.tr("Audio Error"), self.tr("Audio file not found: {0}\n\nCheck paths.").format(self.entry.audio_file))
            else:
                logger.error("Could not determine asset base directory for audio playback.")
                QMessageBox.warning(self, self.tr("Audio Error"), self.tr("Could not determine asset base directory."))
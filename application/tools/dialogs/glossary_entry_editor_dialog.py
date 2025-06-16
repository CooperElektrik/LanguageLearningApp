import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QFormLayout, QDialogButtonBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from application.core.models import GlossaryEntry
from .asset_manager_dialog import AssetManagerDialog

from typing import Optional

class GlossaryEntryEditorDialog(QDialog):
    def __init__(self, entry: Optional[GlossaryEntry] = None, course_root_dir: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Glossary Entry")
        self.setMinimumSize(400, 300)

        self.original_entry = entry
        self.course_root_dir = course_root_dir
        self.edited_entry: Optional[GlossaryEntry] = None # To store the edited data

        self._setup_ui()
        if entry:
            self._load_entry_data(entry)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.word_input = QLineEdit()
        self.word_input.setPlaceholderText("e.g., Saluton")
        form_layout.addRow("Word: *", self.word_input)

        self.translation_input = QLineEdit()
        self.translation_input.setPlaceholderText("e.g., Hello")
        form_layout.addRow("Translation: *", self.translation_input)

        self.pos_input = QLineEdit()
        self.pos_input.setPlaceholderText("e.g., n., v., adj.")
        form_layout.addRow("Part of Speech:", self.pos_input)

        self.example_sentence_input = QTextEdit()
        self.example_sentence_input.setPlaceholderText("e.g., Saluton, kiel vi fartas?")
        self.example_sentence_input.setMinimumHeight(60)
        form_layout.addRow("Example Sentence:", self.example_sentence_input)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("e.g., Common greeting in Esperanto.")
        self.notes_input.setMinimumHeight(60)
        form_layout.addRow("Notes:", self.notes_input)

        # Audio file input with browse button
        audio_layout = QHBoxLayout()
        self.audio_file_input = QLineEdit()
        self.audio_file_input.setPlaceholderText("e.g., assets/audio/saluton.mp3 (relative to course root)")
        audio_layout.addWidget(self.audio_file_input)
        browse_audio_button = QPushButton("Browse...")
        browse_audio_button.clicked.connect(self._browse_audio_file)
        audio_layout.addWidget(browse_audio_button)
        form_layout.addRow("Audio File:", audio_layout)

        main_layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _load_entry_data(self, entry: GlossaryEntry):
        self.word_input.setText(entry.word)
        self.translation_input.setText(entry.translation)
        self.pos_input.setText(entry.part_of_speech or "")
        self.example_sentence_input.setPlainText(entry.example_sentence or "")
        self.notes_input.setPlainText(entry.notes or "")
        self.audio_file_input.setText(entry.audio_file or "")

    def _browse_audio_file(self):
        if not self.course_root_dir:
            QMessageBox.warning(
                self, "Browse Audio", "Course root directory is not set. Please save the manifest first."
            )
            return
        
        dialog = AssetManagerDialog(self.course_root_dir, "audio", self)
        if dialog.exec() == QDialog.Accepted:
            selected_path = dialog.selected_asset_path
            if selected_path:
                self.audio_file_input.setText(selected_path)

    def accept(self):
        # Validate required fields
        if not self.word_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Word cannot be empty.")
            return
        if not self.translation_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Translation cannot be empty.")
            return
        
        self.edited_entry = GlossaryEntry(
            word=self.word_input.text().strip(),
            translation=self.translation_input.text().strip(),
            part_of_speech=self.pos_input.text().strip() or None,
            example_sentence=self.example_sentence_input.toPlainText().strip() or None,
            notes=self.notes_input.toPlainText().strip() or None,
            audio_file=self.audio_file_input.text().strip() or None,
        )
        super().accept()

    def get_edited_entry(self) -> Optional[GlossaryEntry]:
        return self.edited_entry
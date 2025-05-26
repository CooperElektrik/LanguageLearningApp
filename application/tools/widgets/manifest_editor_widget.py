# File: tools/widgets/manifest_editor_widget.py

import os
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QFileDialog, QFormLayout, QMessageBox) # Added QMessageBox
from PySide6.QtCore import Signal, Qt
from typing import Any, Dict

# Correct import for core.models - relies on project_root being added to sys.path by main_editor.py
try:
    from core.models import Course # This is for type hinting and potential direct manipulation
except ImportError:
    logging.warning("Could not import Course model in ManifestEditorWidget.")
    class Course: pass # Dummy class for type hinting

logger = logging.getLogger(__name__)

class ManifestEditorWidget(QWidget):
    data_changed = Signal() # Emits when data in the form is changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_manifest_data: dict = None
        self.current_course_obj: Course = None

        self.form_layout = QFormLayout(self)

        self.course_id_input = QLineEdit()
        self.course_id_input.setReadOnly(True) # IDs are usually fixed
        self.form_layout.addRow("Course ID:", self.course_id_input)

        self.course_title_input = QLineEdit()
        self.course_title_input.textChanged.connect(lambda: self.data_changed.emit())
        self.form_layout.addRow("Course Title:", self.course_title_input)

        self.target_lang_input = QLineEdit()
        self.target_lang_input.textChanged.connect(lambda: self.data_changed.emit())
        self.form_layout.addRow("Target Language:", self.target_lang_input)

        self.source_lang_input = QLineEdit()
        self.source_lang_input.textChanged.connect(lambda: self.data_changed.emit())
        self.form_layout.addRow("Source Language:", self.source_lang_input)

        self.content_file_input = QLineEdit()
        self.content_file_input.setReadOnly(True) # Display only, content is derived
        # For simplicity, we don't allow changing content_file directly here.
        # It's tied to the manifest filename/location.
        self.form_layout.addRow("Content File:", self.content_file_input)

        self.version_input = QLineEdit()
        self.version_input.textChanged.connect(lambda: self.data_changed.emit())
        self.form_layout.addRow("Version:", self.version_input)

        self.author_input = QLineEdit()
        self.author_input.textChanged.connect(lambda: self.data_changed.emit())
        self.form_layout.addRow("Author:", self.author_input)

        self.description_input = QLineEdit()
        self.description_input.textChanged.connect(lambda: self.data_changed.emit())
        self.form_layout.addRow("Description:", self.description_input)


    def load_data(self, manifest_data: Dict[str, Any], course_obj: Course):
        """Loads manifest data and associated course object into the editor fields."""
        self.current_manifest_data = manifest_data
        self.current_course_obj = course_obj

        self.course_id_input.setText(manifest_data.get("course_id", ""))
        self.course_title_input.setText(manifest_data.get("course_title", ""))
        self.target_lang_input.setText(manifest_data.get("target_language", ""))
        self.source_lang_input.setText(manifest_data.get("source_language", ""))
        self.content_file_input.setText(manifest_data.get("content_file", ""))
        self.version_input.setText(manifest_data.get("version", ""))
        self.author_input.setText(manifest_data.get("author", ""))
        self.description_input.setText(manifest_data.get("description", ""))

    def apply_changes_to_data(self, manifest_data: Dict[str, Any], course_obj: Course):
        """Applies current editor field values back to the manifest data and course object."""
        manifest_data["course_title"] = self.course_title_input.text()
        manifest_data["target_language"] = self.target_lang_input.text()
        manifest_data["source_language"] = self.source_lang_input.text()
        # content_file is typically updated by save_course_as, not directly here.
        # manifest_data["content_file"] = self.content_file_input.text() # Not editable
        manifest_data["version"] = self.version_input.text()
        manifest_data["author"] = self.author_input.text()
        manifest_data["description"] = self.description_input.text()

        # Update core.models.Course object as well, as it holds some of this redundant info
        if course_obj:
            course_obj.title = self.course_title_input.text()
            course_obj.target_language = self.target_lang_input.text()
            course_obj.source_language = self.source_lang_input.text()
            course_obj.version = self.version_input.text()
            course_obj.author = self.author_input.text()
            course_obj.description = self.description_input.text()
            # course_obj.content_file = self.content_file_input.text() # Not editable

    def validate(self) -> tuple[bool, str]:
        """Validates the current data in the manifest editor fields."""
        if not self.course_title_input.text().strip():
            return False, "Course Title cannot be empty."
        if not self.target_lang_input.text().strip():
            return False, "Target Language cannot be empty."
        if not self.source_lang_input.text().strip():
            return False, "Source Language cannot be empty."
        # content_file is automatically set by save_as, no direct user input validation needed here.
        
        return True, ""
import os
import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QMessageBox,
    QFrame,
    QDialog,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from application.core.models import GlossaryEntry
from application.core.glossary_loader import load_glossary
from application.core import yaml_serializer

from application.tools.dialogs.glossary_entry_editor_dialog import (
    GlossaryEntryEditorDialog,
)

from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class GlossaryEditorWidget(QWidget):
    data_changed = Signal()  # Emit when glossary data is modified

    def __init__(self, parent=None):
        super().__init__(parent)
        self.glossary_entries: List[GlossaryEntry] = []
        self.current_glossary_filepath: str = None
        self.current_manifest_path: str = (
            None  # Needed to get course root dir for asset dialog
        )

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        main_layout.addWidget(QLabel("Manage Glossary Entries"))
        main_layout.addWidget(self._create_separator())

        # List of glossary entries
        self.glossary_list_widget = QListWidget()
        self.glossary_list_widget.itemDoubleClicked.connect(self._edit_selected_entry)
        main_layout.addWidget(self.glossary_list_widget)

        # Buttons for CRUD operations
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add Entry")
        add_button.clicked.connect(self._add_entry)
        edit_button = QPushButton("Edit Selected")
        edit_button.clicked.connect(self._edit_selected_entry)
        delete_button = QPushButton("Delete Selected")
        delete_button.clicked.connect(self._delete_selected_entry)

        button_layout.addWidget(add_button)
        button_layout.addWidget(edit_button)
        button_layout.addWidget(delete_button)
        button_layout.addStretch(1)
        main_layout.addLayout(button_layout)

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator

    def load_glossary_data(self, manifest_data: Dict[str, Any], manifest_path: str):
        """
        Loads glossary entries based on manifest data.
        """
        self.current_manifest_path = manifest_path
        glossary_filename = manifest_data.get("glossary_file")
        if glossary_filename:
            manifest_dir_abs = os.path.dirname(os.path.abspath(manifest_path))
            self.current_glossary_filepath = os.path.join(
                manifest_dir_abs, glossary_filename
            )
            self.glossary_entries = load_glossary(self.current_glossary_filepath)
        else:
            self.current_glossary_filepath = None
            self.glossary_entries = []
            QMessageBox.information(
                self,
                "Glossary Missing",
                "Manifest does not specify a 'glossary_file'. Create a new one or add to manifest.",
            )
            # Optionally, prompt to create a new glossary file if not specified
            self.data_changed.emit()  # Even if empty, reflect state

        self._populate_list_widget()

    def save_glossary_data(
        self, manifest_data: Dict[str, Any], manifest_path: str
    ) -> bool:
        """
        Saves the current glossary entries to the YAML file.
        Updates manifest_data if glossary_file was missing and a new one is created.
        """
        if not self.current_glossary_filepath:
            # If no glossary file was loaded or specified in manifest, prompt to save as new
            manifest_dir_abs = os.path.dirname(os.path.abspath(manifest_path))
            default_glossary_filename = "glossary.yaml"
            new_filepath, _ = QMessageBox.information(
                self,
                "Save Glossary",
                "No glossary file is specified in the manifest. Would you like to create a new one?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if new_filepath == QMessageBox.No:
                logger.info("User chose not to create a new glossary file.")
                return False

            self.current_glossary_filepath = os.path.join(
                manifest_dir_abs, default_glossary_filename
            )
            # Update the manifest data with the new glossary file name
            manifest_data["glossary_file"] = default_glossary_filename
            logger.info(
                f"New glossary file '{default_glossary_filename}' will be saved and linked in manifest."
            )
            # Trigger manifest save after this, via EditorWindow's _do_save

        if (
            not self.current_glossary_filepath
        ):  # Should not happen if above logic is good
            logger.error("No glossary filepath determined for saving.")
            return False

        return yaml_serializer.save_glossary_to_yaml(
            self.glossary_entries, self.current_glossary_filepath
        )

    def _populate_list_widget(self):
        self.glossary_list_widget.clear()
        for entry in self.glossary_entries:
            item_text = f"{entry.word} - {entry.translation}"
            if entry.part_of_speech:
                item_text += f" ({entry.part_of_speech})"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, entry)  # Store the actual object
            self.glossary_list_widget.addItem(list_item)

    def _add_entry(self):
        dialog = GlossaryEntryEditorDialog(
            course_root_dir=os.path.dirname(self.current_manifest_path), parent=self
        )
        if dialog.exec() == QDialog.Accepted:
            new_entry = dialog.get_edited_entry()
            if new_entry:
                self.glossary_entries.append(new_entry)
                self._populate_list_widget()
                self.data_changed.emit()

    def _edit_selected_entry(self):
        selected_items = self.glossary_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self, "Edit Entry", "Please select an entry to edit."
            )
            return

        current_item = selected_items[0]
        entry_to_edit: GlossaryEntry = current_item.data(Qt.UserRole)

        dialog = GlossaryEntryEditorDialog(
            entry=entry_to_edit,
            course_root_dir=os.path.dirname(self.current_manifest_path),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            edited_entry = dialog.get_edited_entry()
            if edited_entry:
                # Update the original object in the list
                # A more robust way might be to find its index and replace,
                # but direct object modification works for dataclasses if no list reordering occurs.
                entry_to_edit.word = edited_entry.word
                entry_to_edit.translation = edited_entry.translation
                entry_to_edit.part_of_speech = edited_entry.part_of_speech
                entry_to_edit.example_sentence = edited_entry.example_sentence
                entry_to_edit.notes = edited_entry.notes
                entry_to_edit.audio_file = edited_entry.audio_file

                self._populate_list_widget()  # Refresh visual
                self.data_changed.emit()

    def _delete_selected_entry(self):
        selected_items = self.glossary_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self, "Delete Entry", "Please select an entry to delete."
            )
            return

        item_to_delete = selected_items[0]
        entry_to_delete: GlossaryEntry = item_to_delete.data(Qt.UserRole)

        reply = QMessageBox.question(
            self,
            "Delete Entry",
            f"Are you sure you want to delete entry '{entry_to_delete.word}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.glossary_entries.remove(entry_to_delete)
            self._populate_list_widget()
            self.data_changed.emit()

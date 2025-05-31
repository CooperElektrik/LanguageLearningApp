import os
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QScrollArea, QFrame, QStyle
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.models import GlossaryEntry
from ..dialogs.glossary_detail_dialog import GlossaryDetailDialog 
from typing import List

logger = logging.getLogger(__name__)

class GlossaryView(QWidget):
    back_to_overview_signal = Signal()

    def __init__(self, course_manager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.glossary_entries: List[GlossaryEntry] = [] # All loaded entries

        self._setup_ui()
        self.refresh_view() # Load initial data

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)

        # Top Bar with Back Button
        top_bar_layout = QHBoxLayout()
        self.back_button = QPushButton(self.tr("← Back to Course Overview"))
        self.back_button.clicked.connect(self.back_to_overview_signal.emit)
        top_bar_layout.addWidget(self.back_button)
        top_bar_layout.addStretch(1)
        main_layout.addLayout(top_bar_layout)

        # Title
        title_label = QLabel(self.tr("Glossary"))
        title_label.setFont(QFont("Arial", 20, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        main_layout.addWidget(self._create_separator())

        # Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(self.tr("Search words or translations..."))
        self.search_bar.textChanged.connect(self._filter_glossary_list)
        main_layout.addWidget(self.search_bar)

        # Glossary List
        self.glossary_list_widget = QListWidget()
        self.glossary_list_widget.itemDoubleClicked.connect(self._show_entry_details)
        main_layout.addWidget(self.glossary_list_widget)

        main_layout.addStretch(1)

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator

    def refresh_view(self):
        """Loads and displays all glossary entries."""
        self.glossary_entries = self.course_manager.get_glossary_entries()
        self._populate_list_widget(self.glossary_entries)
        logger.info(f"Glossary view refreshed with {len(self.glossary_entries)} entries.")

    def _populate_list_widget(self, entries_to_display: List[GlossaryEntry]):
        self.glossary_list_widget.clear()
        if not entries_to_display:
            # Handle empty glossary or no search results
            self.glossary_list_widget.addItem(QListWidgetItem(self.tr("No glossary entries found.")))
            return

        for entry in entries_to_display:
            item_text = f"{entry.word} - {entry.translation}"
            if entry.part_of_speech:
                item_text += f" ({entry.part_of_speech})"
            
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, entry) # Store the actual GlossaryEntry object
            
            # Optional: Add an icon if audio file exists
            if entry.audio_file:
                list_item.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))
            
            self.glossary_list_widget.addItem(list_item)
        
        self.glossary_list_widget.sortItems(Qt.AscendingOrder) # Keep entries sorted

    def _filter_glossary_list(self, text: str):
        """Filters the glossary list based on search bar text."""
        search_term = text.lower().strip()
        filtered_entries = []

        if not search_term:
            filtered_entries = self.glossary_entries # Show all if no search term
        else:
            for entry in self.glossary_entries:
                if (search_term in entry.word.lower() or
                    search_term in entry.translation.lower() or
                    (entry.example_sentence and search_term in entry.example_sentence.lower()) or
                    (entry.notes and search_term in entry.notes.lower())):
                    filtered_entries.append(entry)
        
        self._populate_list_widget(filtered_entries)


    def _show_entry_details(self, item: QListWidgetItem):
        """Opens a dialog to show full details of the selected glossary entry."""
        entry: GlossaryEntry = item.data(Qt.UserRole)
        if entry:
            dialog = GlossaryDetailDialog(entry, self.course_manager, self)
            dialog.exec()
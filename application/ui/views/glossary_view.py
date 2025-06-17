import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QFrame, QStyle
)
from PySide6.QtCore import Qt, Signal, QEvent

from typing import List

from core.models import GlossaryEntry
from core.course_manager import CourseManager
from ..dialogs.glossary_detail_dialog import GlossaryDetailDialog 

logger = logging.getLogger(__name__)

class GlossaryView(QWidget):
    back_to_overview_signal = Signal()

    def __init__(self, course_manager: CourseManager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.all_glossary_entries: List[GlossaryEntry] = []

        self._setup_ui()
        self.refresh_view()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setObjectName("glossary_view_main_layout")
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Top Bar with Back Button
        top_bar_layout = QHBoxLayout()
        self.back_button = QPushButton(self.tr("← Back to Course Overview"))
        self.back_button.setObjectName("back_button_glossary")
        self.back_button.clicked.connect(self.back_to_overview_signal.emit)
        top_bar_layout.addWidget(self.back_button)
        top_bar_layout.addStretch(1) # Pushes button to the left
        main_layout.addLayout(top_bar_layout)

        # Title
        self.title_label = QLabel(self.tr("Glossary"))
        self.title_label.setObjectName("glossary_title_label")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

        # Separator
        main_layout.addWidget(self._create_separator())

        # Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("glossary_search_bar")
        self.search_bar.setPlaceholderText(self.tr("Search words, translations, examples..."))
        self.search_bar.textChanged.connect(self._filter_glossary_list)
        main_layout.addWidget(self.search_bar)

        # Glossary List
        self.glossary_list_widget = QListWidget()
        self.glossary_list_widget.setObjectName("glossary_list_widget")
        self.glossary_list_widget.itemDoubleClicked.connect(self._show_entry_details)
        main_layout.addWidget(self.glossary_list_widget, 1) # Add stretch factor for the list

    def _create_separator(self) -> QFrame:
        """Creates a horizontal separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("h_separator_glossary")
        return separator

    def refresh_view(self):
        """Loads/reloads and displays all glossary entries."""
        self.all_glossary_entries = self.course_manager.get_glossary_entries()
        # Sort entries once after loading, e.g., by word
        self.all_glossary_entries.sort(key=lambda entry: entry.word.lower())
        
        self._filter_glossary_list(self.search_bar.text()) # Re-apply current filter
        logger.info(f"Glossary view refreshed with {len(self.all_glossary_entries)} total entries.")


    def _populate_list_widget(self, entries_to_display: List[GlossaryEntry]):
        self.glossary_list_widget.clear()
        if not entries_to_display:
            no_results_item = QListWidgetItem(self.tr("No glossary entries found matching your search."))
            if not self.search_bar.text(): # If search bar is empty, means glossary is empty
                 no_results_item.setText(self.tr("No glossary entries available for this course."))
            self.glossary_list_widget.addItem(no_results_item)
            return

        for entry in entries_to_display:
            item_text = f"{entry.word} – {entry.translation}" # Using en-dash for better typography
            if entry.part_of_speech:
                item_text += f" ({entry.part_of_speech})"
            
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, entry) # Store the GlossaryEntry object
            list_item.setToolTip(self.tr("Double-click to see details for '{0}'").format(entry.word))
            
            if entry.audio_file:
                list_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
            
            self.glossary_list_widget.addItem(list_item)
        
        # Sorting is now done on self.all_glossary_entries once,
        # so the filtered list will maintain that relative order.
        # If dynamic sorting of the QListWidget itself is desired after filtering,
        # self.glossary_list_widget.sortItems(Qt.SortOrder.AscendingOrder) can be called here.
        # However, for typical search, maintaining original sorted order of subset is common.


    def _filter_glossary_list(self, text: str):
        """Filters the displayed glossary list based on the search bar text."""
        search_term = text.lower().strip()
        
        if not search_term:
            filtered_entries = self.all_glossary_entries # Show all (already sorted)
        else:
            filtered_entries = []
            for entry in self.all_glossary_entries:
                # Check multiple fields for the search term
                match = (search_term in entry.word.lower() or
                         search_term in entry.translation.lower() or
                         (entry.part_of_speech and search_term in entry.part_of_speech.lower()) or
                         (entry.example_sentence and search_term in entry.example_sentence.lower()) or
                         (entry.notes and search_term in entry.notes.lower()))
                if match:
                    filtered_entries.append(entry)
        
        self._populate_list_widget(filtered_entries)


    def _show_entry_details(self, item: QListWidgetItem):
        """Opens a dialog to show full details of the selected glossary entry."""
        entry_data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(entry_data, GlossaryEntry):
            dialog = GlossaryDetailDialog(entry_data, self.course_manager, self)
            dialog.exec()
        elif item.text().startswith(self.tr("No glossary entries")): # Non-data item
            pass # Do nothing for "no entries" messages
        else:
            logger.warning(f"Clicked item in glossary list without valid GlossaryEntry data: {item.text()}")

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.back_button.setText(self.tr("← Back to Course Overview"))
        self.title_label.setText(self.tr("Glossary"))
        self.search_bar.setPlaceholderText(self.tr("Search words, translations, examples..."))
        
        self.refresh_view() # Repopulates list with potentially new "No entries" text
        logger.debug("GlossaryView retranslated.")
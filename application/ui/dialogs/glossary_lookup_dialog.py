import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QDialogButtonBox
)
from PySide6.QtCore import Qt, QEvent
from typing import List, Optional

from core.models import GlossaryEntry

logger = logging.getLogger(__name__)

class GlossaryLookupDialog(QDialog):
    """A dialog for searching and selecting a glossary entry with autocomplete."""
    def __init__(self, all_entries: List[GlossaryEntry], parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Glossary Lookup"))
        self.setMinimumSize(350, 400)

        self.all_entries = sorted(all_entries, key=lambda e: e.word.lower())
        self.selected_entry: Optional[GlossaryEntry] = None

        main_layout = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("Start typing to search..."))
        self.search_input.textChanged.connect(self._update_suggestions)
        main_layout.addWidget(self.search_input)

        self.suggestions_list = QListWidget()
        self.suggestions_list.itemActivated.connect(self._accept_selection)
        main_layout.addWidget(self.suggestions_list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)
        
        # Initial population
        self._update_suggestions("")
        self.search_input.setFocus()

    def _update_suggestions(self, text: str):
        """Filters glossary entries and updates the suggestions list."""
        self.suggestions_list.clear()
        search_term = text.lower().strip()

        if not search_term:
            filtered = self.all_entries
        else:
            filtered = [
                entry for entry in self.all_entries 
                if search_term in entry.word.lower() or search_term in entry.translation.lower()
            ]

        for entry in filtered:
            item_text = f"{entry.word} – {entry.translation}"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, entry)
            self.suggestions_list.addItem(list_item)

    def _accept_selection(self):
        """Accepts the dialog with the currently selected glossary entry."""
        # Prioritize the explicitly selected item in the list
        selected_items = self.suggestions_list.selectedItems()
        if selected_items:
            item = selected_items[0]
        # If none is selected (e.g., user pressed Enter in QLineEdit), take the first item
        elif self.suggestions_list.count() > 0:
            item = self.suggestions_list.item(0)
        else:
            return # No item to select, do nothing

        self.selected_entry = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def get_selected_entry(self) -> Optional[GlossaryEntry]:
        """Returns the entry that was selected by the user."""
        return self.selected_entry
        
    def keyPressEvent(self, event):
        """Enhances keyboard navigation between the search input and the list."""
        # If user is in the search box and presses Down, focus the list
        if self.search_input.hasFocus() and event.key() == Qt.Key.Key_Down and self.suggestions_list.count() > 0:
            self.suggestions_list.setFocus()
            self.suggestions_list.setCurrentRow(0)
            return

        # If user presses Enter in the search box, trigger acceptance
        if self.search_input.hasFocus() and event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            self._accept_selection()
            return
            
        super().keyPressEvent(event)

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.setWindowTitle(self.tr("Glossary Lookup"))
        self.search_input.setPlaceholderText(self.tr("Start typing to search..."))
        # List items are dynamically generated, their "No entries" text is handled in _update_suggestions
        self._update_suggestions(self.search_input.text()) # Re-filter to update any "No entries" message
        logger.debug("GlossaryLookupDialog retranslated.")
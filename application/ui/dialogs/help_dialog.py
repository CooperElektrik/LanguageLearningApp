import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QDialogButtonBox,
    QWidget,
    QPushButton,
    QLabel,
    QLineEdit,
    QScrollArea,
    QFrame,
    QStyle
)
from PySide6.QtCore import QEvent

logger = logging.getLogger(__name__)

# --- Custom Widget for a single FAQ item (Accordion style) ---
# (This class remains unchanged, it's already excellent)
class FaqItemWidget(QWidget):
    """
    A custom widget representing a single collapsible FAQ item.
    It consists of a question button and an answer label.
    """
    def __init__(self, question: str, answer: str, parent=None):
        super().__init__(parent)
        self.question_text = question
        self.answer_text = answer

        # --- Widgets ---
        self.toggle_button = QPushButton(f"▶ {self.question_text}")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px;
                border: none;
                font-weight: bold;
                background-color: transparent;
                color: #111; /* Color for question text */
            }
            QPushButton:hover {
                background-color: #e6e6e6;
            }
        """)

        self.answer_label = QLabel(self.answer_text)
        self.answer_label.setWordWrap(True)
        self.answer_label.setVisible(False)
        self.answer_label.setStyleSheet("padding: 2px 8px 8px 25px; color: #333;") # Indent answer

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.answer_label)

        # --- Connections ---
        self.toggle_button.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        """Show or hide the answer when the button is toggled."""
        self.answer_label.setVisible(checked)
        if checked:
            self.toggle_button.setText(f"▼ {self.question_text}")
        else:
            self.toggle_button.setText(f"▶ {self.question_text}")

    def expand(self):
        """Public method to expand the item."""
        self.toggle_button.setChecked(True)

    def collapse(self):
        """Public method to collapse the item."""
        self.toggle_button.setChecked(False)
        
    def matches_filter(self, text: str) -> bool:
        """Check if the question or answer contains the filter text."""
        if not text:
            return True
        return text in self.question_text.lower() or text in self.answer_text.lower()


# --- Reworked Help Dialog ---

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Help - FAQ"))
        self.setMinimumSize(700, 500)
        
        self._faq_widgets = [] 

        self._init_ui()
        self._populate_faq_content()
        self._apply_stylesheet()

    def _init_ui(self):
        """Initialize the main UI layout and widgets."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # --- Top Bar (Search and Controls) ---
        top_bar_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("Search for a question..."))
        search_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        self.search_input.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.textChanged.connect(self._on_search_changed)
        top_bar_layout.addWidget(self.search_input)

        self.expand_all_btn = QPushButton(self.tr("Expand All"))
        self.collapse_all_btn = QPushButton(self.tr("Collapse All"))
        self.expand_all_btn.clicked.connect(self._expand_all)
        self.collapse_all_btn.clicked.connect(self._collapse_all)
        top_bar_layout.addWidget(self.expand_all_btn)
        top_bar_layout.addWidget(self.collapse_all_btn)
        
        main_layout.addLayout(top_bar_layout)
        
        # --- Scroll Area for Content ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # THIS IS THE KEY CHANGE: Give the inner widget an object name for styling
        self.scroll_content_widget = QWidget()
        self.scroll_content_widget.setObjectName("scrollAreaWidgetContents")
        
        self.faq_layout = QVBoxLayout(self.scroll_content_widget)
        self.faq_layout.setContentsMargins(10, 10, 10, 10)
        self.faq_layout.setSpacing(5)
        
        self.scroll_area.setWidget(self.scroll_content_widget)
        main_layout.addWidget(self.scroll_area)
        
        # --- Bottom Button Box ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _clear_layout(self, layout):
        """Helper to remove all widgets from a layout."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populate_faq_content(self):
        """Fetch FAQ data and create widgets. (Refactored for clarity)."""
        # Clear previous content and widget references
        self._clear_layout(self.faq_layout)
        self._faq_widgets = []

        help_data = self._get_help_data()
        
        # Build content from top to bottom
        for category_name, questions in help_data.items():
            # Add Category Header
            category_label = QLabel(category_name)
            category_label.setObjectName("categoryHeader")
            self.faq_layout.addWidget(category_label)

            # Add FAQ items for the category
            category_items = []
            sorted_question_keys = sorted(questions.keys(), key=lambda x: int(x))
            for q_key in sorted_question_keys:
                q_data = questions[q_key]
                faq_item = FaqItemWidget(q_data["question"], q_data["answer"])
                self.faq_layout.addWidget(faq_item)
                category_items.append(faq_item)
            
            # Add separator
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            self.faq_layout.addWidget(line)

            # Store widgets for filtering
            self._faq_widgets.append({
                "category_header": category_label,
                "separator": line,
                "items": category_items
            })
        
        self.faq_layout.addStretch() # Pushes all content to the top

    def _apply_stylesheet(self):
        """Apply a global stylesheet for a better look."""
        # The return is removed, and the stylesheet is updated to target the named widget.
        self.setStyleSheet("""
            HelpDialog {
                background-color: #f5f5f5;
            }
            /* Style the frame of the scroll area */
            QScrollArea {
                border: 1px solid #dcdcdc;
                border-radius: 4px;
            }
            /* Style the WIDGET INSIDE the scroll area using its object name */
            #scrollAreaWidgetContents {
                background-color: white;
            }
            #categoryHeader {
                font-size: 16pt;
                font-weight: bold;
                color: #333;
                padding-top: 15px;
                padding-bottom: 5px;
            }
            /* Styles for the control buttons (Expand/Collapse/Close) */
            QDialogButtonBox QPushButton, HelpDialog > QHBoxLayout > QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: normal;
            }
            QDialogButtonBox QPushButton:hover, HelpDialog > QHBoxLayout > QPushButton:hover {
                background-color: #005a9e;
            }
            QDialogButtonBox QPushButton:pressed, HelpDialog > QHBoxLayout > QPushButton:pressed {
                background-color: #004578;
            }
        """)

    def changeEvent(self, event: QEvent):
        """Handles language change events to re-translate the UI."""
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        """Retranslates all the strings in the dialog."""
        self.setWindowTitle(self.tr("Help - FAQ"))
        self.search_input.setPlaceholderText(self.tr("Search for a question..."))
        self.expand_all_btn.setText(self.tr("Expand All"))
        self.collapse_all_btn.setText(self.tr("Collapse All"))
        
        self._populate_faq_content()
        logger.debug("HelpDialog retranslated.")

    def _get_help_data(self) -> dict[str, dict[str, str]]:
        """Returns the help data."""
        return {
            self.tr("Navigation"): {
                "1": {
                    "question": self.tr("How do I start a lesson?"),
                    "answer": self.tr("From the 'Course Navigation' panel on the left, simply click on the lesson you wish to begin.")
                },
                "2": {
                    "question": self.tr("How do I return to the course selection screen?"),
                    "answer": self.tr("Use the 'File' menu and select 'Return to Course Selection'.")
                }
            },
            self.tr("Whisper Model"): {
                "3": {
                    "question": self.tr("What is the Whisper model used for?"),
                    "answer": self.tr("The Whisper model is used for speech-to-text transcription. It analyzes your pronunciation exercises and provides feedback.")
                },
                "4": {
                    "question": self.tr("How can I change the Whisper model?"),
                    "answer": self.tr("You can select a different Whisper model from the 'Settings' dialog. Larger models are more accurate but require more resources.")
                }
            },
            self.tr("VOSK Model"): {
                "5": {
                    "question": self.tr("What is the VOSK model used for?"),
                    "answer": self.tr("The VOSK model is an alternative speech-to-text transcription engine. It is generally smaller and faster than Whisper models, making it suitable for devices with limited resources or for real-time transcription where absolute accuracy is not the primary concern.")
                },
                "6": {
                    "question": self.tr("How can I change the VOSK model?"),
                    "answer": self.tr("You can select a different VOSK model from the 'Settings' dialog. VOSK models are typically language-specific and need to be downloaded separately.")
                }
            },
            self.tr("Whisper vs. VOSK"): {
                "7": {
                    "question": self.tr("What are the main differences between Whisper and VOSK?"),
                    "answer": self.tr(
                        "Whisper models are generally more accurate and support a wider range of languages, but they are larger and require more computational resources (especially for larger models). "
                        "VOSK models are typically smaller, faster, and can run efficiently on less powerful hardware, but they are language-specific and may not be as accurate as Whisper for all use cases. "
                        "Choose Whisper for higher accuracy and broader language support if you have the resources, and VOSK for speed and efficiency on more constrained systems."
                    )
                }
            }
        }
        
    def _on_search_changed(self, text: str):
        """Filter the visible FAQ items based on the search query."""
        query = text.lower().strip()
        
        # When searching, collapse everything to avoid confusion from expanded, non-matching answers
        if query:
            self._collapse_all()

        for category_group in self._faq_widgets:
            any_item_visible_in_category = False
            for item_widget in category_group["items"]:
                is_match = item_widget.matches_filter(query)
                item_widget.setVisible(is_match)
                if is_match:
                    any_item_visible_in_category = True
            
            category_group["category_header"].setVisible(any_item_visible_in_category)
            category_group["separator"].setVisible(any_item_visible_in_category)

    def _expand_all(self):
        """Expand all visible FAQ items."""
        for category_group in self._faq_widgets:
            for item_widget in category_group["items"]:
                if item_widget.isVisible():
                    item_widget.expand()

    def _collapse_all(self):
        """Collapse all visible FAQ items."""
        for category_group in self._faq_widgets:
            for item_widget in category_group["items"]:
                # No need to check for visibility, just collapse all
                item_widget.collapse()
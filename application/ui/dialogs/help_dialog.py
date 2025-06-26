import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTreeView,
    QDialogButtonBox,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QEvent

logger = logging.getLogger(__name__)

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Help - FAQ"))
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tree_view)

        # Initialize the model after the dialog is fully constructed to ensure self.tr() works
        self.model = self._create_faq_model()
        self.tree_view.setModel(self.model)
        
        # Expand all top-level items (categories) by default
        for i in range(self.model.rowCount()):
            self.tree_view.expand(self.model.index(i, 0))
 
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
 
        self.setLayout(layout)

    def changeEvent(self, event: QEvent):
        """Handles language change events to re-translate the UI."""
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        """Retranslates all the strings in the dialog."""
        self.setWindowTitle(self.tr("Help - FAQ"))

        # Re-create the model to apply new translations to its content
        self.model = self._create_faq_model()
        self.tree_view.setModel(self.model)

        # Re-expand all top-level items to maintain user experience
        for i in range(self.model.rowCount()):
            self.tree_view.expand(self.model.index(i, 0))

        logger.debug("HelpDialog retranslated.")

    def _get_help_data(self) -> dict[str, dict[str, str]]:
        """
        Returns the help data dictionary with all strings wrapped in self.tr()
        to ensure they are picked up by the translation system (lupdate).
        """
        return {
            self.tr("Navigation"): {
                1: {
                    "question": self.tr("How do I start a lesson?"),
                    "answer": self.tr("From the 'Course Navigation' panel on the left, simply click on the lesson you wish to begin.")
                },
                2: {
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
            }
        }

    def _create_faq_model(self):
        model = QStandardItemModel()
        root_item = model.invisibleRootItem()
 
        help_data = self._get_help_data() # Get the pre-translated data

        for category_name, questions in help_data.items():
            category_item = QStandardItem(category_name) # category_name is already translated
            category_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = category_item.font()
            font.setBold(True)
            category_item.setFont(font)
            root_item.appendRow(category_item)

            # Sort questions by their keys (e.g., 1, 2, 3, 4)
            # sorted_question_keys = sorted(questions.keys(), key=lambda x: int(x) if x.isdigit() else x) ; AttributeError: 'int' object has no attribute 'isdigit'

            if isinstance(list(questions.keys())[0], int): # Check if keys are integers
                sorted_question_keys = sorted(questions.keys())
            else:
                sorted_question_keys = sorted(questions.keys(), key=lambda x: int(x) if x.isdigit() else x)

            for q_key in sorted_question_keys:
                q_data = questions[q_key]
                question_text = q_data["question"] # Already translated
                answer_text = q_data["answer"] # Already translated

                question_item = QStandardItem(question_text)
                question_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                
                answer_item = QStandardItem(answer_text)
                answer_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                
                question_item.appendRow(answer_item)
                category_item.appendRow(question_item)
                

        return model

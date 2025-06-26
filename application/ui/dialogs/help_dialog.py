import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTreeView,
    QDialogButtonBox,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt

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

        self.model = self._create_faq_model()
        self.tree_view.setModel(self.model)
        
        # Expand all top-level items (categories) by default
        for i in range(self.model.rowCount()):
            self.tree_view.expand(self.model.index(i, 0))

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def _create_faq_model(self):
        model = QStandardItemModel()
        root_item = model.invisibleRootItem()

        # --- Navigation Category ---
        nav_category = QStandardItem(self.tr("Navigation"))
        nav_category.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = nav_category.font()
        font.setBold(True)
        nav_category.setFont(font)
        root_item.appendRow(nav_category)

        # Q1
        q1 = QStandardItem(self.tr("How do I start a lesson?"))
        q1.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        a1 = QStandardItem(self.tr("From the 'Course Navigation' panel on the left, simply click on the lesson you wish to begin."))
        a1.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        q1.appendRow(a1)
        nav_category.appendRow(q1)

        # Q2
        q2 = QStandardItem(self.tr("How do I return to the course selection screen?"))
        q2.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        a2 = QStandardItem(self.tr("Use the 'File' menu and select 'Return to Course Selection'."))
        a2.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        q2.appendRow(a2)
        nav_category.appendRow(q2)

        # --- Whisper Model Category ---
        whisper_category = QStandardItem(self.tr("Whisper Model"))
        whisper_category.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = whisper_category.font()
        font.setBold(True)
        whisper_category.setFont(font)
        root_item.appendRow(whisper_category)

        # Q3
        q3 = QStandardItem(self.tr("What is the Whisper model used for?"))
        q3.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        a3 = QStandardItem(self.tr("The Whisper model is used for speech-to-text transcription. It analyzes your pronunciation exercises and provides feedback."))
        a3.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        q3.appendRow(a3)
        whisper_category.appendRow(q3)

        # Q4
        q4 = QStandardItem(self.tr("How can I change the Whisper model?"))
        q4.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        a4 = QStandardItem(self.tr("You can select a different Whisper model from the 'Settings' dialog. Larger models are more accurate but require more resources."))
        a4.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        q4.appendRow(a4)
        whisper_category.appendRow(q4)

        return model

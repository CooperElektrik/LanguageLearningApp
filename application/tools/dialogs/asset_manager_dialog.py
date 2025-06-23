# application/tools/dialogs/asset_manager_dialog.py

import os
import logging
import shutil
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QWidget,
    QGridLayout,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QMimeData, QByteArray, QSize, Signal
from PySide6.QtGui import QPixmap, QIcon
from typing import Optional

logger = logging.getLogger(__name__)

# Define a custom MIME type for dragging asset paths
_ASSET_PATH_MIME_TYPE = "application/x-ll-asset-path"


class AssetManagerDialog(QDialog):
    # Signal to emit the selected asset's relative path
    asset_selected = Signal(str)

    def __init__(self, course_root_dir: str, asset_type: str, parent=None):
        """
        Initializes the AssetManagerDialog.

        Args:
            course_root_dir (str): The root directory of the course (where manifest.yaml is).
            asset_type (str): 'audio' or 'image', to filter assets.
            parent (QWidget): The parent widget.
        """
        super().__init__(parent)
        self.course_root_dir = os.path.abspath(course_root_dir)
        self.asset_type = asset_type
        self.asset_subdir = os.path.join("assets", f"{self.asset_type}s")
        self.full_asset_dir = os.path.join(self.course_root_dir, self.asset_subdir)
        self.selected_asset_path: Optional[str] = None  # Stores the relative path

        self.setWindowTitle(f"Manage {asset_type.capitalize()} Assets")
        self.setMinimumSize(700, 500)

        self._setup_ui()
        self._populate_asset_list()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Top section: Asset directory info
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(f"Assets stored in: {self.asset_subdir}/"))
        info_layout.addStretch(1)
        main_layout.addLayout(info_layout)

        # Asset list view
        self.asset_list_widget = QListWidget()
        self.asset_list_widget.setViewMode(QListWidget.IconMode)
        self.asset_list_widget.setGridSize(QSize(120, 120))
        self.asset_list_widget.setIconSize(QSize(64, 64))
        self.asset_list_widget.setMovement(
            QListWidget.Static
        )  # Items won't move around visually
        self.asset_list_widget.setSpacing(10)
        self.asset_list_widget.setWordWrap(True)
        self.asset_list_widget.setSelectionMode(QListWidget.SingleSelection)

        self.asset_list_widget.itemDoubleClicked.connect(
            self._handle_double_click_select
        )

        main_layout.addWidget(self.asset_list_widget)

        # Action buttons for managing assets
        button_layout = QHBoxLayout()
        self.import_button = QPushButton(f"Import {self.asset_type.capitalize()}...")
        self.import_button.clicked.connect(self._import_asset)
        button_layout.addWidget(self.import_button)

        self.delete_button = QPushButton(f"Delete {self.asset_type.capitalize()}")
        self.delete_button.clicked.connect(self._delete_selected_asset)
        button_layout.addWidget(self.delete_button)

        button_layout.addStretch(1)

        self.select_button = QPushButton("Select Asset")
        self.select_button.clicked.connect(self._handle_select_asset)
        button_layout.addWidget(self.select_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)

    def _populate_asset_list(self):
        self.asset_list_widget.clear()
        if not os.path.exists(self.full_asset_dir):
            try:
                os.makedirs(self.full_asset_dir, exist_ok=True)
                logger.info(f"Created asset directory: {self.full_asset_dir}")
            except OSError as e:
                QMessageBox.critical(
                    self, "Directory Error", f"Could not create asset directory: {e}"
                )
                return

        for filename in os.listdir(self.full_asset_dir):
            if filename.startswith("."):  # Ignore hidden files like .DS_Store
                continue

            full_path = os.path.join(self.full_asset_dir, filename)
            relative_path = os.path.join(self.asset_subdir, filename).replace(
                os.sep, "/"
            )

            item = QListWidgetItem(filename)
            item.setData(Qt.UserRole, relative_path)  # Store relative path in UserRole

            icon = QIcon()
            if self.asset_type == "image":
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    icon.addPixmap(pixmap)
                else:
                    icon = self.style().standardIcon(
                        self.style().StandardPixmap.SP_MessageBoxWarning
                    )  # Fallback icon
            elif self.asset_type == "audio":
                icon = self.style().standardIcon(
                    self.style().StandardPixmap.SP_MediaVolume
                )  # Generic audio icon

            item.setIcon(icon)
            self.asset_list_widget.addItem(item)

        self.asset_list_widget.sortItems(Qt.AscendingOrder)  # Sort alphabetically

    def _import_asset(self):
        # Determine initial directory for file dialog
        initial_dir = self.course_root_dir
        if not os.path.exists(initial_dir):
            initial_dir = os.path.expanduser("~")  # Fallback to home directory

        filters = ""
        if self.asset_type == "image":
            filters = "Image Files (*.png *.jpg *.jpeg *.gif);;All Files (*)"
        elif self.asset_type == "audio":
            filters = "Audio Files (*.mp3 *.wav *.ogg);;All Files (*)"

        source_file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {self.asset_type.capitalize()} File to Import",
            initial_dir,
            filters,
        )
        if not source_file_path:
            return

        target_file_name = os.path.basename(source_file_path)
        target_full_path = os.path.join(self.full_asset_dir, target_file_name)

        if os.path.exists(target_full_path):
            reply = QMessageBox.question(
                self,
                "File Exists",
                f"A file named '{target_file_name}' already exists in the assets folder. Overwrite?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.No:
                return

        try:
            shutil.copy2(source_file_path, target_full_path)
            logger.info(f"Imported asset '{source_file_path}' to '{target_full_path}'")
            self._populate_asset_list()  # Refresh list after import
            QMessageBox.information(
                self,
                "Import Successful",
                f"'{target_file_name}' imported successfully.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import asset: {e}")

    def _delete_selected_asset(self):
        selected_items = self.asset_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self, "No Selection", "Please select an asset to delete."
            )
            return

        item_to_delete = selected_items[0]
        relative_path = item_to_delete.data(Qt.UserRole)
        filename = os.path.basename(relative_path)
        full_path = os.path.join(self.full_asset_dir, filename)

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{filename}'?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.No:
            return

        try:
            os.remove(full_path)
            logger.info(f"Deleted asset: {full_path}")
            self._populate_asset_list()  # Refresh list after deletion
            QMessageBox.information(
                self, "Delete Successful", f"'{filename}' deleted successfully."
            )
        except Exception as e:
            QMessageBox.critical(self, "Delete Error", f"Failed to delete asset: {e}")

    def _handle_double_click_select(self, item: QListWidgetItem):
        """Handle double-click to select and close dialog."""
        self.selected_asset_path = item.data(Qt.UserRole)
        self.asset_selected.emit(self.selected_asset_path)
        self.accept()

    def _handle_select_asset(self):
        """Handle 'Select Asset' button click."""
        selected_items = self.asset_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self, "No Selection", "Please select an asset to select."
            )
            return

        self.selected_asset_path = selected_items[0].data(Qt.UserRole)
        self.asset_selected.emit(self.selected_asset_path)
        self.accept()

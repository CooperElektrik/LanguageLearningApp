# application/tools/widgets/asset_hub_widget.py

import logging
import os
import shutil

from PySide6.QtCore import QByteArray, QMimeData, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDrag, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .asset_drop_line_edit import ASSET_PATH_MIME_TYPE

logger = logging.getLogger(__name__)


class DraggableAssetListWidget(QListWidget):
    """QListWidget supporting drag of asset items with custom and file-url MIME data."""

    def __init__(self, asset_type: str, parent=None):
        super().__init__(parent)
        self.asset_type = asset_type
        self.setDragEnabled(True)
        self.setViewMode(QListWidget.IconMode)
        self.setGridSize(QSize(90, 80))
        self.setIconSize(QSize(40, 40))
        self.setMovement(QListWidget.Static)
        self.setSpacing(6)
        self.setWordWrap(True)
        self.setSelectionMode(QListWidget.SingleSelection)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return

        rel_path = item.data(Qt.UserRole)
        full_path = item.data(Qt.UserRole + 1)
        if not rel_path:
            return

        mime_data = QMimeData()
        mime_data.setData(ASSET_PATH_MIME_TYPE, QByteArray(rel_path.encode("utf-8")))
        mime_data.setText(rel_path)
        if full_path and os.path.exists(full_path):
            mime_data.setUrls([QUrl.fromLocalFile(full_path)])

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        if not item.icon().isNull():
            drag.setPixmap(item.icon().pixmap(32, 32))

        drag.exec(Qt.CopyAction | Qt.MoveAction)


class AssetHubWidget(QWidget):
    """
    Integrated Asset Hub for browsing, importing, and dragging
    course audio and image assets directly into forms.
    """

    asset_selected = Signal(str)

    def __init__(self, course_root_dir: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("AssetHub")
        self.course_root_dir = os.path.abspath(course_root_dir) if course_root_dir else None

        self._setup_ui()
        if self.course_root_dir:
            self.refresh_assets()

    def set_course_root_dir(self, course_root_dir: str | None):
        self.course_root_dir = os.path.abspath(course_root_dir) if course_root_dir else None
        self.refresh_assets()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        title_label = QLabel("<b>Integrated Asset Hub</b>")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        self.refresh_button = QPushButton("↻")
        self.refresh_button.setToolTip("Refresh Assets")
        self.refresh_button.setFixedWidth(30)
        self.refresh_button.clicked.connect(self.refresh_assets)
        header_layout.addWidget(self.refresh_button)

        main_layout.addLayout(header_layout)

        # Filter bar
        self.search_filter = QLineEdit()
        self.search_filter.setPlaceholderText("Filter assets...")
        self.search_filter.textChanged.connect(self._apply_filter)
        main_layout.addWidget(self.search_filter)

        # Tabs for Audio and Images
        self.tabs = QTabWidget()

        self.audio_list = DraggableAssetListWidget("audio")
        self.audio_list.itemDoubleClicked.connect(self._handle_double_click)
        self.tabs.addTab(self.audio_list, "Audio")

        self.image_list = DraggableAssetListWidget("image")
        self.image_list.itemDoubleClicked.connect(self._handle_double_click)
        self.tabs.addTab(self.image_list, "Images")

        main_layout.addWidget(self.tabs, 1)

        # Action buttons
        actions_layout = QHBoxLayout()
        self.import_button = QPushButton("+ Import...")
        self.import_button.setToolTip("Import asset file into course")
        self.import_button.clicked.connect(self._import_current_type_asset)
        actions_layout.addWidget(self.import_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._delete_selected_asset)
        actions_layout.addWidget(self.delete_button)

        main_layout.addLayout(actions_layout)

    def refresh_assets(self):
        self._populate_list(self.audio_list, "audio")
        self._populate_list(self.image_list, "image")
        self._apply_filter(self.search_filter.text())

    def _populate_list(self, list_widget: DraggableAssetListWidget, asset_type: str):
        list_widget.clear()
        if not self.course_root_dir:
            return

        target_dir = os.path.join(self.course_root_dir, "assets", f"{asset_type}s")
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir, exist_ok=True)
            except OSError:
                return

        for filename in sorted(os.listdir(target_dir)):
            if filename.startswith("."):
                continue

            full_path = os.path.join(target_dir, filename)
            rel_path = os.path.join("assets", f"{asset_type}s", filename).replace("\\", "/")

            item = QListWidgetItem(filename)
            item.setData(Qt.UserRole, rel_path)
            item.setData(Qt.UserRole + 1, full_path)

            icon = QIcon()
            if asset_type == "image":
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    icon.addPixmap(pixmap)
                else:
                    icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
            else:
                icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)

            item.setIcon(icon)
            item.setToolTip(f"{filename}\nDrag onto exercise field")
            list_widget.addItem(item)

    def _apply_filter(self, text: str):
        search = text.strip().lower()
        for list_widget in (self.audio_list, self.image_list):
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                item.setHidden(bool(search and search not in item.text().lower()))

    def _import_current_type_asset(self):
        if not self.course_root_dir:
            QMessageBox.warning(self, "Asset Import", "Please open or save a course first.")
            return

        is_audio = self.tabs.currentIndex() == 0
        asset_type = "audio" if is_audio else "image"
        filters = (
            "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a);;All Files (*)"
            if is_audio
            else "Image Files (*.png *.jpg *.jpeg *.gif *.webp *.svg);;All Files (*)"
        )

        source_file, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {asset_type.capitalize()} to Import",
            self.course_root_dir,
            filters,
        )
        if not source_file:
            return

        target_dir = os.path.join(self.course_root_dir, "assets", f"{asset_type}s")
        os.makedirs(target_dir, exist_ok=True)
        dest_filename = os.path.basename(source_file)
        dest_full = os.path.join(target_dir, dest_filename)

        if os.path.exists(dest_full):
            ans = QMessageBox.question(
                self,
                "File Exists",
                f"Asset '{dest_filename}' already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return

        try:
            shutil.copy2(source_file, dest_full)
            self.refresh_assets()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import: {e}")

    def _delete_selected_asset(self):
        current_list = self.audio_list if self.tabs.currentIndex() == 0 else self.image_list
        item = current_list.currentItem()
        if not item:
            return

        full_path = item.data(Qt.UserRole + 1)
        if not full_path or not os.path.exists(full_path):
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete '{os.path.basename(full_path)}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                os.remove(full_path)
                self.refresh_assets()
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete: {e}")

    def _handle_double_click(self, item: QListWidgetItem):
        rel_path = item.data(Qt.UserRole)
        if rel_path:
            self.asset_selected.emit(rel_path)

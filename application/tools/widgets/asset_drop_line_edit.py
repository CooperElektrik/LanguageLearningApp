# application/tools/widgets/asset_drop_line_edit.py

import logging
import os
import shutil
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLineEdit, QMessageBox

logger = logging.getLogger(__name__)

ASSET_PATH_MIME_TYPE = "application/x-ll-asset-path"


class AssetDropLineEdit(QLineEdit):
    """
    A QLineEdit that accepts drag-and-drop of audio/image assets
    either from the internal Asset Hub or from the external OS file manager.
    Also supports dynamic property-based error validation without inline styles.
    """

    asset_dropped = Signal(str)

    def __init__(
        self,
        current_value: str = "",
        asset_type: str = "audio",
        course_root_dir: str | None = None,
        parent=None,
    ):
        super().__init__(current_value or "", parent)
        self.asset_type = asset_type  # 'audio' or 'image'
        self.course_root_dir = course_root_dir
        self.setAcceptDrops(True)
        self.setPlaceholderText(f"e.g., assets/{self.asset_type}s/filename or drop here")

    def set_course_root_dir(self, course_root_dir: str | None):
        self.course_root_dir = course_root_dir

    def mark_validity(self, is_valid: bool):
        """Sets Qt dynamic property 'hasError' without modifying styleSheet directly."""
        self.setProperty("hasError", not is_valid)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasFormat(ASSET_PATH_MIME_TYPE):
            event.acceptProposedAction()
            return
        if mime_data.hasUrls() and len(mime_data.urls()) > 0:
            file_path = mime_data.urls()[0].toLocalFile()
            if self._is_supported_file(file_path):
                event.acceptProposedAction()
                return
        if mime_data.hasText():
            text = mime_data.text().strip()
            if text.startswith("assets/") or self._is_supported_file(text):
                event.acceptProposedAction()
                return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(ASSET_PATH_MIME_TYPE) or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasFormat(ASSET_PATH_MIME_TYPE):
            rel_path = mime_data.data(ASSET_PATH_MIME_TYPE).data().decode("utf-8")
            self.setText(rel_path)
            self.asset_dropped.emit(rel_path)
            event.acceptProposedAction()
            return

        if mime_data.hasUrls() and len(mime_data.urls()) > 0:
            local_path = mime_data.urls()[0].toLocalFile()
            rel_path = self._import_external_file(local_path)
            if rel_path:
                self.setText(rel_path)
                self.asset_dropped.emit(rel_path)
                event.acceptProposedAction()
                return

        if mime_data.hasText():
            text = mime_data.text().strip()
            if text.startswith("file://"):
                text = text.replace("file://", "")
            if os.path.exists(text):
                rel_path = self._import_external_file(text)
                if rel_path:
                    self.setText(rel_path)
                    self.asset_dropped.emit(rel_path)
                    event.acceptProposedAction()
                    return
            else:
                self.setText(text)
                self.asset_dropped.emit(text)
                event.acceptProposedAction()
                return

        super().dropEvent(event)

    def _is_supported_file(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        if self.asset_type == "audio":
            return ext in [".mp3", ".wav", ".ogg", ".flac", ".m4a"]
        elif self.asset_type == "image":
            return ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]
        return False

    def _import_external_file(self, full_file_path: str) -> str | None:
        if not os.path.isfile(full_file_path):
            return None

        if not self.course_root_dir:
            # If no course directory saved yet, just use basename in standard folder
            return os.path.join("assets", f"{self.asset_type}s", os.path.basename(full_file_path)).replace("\\", "/")

        dest_dir = os.path.join(self.course_root_dir, "assets", f"{self.asset_type}s")
        os.makedirs(dest_dir, exist_ok=True)
        dest_filename = os.path.basename(full_file_path)
        dest_full_path = os.path.join(dest_dir, dest_filename)

        if not os.path.exists(dest_full_path) or os.path.abspath(full_file_path) != os.path.abspath(dest_full_path):
            try:
                shutil.copy2(full_file_path, dest_full_path)
                logger.info(f"Copied dropped asset '{full_file_path}' to '{dest_full_path}'")
            except Exception as e:
                logger.error(f"Failed to copy dropped asset: {e}")
                QMessageBox.warning(self, "Asset Copy Error", f"Could not copy asset to course folder: {e}")
                return None

        rel_path = os.path.join("assets", f"{self.asset_type}s", dest_filename).replace("\\", "/")
        return rel_path

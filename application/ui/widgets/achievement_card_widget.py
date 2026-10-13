# application/ui/widgets/achievement_card_widget.py

import logging
import os

import utils
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QStyle,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class AchievementCardWidget(QFrame):
    """
    Standalone card component for displaying an achievement badge,
    title, description, and locked/unlocked visual state.
    """

    def __init__(
        self,
        title: str = "",
        description: str = "",
        is_unlocked: bool = False,
        icon_filename: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("achievement_frame")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        self._title = title
        self._description = description
        self._is_unlocked = is_unlocked
        self._icon_filename = icon_filename

        self._setup_ui()
        self.update_content(title, description, is_unlocked, icon_filename)

    def set_unlocked(self, is_unlocked: bool):
        """Updates the unlocked state of this card."""
        self.update_content(self._title, self._description, is_unlocked, self._icon_filename)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("achievement_icon_label")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setScaledContents(True)
        self.layout.addWidget(
            self.icon_label,
            stretch=1,
            alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter),
        )

        self.title_label = QLabel()
        self.title_label.setObjectName("achievement_title_label")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(
            self.title_label, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter
        )

        self.desc_label = QLabel()
        self.desc_label.setObjectName("achievement_description_label")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setWordWrap(True)
        self.layout.addWidget(
            self.desc_label, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter
        )

    def update_content(
        self,
        title: str,
        description: str,
        is_unlocked: bool,
        icon_filename: str,
    ):
        self._title = title
        self._description = description
        self._is_unlocked = is_unlocked
        self._icon_filename = icon_filename

        self.setProperty("unlocked", is_unlocked)
        self.title_label.setText(title)
        self.desc_label.setText(description)

        self._load_icon(icon_filename, is_unlocked)

        # Refresh styling for dynamic property
        self.style().unpolish(self)
        self.style().polish(self)

    def _load_icon(self, icon_filename: str, is_unlocked: bool):
        icon_relative_path = os.path.join("assets", "icons", icon_filename)
        icon_path = utils.get_resource_path(icon_relative_path)

        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            pixmap = (
                self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton).pixmap(64, 64)
            )
            logger.warning(f"Achievement icon not found: {icon_path}. Using default icon.")

        if not is_unlocked:
            grayscale_pixmap = QPixmap(pixmap.size())
            grayscale_pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(grayscale_pixmap)
            painter.setOpacity(0.3)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            pixmap = grayscale_pixmap

        self.icon_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio))

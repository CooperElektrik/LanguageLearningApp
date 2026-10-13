# application/ui/widgets/option_card_widget.py

import logging
import os

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from application.core.models import ExerciseOption

logger = logging.getLogger(__name__)

ICON_SIZE = QSize(160, 90)


def create_rounded_card_pixmap(
    original_pixmap: QPixmap, target_size: QSize, corner_radius: int = 10
) -> QPixmap:
    """Scales and rounds the corners of a thumbnail pixmap."""
    aspect_ratio = 16 / 9
    target_width = target_size.width()
    target_height = int(target_width / aspect_ratio)
    final_size = QSize(target_width, target_height)

    scaled = original_pixmap.scaled(
        final_size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    rounded = QPixmap(final_size)
    rounded.fill(Qt.GlobalColor.transparent)

    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, final_size.width(), final_size.height(), corner_radius, corner_radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return rounded


class OptionCardWidget(QFrame):
    """
    Standalone selectable card component for multiple-choice and option exercises.
    Replaces QPushButton hacks with proper focus, checkable states, and responsive layout.
    """

    clicked = Signal()
    toggled = Signal(bool)

    def __init__(
        self,
        index: int,
        text: str = "",
        image_path: str | None = None,
        is_checkable: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.index = index
        self._text = text
        self._image_path = image_path
        self._is_checkable = is_checkable
        self._is_checked = False

        self.setObjectName(f"option_button_{index}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(80)

        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        self.card_layout = QHBoxLayout(self)
        self.card_layout.setContentsMargins(12, 8, 12, 8)
        self.card_layout.setSpacing(12)

        # Image thumbnail (if provided)
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self._image_path and os.path.exists(self._image_path):
            pixmap = QPixmap(self._image_path)
            if not pixmap.isNull():
                rounded = create_rounded_card_pixmap(pixmap, ICON_SIZE)
                self.icon_label.setPixmap(rounded)
                self.card_layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignLeft)

                # Separator
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setFrameShadow(QFrame.Shadow.Sunken)
                self.card_layout.addWidget(sep)

        # Option text
        self.text_label = QLabel(self._text)
        self.text_label.setObjectName("option_card_text")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setWordWrap(True)
        self.card_layout.addWidget(self.text_label, 1)

    def isChecked(self) -> bool:
        return self._is_checked

    def setChecked(self, checked: bool):
        if self._is_checked != checked:
            self._is_checked = checked
            self._update_style()
            self.toggled.emit(checked)

    def _update_style(self):
        self.setProperty("checked", self._is_checked)
        self.setProperty("selected", self._is_checked)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            if self._is_checkable:
                self.setChecked(not self._is_checked)
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def text(self) -> str:
        return self._text

    def click(self):
        if self._is_checkable:
            self.setChecked(not self._is_checked)
        self.clicked.emit()


class OptionGroupWidget(QWidget):
    """
    Responsive group manager for OptionCardWidgets.
    Arranges options in a responsive grid, enforces exclusivity,
    and supports numeric keyboard shortcuts (1-9).
    """

    option_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("OptionGroupWidget")
        self._cards: list[OptionCardWidget] = []
        self._selected_index: int = -1

        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(10)

    def buttons(self) -> list[OptionCardWidget]:
        return self._cards

    def set_options(
        self, options: list[ExerciseOption], assets_base_dir: str | None = None
    ):
        self.clear()
        if not options:
            no_opts = QLabel(self.tr("No options available for this exercise."))
            self.grid_layout.addWidget(no_opts, 0, 0)
            return

        has_images = any(bool(opt.image_file) for opt in options)
        num_cols = 2 if (has_images or len(options) >= 4) else 1

        for i, opt in enumerate(options):
            img_path = None
            if opt.image_file and assets_base_dir:
                candidate = os.path.join(assets_base_dir, opt.image_file)
                if os.path.exists(candidate):
                    img_path = candidate

            card = OptionCardWidget(
                index=i,
                text=opt.text or "",
                image_path=img_path,
                is_checkable=True,
                parent=self,
            )
            card.clicked.connect(lambda idx=i: self._handle_card_clicked(idx))
            self._cards.append(card)

            row, col = divmod(i, num_cols)
            self.grid_layout.addWidget(card, row, col)

    def _handle_card_clicked(self, index: int):
        self.select_index(index)
        self.option_selected.emit(index)

    def select_index(self, index: int):
        self._selected_index = index
        for card in self._cards:
            card.setChecked(card.index == index)

    def get_selected_index(self) -> int:
        return self._selected_index

    def clear_selection(self):
        self._selected_index = -1
        for card in self._cards:
            card.setChecked(False)

    def clear(self):
        self._selected_index = -1
        for card in self._cards:
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def set_focus_on_first(self):
        if self._cards:
            self._cards[0].setFocus()

    def handle_number_key(self, key: int) -> bool:
        """Selects the card matching number keys 1-9."""
        key_map = {
            Qt.Key.Key_1: 0,
            Qt.Key.Key_2: 1,
            Qt.Key.Key_3: 2,
            Qt.Key.Key_4: 3,
            Qt.Key.Key_5: 4,
            Qt.Key.Key_6: 5,
            Qt.Key.Key_7: 6,
            Qt.Key.Key_8: 7,
            Qt.Key.Key_9: 8,
        }
        if key in key_map:
            idx = key_map[key]
            if 0 <= idx < len(self._cards):
                self._handle_card_clicked(idx)
                return True
        return False

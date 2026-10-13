# application/tools/widgets/unit_editor_widget.py

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from application.core.models import Unit
from application.tools.widgets.exercise_editor_widgets import mark_widget_validity

logger = logging.getLogger(__name__)


class UnitEditorWidget(QWidget):
    """
    Inspector form editor for Unit properties using standardized QFormLayout.
    """

    data_changed = Signal()
    title_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UnitEditorWidget")
        self.current_unit: Unit | None = None

        self._setup_ui()

    def _setup_ui(self):
        self.form_layout = QFormLayout(self)
        self.form_layout.setContentsMargins(16, 16, 16, 16)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.setHorizontalSpacing(12)
        self.form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Unit ID
        self.unit_id_edit = QLineEdit()
        self.unit_id_edit.setReadOnly(True)
        id_label = QLabel("Unit ID:")
        self.form_layout.addRow(id_label, self.unit_id_edit)

        # Unit Title
        self.unit_title_edit = QLineEdit()
        self.unit_title_edit.setProperty("field_name", "title")
        self.unit_title_edit.textChanged.connect(self._handle_title_changed)
        title_label = QLabel("Title: *")
        self.form_layout.addRow(title_label, self.unit_title_edit)

    def load_unit(self, unit: Unit):
        self.current_unit = unit
        self.unit_id_edit.setText(unit.unit_id or "")

        self.unit_title_edit.blockSignals(True)
        self.unit_title_edit.setText(unit.title or "")
        self.unit_title_edit.blockSignals(False)

        self._validate_title()

    def _handle_title_changed(self, new_title: str):
        if self.current_unit:
            self.current_unit.title = new_title.strip()
        self._validate_title()
        self.data_changed.emit()
        self.title_changed.emit(new_title.strip())

    def _validate_title(self):
        is_valid = bool(self.unit_title_edit.text().strip())
        mark_widget_validity(self.unit_title_edit, is_valid)

    def focus_field(self, field_name: str | None = None) -> bool:
        """Cleanly routes focus to the specified field."""
        if not field_name or field_name in ["title", "unit_title"]:
            self.unit_title_edit.setFocus()
            mark_widget_validity(self.unit_title_edit, False)
            return True
        elif field_name in ["unit_id", "id"]:
            self.unit_id_edit.setFocus()
            return True
        return False

    def revert(self):
        """Restores inputs back to the committed model values."""
        if self.current_unit:
            self.load_unit(self.current_unit)

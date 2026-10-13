# application/tools/widgets/lesson_editor_widget.py

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from application.core.models import Lesson
from application.tools.widgets.exercise_editor_widgets import mark_widget_validity

logger = logging.getLogger(__name__)


class LessonEditorWidget(QWidget):
    """
    Inspector form editor for Lesson properties using standardized QFormLayout.
    """

    data_changed = Signal()
    title_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LessonEditorWidget")
        self.current_lesson: Lesson | None = None

        self._setup_ui()

    def _setup_ui(self):
        self.form_layout = QFormLayout(self)
        self.form_layout.setContentsMargins(16, 16, 16, 16)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.setHorizontalSpacing(12)
        self.form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Lesson ID
        self.lesson_id_edit = QLineEdit()
        self.lesson_id_edit.setReadOnly(True)
        id_label = QLabel("Lesson ID:")
        self.form_layout.addRow(id_label, self.lesson_id_edit)

        # Lesson Title
        self.lesson_title_edit = QLineEdit()
        self.lesson_title_edit.setProperty("field_name", "title")
        self.lesson_title_edit.textChanged.connect(self._handle_title_changed)
        title_label = QLabel("Title: *")
        self.form_layout.addRow(title_label, self.lesson_title_edit)

        # Parent Unit ID hint
        self.parent_unit_id_edit = QLineEdit()
        self.parent_unit_id_edit.setReadOnly(True)
        unit_label = QLabel("Parent Unit ID:")
        self.form_layout.addRow(unit_label, self.parent_unit_id_edit)

    def load_lesson(self, lesson: Lesson):
        self.current_lesson = lesson
        self.lesson_id_edit.setText(lesson.lesson_id or "")
        self.parent_unit_id_edit.setText(lesson.unit_id or "")

        self.lesson_title_edit.blockSignals(True)
        self.lesson_title_edit.setText(lesson.title or "")
        self.lesson_title_edit.blockSignals(False)

        self._validate_title()

    def _handle_title_changed(self, new_title: str):
        if self.current_lesson:
            self.current_lesson.title = new_title.strip()
        self._validate_title()
        self.data_changed.emit()
        self.title_changed.emit(new_title.strip())

    def _validate_title(self):
        is_valid = bool(self.lesson_title_edit.text().strip())
        mark_widget_validity(self.lesson_title_edit, is_valid)

    def focus_field(self, field_name: str | None = None) -> bool:
        """Cleanly routes focus to the specified field."""
        if not field_name or field_name in ["title", "lesson_title"]:
            self.lesson_title_edit.setFocus()
            mark_widget_validity(self.lesson_title_edit, False)
            return True
        elif field_name in ["lesson_id", "id"]:
            self.lesson_id_edit.setFocus()
            return True
        elif field_name in ["unit_id", "parent_unit_id"]:
            self.parent_unit_id_edit.setFocus()
            return True
        return False

    def revert(self):
        """Restores inputs back to the committed model values."""
        if self.current_lesson:
            self.load_lesson(self.current_lesson)

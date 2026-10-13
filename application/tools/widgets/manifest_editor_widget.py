import logging
import os
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QWidget,
)

from .exercise_editor_widgets import mark_widget_validity

try:
    from application.core.models import Course
except ImportError:
    logging.warning("Could not import Course model in ManifestEditorWidget.")

    class Course:
        pass


logger = logging.getLogger(__name__)


class ManifestEditorWidget(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_manifest_data: dict = None
        self.current_course_obj: Course = None
        self.current_course_dir: str = None

        self.form_layout = QFormLayout(self)
        self.form_layout.setContentsMargins(16, 16, 16, 16)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.setHorizontalSpacing(12)
        self.form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        def add_required_row(label_text: str, input_widget: QWidget, field_name: str):
            label = QLabel(label_text + " *")
            self.form_layout.addRow(label, input_widget)
            input_widget.setProperty("field_name", field_name)
            if isinstance(input_widget, QLineEdit):
                input_widget.textChanged.connect(lambda text: self._validate_field(input_widget))
            return input_widget

        self.course_id_input = QLineEdit()
        self.course_id_input.setReadOnly(True)
        self.form_layout.addRow("Course ID:", self.course_id_input)

        self.course_title_input = QLineEdit()
        self.course_title_input.textChanged.connect(lambda: self.data_changed.emit())
        add_required_row("Course Title:", self.course_title_input, "course_title")

        self.target_lang_input = QLineEdit()
        self.target_lang_input.textChanged.connect(lambda: self.data_changed.emit())
        add_required_row("Target Language:", self.target_lang_input, "target_language")

        self.source_lang_input = QLineEdit()
        self.source_lang_input.textChanged.connect(lambda: self.data_changed.emit())
        add_required_row("Source Language:", self.source_lang_input, "source_language")

        self.content_file_input = QLineEdit()
        self.content_file_input.setReadOnly(True)
        self.form_layout.addRow("Content File:", self.content_file_input)

        self.version_input = QLineEdit()
        self.version_input.textChanged.connect(lambda: self.data_changed.emit())
        add_required_row("Version:", self.version_input, "version")

        self.author_input = QLineEdit()
        self.author_input.textChanged.connect(lambda: self.data_changed.emit())
        self.form_layout.addRow("Author:", self.author_input)

        self.description_input = QTextEdit()
        self.description_input.setAcceptRichText(False)
        self.description_input.setPlaceholderText("A full description of the course.")
        self.description_input.textChanged.connect(lambda: self.data_changed.emit())
        self.form_layout.addRow("Description:", self.description_input)

        image_file_layout = QHBoxLayout()
        self.image_file_input = QLineEdit()
        self.image_file_input.setPlaceholderText("e.g., cover.png")
        self.image_file_input.textChanged.connect(lambda: self.data_changed.emit())
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_for_image)
        image_file_layout.addWidget(self.image_file_input)
        image_file_layout.addWidget(browse_button)
        self.form_layout.addRow("Image File:", image_file_layout)

        self.use_shared_pool_checkbox = QCheckBox(
            "Use the shared asset pool (application/courses/pool)"
        )
        self.use_shared_pool_checkbox.stateChanged.connect(lambda: self.data_changed.emit())
        self.form_layout.addRow("Asset Pool:", self.use_shared_pool_checkbox)

        self.required_inputs = [
            self.course_title_input,
            self.target_lang_input,
            self.source_lang_input,
            self.version_input,
        ]

    def _browse_for_image(self):
        if not self.current_course_obj or not self.current_course_obj.course_id:
            QMessageBox.warning(
                self,
                "Cannot Browse Image",
                "Please save the course first to establish the course directory path.",
            )
            return

        course_dir = self.current_course_dir
        if not course_dir:
            QMessageBox.warning(
                self,
                "Path Error",
                "Could not determine the course directory. Please save the manifest first.",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Course Image",
            course_dir,  # Start browsing in the course directory
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )

        if file_path:
            relative_path = os.path.relpath(file_path, course_dir)
            self.image_file_input.setText(relative_path)
            self.data_changed.emit()

    def _validate_field(self, input_widget: QLineEdit):
        text = input_widget.text().strip()
        mark_widget_validity(input_widget, bool(text))

    def focus_field(self, field_name: str | None = None) -> bool:
        """Cleanly sets focus and highlights an invalid field."""
        field_map = {
            "course_id": self.course_id_input,
            "course_title": self.course_title_input,
            "title": self.course_title_input,
            "target_language": self.target_lang_input,
            "source_language": self.source_lang_input,
            "content_file": self.content_file_input,
            "version": self.version_input,
            "author": self.author_input,
            "description": self.description_input,
            "image_file": self.image_file_input,
        }
        target = field_map.get(field_name) if field_name else self.course_title_input
        if target:
            target.setFocus()
            mark_widget_validity(target, False)
            return True
        return False

    def revert(self):
        """Restores fields back to the committed manifest data."""
        if self.current_manifest_data is not None and self.current_course_obj is not None:
            self.load_data(self.current_manifest_data, self.current_course_obj, self.current_course_dir)

    def load_data(
        self,
        manifest_data: dict[str, Any],
        course_obj: Course,
        course_dir: str | None = None,
    ):
        """Loads manifest data and associated course object into the editor fields.

        ``course_dir`` is the directory holding the manifest; it is needed to
        resolve asset paths relative to the course root.
        """
        self.current_manifest_data = manifest_data
        self.current_course_obj = course_obj
        self.current_course_dir = course_dir

        self.course_id_input.setText(manifest_data.get("course_id", ""))
        self.course_title_input.setText(manifest_data.get("course_title", ""))
        self.target_lang_input.setText(manifest_data.get("target_language", ""))
        self.source_lang_input.setText(manifest_data.get("source_language", ""))
        self.content_file_input.setText(manifest_data.get("content_file", ""))
        self.version_input.setText(manifest_data.get("version", ""))
        self.author_input.setText(manifest_data.get("author", ""))
        self.description_input.setPlainText(manifest_data.get("description", ""))
        self.image_file_input.setText(manifest_data.get("image_file", ""))
        self.use_shared_pool_checkbox.setChecked(manifest_data.get("use_shared_pool", False))

        for widget in self.required_inputs:
            self._validate_field(widget)

    def apply_changes_to_data(self, manifest_data: dict[str, Any], course_obj: Course):
        """Applies current editor field values back to the manifest data and course object."""
        manifest_data["course_title"] = self.course_title_input.text()
        manifest_data["target_language"] = self.target_lang_input.text()
        manifest_data["source_language"] = self.source_lang_input.text()
        manifest_data["version"] = self.version_input.text()
        manifest_data["author"] = self.author_input.text()
        manifest_data["description"] = self.description_input.toPlainText()
        manifest_data["image_file"] = self.image_file_input.text()
        manifest_data["use_shared_pool"] = self.use_shared_pool_checkbox.isChecked()

        if course_obj:
            course_obj.title = self.course_title_input.text()
            course_obj.target_language = self.target_lang_input.text()
            course_obj.source_language = self.source_lang_input.text()
            course_obj.version = self.version_input.text()
            course_obj.author = self.author_input.text()
            course_obj.description = self.description_input.toPlainText()
            course_obj.image_file = self.image_file_input.text()

    def validate(self) -> tuple[bool, str]:
        """Validates the current data in the manifest editor fields."""
        for widget in self.required_inputs:
            if not widget.text().strip():
                field_name = widget.property("field_name")
                return False, f"{field_name.replace('_', ' ').title()} cannot be empty."

        return True, ""

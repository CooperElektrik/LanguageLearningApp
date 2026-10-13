# application/tools/widgets/options_list_editor_widget.py

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from application.core.models import ExerciseOption
except ImportError:
    class ExerciseOption:
        def __init__(self, text: str = "", correct: bool = False, image_file: str | None = None):
            self.text = text
            self.correct = correct
            self.image_file = image_file

logger = logging.getLogger(__name__)


class OptionItemEditDialog(QDialog):
    """Dialog for creating or editing an individual option."""

    def __init__(
        self,
        option_text: str = "",
        option_image_file: str = "",
        is_correct: bool = False,
        allow_image: bool = True,
        show_correct_checkbox: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Edit Option")
        self.allow_image = allow_image
        self.show_correct_checkbox = show_correct_checkbox

        layout = QVBoxLayout(self)

        self.text_edit = QLineEdit(option_text)
        self.image_file_edit = QLineEdit(option_image_file)
        self.correct_checkbox = QCheckBox("Is Correct Option")
        self.correct_checkbox.setChecked(is_correct)

        form_layout = QFormLayout()
        form_layout.addRow("Option Text:", self.text_edit)
        if self.allow_image:
            form_layout.addRow("Image File (Optional):", self.image_file_edit)
        if self.show_correct_checkbox:
            form_layout.addRow(self.correct_checkbox)
        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> tuple[str | None, str | None, bool]:
        text = self.text_edit.text().strip()
        image_file = self.image_file_edit.text().strip() if self.allow_image else ""
        if not text and not image_file:
            QMessageBox.warning(
                self,
                "Input Error",
                "Either option text or an image file must be provided.",
            )
            return None, None, False
        return text, image_file or None, self.correct_checkbox.isChecked()


class OptionsListEditorWidget(QWidget):
    """
    Reusable UI component for authoring and validating choice/option lists
    across multiple exercise types (Multiple Choice, Image Association,
    Fill-in-the-Blank, etc.).
    """

    options_changed = Signal()

    def __init__(
        self,
        heading: str = "Exercise Options",
        mode: str = "mcq",  # "mcq" (requires 1 correct) or "fib" (distractors + target)
        allow_images: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.heading_text = heading
        self.mode = mode
        self.allow_images = allow_images
        self.options: list[ExerciseOption] = []
        self._target_blank_word: str | None = None

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        self.heading_label = QLabel(self.heading_text)
        main_layout.addWidget(self.heading_label)

        self.options_list_widget = QListWidget()
        self.options_list_widget.itemDoubleClicked.connect(self._edit_selected_option)
        main_layout.addWidget(self.options_list_widget)

        buttons_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Option")
        self.add_button.clicked.connect(self._add_option_dialog)
        buttons_layout.addWidget(self.add_button)

        self.edit_button = QPushButton("Edit Selected")
        self.edit_button.clicked.connect(self._edit_selected_option)
        buttons_layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self._delete_selected_option)
        buttons_layout.addWidget(self.delete_button)

        buttons_layout.addStretch(1)
        main_layout.addLayout(buttons_layout)

        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("color: orange;")
        main_layout.addWidget(self.validation_label)

    def set_heading(self, heading: str):
        self.heading_text = heading
        self.heading_label.setText(heading)

    def load_options(self, options: list[ExerciseOption], target_blank: str | None = None):
        """Binds the options list and updates visual items."""
        self.options = options
        self._target_blank_word = target_blank
        self.refresh_display()

    def get_options(self) -> list[ExerciseOption]:
        """Returns the current list of ExerciseOption instances."""
        return self.options

    def set_target_blank_word(self, target: str | None):
        """Updates target blank word (for FIB mode) and revalidates."""
        self._target_blank_word = target.strip() if target and target.strip() else None
        if self.mode == "fib" and self._target_blank_word:
            found = any(opt.text == self._target_blank_word for opt in self.options)
            if not found:
                self.options.append(ExerciseOption(text=self._target_blank_word, correct=False))
                self.refresh_display()
                self.options_changed.emit()
                return
        self.validate()

    def refresh_display(self):
        self.options_list_widget.clear()
        for opt in self.options:
            item_text = opt.text or ""
            if opt.image_file and self.allow_images:
                item_text += f" [{opt.image_file}]"
            if self.mode == "mcq" and getattr(opt, "correct", False):
                item_text += " (Correct)"
            elif self.mode == "fib" and self._target_blank_word and opt.text == self._target_blank_word:
                item_text += " (Target Word)"

            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, opt)
            self.options_list_widget.addItem(list_item)
        self.validate()

    def validate(self) -> tuple[bool, str]:
        if not self.options:
            msg = "Warning: At least one option is recommended."
            self.validation_label.setText(msg)
            self.validation_label.setStyleSheet("color: orange;")
            return False, msg

        if self.mode == "mcq":
            correct_count = sum(1 for opt in self.options if getattr(opt, "correct", False))
            if correct_count == 0:
                msg = "Error: No option marked as correct. Please mark one."
                self.validation_label.setText(msg)
                self.validation_label.setStyleSheet("color: red;")
                return False, msg
            elif correct_count > 1:
                msg = f"Error: {correct_count} options marked correct. Please mark exactly one."
                self.validation_label.setText(msg)
                self.validation_label.setStyleSheet("color: red;")
                return False, msg

        elif self.mode == "fib":
            if self._target_blank_word:
                option_texts = [opt.text for opt in self.options]
                if self._target_blank_word not in option_texts:
                    msg = f"Error: Correct option '{self._target_blank_word}' not found in options list."
                    self.validation_label.setText(msg)
                    self.validation_label.setStyleSheet("color: red;")
                    return False, msg
            else:
                msg = "Error: Correct blank word is empty, but required."
                self.validation_label.setText(msg)
                self.validation_label.setStyleSheet("color: red;")
                return False, msg

        self.validation_label.setText("")
        self.validation_label.setStyleSheet("color: green;")
        return True, ""

    def _add_option_dialog(self):
        if self.mode == "fib":
            text, ok = QInputDialog.getText(self, "Add Option", "Enter option text:")
            if ok and text and text.strip():
                clean_text = text.strip()
                if not any(opt.text == clean_text for opt in self.options):
                    self.options.append(ExerciseOption(text=clean_text, correct=False))
                    self.refresh_display()
                    self.options_changed.emit()
            return

        dialog = OptionItemEditDialog(
            allow_image=self.allow_images,
            show_correct_checkbox=(self.mode == "mcq"),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            text, image_file, is_correct = dialog.get_data()
            if text is not None or image_file is not None:
                new_opt = ExerciseOption(text=text, image_file=image_file, correct=is_correct)
                if is_correct and self.mode == "mcq":
                    for opt in self.options:
                        opt.correct = False
                self.options.append(new_opt)
                self.refresh_display()
                self.options_changed.emit()

    def _edit_selected_option(self):
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Edit Option", "Please select an option to edit.")
            return
        opt: ExerciseOption = selected_items[0].data(Qt.UserRole)

        if self.mode == "fib":
            text, ok = QInputDialog.getText(self, "Edit Option", "Enter option text:", text=opt.text)
            if ok and text and text.strip():
                opt.text = text.strip()
                self.refresh_display()
                self.options_changed.emit()
            return

        dialog = OptionItemEditDialog(
            option_text=opt.text or "",
            option_image_file=opt.image_file or "",
            is_correct=getattr(opt, "correct", False),
            allow_image=self.allow_images,
            show_correct_checkbox=(self.mode == "mcq"),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            text, image_file, is_correct = dialog.get_data()
            if text is not None or image_file is not None:
                opt.text = text
                opt.image_file = image_file
                if is_correct and self.mode == "mcq":
                    for other in self.options:
                        if other is not opt:
                            other.correct = False
                    opt.correct = True
                else:
                    opt.correct = is_correct
                self.refresh_display()
                self.options_changed.emit()

    def _delete_selected_option(self):
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Delete Option", "Please select an option to delete.")
            return
        opt: ExerciseOption = selected_items[0].data(Qt.UserRole)
        reply = QMessageBox.question(
            self,
            "Delete Option",
            f"Are you sure you want to delete option: '{opt.text or opt.image_file}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.options.remove(opt)
            self.refresh_display()
            self.options_changed.emit()

import logging
import os
import shutil
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QScrollArea,
    QGroupBox,
    QCheckBox,
    QMessageBox,
    QFrame,
    QInputDialog,
    QTextEdit,
    QFormLayout,
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
)
from PySide6.QtCore import Signal, Qt, QMimeData
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent
from typing import Optional

try:
    from application.core.models import Exercise, ExerciseOption
    from ..dialogs.asset_manager_dialog import AssetManagerDialog, _ASSET_PATH_MIME_TYPE
except ImportError:
    logging.warning("Could not import Exercise model in ExerciseEditorWidgets.")

    class Exercise:
        pass

    class ExerciseOption:
        pass


logger = logging.getLogger(__name__)


class BaseExerciseEditorWidget(QWidget):
    data_changed = Signal()

    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        course_root_dir: Optional[str],
        parent=None,
    ):
        super().__init__(parent)
        self.exercise = exercise
        self.target_language = target_language
        self.source_language = source_language
        self.course_root_dir = course_root_dir

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        self.type_label = QLabel(
            f"Exercise Type: {exercise.type.replace('_', ' ').title()}"
        )
        self.type_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.layout.addWidget(self.type_label)
        self.layout.addWidget(self._create_separator())

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator

    def _add_input_field(
        self,
        label_text: str,
        current_value: str,
        callback_func,
        is_multiline: bool = False,
        is_required: bool = False,
        placeholder_text: Optional[str] = None,
    ):
        h_layout = QHBoxLayout()
        label_full_text = label_text + (" *" if is_required else "")
        label = QLabel(label_full_text)
        label.setMinimumWidth(120)
        h_layout.addWidget(label)

        if is_multiline:
            input_field = QTextEdit()
            input_field.setPlainText(current_value)
            input_field.textChanged.connect(
                lambda: callback_func(input_field.toPlainText())
            )
            input_field.setMinimumHeight(60)
        else:
            input_field = QLineEdit()
            input_field.setText(current_value)
            input_field.textChanged.connect(callback_func)

        if placeholder_text:
            input_field.setPlaceholderText(placeholder_text)

        input_field.textChanged.connect(
            lambda: self._validate_input_field(input_field, is_required)
        )

        h_layout.addWidget(input_field)
        self.layout.addLayout(h_layout)

        self._validate_input_field(input_field, is_required)
        return input_field

    def _validate_input_field(self, input_widget, is_required: bool):
        if not is_required:
            input_widget.setStyleSheet("")
            return

        text = ""
        if isinstance(input_widget, QLineEdit):
            text = input_widget.text().strip()
        elif isinstance(input_widget, QTextEdit):
            text = input_widget.toPlainText().strip()

        if not text:
            input_widget.setStyleSheet("border: 1px solid red;")
        else:
            input_widget.setStyleSheet("")
        self.data_changed.emit()

    def validate(self) -> tuple[bool, str]:
        """
        Validates the exercise data. Subclasses must override this.
        Returns (is_valid, error_message).
        """
        return True, ""


class TranslationExerciseEditorWidget(BaseExerciseEditorWidget):
    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        course_root_dir: Optional[str],
        parent=None,
    ):
        super().__init__(
            exercise, target_language, source_language, course_root_dir, parent
        )

        prompt_lang_hint = (
            self.source_language
            if exercise.type == "translate_to_target"
            else self.target_language
        )
        self.prompt_input = self._add_input_field(
            f"Prompt ({prompt_lang_hint})",
            exercise.prompt or "",
            self._update_prompt,
            is_required=True,
            placeholder_text="e.g., Hello",
        )

        answer_lang_hint = (
            self.target_language
            if exercise.type == "translate_to_target"
            else self.source_language
        )
        self.answer_input = self._add_input_field(
            f"Answer ({answer_lang_hint})",
            exercise.answer or "",
            self._update_answer,
            is_required=True,
            placeholder_text="e.g., Saluton",
        )

        audio_layout = QHBoxLayout()
        audio_label = QLabel("Audio File:")

        self.audio_file_input = QLineEdit(self.exercise.audio_file or "")
        self.audio_file_input.setPlaceholderText("e.g., assets/sounds/hello.mp3")
        self.audio_file_input.textChanged.connect(self._update_audio_file)
        self.audio_file_input.textChanged.connect(
            lambda: self._validate_input_field(self.audio_file_input, False)
        )

        browse_audio_button = QPushButton("Browse...")
        browse_audio_button.clicked.connect(lambda: self._browse_asset_file("audio"))

        audio_layout.addWidget(audio_label)
        audio_layout.addWidget(self.audio_file_input, 1)
        audio_layout.addWidget(browse_audio_button)
        self.layout.addLayout(audio_layout)

        image_layout = QHBoxLayout()
        image_label = QLabel("Image File:")
        self.image_file_input = QLineEdit(self.exercise.image_file or "")
        self.image_file_input.setPlaceholderText("e.g., assets/images/cat.png")
        self.image_file_input.textChanged.connect(self._update_image_file)
        self.image_file_input.textChanged.connect(
            lambda: self._validate_input_field(self.image_file_input, False)
        )

        browse_image_button = QPushButton("Browse...")
        browse_image_button.clicked.connect(lambda: self._browse_asset_file("image"))

        image_layout.addWidget(image_label)
        image_layout.addWidget(self.image_file_input, 1)
        image_layout.addWidget(browse_image_button)
        self.layout.addLayout(image_layout)

        self.layout.addStretch(1)

    def _update_prompt(self, text: str):
        self.exercise.prompt = text.strip() if text.strip() else None
        self.data_changed.emit()

    def _update_answer(self, text: str):
        self.exercise.answer = text.strip() if text.strip() else None
        self.data_changed.emit()

    def _update_audio_file(self, text: str):
        self.exercise.audio_file = (
            text.strip().replace("\\", "/") if text.strip() else None
        )
        self.data_changed.emit()

    def _browse_audio_file(self):
        self._browse_asset_file("audio")

    def _update_image_file(self, text: str):
        self.exercise.image_file = (
            text.strip().replace("\\", "/") if text.strip() else None
        )
        self.data_changed.emit()

    def _browse_image_file(self):
        self._browse_asset_file("image")

    def _browse_asset_file(self, asset_type: str):
        """
        Launches the AssetManagerDialog to select an asset.
        """
        if not self.course_root_dir:
            QMessageBox.warning(
                self,
                f"Browse {asset_type.capitalize()}",
                "Course root directory is not set. Please save the manifest first to establish the course location.",
            )
            return

        dialog = AssetManagerDialog(self.course_root_dir, asset_type, self)
        # Connect to the signal emitted when an asset is selected
        dialog.asset_selected.connect(
            lambda path: (
                self.audio_file_input.setText(path)
                if asset_type == "audio"
                else self.image_file_input.setText(path)
            )
        )
        dialog.exec() # Show the dialog

    def validate(self) -> tuple[bool, str]:
        if not self.exercise.prompt or not self.exercise.prompt.strip():
            return False, "Translation prompt cannot be empty."
        if not self.exercise.answer or not self.exercise.answer.strip():
            return False, "Translation answer cannot be empty."
        return True, ""


class MultipleChoiceOptionEditDialog(QDialog):
    def __init__(self, option_text="", is_correct=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Option")
        layout = QVBoxLayout(self)

        self.text_edit = QLineEdit(option_text)
        self.correct_checkbox = QCheckBox("Is Correct")
        self.correct_checkbox.setChecked(is_correct)

        form_layout = QFormLayout()
        form_layout.addRow("Option Text:", self.text_edit)
        form_layout.addRow(self.correct_checkbox)
        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> tuple[Optional[str], bool]:
        if not self.text_edit.text().strip():
            QMessageBox.warning(self, "Input Error", "Option text cannot be empty.")
            return None, False
        return self.text_edit.text().strip(), self.correct_checkbox.isChecked()


class MultipleChoiceExerciseEditorWidget(BaseExerciseEditorWidget):
    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        parent=None,
    ):
        super().__init__(exercise, target_language, source_language, getattr(parent, 'course_root_dir', None), parent)

        self.source_word_input = self._add_input_field(
            f"Source Word ({source_language})",
            exercise.source_word or "",
            self._update_source_word,
            placeholder_text="e.g., Thank you",
        )

        self.layout.addWidget(self._create_separator())
        self.layout.addWidget(QLabel(f"Options ({target_language}):"))

        self.options_list_widget = QListWidget()
        self.options_list_widget.itemDoubleClicked.connect(self._edit_selected_option)
        self.layout.addWidget(self.options_list_widget)

        options_button_layout = QHBoxLayout()
        add_option_button = QPushButton("Add Option")
        add_option_button.clicked.connect(self._add_option_dialog)
        edit_option_button = QPushButton("Edit Selected")
        edit_option_button.clicked.connect(self._edit_selected_option)
        delete_option_button = QPushButton("Delete Selected")
        delete_option_button.clicked.connect(self._delete_selected_option)

        options_button_layout.addWidget(add_option_button)
        options_button_layout.addWidget(edit_option_button)
        options_button_layout.addWidget(delete_option_button)
        options_button_layout.addStretch(1)
        self.layout.addLayout(options_button_layout)

        self.options_validation_label = QLabel()
        self.options_validation_label.setStyleSheet("color: orange;")
        self.layout.addWidget(self.options_validation_label)

        self._populate_options_list()
        self._validate_mcq_options()
        self.layout.addStretch(1)

    def _update_source_word(self, text: str):
        self.exercise.source_word = text.strip() if text.strip() else None
        self.data_changed.emit()

    def _populate_options_list(self):
        self.options_list_widget.clear()
        for option_obj in self.exercise.options:
            item_text = option_obj.text
            if option_obj.correct:
                item_text += " (Correct)"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, option_obj)
            self.options_list_widget.addItem(list_item)
        self._validate_mcq_options()

    def _validate_mcq_options(self):
        if not self.exercise.options:
            self.options_validation_label.setText(
                "Warning: At least one option is recommended."
            )
            self.options_validation_label.setStyleSheet("color: orange;")
            return

        correct_count = sum(1 for opt in self.exercise.options if opt.correct)
        if correct_count == 0:
            self.options_validation_label.setText(
                "Error: No option marked as correct. Please mark one."
            )
            self.options_validation_label.setStyleSheet("color: red;")
        elif correct_count > 1:
            self.options_validation_label.setText(
                f"Error: {correct_count} options marked correct. Please mark exactly one."
            )
            self.options_validation_label.setStyleSheet("color: red;")
        else:
            self.options_validation_label.setText("")
            self.options_validation_label.setStyleSheet("color: green;")

    def _add_option_dialog(self):
        dialog = MultipleChoiceOptionEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            text, is_correct = dialog.get_data()
            if text is not None:
                new_option = ExerciseOption(text=text, correct=is_correct)

                if is_correct:
                    for opt in self.exercise.options:
                        opt.correct = False

                self.exercise.options.append(new_option)
                self._populate_options_list()
                self.data_changed.emit()

    def _edit_selected_option(self):
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self, "Edit Option", "Please select an option to edit."
            )
            return

        current_item = selected_items[0]
        option_obj: ExerciseOption = current_item.data(Qt.UserRole)

        dialog = MultipleChoiceOptionEditDialog(
            option_text=option_obj.text, is_correct=option_obj.correct, parent=self
        )
        if dialog.exec() == QDialog.Accepted:
            text, is_correct = dialog.get_data()
            if text is not None:
                option_obj.text = text

                if is_correct:
                    for opt in self.exercise.options:
                        if opt is not option_obj:
                            opt.correct = False
                    option_obj.correct = True
                else:
                    option_obj.correct = False

                self._populate_options_list()
                self.data_changed.emit()

    def _delete_selected_option(self):
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self, "Delete Option", "Please select an option to delete."
            )
            return

        current_item = selected_items[0]
        option_obj: ExerciseOption = current_item.data(Qt.UserRole)

        reply = QMessageBox.question(
            self,
            "Delete Option",
            f"Are you sure you want to delete option: '{option_obj.text}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.exercise.options.remove(option_obj)
            self._populate_options_list()
            self.data_changed.emit()

    def validate(self) -> tuple[bool, str]:
        if not self.exercise.source_word or not self.exercise.source_word.strip():
            return False, "Multiple Choice 'Source Word' cannot be empty."
        if not self.exercise.options:
            return False, "Multiple Choice must have at least one option."
        if not any(opt.correct for opt in self.exercise.options):
            return False, "Multiple Choice must have at least one correct option."
        for opt in self.exercise.options:
            if not opt.text.strip():
                return False, "Multiple Choice options cannot be empty."
        return True, ""


class ImageAssociationExerciseEditorWidget(BaseExerciseEditorWidget):
    """Editor for image_association."""
    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        course_root_dir: Optional[str], # Added course_root_dir
        parent=None,
    ):
        # Call BaseExerciseEditorWidget's __init__ directly, not MultipleChoiceExerciseEditorWidget's
        super().__init__(exercise, target_language, source_language, course_root_dir, parent)
        # Prompt (re-add as it's not in Base but needed here)
        self.prompt_input = self._add_input_field(
            "Prompt", # General prompt, not language specific like MCQ's source_word
            exercise.prompt or "",
            lambda text: setattr(self.exercise, 'prompt', text.strip() if text.strip() else None) or self.data_changed.emit(),
            is_required=True, # Prompt is usually required for association
            placeholder_text="e.g., Which image matches the sound?",
        )

        # Asset File (Image or Audio)
        self.asset_label_text = "Image File:"
        self.asset_type_for_browser = "image"
        current_asset_file = exercise.image_file or ""

        asset_layout = QHBoxLayout()
        asset_label = QLabel(self.asset_label_text)
        self.asset_file_input = QLineEdit(current_asset_file)
        self.asset_file_input.setPlaceholderText(f"e.g., assets/{self.asset_type_for_browser}s/example.png")
        self.asset_file_input.textChanged.connect(self._update_asset_file)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_asset)
        asset_layout.addWidget(asset_label)
        asset_layout.addWidget(self.asset_file_input, 1)
        asset_layout.addWidget(browse_button)
        self.layout.addLayout(asset_layout)

        # The rest is similar to MultipleChoiceExerciseEditorWidget for options
        self.layout.addWidget(self._create_separator())
        self.layout.addWidget(QLabel(f"Options ({target_language}):")) # Options are in target language

        self.options_list_widget = QListWidget()
        self.options_list_widget.itemDoubleClicked.connect(self._edit_selected_option)
        self.layout.addWidget(self.options_list_widget)

        options_button_layout = QHBoxLayout()
        add_option_button = QPushButton("Add Option")
        add_option_button.clicked.connect(self._add_option_dialog)
        edit_option_button = QPushButton("Edit Selected")
        edit_option_button.clicked.connect(self._edit_selected_option)
        delete_option_button = QPushButton("Delete Selected")
        delete_option_button.clicked.connect(self._delete_selected_option)

        options_button_layout.addWidget(add_option_button)
        options_button_layout.addWidget(edit_option_button)
        options_button_layout.addWidget(delete_option_button)
        options_button_layout.addStretch(1)
        self.layout.addLayout(options_button_layout)

        self.options_validation_label = QLabel()
        self.options_validation_label.setStyleSheet("color: orange;")
        self.layout.addWidget(self.options_validation_label)

        self._populate_options_list() # From MCQ
        self._validate_mcq_options() # From MCQ
        self.layout.addStretch(1)

    def _update_asset_file(self, text: str):
        path = text.strip().replace("\\", "/") or None
        self.exercise.image_file = path
        self.data_changed.emit()

    def _browse_asset(self):
        # Uses self.course_root_dir from BaseExerciseEditorWidget
        if not self.course_root_dir:
            QMessageBox.warning(self, "Browse Asset", "Course root directory not set. Cannot browse assets.")
            return
        dialog = AssetManagerDialog(self.course_root_dir, self.asset_type_for_browser, self)
        dialog.asset_selected.connect(self.asset_file_input.setText)
        dialog.exec()

    # Methods from MultipleChoiceExerciseEditorWidget that are reused:
    # _populate_options_list, _validate_mcq_options, _add_option_dialog,
    # _edit_selected_option, _delete_selected_option
    # We need to copy them here or make AssociationExerciseEditorWidget inherit from a
    # common base that has these, if we don't want to inherit from MultipleChoiceExerciseEditorWidget directly.
    # For simplicity, let's assume these methods are available via a common mixin or copied.
    # The current structure of AssociationExerciseEditorWidget in the input already re-implements these.

    def _populate_options_list(self): # Copied from MultipleChoiceExerciseEditorWidget
        self.options_list_widget.clear()
        for option_obj in self.exercise.options:
            item_text = option_obj.text
            if option_obj.correct:
                item_text += " (Correct)"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, option_obj)
            self.options_list_widget.addItem(list_item)
        self._validate_mcq_options()

    def _validate_mcq_options(self): # Copied from MultipleChoiceExerciseEditorWidget
        if not self.exercise.options:
            self.options_validation_label.setText("Warning: At least one option is recommended.")
            self.options_validation_label.setStyleSheet("color: orange;")
            return

        correct_count = sum(1 for opt in self.exercise.options if opt.correct)
        if correct_count == 0:
            self.options_validation_label.setText("Error: No option marked as correct. Please mark one.")
            self.options_validation_label.setStyleSheet("color: red;")
        elif correct_count > 1:
            self.options_validation_label.setText(f"Error: {correct_count} options marked correct. Please mark exactly one.")
            self.options_validation_label.setStyleSheet("color: red;")
        else:
            self.options_validation_label.setText("")
            self.options_validation_label.setStyleSheet("color: green;")

    def _add_option_dialog(self): # Copied from MultipleChoiceExerciseEditorWidget
        dialog = MultipleChoiceOptionEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            text, is_correct = dialog.get_data()
            if text is not None:
                new_option = ExerciseOption(text=text, correct=is_correct)
                if is_correct:
                    for opt in self.exercise.options:
                        opt.correct = False
                self.exercise.options.append(new_option)
                self._populate_options_list()
                self.data_changed.emit()

    def _edit_selected_option(self): # Copied from MultipleChoiceExerciseEditorWidget
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Edit Option", "Please select an option to edit.")
            return
        current_item = selected_items[0]
        option_obj: ExerciseOption = current_item.data(Qt.UserRole)
        dialog = MultipleChoiceOptionEditDialog(option_text=option_obj.text, is_correct=option_obj.correct, parent=self)
        if dialog.exec() == QDialog.Accepted:
            text, is_correct = dialog.get_data()
            if text is not None:
                option_obj.text = text
                if is_correct:
                    for opt in self.exercise.options:
                        if opt is not option_obj: opt.correct = False
                    option_obj.correct = True
                else:
                    option_obj.correct = False
                self._populate_options_list()
                self.data_changed.emit()

    def _delete_selected_option(self): # Copied from MultipleChoiceExerciseEditorWidget
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Delete Option", "Please select an option to delete.")
            return
        current_item = selected_items[0]
        option_obj: ExerciseOption = current_item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "Delete Option", f"Are you sure you want to delete option: '{option_obj.text}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.exercise.options.remove(option_obj)
            self._populate_options_list()
            self.data_changed.emit()

    def validate(self) -> tuple[bool, str]:
        if not self.exercise.prompt or not self.exercise.prompt.strip():
            return False, "Prompt cannot be empty."
        # image_file can be optional if prompt is descriptive enough
        # if not self.exercise.image_file:
        #     return False, "Image file must be selected."
        if not self.exercise.options:
            return False, "Must have at least one option."
        if not any(opt.correct for opt in self.exercise.options):
            return False, "Must have at least one correct option."
        if sum(1 for opt in self.exercise.options if opt.correct) > 1:
            return False, "Only one option can be correct."
        for opt in self.exercise.options:
            if not opt.text.strip():
                return False, "Option text cannot be empty."
        return True, ""


class ListenAndSelectExerciseEditorWidget(ImageAssociationExerciseEditorWidget): # Inherits option handling
    """Editor for listen_and_select. Similar to ImageAssociation but with Audio."""
    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        course_root_dir: Optional[str],
        parent=None,
    ):
        # Call BaseExerciseEditorWidget's __init__ directly
        BaseExerciseEditorWidget.__init__(self, exercise, target_language, source_language, course_root_dir, parent)

        self.prompt_input = self._add_input_field(
            "Prompt",
            exercise.prompt or "",
            lambda text: setattr(self.exercise, 'prompt', text.strip() if text.strip() else None) or self.data_changed.emit(),
            is_required=True,
            placeholder_text="e.g., Which option matches the sound?",
        )

        self.asset_label_text = "Audio File:"
        self.asset_type_for_browser = "audio"
        current_asset_file = exercise.audio_file or ""

        # Re-setup asset input from ImageAssociation, but for audio
        asset_layout = QHBoxLayout()
        asset_label = QLabel(self.asset_label_text)
        self.asset_file_input = QLineEdit(current_asset_file)
        self.asset_file_input.setPlaceholderText(f"e.g., assets/{self.asset_type_for_browser}s/example.mp3")
        self.asset_file_input.textChanged.connect(self._update_asset_file) # Uses overridden _update_asset_file
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_asset) # Uses inherited _browse_asset
        asset_layout.addWidget(asset_label)
        asset_layout.addWidget(self.asset_file_input, 1)
        asset_layout.addWidget(browse_button)
        self.layout.addLayout(asset_layout)

        # Re-setup options UI from ImageAssociation
        self.layout.addWidget(self._create_separator())
        self.layout.addWidget(QLabel(f"Options ({target_language}):"))
        self.options_list_widget = QListWidget()
        self.options_list_widget.itemDoubleClicked.connect(self._edit_selected_option)
        self.layout.addWidget(self.options_list_widget)
        options_button_layout = QHBoxLayout()
        add_option_button = QPushButton("Add Option")
        add_option_button.clicked.connect(self._add_option_dialog)
        edit_option_button = QPushButton("Edit Selected")
        edit_option_button.clicked.connect(self._edit_selected_option)
        delete_option_button = QPushButton("Delete Selected")
        delete_option_button.clicked.connect(self._delete_selected_option)
        options_button_layout.addWidget(add_option_button)
        options_button_layout.addWidget(edit_option_button)
        options_button_layout.addWidget(delete_option_button)
        options_button_layout.addStretch(1)
        self.layout.addLayout(options_button_layout)
        self.options_validation_label = QLabel()
        self.options_validation_label.setStyleSheet("color: orange;")
        self.layout.addWidget(self.options_validation_label)

        self._populate_options_list()
        self._validate_mcq_options()
        self.layout.addStretch(1)

    def _update_asset_file(self, text: str): # Override for audio_file
        path = text.strip().replace("\\", "/") or None
        self.exercise.audio_file = path
        self.data_changed.emit()

    def validate(self) -> tuple[bool, str]: # Override for audio_file if needed
        is_valid, msg = super().validate()
        if not is_valid:
            return is_valid, msg
        # audio_file can be optional if prompt is descriptive enough
        # if not self.exercise.audio_file:
        #     return False, "Audio file must be selected."
        return True, ""


class SentenceJumbleExerciseEditorWidget(BaseExerciseEditorWidget):
    def __init__(self, exercise: Exercise, target_language: str, source_language: str, parent=None):
        super().__init__(exercise, target_language, source_language, course_root_dir=None, parent=parent)
        self._add_input_field("Prompt (Optional)", exercise.prompt or "", lambda text: setattr(self.exercise, 'prompt', text.strip() or None) or self.data_changed.emit())
        self._add_input_field(f"Correct Answer (Full Sentence in {target_language})", exercise.answer or "", lambda text: setattr(self.exercise, 'answer', text.strip() or None) or self.data_changed.emit(), is_required=True)
        
        self.layout.addWidget(QLabel(f"Words/Phrases to Jumble (one per line, in {target_language}): *"))
        self.words_input = QTextEdit("\n".join(exercise.words or []))
        self.words_input.textChanged.connect(self._update_words)
        self.layout.addWidget(self.words_input)
        self.layout.addStretch(1)

    def _update_words(self):
        self.exercise.words = [line.strip() for line in self.words_input.toPlainText().split("\n") if line.strip()]
        self.data_changed.emit()
        self._validate_input_field(self.words_input, True) # Basic validation for non-empty

    def _validate_input_field(self, input_widget, is_required: bool): # Override for QTextEdit specific to words
        if isinstance(input_widget, QTextEdit) and input_widget == self.words_input:
            if is_required and not self.exercise.words:
                input_widget.setStyleSheet("border: 1px solid red;")
            else:
                input_widget.setStyleSheet("")
        else: # Call super for other QLineEdit fields if any, or general handling
            super()._validate_input_field(input_widget, is_required)
        self.data_changed.emit()

    def validate(self) -> tuple[bool, str]:
        if not self.exercise.answer or not self.exercise.answer.strip():
            return False, "Correct Answer (Full Sentence) cannot be empty."
        if not self.exercise.words or not any(w.strip() for w in self.exercise.words):
            return False, "Words/Phrases to Jumble cannot be empty."
        return True, ""


class DictationExerciseEditorWidget(BaseExerciseEditorWidget):
    def __init__(self, exercise: Exercise, target_language: str, source_language: str, course_root_dir: Optional[str], parent=None):
        super().__init__(exercise, target_language, source_language, course_root_dir, parent)

        self._add_input_field(
            f"Instruction/Prompt ({target_language}, Optional)",
            exercise.prompt or "",
            lambda text: setattr(self.exercise, 'prompt', text.strip() or None) or self.data_changed.emit(),
            is_multiline=True,
            placeholder_text="e.g., Listen and write what you hear."
        )
        self._add_input_field(
            f"Correct Transcription ({target_language})",
            exercise.answer or "",
            lambda text: setattr(self.exercise, 'answer', text.strip() or None) or self.data_changed.emit(),
            is_multiline=True,
            is_required=True,
            placeholder_text="The sentence that will be spoken and should be typed."
        )

        audio_layout = QHBoxLayout()
        audio_label = QLabel("Audio File (of transcription): *") # Marked as important
        self.audio_file_input = QLineEdit(self.exercise.audio_file or "")
        self.audio_file_input.setPlaceholderText("e.g., assets/sounds/dictation_sentence.mp3")
        self.audio_file_input.textChanged.connect(self._update_audio_file)
        browse_audio_button = QPushButton("Browse...")
        browse_audio_button.clicked.connect(self._browse_audio)
        audio_layout.addWidget(audio_label)
        audio_layout.addWidget(self.audio_file_input, 1)
        audio_layout.addWidget(browse_audio_button)
        self.layout.addLayout(audio_layout)
        self.layout.addStretch(1)

    def _update_audio_file(self, text: str):
        self.exercise.audio_file = text.strip().replace("\\", "/") or None
        self.data_changed.emit()
        self._validate_input_field(self.audio_file_input, True) # Validate audio file as required

    def _browse_audio(self):
        if not self.course_root_dir:
            QMessageBox.warning(self, "Browse Audio", "Course root directory not set. Cannot browse assets.")
            return
        dialog = AssetManagerDialog(self.course_root_dir, "audio", self)
        dialog.asset_selected.connect(self.audio_file_input.setText)
        dialog.exec()

    def validate(self) -> tuple[bool, str]:
        if not self.exercise.answer or not self.exercise.answer.strip():
            return False, "Correct Transcription cannot be empty."
        if not self.exercise.audio_file or not self.exercise.audio_file.strip():
            # Consider if audio_file should be strictly required or just a warning
            return False, "Audio File for dictation is required."
        return True, ""


class ContextBlockExerciseEditorWidget(BaseExerciseEditorWidget):
    def __init__(self, exercise: Exercise, parent=None):
        # Context blocks are language-agnostic and typically don't have direct assets from root
        super().__init__(exercise, target_language="N/A", source_language="N/A", course_root_dir=None, parent=parent)
        self._add_input_field("Title (Optional)", exercise.title or "", lambda text: setattr(self.exercise, 'title', text.strip() or None) or self.data_changed.emit())

        # Add the image file input field, similar to other widgets
        image_layout = QHBoxLayout()
        image_label = QLabel("Image File (Optional):")
        self.image_file_input = QLineEdit(self.exercise.image_file or "")
        self.image_file_input.setPlaceholderText("e.g., assets/images/lesson_intro.png")
        self.image_file_input.textChanged.connect(self._update_image_file)

        browse_image_button = QPushButton("Browse...")
        browse_image_button.clicked.connect(self._browse_image_file)

        image_layout.addWidget(image_label)
        image_layout.addWidget(self.image_file_input, 1)
        image_layout.addWidget(browse_image_button)
        self.layout.addLayout(image_layout)

        self.layout.addWidget(QLabel("Content (Markdown supported): *"))
        self.prompt_input = QTextEdit(exercise.prompt or "") # 'prompt' field holds the content
        self.prompt_input.textChanged.connect(self._update_prompt_content)
        self.layout.addWidget(self.prompt_input)
        self.layout.addStretch(1)

    def _update_prompt_content(self):
        self.exercise.prompt = self.prompt_input.toPlainText().strip() or None # Content is stored in 'prompt'
        self.data_changed.emit()
        self._validate_input_field(self.prompt_input, True) # Validate content as required

    def _update_image_file(self, text: str):
        self.exercise.image_file = text.strip().replace("\\", "/") or None
        self.data_changed.emit()

    def _browse_image_file(self):
        if not self.course_root_dir:
            QMessageBox.warning(self, "Browse Image", "Course root directory not set. Cannot browse assets.")
            return
        dialog = AssetManagerDialog(self.course_root_dir, "image", self)
        dialog.asset_selected.connect(self.image_file_input.setText)
        dialog.exec()

    def validate(self) -> tuple[bool, str]:
        if not self.exercise.prompt or not self.exercise.prompt.strip():
            return False, "Content for the context block cannot be empty."
        return True, ""

class FillInTheBlankExerciseEditorWidget(BaseExerciseEditorWidget):
    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        parent=None,
    ):
        super().__init__(exercise, target_language, source_language, getattr(parent, 'course_root_dir', None), parent)

        self.template_input = self._add_input_field(
            f"Sentence Template ({target_language}) (use __BLANK__)",
            exercise.sentence_template or "",
            self._update_sentence_template,
            is_multiline=True,
            is_required=True,
            placeholder_text="e.g., Mi __BLANK__ feliĉa.",
        )

        self.correct_option_text_input = self._add_input_field(
            f"Correct Blank Word ({target_language})",
            exercise.correct_option or "",
            self._update_correct_option_text,
            is_required=True,
            placeholder_text="e.g., estas",
        )

        self.correct_option_text_input.textChanged.connect(
            self._sync_correct_option_to_options_list
        )

        self.hint_input = self._add_input_field(
            f"Translation Hint ({source_language})",
            exercise.translation_hint or "",
            self._update_translation_hint,
            is_required=True,
            placeholder_text="e.g., I am happy.",
        )

        self.layout.addWidget(self._create_separator())
        self.layout.addWidget(
            QLabel(
                "Available Options for Blank (will be shuffled in app, include the correct one):"
            )
        )

        self.options_list_widget = QListWidget()
        self.options_list_widget.itemDoubleClicked.connect(
            self._edit_selected_option_dialog
        )
        self.layout.addWidget(self.options_list_widget)

        options_button_layout = QHBoxLayout()
        add_option_button = QPushButton("Add Option")
        add_option_button.clicked.connect(self._add_option_dialog)
        edit_option_button = QPushButton("Edit Selected")
        edit_option_button.clicked.connect(self._edit_selected_option_dialog)
        delete_option_button = QPushButton("Delete Selected")
        delete_option_button.clicked.connect(self._delete_selected_option)

        options_button_layout.addWidget(add_option_button)
        options_button_layout.addWidget(edit_option_button)
        options_button_layout.addWidget(delete_option_button)
        options_button_layout.addStretch(1)
        self.layout.addLayout(options_button_layout)

        self.options_validation_label = QLabel()
        self.options_validation_label.setStyleSheet("color: orange;")
        self.layout.addWidget(self.options_validation_label)

        self._populate_options_list()
        self._validate_fib_options()
        self._sync_correct_option_to_options_list()
        self.layout.addStretch(1)

    def _update_sentence_template(self, text: str):
        self.exercise.sentence_template = text.strip() if text.strip() else None
        self.data_changed.emit()

    def _update_correct_option_text(self, text: str):
        self.exercise.correct_option = text.strip() if text.strip() else None
        self._sync_correct_option_to_options_list()
        self.data_changed.emit()

    def _update_translation_hint(self, text: str):
        self.exercise.translation_hint = text.strip() if text.strip() else None
        self.data_changed.emit()

    def _populate_options_list(self):
        self.options_list_widget.clear()
        for option_obj in self.exercise.options:
            list_item = QListWidgetItem(option_obj.text)
            self.options_list_widget.addItem(list_item)
        self._validate_fib_options()

    def _validate_fib_options(self):
        if not self.exercise.options:
            self.options_validation_label.setText(
                "Error: Options list cannot be empty."
            )
            self.options_validation_label.setStyleSheet("color: red;")
            return

        correct_text = self.exercise.correct_option
        if correct_text and correct_text.strip():
            option_texts = [opt.text for opt in self.exercise.options]
            if correct_text.strip() not in option_texts:
                self.options_validation_label.setText(
                    f"Error: Correct option '{correct_text}' not found in options list."
                )
                self.options_validation_label.setStyleSheet("color: red;")
                return
        else:
            self.options_validation_label.setText(
                "Error: Correct option is empty, but required."
            )
            self.options_validation_label.setStyleSheet("color: red;")
            return

        self.options_validation_label.setText("")
        self.options_validation_label.setStyleSheet("color: green;")

    def _sync_correct_option_to_options_list(self):
        """Ensures the self.exercise.correct_option text is present in self.exercise.options list."""
        correct_text = self.exercise.correct_option
        if correct_text and correct_text.strip():
            found = any(
                opt.text == correct_text.strip() for opt in self.exercise.options
            )
            if not found:
                self.exercise.options.append(
                    ExerciseOption(text=correct_text.strip(), correct=False)
                )
                self._populate_options_list()
                self.data_changed.emit()
        self._validate_fib_options()

    def _add_option_dialog(self):
        option_text, ok = QInputDialog.getText(self, "Add Option", "Enter option text:")
        if ok and option_text and option_text.strip():
            if not any(
                opt.text == option_text.strip() for opt in self.exercise.options
            ):
                self.exercise.options.append(
                    ExerciseOption(text=option_text.strip(), correct=False)
                )
                self._populate_options_list()
                self.data_changed.emit()
            else:
                QMessageBox.information(
                    self, "Add Option", "This option text already exists."
                )
        elif ok:
            QMessageBox.warning(self, "Invalid Input", "Option text cannot be empty.")

    def _edit_selected_option_dialog(self):
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self, "Edit Option", "Please select an option to edit."
            )
            return

        current_item = selected_items[0]
        option_obj: ExerciseOption = current_item.data(Qt.UserRole)

        new_text, ok = QInputDialog.getText(
            self, "Edit Option", "Enter new option text:", text=option_obj.text
        )
        if ok and new_text and new_text.strip():
            option_obj.text = new_text.strip()
            self._populate_options_list()
            self.data_changed.emit()
        elif ok:
            QMessageBox.warning(self, "Invalid Input", "Option text cannot be empty.")

    def _delete_selected_option(self):
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self, "Delete Option", "Please select an option to delete."
            )
            return

        current_item = selected_items[0]
        option_obj: ExerciseOption = current_item.data(Qt.UserRole)

        if len(self.exercise.options) <= 1:
            QMessageBox.warning(
                self, "Delete Option", "Cannot delete the last option from the list."
            )
            return

        reply = QMessageBox.question(
            self,
            "Delete Option",
            f"Are you sure you want to delete option: '{option_obj.text}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.exercise.options.remove(option_obj)
            self._populate_options_list()
            self.data_changed.emit()
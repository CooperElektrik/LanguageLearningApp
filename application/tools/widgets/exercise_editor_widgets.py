import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from application.core.models import Exercise, ExerciseOption

    from ..dialogs.asset_manager_dialog import AssetManagerDialog
    from .asset_drop_line_edit import AssetDropLineEdit
except ImportError:
    logging.warning("Could not import Exercise model in ExerciseEditorWidgets.")

    class Exercise:
        def __init__(self, *args, **kwargs):
            pass

    class ExerciseOption:
        def __init__(self, *args, **kwargs):
            self.text = ""
            self.correct = False
            self.image_file = None

    class AssetManagerDialog:
        def __init__(self, *args, **kwargs):
            pass

    class AssetDropLineEdit(QLineEdit):
        pass


def mark_widget_validity(widget: QWidget, is_valid: bool):
    """Sets Qt dynamic property 'hasError' without modifying styleSheet directly."""
    widget.setProperty("hasError", not is_valid)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


logger = logging.getLogger(__name__)


class BaseExerciseEditorWidget(QWidget):
    data_changed = Signal()

    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        course_root_dir: str | None,
        parent=None,
    ):
        super().__init__(parent)
        self.exercise = exercise
        self.target_language = target_language
        self.source_language = source_language
        self.course_root_dir = course_root_dir

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(8)

        self.form_layout = QFormLayout()
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.setHorizontalSpacing(12)
        self.form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.layout.addLayout(self.form_layout)

        self.type_label = QLabel(f"Exercise Type: {exercise.type.replace('_', ' ').title()}")
        self.type_label.setObjectName("ExerciseTypeHeader")
        self.type_label.setVisible(False)  # Handled by InspectorHeaderWidget banner

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        return separator

    def _add_asset_field(
        self,
        asset_type: str,
        label_text: str,
        current_value: str | None,
        on_change,
        field_name: str | None = None,
    ):
        """Adds a labelled asset path field with drag-and-drop and a Browse... button using QFormLayout."""
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label = QLabel(label_text)
        line_edit = AssetDropLineEdit(
            current_value or "",
            asset_type=asset_type,
            course_root_dir=self.course_root_dir,
        )
        line_edit.setProperty("field_name", field_name or f"{asset_type}_file")
        line_edit.textChanged.connect(on_change)
        line_edit.asset_dropped.connect(on_change)

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(lambda: self._browse_asset(asset_type, line_edit))

        row_layout.addWidget(line_edit, 1)
        row_layout.addWidget(browse_button)
        self.form_layout.addRow(label, row_layout)
        return line_edit

    def _browse_asset(self, asset_type: str, target_line_edit: QLineEdit):
        """Opens the asset manager and writes the chosen path into the field."""
        if not self.course_root_dir:
            QMessageBox.warning(
                self,
                f"Browse {asset_type.capitalize()}",
                "Course root directory is not set. Please save the manifest first to establish the course location.",
            )
            return
        dialog = AssetManagerDialog(self.course_root_dir, asset_type, self)
        dialog.asset_selected.connect(target_line_edit.setText)
        dialog.exec()

    def _add_input_field(
        self,
        label_text: str,
        current_value: str,
        callback_func,
        is_multiline: bool = False,
        is_required: bool = False,
        placeholder_text: str | None = None,
        field_name: str | None = None,
    ):
        label_full_text = label_text + (" *" if is_required else "")
        label = QLabel(label_full_text)

        if is_multiline:
            input_field = QTextEdit()
            input_field.setPlainText(current_value)
            input_field.textChanged.connect(lambda: callback_func(input_field.toPlainText()))
            input_field.setMinimumHeight(60)
        else:
            input_field = QLineEdit()
            input_field.setText(current_value)
            input_field.textChanged.connect(callback_func)

        if placeholder_text:
            input_field.setPlaceholderText(placeholder_text)
        if field_name:
            input_field.setProperty("field_name", field_name)

        input_field.textChanged.connect(
            lambda: self._validate_input_field(input_field, is_required)
        )

        self.form_layout.addRow(label, input_field)
        self._validate_input_field(input_field, is_required)
        return input_field

    def _validate_input_field(self, input_widget, is_required: bool):
        if not is_required:
            mark_widget_validity(input_widget, True)
            return

        text = ""
        if isinstance(input_widget, QLineEdit):
            text = input_widget.text().strip()
        elif isinstance(input_widget, QTextEdit):
            text = input_widget.toPlainText().strip()

        mark_widget_validity(input_widget, bool(text))
        self.data_changed.emit()

    def focus_field(self, field_name: str | None = None) -> bool:
        """Cleanly sets focus and marks validity on the specified invalid field."""
        lookup = field_name or "prompt"
        # Check direct attributes
        for attr in [f"{lookup}_input", f"{lookup}_edit", lookup]:
            w = getattr(self, attr, None)
            if w and hasattr(w, "setFocus"):
                w.setFocus()
                mark_widget_validity(w, False)
                return True

        # Check by property field_name
        for child in self.findChildren((QLineEdit, QTextEdit)):
            if child.property("field_name") == lookup:
                child.setFocus()
                mark_widget_validity(child, False)
                return True

        # Fallback to first editable widget
        first = self.findChild(QLineEdit) or self.findChild(QTextEdit)
        if first:
            first.setFocus()
            mark_widget_validity(first, False)
            return True
        return False

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
        course_root_dir: str | None,
        parent=None,
    ):
        super().__init__(exercise, target_language, source_language, course_root_dir, parent)

        prompt_lang_hint = (
            self.source_language if exercise.type == "translate_to_target" else self.target_language
        )
        self.prompt_input = self._add_input_field(
            f"Prompt ({prompt_lang_hint})",
            exercise.prompt or "",
            self._update_prompt,
            is_required=True,
            placeholder_text="e.g., Hello",
        )

        answer_lang_hint = (
            self.target_language if exercise.type == "translate_to_target" else self.source_language
        )
        self.answer_input = self._add_input_field(
            f"Answer ({answer_lang_hint})",
            exercise.answer or "",
            self._update_answer,
            is_required=True,
            placeholder_text="e.g., Saluton",
        )

        self.audio_file_input = self._add_asset_field(
            "audio", "Audio File:", self.exercise.audio_file, self._update_audio_file
        )
        self.audio_file_input.textChanged.connect(
            lambda: self._validate_input_field(self.audio_file_input, False)
        )

        self.image_file_input = self._add_asset_field(
            "image", "Image File:", self.exercise.image_file, self._update_image_file
        )
        self.image_file_input.textChanged.connect(
            lambda: self._validate_input_field(self.image_file_input, False)
        )

        self.layout.addStretch(1)

    def _update_prompt(self, text: str):
        self.exercise.prompt = text.strip() if text.strip() else None
        self.data_changed.emit()

    def _update_answer(self, text: str):
        self.exercise.answer = text.strip() if text.strip() else None
        self.data_changed.emit()

    def _update_audio_file(self, text: str):
        self.exercise.audio_file = text.strip().replace("\\", "/") if text.strip() else None
        self.data_changed.emit()

    def _update_image_file(self, text: str):
        self.exercise.image_file = text.strip().replace("\\", "/") if text.strip() else None
        self.data_changed.emit()

    def validate(self) -> tuple[bool, str]:
        if not self.exercise.prompt or not self.exercise.prompt.strip():
            return False, "Translation prompt cannot be empty."
        if not self.exercise.answer or not self.exercise.answer.strip():
            return False, "Translation answer cannot be empty."
        return True, ""


class MultipleChoiceOptionEditDialog(QDialog):
    def __init__(self, option_text="", option_image_file="", is_correct=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Option")
        layout = QVBoxLayout(self)

        self.text_edit = QLineEdit(option_text)
        self.image_file_edit = QLineEdit(option_image_file)
        self.correct_checkbox = QCheckBox("Is Correct")
        self.correct_checkbox.setChecked(is_correct)

        form_layout = QFormLayout()
        form_layout.addRow("Option Text:", self.text_edit)
        form_layout.addRow("Image File:", self.image_file_edit)
        form_layout.addRow(self.correct_checkbox)
        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> tuple[str | None, str | None, bool]:
        text = self.text_edit.text().strip()
        image_file = self.image_file_edit.text().strip()
        if not text and not image_file:
            QMessageBox.warning(
                self,
                "Input Error",
                "Either option text or an image file must be provided.",
            )
            return None, None, False
        return text, image_file, self.correct_checkbox.isChecked()


class OptionsEditorMixin:
    """Shared option-list editing for option-based exercise editors.

    ``MultipleChoiceExerciseEditorWidget`` and
    ``ImageAssociationExerciseEditorWidget`` used to carry byte-identical copies
    of this code; the copies diverged and one silently unpacked the wrong tuple
    shape from the option dialog.  Sharing it here removes that whole class of
    bug along with a few hundred duplicated lines.

    Hosts must provide ``self.exercise``, ``self.layout``, ``self.data_changed``
    and ``_create_separator`` (all supplied by ``BaseExerciseEditorWidget``).
    """

    def _setup_options_section(self, heading: str):
        """Builds the option list, its action buttons and validation label."""
        self.layout.addWidget(self._create_separator())
        self.layout.addWidget(QLabel(heading))

        self.options_list_widget = QListWidget()
        self.options_list_widget.itemDoubleClicked.connect(self._edit_selected_option)
        self.layout.addWidget(self.options_list_widget)

        buttons_layout = QHBoxLayout()
        for text, slot in (
            ("Add Option", self._add_option_dialog),
            ("Edit Selected", self._edit_selected_option),
            ("Delete Selected", self._delete_selected_option),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons_layout.addWidget(button)
        buttons_layout.addStretch(1)
        self.layout.addLayout(buttons_layout)

        self.options_validation_label = QLabel()
        self.options_validation_label.setStyleSheet("color: orange;")
        self.layout.addWidget(self.options_validation_label)

        self._populate_options_list()

    def _populate_options_list(self):
        self.options_list_widget.clear()
        for option_obj in self.exercise.options:
            item_text = option_obj.text or ""
            if option_obj.image_file:
                item_text += f" [{option_obj.image_file}]"
            if option_obj.correct:
                item_text += " (Correct)"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, option_obj)
            self.options_list_widget.addItem(list_item)
        self._validate_mcq_options()

    def _validate_mcq_options(self):
        if not self.exercise.options:
            self.options_validation_label.setText("Warning: At least one option is recommended.")
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
            text, image_file, is_correct = dialog.get_data()
            if text is not None or image_file is not None:
                new_option = ExerciseOption(text=text, image_file=image_file, correct=is_correct)
                if is_correct:
                    for opt in self.exercise.options:
                        opt.correct = False
                self.exercise.options.append(new_option)
                self._populate_options_list()
                self.data_changed.emit()

    def _edit_selected_option(self):
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Edit Option", "Please select an option to edit.")
            return
        option_obj: ExerciseOption = selected_items[0].data(Qt.UserRole)
        dialog = MultipleChoiceOptionEditDialog(
            option_text=option_obj.text,
            option_image_file=option_obj.image_file,
            is_correct=option_obj.correct,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            text, image_file, is_correct = dialog.get_data()
            if text is not None or image_file is not None:
                option_obj.text = text
                option_obj.image_file = image_file
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
            QMessageBox.information(self, "Delete Option", "Please select an option to delete.")
            return
        option_obj: ExerciseOption = selected_items[0].data(Qt.UserRole)
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


class MultipleChoiceExerciseEditorWidget(OptionsEditorMixin, BaseExerciseEditorWidget):
    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        parent=None,
    ):
        super().__init__(
            exercise,
            target_language,
            source_language,
            getattr(parent, "course_root_dir", None),
            parent,
        )

        self.source_word_input = self._add_input_field(
            f"Source Word ({source_language})",
            exercise.source_word or "",
            self._update_source_word,
            placeholder_text="e.g., Thank you",
        )

        self._setup_options_section(f"Options ({target_language}):")
        self.layout.addStretch(1)

    def _update_source_word(self, text: str):
        self.exercise.source_word = text.strip() if text.strip() else None
        self.data_changed.emit()

    def validate(self) -> tuple[bool, str]:
        if not self.exercise.source_word or not self.exercise.source_word.strip():
            return False, "Multiple Choice 'Source Word' cannot be empty."
        if not self.exercise.options:
            return False, "Multiple Choice must have at least one option."
        if not any(opt.correct for opt in self.exercise.options):
            return False, "Multiple Choice must have at least one correct option."
        for opt in self.exercise.options:
            if not opt.text.strip() and not opt.image_file.strip():
                return False, "Multiple Choice options cannot be empty."
        return True, ""


class ImageAssociationExerciseEditorWidget(OptionsEditorMixin, BaseExerciseEditorWidget):
    """Editor for image_association."""

    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        course_root_dir: str | None,  # Added course_root_dir
        parent=None,
    ):
        # Call BaseExerciseEditorWidget's __init__ directly, not MultipleChoiceExerciseEditorWidget's
        super().__init__(exercise, target_language, source_language, course_root_dir, parent)
        # Prompt (re-add as it's not in Base but needed here)
        self.prompt_input = self._add_input_field(
            "Prompt",  # General prompt, not language specific like MCQ's source_word
            exercise.prompt or "",
            lambda text: (
                setattr(self.exercise, "prompt", text.strip() if text.strip() else None)
                or self.data_changed.emit()
            ),
            is_required=True,  # Prompt is usually required for association
            placeholder_text="e.g., Which image matches the sound?",
        )

        self.asset_file_input = self._add_asset_field(
            "image", "Image File:", exercise.image_file, self._update_asset_file
        )

        self._setup_options_section(f"Options ({target_language}):")
        self.layout.addStretch(1)

    def _update_asset_file(self, text: str):
        path = text.strip().replace("\\", "/") or None
        self.exercise.image_file = path
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


class ListenAndSelectExerciseEditorWidget(
    ImageAssociationExerciseEditorWidget
):  # Inherits option handling
    """Editor for listen_and_select. Similar to ImageAssociation but with Audio."""

    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        course_root_dir: str | None,
        parent=None,
    ):
        # Call BaseExerciseEditorWidget's __init__ directly
        BaseExerciseEditorWidget.__init__(
            self, exercise, target_language, source_language, course_root_dir, parent
        )

        self.prompt_input = self._add_input_field(
            "Prompt",
            exercise.prompt or "",
            lambda text: (
                setattr(self.exercise, "prompt", text.strip() if text.strip() else None)
                or self.data_changed.emit()
            ),
            is_required=True,
            placeholder_text="e.g., Which option matches the sound?",
        )

        self.asset_file_input = self._add_asset_field(
            "audio", "Audio File:", exercise.audio_file, self._update_asset_file
        )

        self._setup_options_section(f"Options ({target_language}):")
        self.layout.addStretch(1)

    def _update_asset_file(self, text: str):  # Override for audio_file
        path = text.strip().replace("\\", "/") or None
        self.exercise.audio_file = path
        self.data_changed.emit()

    def validate(self) -> tuple[bool, str]:  # Override for audio_file if needed
        is_valid, msg = super().validate()
        if not is_valid:
            return is_valid, msg
        # audio_file can be optional if prompt is descriptive enough
        # if not self.exercise.audio_file:
        #     return False, "Audio file must be selected."
        return True, ""


class SentenceJumbleExerciseEditorWidget(BaseExerciseEditorWidget):
    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        parent=None,
    ):
        super().__init__(
            exercise,
            target_language,
            source_language,
            course_root_dir=None,
            parent=parent,
        )
        self._add_input_field(
            "Prompt (Optional)",
            exercise.prompt or "",
            lambda text: (
                setattr(self.exercise, "prompt", text.strip() or None) or self.data_changed.emit()
            ),
        )
        self._add_input_field(
            f"Correct Answer (Full Sentence in {target_language})",
            exercise.answer or "",
            lambda text: (
                setattr(self.exercise, "answer", text.strip() or None) or self.data_changed.emit()
            ),
            is_required=True,
        )

        self.layout.addWidget(
            QLabel(f"Words/Phrases to Jumble (one per line, in {target_language}): *")
        )
        self.words_input = QTextEdit("\n".join(exercise.words or []))
        self.words_input.textChanged.connect(self._update_words)
        self.layout.addWidget(self.words_input)
        self.layout.addStretch(1)

    def _update_words(self):
        self.exercise.words = [
            line.strip() for line in self.words_input.toPlainText().split("\n") if line.strip()
        ]
        self.data_changed.emit()
        self._validate_input_field(self.words_input, True)  # Basic validation for non-empty

    def _validate_input_field(
        self, input_widget, is_required: bool
    ):  # Override for QTextEdit specific to words
        if isinstance(input_widget, QTextEdit) and input_widget == self.words_input:
            has_words = bool(self.exercise.words)
            mark_widget_validity(input_widget, not is_required or has_words)
        else:
            super()._validate_input_field(input_widget, is_required)
        self.data_changed.emit()

    def validate(self) -> tuple[bool, str]:
        if not self.exercise.answer or not self.exercise.answer.strip():
            return False, "Correct Answer (Full Sentence) cannot be empty."
        if not self.exercise.words or not any(w.strip() for w in self.exercise.words):
            return False, "Words/Phrases to Jumble cannot be empty."
        return True, ""


class DictationExerciseEditorWidget(BaseExerciseEditorWidget):
    def __init__(
        self,
        exercise: Exercise,
        target_language: str,
        source_language: str,
        course_root_dir: str | None,
        parent=None,
    ):
        super().__init__(exercise, target_language, source_language, course_root_dir, parent)

        self._add_input_field(
            f"Instruction/Prompt ({target_language}, Optional)",
            exercise.prompt or "",
            lambda text: (
                setattr(self.exercise, "prompt", text.strip() or None) or self.data_changed.emit()
            ),
            is_multiline=True,
            placeholder_text="e.g., Listen and write what you hear.",
        )
        self._add_input_field(
            f"Correct Transcription ({target_language})",
            exercise.answer or "",
            lambda text: (
                setattr(self.exercise, "answer", text.strip() or None) or self.data_changed.emit()
            ),
            is_multiline=True,
            is_required=True,
            placeholder_text="The sentence that will be spoken and should be typed.",
        )

        self.audio_file_input = self._add_asset_field(
            "audio",
            "Audio File (of transcription): *",  # Marked as important
            self.exercise.audio_file,
            self._update_audio_file,
        )
        self.layout.addStretch(1)

    def _update_audio_file(self, text: str):
        self.exercise.audio_file = text.strip().replace("\\", "/") or None
        self.data_changed.emit()
        self._validate_input_field(self.audio_file_input, True)  # Validate audio file as required

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
        super().__init__(
            exercise,
            target_language="N/A",
            source_language="N/A",
            course_root_dir=None,
            parent=parent,
        )
        self._add_input_field(
            "Title (Optional)",
            exercise.title or "",
            lambda text: (
                setattr(self.exercise, "title", text.strip() or None) or self.data_changed.emit()
            ),
        )

        self.image_file_input = self._add_asset_field(
            "image",
            "Image File (Optional):",
            self.exercise.image_file,
            self._update_image_file,
        )

        self.layout.addWidget(QLabel("Content (Markdown supported): *"))
        self.prompt_input = QTextEdit(exercise.prompt or "")  # 'prompt' field holds the content
        self.prompt_input.textChanged.connect(self._update_prompt_content)
        self.layout.addWidget(self.prompt_input)
        self.layout.addStretch(1)

    def _update_prompt_content(self):
        self.exercise.prompt = (
            self.prompt_input.toPlainText().strip() or None
        )  # Content is stored in 'prompt'
        self.data_changed.emit()
        self._validate_input_field(self.prompt_input, True)  # Validate content as required

    def _update_image_file(self, text: str):
        self.exercise.image_file = text.strip().replace("\\", "/") or None
        self.data_changed.emit()

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
        super().__init__(
            exercise,
            target_language,
            source_language,
            getattr(parent, "course_root_dir", None),
            parent,
        )

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
        self.options_list_widget.itemDoubleClicked.connect(self._edit_selected_option_dialog)
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
            self.options_validation_label.setText("Error: Options list cannot be empty.")
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
            self.options_validation_label.setText("Error: Correct option is empty, but required.")
            self.options_validation_label.setStyleSheet("color: red;")
            return

        self.options_validation_label.setText("")
        self.options_validation_label.setStyleSheet("color: green;")

    def _sync_correct_option_to_options_list(self):
        """Ensures the self.exercise.correct_option text is present in self.exercise.options list."""
        correct_text = self.exercise.correct_option
        if correct_text and correct_text.strip():
            found = any(opt.text == correct_text.strip() for opt in self.exercise.options)
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
            if not any(opt.text == option_text.strip() for opt in self.exercise.options):
                self.exercise.options.append(
                    ExerciseOption(text=option_text.strip(), correct=False)
                )
                self._populate_options_list()
                self.data_changed.emit()
            else:
                QMessageBox.information(self, "Add Option", "This option text already exists.")
        elif ok:
            QMessageBox.warning(self, "Invalid Input", "Option text cannot be empty.")

    def _edit_selected_option_dialog(self):
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Edit Option", "Please select an option to edit.")
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
            QMessageBox.information(self, "Delete Option", "Please select an option to delete.")
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

    def validate(self) -> tuple[bool, str]:
        if not self.exercise.sentence_template or not self.exercise.sentence_template.strip():
            return False, "Sentence template cannot be empty."
        if "__BLANK__" not in self.exercise.sentence_template:
            return False, "Sentence template must contain the '__BLANK__' placeholder."
        if not self.exercise.correct_option or not self.exercise.correct_option.strip():
            return False, "Correct blank word cannot be empty."
        if not self.exercise.translation_hint or not self.exercise.translation_hint.strip():
            return False, "Translation hint cannot be empty."
        if not self.exercise.options:
            return False, "Please provide at least one option for the blank."
        option_texts = [opt.text for opt in self.exercise.options]
        if self.exercise.correct_option.strip() not in option_texts:
            return False, "The correct blank word must be one of the options."
        return True, ""

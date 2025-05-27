# File: tools/widgets/exercise_editor_widgets.py

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QRadioButton, QButtonGroup, QScrollArea,
                               QGroupBox, QCheckBox, QMessageBox, QFrame, QInputDialog, QTextEdit, QFormLayout, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QFileDialog)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from typing import Optional

# Correct import for core.models - relies on project_root being added to sys.path by main_editor.py
try:
    from core.models import Exercise, ExerciseOption
except ImportError:
    logging.warning("Could not import Exercise model in ExerciseEditorWidgets.")
    class Exercise: pass
    class ExerciseOption: pass

logger = logging.getLogger(__name__)

class BaseExerciseEditorWidget(QWidget):
    data_changed = Signal() # Emits when data within the exercise is changed

    def __init__(self, exercise: Exercise, target_language: str, source_language: str, parent=None):
        super().__init__(parent)
        self.exercise = exercise
        self.target_language = target_language
        self.source_language = source_language
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10) # Add some spacing

        # Common header
        self.type_label = QLabel(f"Exercise Type: {exercise.type.replace('_', ' ').title()}")
        self.type_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.layout.addWidget(self.type_label)
        self.layout.addWidget(self._create_separator())

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator

    def _add_input_field(self, label_text: str, current_value: str, callback_func, is_multiline: bool = False):
        h_layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setMinimumWidth(120) # Align labels
        h_layout.addWidget(label)
        
        input_field = QLineEdit()
        if is_multiline:
            input_field = QTextEdit() # Use QTextEdit for multiline input
            input_field.setPlainText(current_value)
            input_field.textChanged.connect(lambda: callback_func(input_field.toPlainText()))
            input_field.setMinimumHeight(60) # Give multiline field some height
        else:
            input_field.setText(current_value)
            input_field.textChanged.connect(callback_func)
        
        h_layout.addWidget(input_field)
        self.layout.addLayout(h_layout)
        return input_field # Return input field for direct access if needed

    def validate(self) -> tuple[bool, str]:
        """
        Validates the exercise data. Subclasses must override this.
        Returns (is_valid, error_message).
        """
        return True, ""


class TranslationExerciseEditorWidget(BaseExerciseEditorWidget):
    def __init__(self, exercise: Exercise, target_language: str, source_language: str, parent=None):
        super().__init__(exercise, target_language, source_language, parent)
        
        # Determine language for prompt based on exercise type
        prompt_lang_hint = self.source_language if exercise.type == 'translate_to_target' else self.target_language
        self.prompt_input = self._add_input_field(f"Prompt ({prompt_lang_hint}):", 
                                                 exercise.prompt or "", 
                                                 self._update_prompt)

        # Determine language for answer based on exercise type
        answer_lang_hint = self.target_language if exercise.type == 'translate_to_target' else self.source_language
        self.answer_input = self._add_input_field(f"Answer ({answer_lang_hint}):", 
                                                  exercise.answer or "", 
                                                  self._update_answer)
        
        audio_layout = QHBoxLayout()
        self.audio_file_input = QLineEdit(self.exercise.audio_file or "")
        self.audio_file_input.setPlaceholderText("e.g., sounds/hello.mp3 (relative to course content file)")
        self.audio_file_input.textChanged.connect(self._update_audio_file)
        
        browse_audio_button = QPushButton("Browse Audio...")
        browse_audio_button.clicked.connect(self._browse_audio_file)
        
        audio_layout.addWidget(QLabel("Audio File:"))
        audio_layout.addWidget(self.audio_file_input, 1) # Stretch line edit
        audio_layout.addWidget(browse_audio_button)
        self.layout.addLayout(audio_layout)

        self.layout.addStretch(1)

    def _update_prompt(self, text: str):
        self.exercise.prompt = text
        self.data_changed.emit()

    def _update_answer(self, text: str):
        self.exercise.answer = text
        self.data_changed.emit()

    def _update_audio_file(self, text: str):
        self.exercise.audio_file = text.strip() if text.strip() else None
        self.data_changed.emit()

    def _browse_audio_file(self):
        # The editor needs to know the base directory of the course content YAML to make relative paths intuitive.
        # For now, assume the user manages relative paths, or the dialog opens in a sensible default location.
        # A more advanced editor would have a "project root" or "course assets" directory.
        
        # Try to open file dialog in a 'sounds' or 'assets' subdir of where the manifest might be, if known.
        # This is tricky as editor_window manages current_manifest_path.
        # For simplicity, let it open in last used dir or home. User needs to pick relative path.
        
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", "Audio Files (*.mp3 *.wav *.ogg)")
        if file_path:
            # We need to store a path relative to the course content YAML.
            # This requires knowing where the course content YAML will be saved.
            # For now, just store the filename or a manually entered relative path.
            # Or, try to make it relative if a course is loaded.
            # This part is complex if the course isn't saved yet.
            # Let's prompt the user to ensure the path is relative.
            
            # Simple approach: just use the selected file path.
            # User must ensure it's correctly relative or the packager/app must resolve it.
            # A better approach: if current_course_content_path is known, try to make relative.
            # For now, we'll store what the user picks or types.
            
            # Simplest: Get only the filename if it's in a common 'sounds' folder,
            # otherwise, it could be a relative path they construct.
            # For demonstration, let's just take the filename, assuming it will be in a 'sounds/' dir.
            # This is a simplification. A real editor would need robust relative path management.
            
            # Let's just set the input field text and let the user ensure it's a correct relative path
            self.audio_file_input.setText(file_path) # User might need to edit this to be relative like "sounds/file.mp3"
            self._update_audio_file(file_path) # Trigger update

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
    def __init__(self, exercise: Exercise, target_language: str, source_language: str, parent=None):
        super().__init__(exercise, target_language, source_language, parent)

        self.source_word_input = self._add_input_field(f"Source Word ({source_language}):", 
                                                      exercise.source_word or "", 
                                                      self._update_source_word)

        self.layout.addWidget(self._create_separator())
        self.layout.addWidget(QLabel(f"Options ({target_language}):"))
        
        # --- New QListWidget for options ---
        self.options_list_widget = QListWidget()
        self.options_list_widget.itemDoubleClicked.connect(self._edit_selected_option) # Edit on double-click
        self.layout.addWidget(self.options_list_widget)

        # --- Buttons for option management ---
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
        
        self._populate_options_list() # Initial population
        self.layout.addStretch(1) # Ensure main layout pushes content up

    def _update_source_word(self, text: str):
        self.exercise.source_word = text
        self.data_changed.emit()

    def _populate_options_list(self):
        self.options_list_widget.clear()
        # Ensure there's always at least one correct option if options exist
        if self.exercise.options and not any(opt.correct for opt in self.exercise.options):
            self.exercise.options[0].correct = True # Default first to correct if none are

        for option_obj in self.exercise.options:
            item_text = option_obj.text
            if option_obj.correct:
                item_text += " (Correct)"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, option_obj) # Store the ExerciseOption object
            self.options_list_widget.addItem(list_item)

    def _add_option_dialog(self):
        dialog = MultipleChoiceOptionEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            text, is_correct = dialog.get_data()
            if text is not None:
                new_option = ExerciseOption(text=text, correct=is_correct)
                
                if is_correct: # Ensure only one correct option
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
        
        current_item = selected_items[0]
        option_obj: ExerciseOption = current_item.data(Qt.UserRole)
        
        dialog = MultipleChoiceOptionEditDialog(option_text=option_obj.text, is_correct=option_obj.correct, parent=self)
        if dialog.exec() == QDialog.Accepted:
            text, is_correct = dialog.get_data()
            if text is not None:
                option_obj.text = text
                
                if is_correct:
                    # Unset other correct options
                    for opt in self.exercise.options:
                        if opt is not option_obj: # Check object identity
                            opt.correct = False
                    option_obj.correct = True
                else: # User unchecked it
                    option_obj.correct = False
                    # Ensure at least one option remains correct if this was the one
                    if not any(opt.correct for opt in self.exercise.options):
                        QMessageBox.warning(self, "Validation", "At least one option must be correct. Re-marking this as correct.")
                        option_obj.correct = True # Revert or prompt user
                
                self._populate_options_list()
                self.data_changed.emit()

    def _delete_selected_option(self):
        selected_items = self.options_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Delete Option", "Please select an option to delete.")
            return
            
        current_item = selected_items[0]
        option_obj: ExerciseOption = current_item.data(Qt.UserRole)

        if option_obj.correct and len(self.exercise.options) <= 1:
             QMessageBox.warning(self, "Delete Option", "Cannot delete the only option if it's marked correct. Add another correct option first or unmark this.")
             return
        
        reply = QMessageBox.question(self, "Delete Option", f"Are you sure you want to delete option: '{option_obj.text}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.exercise.options.remove(option_obj)
            # If the deleted option was correct, ensure another one becomes correct or handle appropriately
            if option_obj.correct and self.exercise.options and not any(opt.correct for opt in self.exercise.options):
                self.exercise.options[0].correct = True # Make first remaining option correct
                QMessageBox.information(self, "Auto-Correction", f"'{self.exercise.options[0].text}' is now marked as the correct option.")
            
            self._populate_options_list()
            self.data_changed.emit()


    def _update_option_text(self, option: ExerciseOption, new_text: str):
        option.text = new_text
        self.data_changed.emit()

    def _update_option_correctness(self, option: ExerciseOption, state: int):
        # Ensure only one option can be correct for MC
        if state == Qt.CheckState.Checked:
            for opt in self.exercise.options:
                if opt is not option: # Use 'is not' for object identity check
                    opt.correct = False
            option.correct = True
            # Re-populate to update checkboxes visually (uncheck others)
            self.data_changed.emit()
            self._populate_options() # Re-draw to reflect the single correct option
        else: # Unchecked
            # Prevent unchecking if it's the only correct option, ensure at least one is correct if possible
            if option.correct and sum(1 for opt in self.exercise.options if opt.correct) == 1:
                QMessageBox.warning(self, "Warning", "At least one option must be marked as correct for Multiple Choice.")
                # Force re-check the current checkbox
                self._populate_options() # Re-draw to reflect the single correct option
            else:
                option.correct = False
                self.data_changed.emit()

    def _add_option(self):
        new_option_text, ok = QInputDialog.getText(self, "New Option", "Enter new option text:")
        if ok and new_option_text:
            new_option = ExerciseOption(text=new_option_text.strip(), correct=False) # Strip whitespace
            self.exercise.options.append(new_option)
            self._populate_options() # Re-populate all to maintain order/index integrity
            self.data_changed.emit()

    def _delete_option_ui(self, widget_to_delete: QWidget, option_obj: ExerciseOption):
        reply = QMessageBox.question(self, "Delete Option", "Are you sure you want to delete this option?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Remove from model's list
            self.exercise.options.remove(option_obj)
            # Re-populate to refresh UI and ensure correct references for remaining
            self._populate_options() 
            self.data_changed.emit()
            # If the deleted option was the last correct one and there are other options,
            # consider marking another one correct or warning. For now, rely on validation.


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

# FILE: application/tools/widgets/exercise_editor_widgets.py

# ... (Existing imports, BaseExerciseEditorWidget, TranslationExerciseEditorWidget, MultipleChoiceOptionEditDialog, MultipleChoiceExerciseEditorWidget) ...

class FillInTheBlankExerciseEditorWidget(BaseExerciseEditorWidget):
    def __init__(self, exercise: Exercise, target_language: str, source_language: str, parent=None):
        super().__init__(exercise, target_language, source_language, parent)
        
        self.template_input = self._add_input_field(
            f"Sentence Template ({target_language}) (use __BLANK__):",
            exercise.sentence_template or "",
            self._update_sentence_template,
            is_multiline=True
        )

        self.correct_option_text_input = self._add_input_field( # Renamed for clarity
            f"Correct Blank Word ({target_language}):",
            exercise.correct_option or "",
            self._update_correct_option_text # Renamed method
        )
        # Removed: self.correct_option_input.textChanged.connect(self._sync_correct_option_in_options)
        # Syncing will happen when correct_option_text_input changes or options list is modified.

        self.hint_input = self._add_input_field(
            f"Translation Hint ({source_language}):",
            exercise.translation_hint or "",
            self._update_translation_hint
        )
        
        self.layout.addWidget(self._create_separator())
        self.layout.addWidget(QLabel("Available Options for Blank (will be shuffled in app, include the correct one):"))
        
        # --- New QListWidget for options ---
        self.options_list_widget = QListWidget()
        self.options_list_widget.itemDoubleClicked.connect(self._edit_selected_option_dialog) # Edit on double-click
        self.layout.addWidget(self.options_list_widget)

        # --- Buttons for option management ---
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
        
        self._populate_options_list() # Initial population
        self._sync_correct_option_to_options_list() # Ensure correct option is in the list
        self.layout.addStretch(1)


    def _update_sentence_template(self, text: str):
        self.exercise.sentence_template = text
        self.data_changed.emit()

    def _update_correct_option_text(self, text: str): # Renamed method
        self.exercise.correct_option = text.strip()
        self._sync_correct_option_to_options_list() # Ensure it's in the options list
        self.data_changed.emit()

    def _update_translation_hint(self, text: str):
        self.exercise.translation_hint = text
        self.data_changed.emit()

    def _populate_options_list(self):
        self.options_list_widget.clear()
        # self.exercise.options is List[ExerciseOption], but for FIB, 'correct' flag on ExerciseOption is not used.
        # We only care about the text.
        for option_obj in self.exercise.options:
            list_item = QListWidgetItem(option_obj.text)
            list_item.setData(Qt.UserRole, option_obj) # Store the ExerciseOption object
            self.options_list_widget.addItem(list_item)

    def _sync_correct_option_to_options_list(self):
        """Ensures the self.exercise.correct_option text is present in self.exercise.options list."""
        correct_text = self.exercise.correct_option
        if correct_text and correct_text.strip():
            found = any(opt.text == correct_text for opt in self.exercise.options)
            if not found:
                # Add the correct option to the list of options if not already present
                # For FIB, the ExerciseOption's 'correct' flag is irrelevant, only its text matters.
                self.exercise.options.append(ExerciseOption(text=correct_text, correct=False))
                self._populate_options_list() # Re-populate to reflect addition
                self.data_changed.emit() # Data has changed


    def _add_option_dialog(self):
        option_text, ok = QInputDialog.getText(self, "Add Option", "Enter option text:")
        if ok and option_text and option_text.strip():
            # Avoid adding duplicates directly, though user can edit to create duplicates
            if not any(opt.text == option_text.strip() for opt in self.exercise.options):
                # For FIB, the 'correct' flag on ExerciseOption is not used for display/logic,
                # only the text. The main exercise.correct_option field is authoritative.
                self.exercise.options.append(ExerciseOption(text=option_text.strip(), correct=False))
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
        
        new_text, ok = QInputDialog.getText(self, "Edit Option", "Enter new option text:", text=option_obj.text)
        if ok and new_text and new_text.strip():
            old_text = option_obj.text
            option_obj.text = new_text.strip()
            # If the edited option was the correct one, update self.exercise.correct_option
            if self.exercise.correct_option == old_text:
                self.exercise.correct_option = new_text.strip()
                # Update the QLineEdit for correct_option_text if it's visible and linked
                if hasattr(self, 'correct_option_text_input'):
                    self.correct_option_text_input.setText(new_text.strip())

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

        if option_obj.text == self.exercise.correct_option and len(self.exercise.options) <= 1:
            QMessageBox.warning(self, "Delete Option", "Cannot delete the only option if it's also the correct answer. Change the correct answer first or add more options.")
            return

        reply = QMessageBox.question(self, "Delete Option", f"Are you sure you want to delete option: '{option_obj.text}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            is_correct_deleted = (option_obj.text == self.exercise.correct_option)
            self.exercise.options.remove(option_obj)
            
            if is_correct_deleted:
                # If the correct option was deleted, clear it or prompt user
                self.exercise.correct_option = "" # Clear it
                if hasattr(self, 'correct_option_text_input'):
                     self.correct_option_text_input.setText("")
                QMessageBox.information(self, "Correct Option Deleted", "The correct option was deleted. Please specify a new correct option from the remaining choices.")

            self._populate_options_list()
            self.data_changed.emit()
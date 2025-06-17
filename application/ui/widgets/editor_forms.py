import logging
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QTextEdit, QComboBox, QGroupBox, 
    QVBoxLayout, QPushButton, QListWidget, QListWidgetItem, QCheckBox
)
from PySide6.QtCore import Signal, Qt
from typing import Any

from core.models import Exercise, Unit, Lesson, GlossaryEntry, ExerciseOption

logger = logging.getLogger(__name__)

class BaseEditorForm(QWidget):
    """Base class for all editor forms with common data handling."""
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_object = None

    def load_data(self, obj: Any):
        """Loads data from the given object into the form's widgets."""
        logger.debug(f"Loading data for object: {obj} into {self.__class__.__name__}")
        self.data_object = obj
        # Disconnect signals while loading data to prevent premature firing
        self._set_signals_blocked(True)
        self._populate_fields()
        self._set_signals_blocked(False)
    
    def _populate_fields(self):
        """Subclasses must implement this to set widget values from the data object."""
        logger.debug(f"Calling _populate_fields in {self.__class__.__name__} for {self.data_object}")
        raise NotImplementedError
    
    def _connect_signals(self):
        """Subclasses must implement this to connect widget signals to the data_changed signal."""
        logger.debug(f"Calling _connect_signals in {self.__class__.__name__}")
        raise NotImplementedError

    def _set_signals_blocked(self, blocked: bool):
        """Blocks or unblocks signals for all relevant widgets."""
        # This is a generic implementation; subclasses may need to be more specific
        for widget in self.findChildren(QWidget):
            if hasattr(widget, 'blockSignals'):
                # logger.debug(f"Setting blockSignals({blocked}) for widget: {widget.objectName()} in {self.__class__.__name__}")
                widget.blockSignals(blocked)

class UnitEditorForm(BaseEditorForm):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        self.id_input = QLineEdit()
        self.title_input = QLineEdit()
        layout.addRow("Unit ID:", self.id_input)
        layout.addRow("Title:", self.title_input)
        self._connect_signals()
    
    def _populate_fields(self):
        if isinstance(self.data_object, Unit):
            logger.debug(f"Populating UnitEditorForm with Unit ID: {self.data_object.unit_id}, Title: {self.data_object.title}")
            self.id_input.setText(self.data_object.unit_id or "")
            self.title_input.setText(self.data_object.title or "")
        else:
            logger.warning(f"Attempted to populate UnitEditorForm with non-Unit object: {type(self.data_object)}")

    def _connect_signals(self):
        logger.debug("Connecting signals for UnitEditorForm")
        self.id_input.textChanged.connect(self._on_id_changed)
        self.title_input.textChanged.connect(self._on_title_changed)

    def _on_id_changed(self, text):
        if self.data_object: self.data_object.unit_id = text; self.data_changed.emit(); logger.debug(f"Unit ID changed to: {text}")
    
    def _on_title_changed(self, text):
        if self.data_object: self.data_object.title = text; self.data_changed.emit(); logger.debug(f"Unit Title changed to: {text}")



class LessonEditorForm(BaseEditorForm):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        self.id_input = QLineEdit()
        self.title_input = QLineEdit()
        layout.addRow("Lesson ID:", self.id_input)
        layout.addRow("Title:", self.title_input)
        self._connect_signals()
    
    def _populate_fields(self):
        if isinstance(self.data_object, Lesson):
            logger.debug(f"Populating LessonEditorForm with Lesson ID: {self.data_object.lesson_id}, Title: {self.data_object.title}")
            self.id_input.setText(self.data_object.lesson_id or "")
            self.title_input.setText(self.data_object.title or "")
        else:
            logger.warning(f"Attempted to populate LessonEditorForm with non-Lesson object: {type(self.data_object)}")

    def _connect_signals(self):
        logger.debug("Connecting signals for LessonEditorForm")
        self.id_input.textChanged.connect(self._on_id_changed)
        self.title_input.textChanged.connect(self._on_title_changed)

    def _on_id_changed(self, text):
        if self.data_object: self.data_object.lesson_id = text; self.data_changed.emit(); logger.debug(f"Lesson ID changed to: {text}")
    
    def _on_title_changed(self, text):
        if self.data_object: self.data_object.title = text; self.data_changed.emit(); logger.debug(f"Lesson Title changed to: {text}")


class ExerciseEditorForm(BaseEditorForm):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        
        # General Fields
        form_layout = QFormLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "translate_to_target", "translate_to_source", "dictation",
            "multiple_choice_translation", "image_association", "listen_and_select",
            "fill_in_the_blank", "sentence_jumble", "context_block"
        ])
        self.title_input = QLineEdit() # For context_block
        self.prompt_input = QTextEdit()
        self.answer_input = QLineEdit()
        self.audio_input = QLineEdit()
        self.image_input = QLineEdit()
        
        form_layout.addRow("Type:", self.type_combo)
        form_layout.addRow("Title:", self.title_input)
        form_layout.addRow("Prompt/Content:", self.prompt_input)
        form_layout.addRow("Answer:", self.answer_input)
        form_layout.addRow("Audio File:", self.audio_input)
        form_layout.addRow("Image File:", self.image_input)
        self.main_layout.addLayout(form_layout)

        # Type-specific field groups
        self._setup_mcq_group()
        self._setup_jumble_group()

        self._connect_signals()

    def _setup_mcq_group(self):
        self.mcq_group = QGroupBox("Multiple Choice Options")
        layout = QVBoxLayout(self.mcq_group)
        self.options_list = QListWidget()
        layout.addWidget(self.options_list)
        self.main_layout.addWidget(self.mcq_group)

    def _setup_jumble_group(self):
        self.jumble_group = QGroupBox("Sentence Jumble Words")
        layout = QVBoxLayout(self.jumble_group)
        self.words_input = QTextEdit() # One word per line
        self.words_input.setPlaceholderText("Enter one word or phrase per line.")
        layout.addWidget(self.words_input)
        self.main_layout.addWidget(self.jumble_group)

    def _populate_fields(self):
        if not isinstance(self.data_object, Exercise):
            logger.warning(f"Attempted to populate ExerciseEditorForm with non-Exercise object: {type(self.data_object)}")
            return
        
        ex = self.data_object
        self.type_combo.setCurrentText(ex.type)
        self.title_input.setText(ex.title or "")
        self.prompt_input.setPlainText(ex.prompt or "")
        self.answer_input.setText(ex.answer or "")
        self.audio_input.setText(ex.audio_file or "")
        self.image_input.setText(ex.image_file or "")
        logger.debug(f"Populating ExerciseEditorForm for exercise type: {ex.type}, title: {ex.title}")

        # Populate MCQ options
        self.options_list.clear()
        if ex.options:
            for opt in ex.options:
                item = QListWidgetItem(opt.text)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if opt.correct else Qt.Unchecked)
                self.options_list.addItem(item)
            logger.debug(f"Populated {len(ex.options)} MCQ options.")
        
        # Populate Jumble words
        self.words_input.setPlainText("\n".join(ex.words) if ex.words else "")
        if ex.words: logger.debug(f"Populated {len(ex.words)} jumble words.")

        self._update_visible_fields(ex.type)

    def _connect_signals(self):
        logger.debug("Connecting signals for ExerciseEditorForm")
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        self.title_input.textChanged.connect(self._on_field_changed)
        self.prompt_input.textChanged.connect(self._on_field_changed)
        self.answer_input.textChanged.connect(self._on_field_changed)
        self.audio_input.textChanged.connect(self._on_field_changed)
        self.image_input.textChanged.connect(self._on_field_changed)
        self.words_input.textChanged.connect(self._on_field_changed)
        self.options_list.itemChanged.connect(self._on_field_changed)
    
    def _on_type_changed(self, new_type: str):
        if self.data_object:
            self.data_object.type = new_type
            logger.debug(f"Exercise type changed to: {new_type}. Updating visible fields.")
            self._update_visible_fields(new_type)
            self.data_changed.emit()
            logger.debug("data_changed emitted due to type change.")

    def _on_field_changed(self):
        if not self.data_object:
            return
        # This is a generic handler. We just save everything.
        ex = self.data_object
        ex.title = self.title_input.text() or None
        ex.prompt = self.prompt_input.toPlainText() or None
        ex.answer = self.answer_input.text() or None
        ex.audio_file = self.audio_input.text() or None
        ex.image_file = self.image_input.text() or None
        ex.words = [line for line in self.words_input.toPlainText().split('\n') if line.strip()]
        
        # For options, we need to rebuild the list
        ex.options = []
        for i in range(self.options_list.count()):
            item = self.options_list.item(i)
            ex.options.append(ExerciseOption(
                text=item.text(),
                correct=item.checkState() == Qt.Checked
            ))
        logger.debug(f"Exercise field changed. Title: {ex.title}, Prompt: {ex.prompt is not None}, Answer: {ex.answer}, Audio: {ex.audio_file}, Image: {ex.image_file}, NumWords: {len(ex.words)}, NumOptions: {len(ex.options)}")
        self.data_changed.emit()
        logger.debug("data_changed emitted due to field change.")
    
    def _update_visible_fields(self, ex_type: str):
        logger.debug(f"Updating visible fields for exercise type: {ex_type}")
        """Show/hide fields based on the selected exercise type."""
        is_translation = ex_type in ["translate_to_target", "translate_to_source", "dictation"]
        is_mcq = ex_type in ["multiple_choice_translation", "image_association", "listen_and_select"]
        is_jumble = ex_type == "sentence_jumble"
        is_context = ex_type == "context_block"

        self.mcq_group.setVisible(is_mcq)
        logger.debug(f"MCQ group visible: {is_mcq}")
        self.jumble_group.setVisible(is_jumble)
        logger.debug(f"Jumble group visible: {is_jumble}")
        self.answer_input.setVisible(is_translation or is_jumble)
        logger.debug(f"Answer input visible: {is_translation or is_jumble}")
        self.title_input.setVisible(is_context)
        logger.debug(f"Title input visible: {is_context}")
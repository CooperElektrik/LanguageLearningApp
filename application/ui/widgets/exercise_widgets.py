from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QRadioButton, QButtonGroup, QHBoxLayout, QScrollArea,
                               QFrame)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
import random

from core.models import Exercise # Assuming core is a sibling directory or in PYTHONPATH

class BaseExerciseWidget(QWidget):
    answer_submitted = Signal(str) # Emits the user's answer string

    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(parent)
        self.exercise = exercise
        self.course_manager = course_manager # To get formatted prompts
        self.layout = QVBoxLayout(self)
        self.prompt_label = QLabel()
        self.prompt_label.setFont(QFont("Arial", 14))
        self.prompt_label.setWordWrap(True)
        self.layout.addWidget(self.prompt_label)

    def get_answer(self) -> str:
        raise NotImplementedError("Subclasses must implement get_answer")

    def clear_input(self):
        raise NotImplementedError("Subclasses must implement clear_input")
    
    def set_focus_on_input(self):
        pass # Subclasses can implement this

class TranslationExerciseWidget(BaseExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        
        formatted_prompt = self.course_manager.get_formatted_prompt(self.exercise)
        self.prompt_label.setText(formatted_prompt)

        self.answer_input = QLineEdit()
        self.answer_input.setFont(QFont("Arial", 12))
        self.layout.addWidget(self.answer_input)
        self.answer_input.returnPressed.connect(lambda: self.answer_submitted.emit(self.get_answer()))


    def get_answer(self) -> str:
        return self.answer_input.text()

    def clear_input(self):
        self.answer_input.clear()
        
    def set_focus_on_input(self):
        self.answer_input.setFocus()


class MultipleChoiceExerciseWidget(BaseExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)

        formatted_prompt = self.course_manager.get_formatted_prompt(self.exercise)
        self.prompt_label.setText(formatted_prompt)
        
        self.options_group = QButtonGroup(self)
        self.options_layout = QVBoxLayout()

        # Shuffle options before displaying if they are not already pre-shuffled with correct flags
        # Note: core.course_loader._parse_exercise already shuffles for FIB, not for MC.
        # For MC, the order from YAML is usually intentional. If shuffling is desired for MC, do it here.
        # options_to_display = random.sample(self.exercise.options, len(self.exercise.options))
        options_to_display = self.exercise.options


        for i, option in enumerate(options_to_display):
            rb = QRadioButton(option.text)
            rb.setFont(QFont("Arial", 12))
            self.options_layout.addWidget(rb)
            self.options_group.addButton(rb, i) # Use index as ID

        self.layout.addLayout(self.options_layout)
        self.options_group.buttonClicked.connect(lambda: self.answer_submitted.emit(self.get_answer()))


    def get_answer(self) -> str:
        checked_button = self.options_group.checkedButton()
        return checked_button.text() if checked_button else ""

    def clear_input(self):
        # For radio buttons, effectively means unchecking, but usually one stays checked.
        # Or disable submission until one is re-selected.
        # For now, this might not be strictly needed or could reset to no selection if allowed.
        checked_button = self.options_group.checkedButton()
        if checked_button:
            self.options_group.setExclusive(False) # Allow unchecking
            checked_button.setChecked(False)
            self.options_group.setExclusive(True) # Restore exclusive behavior
            
    def set_focus_on_input(self):
        if self.options_group.buttons():
            self.options_group.buttons()[0].setFocus()


class FillInTheBlankExerciseWidget(BaseExerciseWidget):
    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(exercise, course_manager, parent)
        
        formatted_prompt = self.course_manager.get_formatted_prompt(self.exercise)
        self.prompt_label.setText(formatted_prompt)

        # Display options as radio buttons
        self.options_group = QButtonGroup(self)
        self.options_layout = QVBoxLayout() # Could be QHBoxLayout for fewer options

        # Options are already shuffled with 'correct' flag by course_loader
        for i, option in enumerate(self.exercise.options):
            rb = QRadioButton(option.text)
            rb.setFont(QFont("Arial", 12))
            self.options_layout.addWidget(rb)
            self.options_group.addButton(rb, i)
        
        self.layout.addLayout(self.options_layout)
        self.options_group.buttonClicked.connect(lambda: self.answer_submitted.emit(self.get_answer()))

    def get_answer(self) -> str:
        checked_button = self.options_group.checkedButton()
        return checked_button.text() if checked_button else ""

    def clear_input(self):
        checked_button = self.options_group.checkedButton()
        if checked_button:
            self.options_group.setExclusive(False)
            checked_button.setChecked(False)
            self.options_group.setExclusive(True)
            
    def set_focus_on_input(self):
        if self.options_group.buttons():
            self.options_group.buttons()[0].setFocus()
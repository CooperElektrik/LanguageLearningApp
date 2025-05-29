import logging, os, sys

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QRadioButton, QButtonGroup, QPushButton, QMessageBox)
from PySide6.QtCore import Signal, QUrl
from PySide6.QtGui import QFont
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from core.models import Exercise

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class BaseExerciseWidget(QWidget):
    answer_submitted = Signal(str) # Emits the user's answer string

    def __init__(self, exercise: Exercise, course_manager, parent=None):
        super().__init__(parent)
        self.exercise = exercise
        self.course_manager = course_manager # To get formatted prompts
        self.course_content_base_dir = self.course_manager.get_course_content_directory()
        self.layout = QVBoxLayout(self)
        self.prompt_label = QLabel()
        self.prompt_label.setFont(QFont("Arial", 14))
        self.prompt_label.setWordWrap(True)
        self.layout.addWidget(self.prompt_label)

        self.assets_base_dir = self.course_manager.get_course_manifest_directory()
        if not self.assets_base_dir: # Fallback if manifest path not set
             self.assets_base_dir = self.course_manager.get_course_content_directory()
             if self.assets_base_dir:
                 logging.warning("Using content directory as asset base. Manifest directory preferred.")
             else:
                 logging.error("Could not determine asset base directory.")

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

        if self.exercise.audio_file:
            logger.info(f"Created play button from {self.exercise.audio_file}")
            self.play_audio_button = QPushButton("🔊 Play Audio")
            self.play_audio_button.clicked.connect(self._play_audio)
            self.layout.addWidget(self.play_audio_button)
            
            self._media_player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._media_player.setAudioOutput(self._audio_output)

        self.answer_input = QLineEdit()
        self.answer_input.setFont(QFont("Arial", 12))
        self.layout.addWidget(self.answer_input)
        self.answer_input.returnPressed.connect(lambda: self.answer_submitted.emit(self.get_answer()))

    def _play_audio(self):
        if self.exercise.audio_file and hasattr(self, '_media_player'):
            if self.assets_base_dir: # Use the new assets_base_dir
                full_audio_path = os.path.join(self.assets_base_dir, self.exercise.audio_file)
            else: 
                full_audio_path = self.exercise.audio_file 
                logging.warning(f"Asset base directory not set. Trying to play audio from: {full_audio_path}")


            if os.path.exists(full_audio_path):
                self._media_player.setSource(QUrl.fromLocalFile(full_audio_path))
                if self._media_player.error() == QMediaPlayer.NoError:
                    self._media_player.play()
                else:
                    logging.error(f"Error setting media source for {full_audio_path}: {self._media_player.errorString()}")
                    QMessageBox.warning(self, "Audio Error", f"Cannot play audio: {self._media_player.errorString()}")

            else:
                logging.error(f"Audio file not found: {full_audio_path}")
                QMessageBox.warning(self, "Audio Error", f"Audio file not found: {self.exercise.audio_file}\n\nCheck paths.")

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
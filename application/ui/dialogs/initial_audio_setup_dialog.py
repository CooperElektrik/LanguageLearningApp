import logging
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QMessageBox
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtCore import QSettings
from application import settings as app_settings

logger = logging.getLogger(__name__)

class InitialAudioSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Initial Audio Setup"))
        self.setModal(True)
        self.setMinimumWidth(450)
        self.q_settings = QSettings()

        main_layout = QVBoxLayout(self)

        info_label = QLabel(self.tr(
            "Welcome! To enable pronunciation exercises, please configure your audio settings.\n"
            "You can change these later in the main settings menu."
        ))
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

        # Microphone selection
        mic_label = QLabel(self.tr("Select your microphone:"))
        self.mic_combo = QComboBox()
        self._populate_audio_input_devices()
        main_layout.addWidget(mic_label)
        main_layout.addWidget(self.mic_combo)

        # Whisper model selection
        whisper_label = QLabel(self.tr("Select a speech recognition model:"))
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems(["None"] + app_settings.WHISPER_MODELS_AVAILABLE)
        self.whisper_combo.setToolTip(self.tr(
            "'None' will disable pronunciation exercises. 'base' is fastest, 'medium' is most accurate. "
            "The model will be downloaded on first use."
        ))
        # Set a sensible default for first-time users
        self.whisper_combo.setCurrentText(app_settings.WHISPER_MODEL_DEFAULT)
        main_layout.addWidget(whisper_label)
        main_layout.addWidget(self.whisper_combo)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.save_and_accept)
        main_layout.addWidget(buttons)

    def _populate_audio_input_devices(self):
        default_device = QMediaDevices.defaultAudioInput()
        for device in QMediaDevices.audioInputs():
            self.mic_combo.addItem(device.description(), userData=device.id().toStdString())
        
        if not default_device.isNull():
            index = self.mic_combo.findData(default_device.id().toStdString())
            if index != -1:
                self.mic_combo.setCurrentIndex(index)

    def save_and_accept(self):
        # Save microphone choice
        selected_mic_id = self.mic_combo.currentData()
        self.q_settings.setValue(app_settings.QSETTINGS_KEY_AUDIO_INPUT_DEVICE, selected_mic_id)
        logger.info(f"Initial setup: Saved audio input device ID: {selected_mic_id}")

        # Save Whisper model choice
        selected_model = self.whisper_combo.currentText()
        self.q_settings.setValue(app_settings.QSETTINGS_KEY_WHISPER_MODEL, selected_model if selected_model != "None" else "")
        logger.info(f"Initial setup: Saved Whisper model selection: {selected_model}")
        
        # Mark setup as done
        self.q_settings.setValue(app_settings.QSETTINGS_KEY_INITIAL_AUDIO_SETUP_DONE, True)

        if selected_model != "None":
            QMessageBox.information(self, self.tr("Model Download"), self.tr(
                "The selected speech recognition model will be downloaded the first time you start a pronunciation exercise. "
                "This may take several minutes depending on the model size and your internet connection."
            ))
        
        self.accept()
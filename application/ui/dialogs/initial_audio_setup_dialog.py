import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QDialogButtonBox,
    QMessageBox,
)
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtCore import QSettings, Qt
import settings as app_settings

try:
    import torch

    IS_CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    IS_CUDA_AVAILABLE = False
    torch = None  # Prevent linting errors if torch is used elsewhere conditionally


logger = logging.getLogger(__name__)


class InitialAudioSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Initial Audio Setup"))
        self.setModal(True)
        self.setMinimumWidth(450)
        self.q_settings = QSettings()

        main_layout = QVBoxLayout(self)

        info_label = QLabel(
            self.tr(
                "Welcome! To enable pronunciation exercises, please configure your audio settings.\n"
                "You can change these later in the main settings menu."
            )
        )
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
        self._populate_whisper_models()

        self.whisper_combo.setCurrentText(app_settings.WHISPER_MODEL_DEFAULT)
        main_layout.addWidget(whisper_label)
        main_layout.addWidget(self.whisper_combo)

        # Add a note about CUDA build requirements
        cuda_note_label = QLabel(
            self.tr(
                "<i><b>Note:</b> For GPU acceleration (recommended for Medium model), "
                "the application must be run from an environment with a CUDA-enabled PyTorch build. "
                "Otherwise, models will run on the CPU.</i>"
            )
        )
        cuda_note_label.setWordWrap(True)
        main_layout.addWidget(cuda_note_label)

        # Add CUDA availability status
        if IS_CUDA_AVAILABLE:
            cuda_status_text = self.tr(
                "<b>CUDA Status:</b> <font color='green'>Available</font>"
            )
        else:
            cuda_status_text = self.tr(
                "<b>CUDA Status:</b> <font color='red'>Not Available</font>"
            )

        cuda_status_label = QLabel(cuda_status_text)
        main_layout.addWidget(cuda_status_label)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.save_and_accept)
        main_layout.addWidget(buttons)

    def _populate_audio_input_devices(self):
        default_device = QMediaDevices.defaultAudioInput()
        for device in QMediaDevices.audioInputs():
            self.mic_combo.addItem(
                device.description(), userData=device.id().toStdString()
            )

        if not default_device.isNull():
            index = self.mic_combo.findData(default_device.id().toStdString())
            if index != -1:
                self.mic_combo.setCurrentIndex(index)

    def _populate_whisper_models(self):
        """Populates the Whisper model combo box with detailed tooltips."""
        self.whisper_combo.addItem("None", userData="None")  # Option to disable

        for model_name, info in app_settings.WHISPER_MODEL_INFO.items():
            self.whisper_combo.addItem(model_name, userData=model_name)
            # Set the tooltip for the item we just added
            tooltip_text = self.tr(
                "Model: {model_name}\n"
                "Size: {size}\n"
                "Parameters: {params}\n"
                "Recommended Device: {device_rec}"
            ).format(
                **info, model_name=model_name
            )  # Unpack dict and add model_name

            self.whisper_combo.setItemData(
                self.whisper_combo.count() - 1,
                tooltip_text,
                Qt.ItemDataRole.ToolTipRole,
            )

    def save_and_accept(self):
        # Save microphone choice
        selected_mic_id = self.mic_combo.currentData()
        self.q_settings.setValue(
            app_settings.QSETTINGS_KEY_AUDIO_INPUT_DEVICE, selected_mic_id
        )
        logger.info(f"Initial setup: Saved audio input device ID: {selected_mic_id}")

        # Save Whisper model choice
        selected_model = self.whisper_combo.currentText()
        self.q_settings.setValue(
            app_settings.QSETTINGS_KEY_WHISPER_MODEL,
            selected_model if selected_model != "None" else "",
        )
        logger.info(f"Initial setup: Saved Whisper model selection: {selected_model}")

        # Mark setup as done
        self.q_settings.setValue(
            app_settings.QSETTINGS_KEY_INITIAL_AUDIO_SETUP_DONE, True
        )

        if selected_model != "None":
            QMessageBox.information(
                self,
                self.tr("Model Download"),
                self.tr(
                    "The selected speech recognition model will be downloaded the first time you start a pronunciation exercise. "
                    "This may take several minutes depending on the model size and your internet connection."
                ),
            )

        self.accept()

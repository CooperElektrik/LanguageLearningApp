import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QDialogButtonBox,
    QMessageBox,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtCore import QSettings, Qt
import settings as app_settings

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

        # STT Engine Selection
        stt_engine_label = QLabel(self.tr("Select Speech Recognition Engine:"))
        self.stt_engine_combo = QComboBox()
        self.stt_engine_combo.addItems(app_settings.STT_ENGINES_AVAILABLE)
        self.stt_engine_combo.currentTextChanged.connect(self._on_stt_engine_changed)
        main_layout.addWidget(stt_engine_label)
        main_layout.addWidget(self.stt_engine_combo)

        # Whisper-specific widgets
        self.whisper_label = QLabel(self.tr("Whisper Model:"))
        self.whisper_combo = QComboBox()
        self._populate_whisper_models()
        main_layout.addWidget(self.whisper_label)
        main_layout.addWidget(self.whisper_combo)

        # VOSK-specific widgets
        self.vosk_label = QLabel(self.tr("VOSK Model:"))
        self.vosk_combo = QComboBox()
        self._populate_vosk_models()
        main_layout.addWidget(self.vosk_label)
        main_layout.addWidget(self.vosk_combo)

        # CUDA Status Layout (for Whisper)
        cuda_layout = QHBoxLayout()
        self.cuda_status_label = QLabel(self.tr("CUDA Status: Unknown"))
        cuda_layout.addWidget(self.cuda_status_label)

        self.check_cuda_button = QPushButton(self.tr("Check Now"))
        self.check_cuda_button.clicked.connect(self.check_cuda_availability)
        cuda_layout.addWidget(self.check_cuda_button)
        main_layout.addLayout(cuda_layout)

        # Set initial selections and visibility
        self.stt_engine_combo.setCurrentText(app_settings.STT_ENGINE_DEFAULT)
        self._on_stt_engine_changed(app_settings.STT_ENGINE_DEFAULT) # Manually trigger to set initial visibility

        # Set initial model selections based on settings or defaults
        current_whisper_model = self.q_settings.value(
            app_settings.QSETTINGS_KEY_WHISPER_MODEL,
            app_settings.WHISPER_MODEL_DEFAULT,
            type=str,
        )
        # Find the index by userData (model name) and set it
        whisper_index = self.whisper_combo.findData(current_whisper_model)
        if whisper_index != -1:
            self.whisper_combo.setCurrentIndex(whisper_index)
        else:
            self.whisper_combo.setCurrentText("None") # Fallback if default not found

        current_vosk_model = self.q_settings.value(
            app_settings.QSETTINGS_KEY_VOSK_MODEL,
            app_settings.VOSK_MODEL_DEFAULT,
            type=str,
        )
        vosk_index = self.vosk_combo.findData(current_vosk_model)
        if vosk_index != -1:
            self.vosk_combo.setCurrentIndex(vosk_index)
        else:
            self.vosk_combo.setCurrentText("None") # Fallback if default not found

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

        from application.core.whisper_engine import check_whisper_model_downloaded

        for model_name, info in app_settings.WHISPER_MODEL_INFO.items():
            display_name = model_name
            if check_whisper_model_downloaded(model_name):
                display_name += self.tr(" (Downloaded)")
            else:
                display_name += self.tr(" (Not Downloaded)")

            self.whisper_combo.addItem(display_name, userData=model_name)
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

    def _populate_vosk_models(self):
        """Populates the VOSK model combo box with detailed tooltips."""
        self.vosk_combo.addItem("None", userData="None")  # Option to disable

        # No download check for VOSK models currently, as they are expected to be present
        # or downloaded by the STTManager.
        for model_name, info in app_settings.VOSK_MODEL_INFO.items():
            self.vosk_combo.addItem(model_name, userData=model_name)
            # Set the tooltip for the item we just added
            tooltip_text = self.tr(
                "Model: {model_name}\n"
                "Size: {size}\n"
                "Language: {lang}\n"
                "Description: {description}"
            ).format(**info, model_name=model_name)
            self.vosk_combo.setItemData(
                self.vosk_combo.count() - 1,
                tooltip_text,
                Qt.ItemDataRole.ToolTipRole,
            )

    def _on_stt_engine_changed(self, engine_name: str):
        """Toggles visibility of Whisper/VOSK specific settings based on selected engine."""
        is_whisper = (engine_name == app_settings.STT_ENGINE_WHISPER)
        is_vosk = (engine_name == app_settings.STT_ENGINE_VOSK)

        self.whisper_label.setVisible(is_whisper)
        self.whisper_combo.setVisible(is_whisper)
        self.cuda_status_label.setVisible(is_whisper)
        self.check_cuda_button.setVisible(is_whisper)

        self.vosk_label.setVisible(is_vosk)
        self.vosk_combo.setVisible(is_vosk)

    def save_and_accept(self):
        # Save microphone choice
        selected_mic_id = self.mic_combo.currentData()
        self.q_settings.setValue(
            app_settings.QSETTINGS_KEY_AUDIO_INPUT_DEVICE, selected_mic_id
        )
        logger.info(f"Initial setup: Saved audio input device ID: {selected_mic_id}")

        # Save STT Engine choice
        selected_engine = self.stt_engine_combo.currentText()
        self.q_settings.setValue(
            app_settings.QSETTINGS_KEY_STT_ENGINE, selected_engine
        )
        logger.info(f"Initial setup: Saved STT engine selection: {selected_engine}")

        # Save model choice based on selected engine
        if selected_engine == app_settings.STT_ENGINE_WHISPER:
            selected_model = self.whisper_combo.currentData()
            self.q_settings.setValue(
                app_settings.QSETTINGS_KEY_WHISPER_MODEL,
                selected_model if selected_model != "None" else "",
            )
            logger.info(f"Initial setup: Saved Whisper model selection: {selected_model}")
            if selected_model != "None":
                QMessageBox.information(
                    self,
                    self.tr("Model Download"),
                    self.tr(
                        "The selected speech recognition model will be downloaded the first time you start a pronunciation exercise. "
                        "This may take several minutes depending on the model size and your internet connection."
                    ),
                )
        elif selected_engine == app_settings.STT_ENGINE_VOSK:
            selected_model = self.vosk_combo.currentData()
            self.q_settings.setValue(
                app_settings.QSETTINGS_KEY_VOSK_MODEL,
                selected_model if selected_model != "None" else "",
            )
            logger.info(f"Initial setup: Saved VOSK model selection: {selected_model}")
            if selected_model != "None":
                QMessageBox.information(
                    self,
                    self.tr("Model Download"),
                    self.tr(
                        "The selected VOSK model will be extracted the first time you start a pronunciation exercise. Subsequent loads will be faster."
                    ),
                )

        # Mark setup as done
        self.q_settings.setValue(
            app_settings.QSETTINGS_KEY_INITIAL_AUDIO_SETUP_DONE, True
        )

        self.accept()

    def check_cuda_availability(self):
        """Checks for PyTorch and CUDA availability and updates the label."""
        self.cuda_status_label.setText(self.tr("Checking..."))
        try:
            from application.core.whisper_engine import _TORCH_AVAILABLE

            if _TORCH_AVAILABLE:
                import torch # type: ignore
                if torch.cuda.is_available():
                    self.cuda_status_label.setText(self.tr("CUDA Status: Available"))
                else:
                    self.cuda_status_label.setText(
                        self.tr("CUDA Status: Not Available (PyTorch installed)")
                    )
            else:
                self.cuda_status_label.setText(
                    self.tr("CUDA Status: Not Available (PyTorch not installed)")
                )
        except Exception:
            self.cuda_status_label.setText(
                self.tr("CUDA Status: Not Available (Error checking PyTorch)")
            )

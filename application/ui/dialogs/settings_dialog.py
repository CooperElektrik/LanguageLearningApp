import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGroupBox,
    QCheckBox,
    QSlider,
    QLabel,
    QDialogButtonBox,
    QHBoxLayout,
    QComboBox,
    QFormLayout,
    QPushButton,
    QMessageBox,
)
from PySide6.QtMultimedia import QMediaDevices  # Added for audio device listing
from PySide6.QtCore import Qt, QSettings, Signal, QEvent

import settings
import utils

from core.stt_manager import STTManager

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):

    theme_changed = Signal(str)  # Emitted when the theme is changed
    font_size_changed = Signal(int)  # Emitted when font size slider changes
    locale_changed = Signal(
        str
    )  # Emitted when locale is changed (sends locale code e.g. "en", "vi", or "System")

    def __init__(self, stt_manager: STTManager, parent=None):
        super().__init__(parent)
        self.stt_manager = stt_manager
        self.setWindowTitle(self.tr("Settings"))
        self.setMinimumWidth(400)
        logger.info("SettingsDialog initialized.")

        self.q_settings = QSettings()

        main_layout = QVBoxLayout(self)

        # --- Audio Settings ---
        self.audio_group = QGroupBox(self.tr("Audio"))
        audio_layout = QVBoxLayout(self.audio_group)

        self.sound_enabled_checkbox = QCheckBox(self.tr("Enable sound effects"))
        audio_layout.addWidget(self.sound_enabled_checkbox)

        self.autoplay_audio_checkbox = QCheckBox(self.tr("Autoplay audio in exercises"))
        audio_layout.addWidget(self.autoplay_audio_checkbox)

        # Pronunciation/Microphone settings group (new, within Audio)
        self.pronunciation_settings_group = QGroupBox(
            self.tr("Pronunciation and Microphone")
        )
        self.pronunciation_settings_layout = QFormLayout(
            self.pronunciation_settings_group
        )

        self.stt_engine_combo = QComboBox()
        self.stt_engine_combo.addItems(settings.STT_ENGINES_AVAILABLE)
        self.stt_engine_combo.currentTextChanged.connect(self._on_stt_engine_changed)
        self.pronunciation_settings_layout.addRow(
            self.tr("STT Engine:"), self.stt_engine_combo
        )

        # Whisper-specific widgets
        self.whisper_model_combo = QComboBox()
        self._populate_whisper_models()
        self.whisper_model_label = QLabel(self.tr("Whisper Model:"))
        self.pronunciation_settings_layout.addRow(
            self.whisper_model_label, self.whisper_model_combo
        )

        self.cuda_availability_label = QLabel(self.tr("Unknown"))
        self.cuda_availability_label.setObjectName("cuda_availability_label")
        self.check_cuda_button = QPushButton(self.tr("Check Now"))
        self.check_cuda_button.clicked.connect(self.check_cuda_availability)

        cuda_status_layout = QHBoxLayout()
        cuda_status_layout.addWidget(self.cuda_availability_label)
        cuda_status_layout.addWidget(self.check_cuda_button)
        self.cuda_status_label = QLabel(self.tr("CUDA Status:"))
        self.pronunciation_settings_layout.addRow(
            self.cuda_status_label, cuda_status_layout
        )

        # VOSK-specific widgets
        self.vosk_model_combo = QComboBox()
        self._populate_vosk_models()
        self.vosk_model_label = QLabel(self.tr("VOSK Model:"))
        self.pronunciation_settings_layout.addRow(
            self.vosk_model_label, self.vosk_model_combo
        )

        self.unload_model_button = QPushButton(self.tr("Unload Model from Memory"))
        self.unload_model_button.clicked.connect(self._unload_model)
        self.pronunciation_settings_layout.addRow(self.unload_model_button)

        self.audio_input_device_combo = QComboBox()
        self._populate_audio_input_devices()
        self.pronunciation_settings_layout.addRow(
            self.tr("Microphone Input Device:"), self.audio_input_device_combo
        )

        audio_layout.addWidget(
            self.pronunciation_settings_group
        )  # Add the new sub-group to the main audio layout

        volume_layout = QHBoxLayout()
        self.volume_label = QLabel(self.tr("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.valueChanged.connect(
            utils.update_sound_volume
        )  # Live update

        volume_layout.addWidget(self.volume_label)
        volume_layout.addWidget(self.volume_slider)
        audio_layout.addLayout(volume_layout)

        main_layout.addWidget(self.audio_group)

        # --- UI Settings ---
        # UI Settings (General, then Theme, then Font)
        self.ui_group = QGroupBox(self.tr("User Interface"))
        ui_layout = QFormLayout(self.ui_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(settings.AVAILABLE_THEMES.keys()))
        ui_layout.addRow(self.tr("Theme:"), self.theme_combo)

        self.locale_combo = QComboBox()
        self._populate_locale_combo()
        ui_layout.addRow(self.tr("Language:"), self.locale_combo)

        # Font Size controls: label + slider + current value display
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setMinimum(8)  # Min font size
        self.font_size_slider.setMaximum(14)  # Max font size
        self.font_size_slider.setValue(settings.DEFAULT_FONT_SIZE)  # Initial value
        self.font_size_slider.valueChanged.connect(self._update_font_size_label)
        self.font_size_label = QLabel(
            str(settings.DEFAULT_FONT_SIZE) + " pt"
        )  # Initial label
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(self.font_size_slider)
        font_size_layout.addWidget(self.font_size_label)
        ui_layout.addRow(self.tr("Font Size:"), font_size_layout)
        font_size_note = QLabel(self.tr("Note: Themes that set font sizes explicitly cannot be changed."))
        font_size_note.setWordWrap(True)
        ui_layout.addRow(font_size_note)

        self.autoshow_hints_checkbox = QCheckBox(
            self.tr("Show hints automatically in exercises")
        )
        ui_layout.addRow(self.autoshow_hints_checkbox)  # Add as a new row

        self.reset_ui_button = QPushButton(self.tr("Reset UI Settings to Default"))
        self.reset_ui_button.clicked.connect(self._reset_ui_settings)
        ui_layout.addRow(self.reset_ui_button)  # Add as a new row
        main_layout.addWidget(self.ui_group)

        # --- Developer Settings ---
        self.dev_group = QGroupBox(self.tr("Developer"))
        dev_layout = QFormLayout(self.dev_group)

        self.dev_mode_checkbox = QCheckBox(self.tr("Enable Developer Mode"))
        self.dev_mode_checkbox.setToolTip(
            self.tr(
                "Requires application restart to take full effect for logging and some startup features."
            )
        )
        dev_layout.addRow(self.dev_mode_checkbox)

        self.reset_onboarding_button = QPushButton(
            self.tr("Reset Onboarding Message Flag")
        )
        self.reset_onboarding_button.setToolTip(
            self.tr(
                "Allows the onboarding message to be shown again the next time a course is loaded."
            )
        )
        self.reset_onboarding_button.clicked.connect(self._reset_onboarding_flag)
        dev_layout.addRow(self.reset_onboarding_button)

        main_layout.addWidget(self.dev_group)

        # --- Dialog Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.apply_settings
        )
        main_layout.addWidget(buttons)

        self.load_settings()

    def _populate_whisper_models(self):
        """Populates the Whisper model combo box with detailed tooltips."""
        self.whisper_model_combo.addItem("None", userData="None")  # Option to disable

        from application.core.whisper_engine import check_whisper_model_downloaded

        for model_name, info in settings.WHISPER_MODEL_INFO.items():
            display_name = model_name
            if check_whisper_model_downloaded(model_name):
                display_name += self.tr(" (Downloaded)")
            else:
                display_name += self.tr(" (Not Downloaded)")

            self.whisper_model_combo.addItem(display_name, userData=model_name)
            # Set the tooltip for the item we just added
            tooltip_text = self.tr(
                "Model: {model_name}\n"
                "Size: {size}\n"
                "Parameters: {params}\n"
                "Recommended Device: {device_rec}\n"
                "Expected processing time (CPU): {ptime}\n"
            ).format(**info, model_name=model_name)
            self.whisper_model_combo.setItemData(
                self.whisper_model_combo.count() - 1,
                tooltip_text,
                Qt.ItemDataRole.ToolTipRole,
            )

    def _populate_vosk_models(self):
        """Populates the VOSK model combo box with detailed tooltips."""
        self.vosk_model_combo.addItem("None", userData="None")  # Option to disable

        for model_name, info in settings.VOSK_MODEL_INFO.items():
            self.vosk_model_combo.addItem(model_name, userData=model_name)
            # Set the tooltip for the item we just added
            tooltip_text = self.tr(
                "Model: {model_name}\n"
                "Size: {size}\n"
                "Language: {lang}\n"
                "Description: {description}\n"
            ).format(**info, model_name=model_name)
            self.vosk_model_combo.setItemData(
                self.vosk_model_combo.count() - 1,
                tooltip_text,
                Qt.ItemDataRole.ToolTipRole,
            )

    def _populate_audio_input_devices(self):
        """Populates the audio input device combo box."""
        # QMediaDevices is imported at the top of the file

        self.audio_input_device_combo.clear()
        default_device_info = QMediaDevices.defaultAudioInput()  # QAudioDevice object
        default_device_id_str = (
            default_device_info.id().toStdString()
            if not default_device_info.isNull()
            else ""
        )

        for device in QMediaDevices.audioInputs():
            # Store device.id().toStdString() (str) as userData, display description()
            self.audio_input_device_combo.addItem(
                device.description(), userData=device.id().toStdString()
            )
            if device.id().toStdString() == default_device_id_str:
                self.audio_input_device_combo.setCurrentText(
                    device.description()
                )  # Set default

    def _populate_locale_combo(self):
        """Populates the locale combo box with available languages."""
        self.available_locales = utils.get_available_locales()  # Store for mapping
        # Sort by display name for user-friendliness, keeping "System" first
        sorted_display_names = sorted(
            self.available_locales.keys(),
            key=lambda x: (x != settings.DEFAULT_LOCALE, x),
        )
        for display_name in sorted_display_names:
            locale_code = self.available_locales[display_name]
            self.locale_combo.addItem(display_name, userData=locale_code)

    def load_settings(self):
        """Loads settings from QSettings and updates the UI controls."""
        sound_enabled = self.q_settings.value(
            settings.QSETTINGS_KEY_SOUND_ENABLED,
            settings.SOUND_EFFECTS_ENABLED_DEFAULT,
            type=bool,
        )
        self.sound_enabled_checkbox.setChecked(sound_enabled)

        autoplay_audio_enabled = self.q_settings.value(
            settings.QSETTINGS_KEY_AUTOPLAY_AUDIO,
            settings.AUTOPLAY_AUDIO_DEFAULT,
            type=bool,
        )
        self.autoplay_audio_checkbox.setChecked(autoplay_audio_enabled)

        # Load preferred audio input device
        default_audio_input_id = ""
        default_device_info = QMediaDevices.defaultAudioInput()
        if not default_device_info.isNull():
            default_audio_input_id = default_device_info.id().toStdString()

        preferred_device_id = self.q_settings.value(
            settings.QSETTINGS_KEY_AUDIO_INPUT_DEVICE, default_audio_input_id, type=str
        )
        # Find and set the selected device in the combo box
        index = self.audio_input_device_combo.findData(preferred_device_id)
        if index != -1:
            self.audio_input_device_combo.setCurrentIndex(index)
        elif (
            default_audio_input_id
        ):  # Fallback to current system default if saved one not found
            logger.warning(
                f"Preferred audio input device ID '{preferred_device_id}' not found. Defaulting to system default."
            )
            default_index = self.audio_input_device_combo.findData(
                default_audio_input_id
            )
            if default_index != -1:
                self.audio_input_device_combo.setCurrentIndex(default_index)
        else:
            logger.warning(
                f"Preferred audio input device ID '{preferred_device_id}' not found and no system default available."
            )

        current_whisper_model = self.q_settings.value(
            settings.QSETTINGS_KEY_WHISPER_MODEL,
            settings.WHISPER_MODEL_DEFAULT,
            type=str,
        )
        self.whisper_model_combo.setCurrentText(
            current_whisper_model if current_whisper_model else "None"
        )

        current_vosk_model = self.q_settings.value(
            settings.QSETTINGS_KEY_VOSK_MODEL,
            settings.VOSK_MODEL_DEFAULT,
            type=str,
        )
        self.vosk_model_combo.setCurrentText(
            current_vosk_model if current_vosk_model else "None"
        )

        current_stt_engine = self.q_settings.value(
            settings.QSETTINGS_KEY_STT_ENGINE,
            settings.STT_ENGINE_DEFAULT,
            type=str,
        )
        self.stt_engine_combo.setCurrentText(current_stt_engine)
        self._on_stt_engine_changed(current_stt_engine) # Manually trigger to set visibility

        autoshow_hints_enabled = self.q_settings.value(
            settings.QSETTINGS_KEY_AUTOSHOW_HINTS,
            settings.AUTOSHOW_HINTS_DEFAULT,
            type=bool,
        )
        self.autoshow_hints_checkbox.setChecked(autoshow_hints_enabled)

        volume = self.q_settings.value(
            settings.QSETTINGS_KEY_SOUND_VOLUME, settings.SOUND_VOLUME_DEFAULT, type=int
        )

        # Load Font Size setting (default if not found)
        current_font_size = self.q_settings.value(
            settings.QSETTINGS_KEY_FONT_SIZE, settings.DEFAULT_FONT_SIZE, type=int
        )
        self.font_size_slider.setValue(current_font_size)

        self.volume_slider.setValue(volume)

        current_theme_name = self.q_settings.value(
            settings.QSETTINGS_KEY_UI_THEME,
            "Fancy Light",  # Default to "Fancy Light" theme
            type=str,
        )
        if current_theme_name in settings.AVAILABLE_THEMES:
            self.theme_combo.setCurrentText(current_theme_name)
        else:  # Handle case where saved theme is no longer available
            self.theme_combo.setCurrentText("System")
            logger.warning(
                f"Saved theme '{current_theme_name}' not found in available themes. Defaulting to 'System'."
            )

        current_locale_code = self.q_settings.value(
            settings.QSETTINGS_KEY_LOCALE, settings.DEFAULT_LOCALE, type=str  # "System"
        )
        # Find the display name for the saved locale code
        for display_name, code_val in self.available_locales.items():
            if code_val == current_locale_code:
                self.locale_combo.setCurrentText(display_name)
                break
        else:  # If saved code not found (e.g. qm file removed), default to "System"
            self.locale_combo.setCurrentText(settings.DEFAULT_LOCALE)

        dev_mode_enabled = self.q_settings.value(
            settings.QSETTINGS_KEY_DEVELOPER_MODE,
            settings.DEVELOPER_MODE_DEFAULT,
            type=bool,
        )
        self.dev_mode_checkbox.setChecked(dev_mode_enabled)

    def _update_font_size_label(self, value):
        """Update the font size label when the slider value changes."""
        self.font_size_label.setText(str(value) + " pt")
        self.font_size_changed.emit(value)  # Emit as live-update signal

    def _on_stt_engine_changed(self, engine_name: str):
        """Toggles visibility of Whisper/VOSK specific settings based on selected engine."""
        is_whisper = (engine_name == settings.STT_ENGINE_WHISPER)
        is_vosk = (engine_name == settings.STT_ENGINE_VOSK)

        self.whisper_model_label.setVisible(is_whisper)
        self.whisper_model_combo.setVisible(is_whisper)
        self.cuda_availability_label.setVisible(is_whisper)
        self.check_cuda_button.setVisible(is_whisper)
        self.cuda_status_label.setVisible(is_whisper)

        self.vosk_model_label.setVisible(is_vosk)
        self.vosk_model_combo.setVisible(is_vosk)

        # Unload button is always visible, but its action depends on the active engine
        # self.unload_model_button.setVisible(is_whisper or is_vosk)

    def _reset_ui_settings(self):
        """Resets UI related settings (theme, font size) to their defaults and applies them live."""
        # Reset theme
        self.theme_combo.setCurrentText(
            "Fancy Light"
        )  # Assuming "Fancy Light" is the default key
        self.theme_changed.emit("Fancy Light")

        # Reset font size
        self.font_size_slider.setValue(settings.DEFAULT_FONT_SIZE)
        # self._update_font_size_label(settings.DEFAULT_FONT_SIZE) # This will also emit font_size_changed

        # Reset locale
        self.locale_combo.setCurrentText(settings.DEFAULT_LOCALE)  # "System"
        self.locale_changed.emit(settings.DEFAULT_LOCALE)

        # Reset Developer Mode
        self.dev_mode_checkbox.setChecked(settings.DEVELOPER_MODE_DEFAULT)
        # Note: Developer mode changes often require a restart to fully apply (e.g., logging)

        QMessageBox.information(
            self,
            self.tr("UI Settings Reset"),
            self.tr(
                "Theme, font size and language have been reset to defaults. Click OK or Apply to save."
            ),
        )
        self.retranslateUi()  # Ensure dialog itself updates if language was reset

    def apply_settings(self):
        """Saves the current state of the UI controls to QSettings."""
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_SOUND_ENABLED,
            self.sound_enabled_checkbox.isChecked(),
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_AUTOPLAY_AUDIO,
            self.autoplay_audio_checkbox.isChecked(),
        )
        # Save selected audio input device
        selected_device_id = (
            self.audio_input_device_combo.currentData()
        )  # This is the ID string
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_AUDIO_INPUT_DEVICE, selected_device_id
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_STT_ENGINE,
            self.stt_engine_combo.currentText(),
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_WHISPER_MODEL,
            (
                self.whisper_model_combo.currentData()
                if self.whisper_model_combo.currentData() != "None"
                else ""
            ),
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_VOSK_MODEL,
            (
                self.vosk_model_combo.currentText()
                if self.vosk_model_combo.currentText() != "None"
                else ""
            ),
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_SOUND_VOLUME, self.volume_slider.value()
        )

        # Save Font Size setting
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_FONT_SIZE, self.font_size_slider.value()
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_AUTOSHOW_HINTS,
            self.autoshow_hints_checkbox.isChecked(),
        )
        utils.update_sound_volume()  # Ensure live update takes effect if slider was just moved

        selected_theme_name = self.theme_combo.currentText()
        self.q_settings.setValue(settings.QSETTINGS_KEY_UI_THEME, selected_theme_name)
        self.theme_changed.emit(selected_theme_name)  # Emit signal AFTER saving

        selected_locale_code = (
            self.locale_combo.currentData()
        )  # userData stores the code ("en", "vi", "System")
        self.q_settings.setValue(settings.QSETTINGS_KEY_LOCALE, selected_locale_code)
        self.locale_changed.emit(selected_locale_code)

        self.q_settings.setValue(
            settings.QSETTINGS_KEY_DEVELOPER_MODE, self.dev_mode_checkbox.isChecked()
        )

        logger.info("Settings applied.")

    def save_settings(self):
        """Applies the settings and closes the dialog."""
        self.apply_settings()
        self.accept()

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.setWindowTitle(self.tr("Settings"))

        # Audio Settings
        self.audio_group.setTitle(self.tr("Audio"))
        self.sound_enabled_checkbox.setText(self.tr("Enable sound effects"))

        self.unload_model_button.setText(self.tr("Unload Model from Memory"))

        self.pronunciation_settings_group.setTitle(
            self.tr("Pronunciation and Microphone")
        )
        # Retranslate labels within the QFormLayout for pronunciation settings
        stt_engine_label = self.pronunciation_settings_layout.labelForField(
            self.stt_engine_combo
        )
        if stt_engine_label:
            stt_engine_label.setText(self.tr("STT Engine:"))

        whisper_model_label = self.pronunciation_settings_layout.labelForField(
            self.whisper_model_combo
        )
        if whisper_model_label:
            whisper_model_label.setText(self.tr("Whisper Model:"))

        vosk_model_label = self.pronunciation_settings_layout.labelForField(
            self.vosk_model_combo
        )
        if vosk_model_label:
            vosk_model_label.setText(self.tr("VOSK Model:"))

        mic_label = self.pronunciation_settings_layout.labelForField(
            self.audio_input_device_combo
        )
        if mic_label:
            mic_label.setText(self.tr("Microphone Input Device:"))

        cuda_status_label = self.pronunciation_settings_layout.labelForField(
            self.cuda_availability_label
        )
        if cuda_status_label:
            cuda_status_label.setText(self.tr("CUDA Status:"))

        # Re-check the availability to update the text properly
        # self.check_cuda_availability() # This might be too slow to do here.

        self.autoplay_audio_checkbox.setText(self.tr("Autoplay audio in exercises"))
        # Assuming volume_label was defined as self.volume_label
        if hasattr(self, "volume_label") and isinstance(self.volume_label, QLabel):
            self.volume_label.setText(self.tr("Volume:"))

        # UI Settings
        self.ui_group.setTitle(self.tr("User Interface"))
        # Row labels in QFormLayout are tricky to retranslate directly without storing references.
        # For simplicity, we might accept that QFormLayout row labels don't auto-update
        # or we would need to store references to those QLabel objects.
        # self.ui_layout.labelForField(self.theme_combo).setText(self.tr("Theme:")) # Example if labels were stored
        self.autoshow_hints_checkbox.setText(
            self.tr("Show hints automatically in exercises")
        )
        self.reset_ui_button.setText(self.tr("Reset UI Settings to Default"))

        # Developer Settings
        self.dev_group.setTitle(self.tr("Developer"))
        self.dev_mode_checkbox.setText(self.tr("Enable Developer Mode"))
        self.reset_onboarding_button.setText(self.tr("Reset Onboarding Message Flag"))
        self.reset_onboarding_button.setToolTip(
            self.tr(
                "Allows the onboarding message to be shown again the next time a course is loaded."
            )
        )
        self.dev_mode_checkbox.setToolTip(
            self.tr(
                "Requires application restart to take full effect for logging and some startup features."
            )
        )
        # Dialog Buttons - standard buttons usually retranslate automatically.
        # If custom text was set, it would need retranslation.
        logger.debug("SettingsDialog retranslated.")

    def _reset_onboarding_flag(self):
        """Resets the onboarding seen flag in QSettings."""
        self.q_settings.setValue(settings.QSETTINGS_KEY_GLOBAL_ONBOARDING_SEEN, False)
        self.q_settings.setValue(settings.QSETTINGS_KEY_INITIAL_AUDIO_SETUP_DONE, False)
        self.q_settings.setValue(settings.QSETTINGS_KEY_INITIAL_UI_SETUP_DONE, False)
        logger.info(
            "Onboarding message flag has been reset. It will show again on the next course load."
        )
        QMessageBox.information(
            self,
            self.tr("Onboarding Reset"),
            self.tr(
                "The onboarding message flag has been reset.\nThe welcome guide will be shown the next time you load a course."
            ),
        )

    def _unload_model(self):
        selected_engine = self.stt_manager.get_selected_stt_engine()
        loaded_model_name = self.stt_manager.get_loaded_model_name()

        if selected_engine == settings.STT_ENGINE_WHISPER:
            if self.stt_manager._active_whisper_model_instance:
                self.stt_manager.unload_model()
                QMessageBox.information(
                    self,
                    self.tr("Model Unloaded"),
                    self.tr("Whisper model '{0}' has been unloaded from memory.").format(
                        loaded_model_name or "None"
                    ),
                )
            else:
                QMessageBox.information(
                    self,
                    self.tr("No Model Loaded"),
                    self.tr("No Whisper model is currently loaded."),
                )
        elif selected_engine == settings.STT_ENGINE_VOSK:
            if self.stt_manager._active_vosk_model_instance:
                self.stt_manager.unload_model()
                QMessageBox.information(
                    self,
                    self.tr("Model Unloaded"),
                    self.tr("VOSK model '{0}' has been unloaded from memory.").format(
                        loaded_model_name or "None"
                    ),
                )
            else:
                QMessageBox.information(
                    self,
                    self.tr("No Model Loaded"),
                    self.tr("No VOSK model is currently loaded."),
                )
        else:
            QMessageBox.warning(
                self,
                self.tr("Unknown Engine"),
                self.tr("Cannot unload model for unknown STT engine."),
            )

    def check_cuda_availability(self):
        """Checks for PyTorch and CUDA availability and updates the label."""
        self.cuda_availability_label.setText(self.tr("Checking..."))
        try:
            from application.core.whisper_engine import _TORCH_AVAILABLE

            if _TORCH_AVAILABLE:
                import torch # type: ignore
                if torch.cuda.is_available():
                    self.cuda_availability_label.setText(self.tr("Available"))
                    self.cuda_availability_label.setProperty("available", True)
                else:
                    self.cuda_availability_label.setText(self.tr("Not Available"))
                    self.cuda_availability_label.setProperty("available", False)
            else:
                self.cuda_availability_label.setText(self.tr("PyTorch not installed"))
                self.cuda_availability_label.setProperty("available", False)
        except Exception:
            self.cuda_availability_label.setText(self.tr("Error checking PyTorch"))
            self.cuda_availability_label.setProperty("available", False)

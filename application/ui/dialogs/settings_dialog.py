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
from PySide6.QtMultimedia import QMediaDevices # Added for audio device listing
from PySide6.QtCore import Qt, QSettings, Signal, QEvent

import settings
import utils

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):

    theme_changed = Signal(str)  # Emitted when the theme is changed
    font_size_changed = Signal(int)  # Emitted when font size slider changes
    locale_changed = Signal(
        str
    )  # Emitted when locale is changed (sends locale code e.g. "en", "vi", or "System")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Settings"))
        self.setMinimumWidth(400)

        self.q_settings = QSettings()

        main_layout = QVBoxLayout(self)

        # --- Audio Settings ---
        audio_group = QGroupBox(self.tr("Audio"))
        audio_layout = QVBoxLayout(audio_group)

        self.sound_enabled_checkbox = QCheckBox(self.tr("Enable sound effects"))
        audio_layout.addWidget(self.sound_enabled_checkbox)

        self.autoplay_audio_checkbox = QCheckBox(self.tr("Autoplay audio in exercises"))
        audio_layout.addWidget(self.autoplay_audio_checkbox)

        # Pronunciation/Microphone settings group (new, within Audio)
        self.pronunciation_settings_group = QGroupBox(self.tr("Pronunciation & Microphone"))
        self.pronunciation_settings_layout = QFormLayout(self.pronunciation_settings_group)
        
        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItems(["None"] + settings.WHISPER_MODELS_AVAILABLE) # "None" to disable
        self.pronunciation_settings_layout.addRow(self.tr("Whisper Model:"), self.whisper_model_combo)

        self.audio_input_device_combo = QComboBox()
        self._populate_audio_input_devices()
        self.pronunciation_settings_layout.addRow(self.tr("Microphone Input Device:"), self.audio_input_device_combo)
        
        audio_layout.addWidget(self.pronunciation_settings_group) # Add the new sub-group to the main audio layout

        volume_layout = QHBoxLayout()
        volume_label = QLabel(self.tr("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.valueChanged.connect(
            utils.update_sound_volume
        )  # Live update

        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        audio_layout.addLayout(volume_layout)

        main_layout.addWidget(audio_group)

        # --- UI Settings ---
        # UI Settings (General, then Theme, then Font)
        ui_group = QGroupBox(self.tr("User Interface"))
        ui_layout = QFormLayout(ui_group)

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

        self.autoshow_hints_checkbox = QCheckBox(
            self.tr("Show hints automatically in exercises")
        )
        ui_layout.addRow(self.autoshow_hints_checkbox)  # Add as a new row

        self.reset_ui_button = QPushButton(self.tr("Reset UI Settings to Default"))
        self.reset_ui_button.clicked.connect(self._reset_ui_settings)
        ui_layout.addRow(self.reset_ui_button)  # Add as a new row
        main_layout.addWidget(ui_group)

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

    def _populate_audio_input_devices(self):
        """Populates the audio input device combo box."""
        # QMediaDevices is imported at the top of the file

        self.audio_input_device_combo.clear()
        default_device_info = QMediaDevices.defaultAudioInput() # QAudioDevice object
        default_device_id_str = default_device_info.id().toStdString() if not default_device_info.isNull() else ""

        for device in QMediaDevices.audioInputs():
            # Store device.id().toStdString() (str) as userData, display description()
            self.audio_input_device_combo.addItem(device.description(), userData=device.id().toStdString())
            if device.id().toStdString() == default_device_id_str:
                self.audio_input_device_combo.setCurrentText(device.description()) # Set default
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
            settings.QSETTINGS_KEY_AUDIO_INPUT_DEVICE,
            default_audio_input_id, 
            type=str
        )
        # Find and set the selected device in the combo box
        index = self.audio_input_device_combo.findData(preferred_device_id)
        if index != -1:
            self.audio_input_device_combo.setCurrentIndex(index)
        elif default_audio_input_id: # Fallback to current system default if saved one not found
            logger.warning(f"Preferred audio input device ID '{preferred_device_id}' not found. Defaulting to system default.")
            default_index = self.audio_input_device_combo.findData(default_audio_input_id)
            if default_index != -1:
                self.audio_input_device_combo.setCurrentIndex(default_index)
        else:
            logger.warning(f"Preferred audio input device ID '{preferred_device_id}' not found and no system default available.")

        current_whisper_model = self.q_settings.value(
            settings.QSETTINGS_KEY_WHISPER_MODEL,
            settings.WHISPER_MODEL_DEFAULT, type=str
        )
        self.whisper_model_combo.setCurrentText(current_whisper_model if current_whisper_model else "None")

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
            "System",  # Default to "System" theme
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

    def _reset_ui_settings(self):
        """Resets UI related settings (theme, font size) to their defaults and applies them live."""
        # Reset theme
        self.theme_combo.setCurrentText(
            "System"
        )  # Assuming "System" is the default key
        self.theme_changed.emit("System")

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
        selected_device_id = self.audio_input_device_combo.currentData() # This is the ID string
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_AUDIO_INPUT_DEVICE,
            selected_device_id
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_WHISPER_MODEL,
            self.whisper_model_combo.currentText() if self.whisper_model_combo.currentText() != "None" else ""
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
        
        self.pronunciation_settings_group.setTitle(self.tr("Pronunciation & Microphone"))
        # Retranslate labels within the QFormLayout for pronunciation settings
        whisper_label = self.pronunciation_settings_layout.labelForField(self.whisper_model_combo)
        if whisper_label:
            whisper_label.setText(self.tr("Whisper Model:"))
        mic_label = self.pronunciation_settings_layout.labelForField(self.audio_input_device_combo)
        if mic_label:
            mic_label.setText(self.tr("Microphone Input Device:"))

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

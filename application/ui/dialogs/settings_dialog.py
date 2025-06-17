import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QCheckBox, QSlider, QLabel,
    QDialogButtonBox, QHBoxLayout, QComboBox, QFormLayout
)
from PySide6.QtCore import Qt, QSettings, Signal
 
import settings
import utils

logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    
    theme_changed = Signal(str) # Emitted when the theme is changed
    font_size_changed = Signal(int) # Emitted when font size slider changes

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

        volume_layout = QHBoxLayout()
        volume_label = QLabel(self.tr("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.valueChanged.connect(utils.update_sound_volume) # Live update
        
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
        
        # Font Size controls: label + slider + current value display
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setMinimum(8)  # Min font size
        self.font_size_slider.setMaximum(14)  # Max font size
        self.font_size_slider.setValue(settings.DEFAULT_FONT_SIZE)  # Initial value
        self.font_size_slider.valueChanged.connect(self._update_font_size_label)
        self.font_size_label = QLabel(str(settings.DEFAULT_FONT_SIZE) + " pt") # Initial label
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(self.font_size_slider)
        font_size_layout.addWidget(self.font_size_label)
        ui_layout.addRow(self.tr("Font Size:"), font_size_layout)
        main_layout.addWidget(ui_group)

        # --- Dialog Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_settings)
        main_layout.addWidget(buttons)

        self.load_settings()

    def load_settings(self):
        """Loads settings from QSettings and updates the UI controls."""
        sound_enabled = self.q_settings.value(
            settings.QSETTINGS_KEY_SOUND_ENABLED, 
            settings.SOUND_EFFECTS_ENABLED_DEFAULT, 
            type=bool
        )
        self.sound_enabled_checkbox.setChecked(sound_enabled)

        volume = self.q_settings.value(
            settings.QSETTINGS_KEY_SOUND_VOLUME, 
            settings.SOUND_VOLUME_DEFAULT, 
            type=int
        )
        
        # Load Font Size setting (default if not found)
        current_font_size = self.q_settings.value(
            settings.QSETTINGS_KEY_FONT_SIZE, 
            settings.DEFAULT_FONT_SIZE, 
            type=int
        )
        self.font_size_slider.setValue(current_font_size)

        self.volume_slider.setValue(volume)

        current_theme_name = self.q_settings.value(
            settings.QSETTINGS_KEY_UI_THEME,
            "System", # Default to "System" theme
            type=str
        )
        if current_theme_name in settings.AVAILABLE_THEMES:
            self.theme_combo.setCurrentText(current_theme_name)
        else: # Handle case where saved theme is no longer available
            self.theme_combo.setCurrentText("System")
            logger.warning(f"Saved theme '{current_theme_name}' not found in available themes. Defaulting to 'System'.")

    def _update_font_size_label(self, value):
        """Update the font size label when the slider value changes."""
        self.font_size_label.setText(str(value) + " pt")
        self.font_size_changed.emit(value) # Emit as live-update signal

    def apply_settings(self):
        """Saves the current state of the UI controls to QSettings."""
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_SOUND_ENABLED, 
            self.sound_enabled_checkbox.isChecked()
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_SOUND_VOLUME, 
            self.volume_slider.value()
        )

        # Save Font Size setting
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_FONT_SIZE, 
            self.font_size_slider.value()
        )
        utils.update_sound_volume() # Ensure live update takes effect if slider was just moved
        
        selected_theme_name = self.theme_combo.currentText()
        self.q_settings.setValue(settings.QSETTINGS_KEY_UI_THEME, selected_theme_name)
        self.theme_changed.emit(selected_theme_name) # Emit signal AFTER saving

        logger.info("Settings applied.")

    def save_settings(self):
        """Applies the settings and closes the dialog."""
        self.apply_settings()
        self.accept()
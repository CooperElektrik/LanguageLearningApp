import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QSlider,
    QHBoxLayout,
    QDialogButtonBox,
    QFormLayout,
)
from PySide6.QtCore import Qt, QSettings, Signal, QEvent

try:
    from application import settings, utils
except ImportError:
    import settings
    import utils

logger = logging.getLogger(__name__)


class InitialUISetupDialog(QDialog):
    """A dialog for the initial setup of UI settings like theme, language, and font size."""

    theme_changed = Signal(str)
    font_size_changed = Signal(int)
    locale_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Initial Setup"))
        self.setModal(True)
        self.setMinimumWidth(450)
        self.q_settings = QSettings()

        main_layout = QVBoxLayout(self)

        self.info_label = QLabel(
            self.tr(
                "Welcome!\n"
                "Since this is your first time opening this application, let's set up your user interface. You can change the UI theme, language, and font size here and preview the changes live. These can be adjusted later in the main settings menu."
            )
        )
        self.info_label.setWordWrap(True)
        main_layout.addWidget(self.info_label)

        # --- UI Settings Form ---
        form_layout = QFormLayout()

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(settings.AVAILABLE_THEMES.keys()))
        self.theme_combo.currentTextChanged.connect(self.theme_changed)
        self.theme_label = QLabel(self.tr("Theme:"))
        form_layout.addRow(self.theme_label, self.theme_combo)

        # Language
        self.locale_combo = QComboBox()
        self._populate_locale_combo()
        self.locale_combo.currentTextChanged.connect(self._on_locale_changed)
        self.language_label = QLabel(self.tr("Language:"))
        form_layout.addRow(self.language_label, self.locale_combo)

        # Font Size
        font_size_layout = QHBoxLayout()
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setMinimum(8)
        self.font_size_slider.setMaximum(14)
        self.font_size_slider.valueChanged.connect(self._update_font_size_label)
        self.font_size_value_label = QLabel()
        font_size_layout.addWidget(self.font_size_slider)
        font_size_layout.addWidget(self.font_size_value_label)
        self.font_size_label = QLabel(self.tr("Font Size:"))
        form_layout.addRow(self.font_size_label, font_size_layout)

        main_layout.addLayout(form_layout)

        # --- Buttons ---
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.save_and_accept)
        main_layout.addWidget(buttons)

        self.load_settings()

    def _populate_locale_combo(self):
        """Populates the locale combo box with available languages."""
        self.available_locales = utils.get_available_locales()
        sorted_display_names = sorted(
            self.available_locales.keys(),
            key=lambda x: (x != settings.DEFAULT_LOCALE, x),
        )
        for display_name in sorted_display_names:
            locale_code = self.available_locales[display_name]
            self.locale_combo.addItem(display_name, userData=locale_code)

    def _on_locale_changed(self, text):
        """Emits the locale_changed signal with the locale code."""
        locale_code = self.locale_combo.currentData()
        if locale_code:
            self.locale_changed.emit(locale_code)

    def _update_font_size_label(self, value):
        """Update the font size label and emit the signal."""
        self.font_size_value_label.setText(f"{value} pt")
        self.font_size_changed.emit(value)

    def load_settings(self):
        """Loads current settings to initialize the dialog's state."""
        # Theme
        current_theme_name = self.q_settings.value(
            settings.QSETTINGS_KEY_UI_THEME, "Nao Tomori", type=str
        )
        self.theme_combo.setCurrentText(current_theme_name)

        # Language
        current_locale_code = self.q_settings.value(
            settings.QSETTINGS_KEY_LOCALE, settings.DEFAULT_LOCALE, type=str
        )
        for display_name, code_val in self.available_locales.items():
            if code_val == current_locale_code:
                self.locale_combo.setCurrentText(display_name)
                break

        # Font Size
        current_font_size = self.q_settings.value(
            settings.QSETTINGS_KEY_FONT_SIZE, settings.DEFAULT_FONT_SIZE, type=int
        )
        self.font_size_slider.setValue(current_font_size)
        self._update_font_size_label(current_font_size)

    def save_and_accept(self):
        """Saves the selected settings and closes the dialog."""
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_UI_THEME, self.theme_combo.currentText()
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_LOCALE, self.locale_combo.currentData()
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_FONT_SIZE, self.font_size_slider.value()
        )
        self.q_settings.setValue(settings.QSETTINGS_KEY_INITIAL_UI_SETUP_DONE, True)
        logger.info("Initial UI setup completed and settings saved.")
        self.accept()

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.setWindowTitle(self.tr("Initial Setup"))
        self.info_label.setText(
            self.tr(
                "Welcome!\n"
                "Since this is your first time opening this application, let's set up your user interface. You can change the UI theme, language, and font size here and preview the changes live. These can be adjusted later in the main settings menu."
            )
        )
        self.theme_label.setText(self.tr("Theme:"))
        self.language_label.setText(self.tr("Language:"))
        self.font_size_label.setText(self.tr("Font Size:"))
        logger.debug("InitialUISetupDialog retranslated.")
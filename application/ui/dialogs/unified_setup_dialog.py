import logging

from PySide6.QtCore import QEvent, QSettings, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from application import settings, utils
    from application.ui.dialogs import settings_widgets
except ImportError:
    import settings
    import utils
    from ui.dialogs import settings_widgets

logger = logging.getLogger(__name__)


class UnifiedSetupDialog(QDialog):
    """A unified dialog for the initial setup of all settings."""

    font_size_changed = Signal(int)
    locale_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Initial Setup"))
        self.setModal(True)
        self.setMinimumSize(600, 400)
        self.q_settings = QSettings()

        # Main layout
        main_layout = QHBoxLayout()

        # Navigation List
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(150)
        main_layout.addWidget(self.nav_list)

        # Settings Stack
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # Create pages
        self.create_welcome_page()
        self.create_ui_settings_page()
        self.create_audio_settings_page()

        # Connect navigation
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)

        # Button layout
        button_layout = QHBoxLayout()
        self.back_button = QPushButton(self.tr("Back"))
        self.next_button = QPushButton(self.tr("Next"))
        self.ok_button = QPushButton(self.tr("OK"))

        self.back_button.clicked.connect(self.go_back)
        self.next_button.clicked.connect(self.go_next)
        self.ok_button.clicked.connect(self.save_and_accept)

        button_layout.addWidget(self.back_button)
        button_layout.addWidget(self.next_button)
        button_layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        button_layout.addWidget(self.ok_button)

        # Add layouts to a main vertical layout
        v_layout = QVBoxLayout(self)
        v_layout.addLayout(main_layout)
        v_layout.addLayout(button_layout)

        self.load_settings()
        self.nav_list.setCurrentRow(0)
        self.update_button_states()
        self.nav_list.currentRowChanged.connect(self.update_button_states)

    def go_back(self):
        current_index = self.nav_list.currentRow()
        if current_index > 0:
            self.nav_list.setCurrentRow(current_index - 1)

    def go_next(self):
        current_index = self.nav_list.currentRow()
        if current_index < self.nav_list.count() - 1:
            self.nav_list.setCurrentRow(current_index + 1)

    def update_button_states(self):
        current_index = self.nav_list.currentRow()
        self.back_button.setEnabled(current_index > 0)
        self.next_button.setEnabled(current_index < self.nav_list.count() - 1)
        self.ok_button.setEnabled(current_index == self.nav_list.count() - 1)

    def create_welcome_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(
            self.tr(
                "Welcome!\n\n"
                "Since this is your first time running the application, "
                "let's configure some basic settings. You can change these "
                "at any time from the main settings menu."
            )
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.stack.addWidget(page)
        self.nav_list.addItem(self.tr("Welcome"))

    def create_ui_settings_page(self):
        page = QWidget()
        layout = QFormLayout(page)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Language
        self.locale_combo = QComboBox()
        self._populate_locale_combo()
        self.locale_combo.currentTextChanged.connect(self._on_locale_changed)
        layout.addRow(self.tr("Language:"), self.locale_combo)

        # Font Size
        font_size_layout = QHBoxLayout()
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setMinimum(8)
        self.font_size_slider.setMaximum(14)
        self.font_size_slider.valueChanged.connect(self._update_font_size_label)
        self.font_size_value_label = QLabel()
        font_size_layout.addWidget(self.font_size_slider)
        font_size_layout.addWidget(self.font_size_value_label)
        layout.addRow(self.tr("Font Size:"), font_size_layout)

        self.stack.addWidget(page)
        self.nav_list.addItem(self.tr("User Interface"))

    def create_audio_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        stt_info_label = QLabel(
            self.tr(
                "Speech-to-Text (STT) is used for pronunciation exercises.\n\n"
                "• VOSK: Lightweight, offline, and fast. Good for general use.\n"
                "• Whisper: More accurate, but requires more resources (GPU recommended)."
            )
        )
        stt_info_label.setWordWrap(True)
        layout.addWidget(stt_info_label)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Calculate max label width
        labels_text = [
            self.tr("Microphone:"),
            self.tr("STT Engine:"),
            self.tr("Whisper Model:"),
            self.tr("VOSK Model:"),
            self.tr("CUDA:"),
        ]
        font_metrics = QFontMetrics(self.font())
        max_width = max(font_metrics.horizontalAdvance(text) for text in labels_text)
        label_width = max_width + 10  # Add some padding

        # Microphone selection
        mic_label = QLabel(self.tr("Microphone:"))
        mic_label.setFixedWidth(label_width)
        self.mic_combo = QComboBox()
        self._populate_audio_input_devices()
        form_layout.addRow(mic_label, self.mic_combo)

        # STT Engine Selection
        stt_engine_label = QLabel(self.tr("STT Engine:"))
        stt_engine_label.setFixedWidth(label_width)
        self.stt_engine_combo = QComboBox()
        self.stt_engine_combo.addItems(settings.STT_ENGINES_AVAILABLE)
        self.stt_engine_combo.currentTextChanged.connect(self._on_stt_engine_changed)
        form_layout.addRow(stt_engine_label, self.stt_engine_combo)

        # Whisper-specific widgets
        self.whisper_label = QLabel(self.tr("Whisper Model:"))
        self.whisper_label.setFixedWidth(label_width)
        self.whisper_combo = QComboBox()
        self._populate_whisper_models()
        form_layout.addRow(self.whisper_label, self.whisper_combo)

        # VOSK-specific widgets
        self.vosk_label = QLabel(self.tr("VOSK Model:"))
        self.vosk_label.setFixedWidth(label_width)
        self.vosk_combo = QComboBox()
        self._populate_vosk_models()
        form_layout.addRow(self.vosk_label, self.vosk_combo)

        # CUDA Status Layout (for Whisper)
        self.cuda_label = QLabel(self.tr("CUDA:"))
        self.cuda_label.setFixedWidth(label_width)
        cuda_layout = QHBoxLayout()
        self.cuda_status_label = QLabel(self.tr("CUDA Status: Unknown"))
        cuda_layout.addWidget(self.cuda_status_label)
        self.check_cuda_button = QPushButton(self.tr("Check Now"))
        self.check_cuda_button.clicked.connect(self.check_cuda_availability)
        cuda_layout.addWidget(self.check_cuda_button)
        form_layout.addRow(self.cuda_label, cuda_layout)

        layout.addLayout(form_layout)
        self.stack.addWidget(page)
        self.nav_list.addItem(self.tr("Audio"))

    def _populate_locale_combo(self):
        self.available_locales = utils.get_available_locales()
        settings_widgets.populate_locale_combo(
            self.locale_combo, self.available_locales
        )

    def _on_locale_changed(self, text):
        locale_code = self.locale_combo.currentData()
        if locale_code:
            self.locale_changed.emit(locale_code)

    def _update_font_size_label(self, value):
        self.font_size_value_label.setText(f"{value} pt")
        self.font_size_changed.emit(value)

    def _populate_audio_input_devices(self):
        settings_widgets.populate_audio_input_devices(self.mic_combo)

    def _populate_whisper_models(self):
        settings_widgets.populate_whisper_model_combo(
            self.whisper_combo, self.tr, include_processing_time=False
        )

    def _populate_vosk_models(self):
        settings_widgets.populate_vosk_model_combo(self.vosk_combo, self.tr)

    def _on_stt_engine_changed(self, engine_name: str):
        is_whisper = engine_name == settings.STT_ENGINE_WHISPER
        is_vosk = engine_name == settings.STT_ENGINE_VOSK

        self.whisper_label.setVisible(is_whisper)
        self.whisper_combo.setVisible(is_whisper)
        self.cuda_label.setVisible(is_whisper)
        self.cuda_status_label.setVisible(is_whisper)
        self.check_cuda_button.setVisible(is_whisper)

        self.vosk_label.setVisible(is_vosk)
        self.vosk_combo.setVisible(is_vosk)

    def load_settings(self):
        # UI Settings
        current_locale_code = self.q_settings.value(
            settings.QSETTINGS_KEY_LOCALE, settings.DEFAULT_LOCALE, type=str
        )
        for display_name, code_val in self.available_locales.items():
            if code_val == current_locale_code:
                self.locale_combo.setCurrentText(display_name)
                break
        current_font_size = self.q_settings.value(
            settings.QSETTINGS_KEY_FONT_SIZE, settings.DEFAULT_FONT_SIZE, type=int
        )
        self.font_size_slider.setValue(current_font_size)
        self._update_font_size_label(current_font_size)

        # Audio Settings
        self.stt_engine_combo.setCurrentText(settings.STT_ENGINE_DEFAULT)
        self._on_stt_engine_changed(settings.STT_ENGINE_DEFAULT)
        current_whisper_model = self.q_settings.value(
            settings.QSETTINGS_KEY_WHISPER_MODEL,
            settings.WHISPER_MODEL_DEFAULT,
            type=str,
        )
        whisper_index = self.whisper_combo.findData(current_whisper_model)
        if whisper_index != -1:
            self.whisper_combo.setCurrentIndex(whisper_index)
        else:
            self.whisper_combo.setCurrentText("None")
        current_vosk_model = self.q_settings.value(
            settings.QSETTINGS_KEY_VOSK_MODEL,
            settings.VOSK_MODEL_DEFAULT,
            type=str,
        )
        vosk_index = self.vosk_combo.findData(current_vosk_model)
        if vosk_index != -1:
            self.vosk_combo.setCurrentIndex(vosk_index)
        else:
            self.vosk_combo.setCurrentText("None")

    def save_and_accept(self):
        # UI Settings
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_LOCALE, self.locale_combo.currentData()
        )
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_FONT_SIZE, self.font_size_slider.value()
        )
        self.q_settings.setValue(settings.QSETTINGS_KEY_INITIAL_UI_SETUP_DONE, True)

        # Audio Settings
        selected_mic_id = self.mic_combo.currentData()
        self.q_settings.setValue(
            settings.QSETTINGS_KEY_AUDIO_INPUT_DEVICE, selected_mic_id
        )
        selected_engine = self.stt_engine_combo.currentText()
        self.q_settings.setValue(settings.QSETTINGS_KEY_STT_ENGINE, selected_engine)
        if selected_engine == settings.STT_ENGINE_WHISPER:
            selected_model = self.whisper_combo.currentData()
            self.q_settings.setValue(
                settings.QSETTINGS_KEY_WHISPER_MODEL,
                selected_model if selected_model != "None" else "",
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
        elif selected_engine == settings.STT_ENGINE_VOSK:
            selected_model = self.vosk_combo.currentData()
            self.q_settings.setValue(
                settings.QSETTINGS_KEY_VOSK_MODEL,
                selected_model if selected_model != "None" else "",
            )
            if selected_model != "None":
                QMessageBox.information(
                    self,
                    self.tr("Model Download"),
                    self.tr(
                        "The selected VOSK model will be extracted the first time you start a pronunciation exercise. Subsequent loads will be faster."
                    ),
                )
        self.q_settings.setValue(settings.QSETTINGS_KEY_INITIAL_AUDIO_SETUP_DONE, True)

        logger.info("Initial setup completed and settings saved.")
        self.accept()

    def check_cuda_availability(self):
        self.cuda_status_label.setText(self.tr("Checking..."))
        status = settings_widgets.detect_cuda_status()
        if status == settings_widgets.CUDA_AVAILABLE:
            text = self.tr("CUDA Status: Available")
        elif status == settings_widgets.CUDA_NOT_AVAILABLE:
            text = self.tr("CUDA Status: Not Available (PyTorch installed)")
        elif status == settings_widgets.CUDA_TORCH_MISSING:
            text = self.tr("CUDA Status: Not Available (PyTorch not installed)")
        else:
            text = self.tr("CUDA Status: Not Available (Error checking PyTorch)")
        self.cuda_status_label.setText(text)

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.setWindowTitle(self.tr("Initial Setup"))
        # Welcome page
        self.nav_list.item(0).setText(self.tr("Welcome"))
        welcome_page = self.stack.widget(0)
        welcome_label = welcome_page.findChild(QLabel)
        if welcome_label:
            welcome_label.setText(
                self.tr(
                    "Welcome!\n\n"
                    "Since this is your first time running the application, "
                    "let's configure some basic settings. You can change these "
                    "at any time from the main settings menu."
                )
            )

        # UI page
        self.nav_list.item(1).setText(self.tr("User Interface"))
        ui_page = self.stack.widget(1)
        form_layout = ui_page.layout()
        form_layout.labelForField(self.locale_combo).setText(self.tr("Language:"))
        form_layout.labelForField(self.font_size_slider.parent()).setText(
            self.tr("Font Size:")
        )

        # Audio page
        self.nav_list.item(2).setText(self.tr("Audio"))
        audio_page = self.stack.widget(2)
        stt_info_label = audio_page.findChild(QLabel)
        if stt_info_label:
            stt_info_label.setText(
                self.tr(
                    "Speech-to-Text (STT) is used for pronunciation exercises.\n\n"
                    "• VOSK: Lightweight, offline, and fast. Good for general use.\n"
                    "• Whisper: More accurate, but requires more resources (GPU recommended)."
                )
            )
        form_layout = audio_page.findChild(QFormLayout)
        if form_layout:
            form_layout.labelForField(self.mic_combo).setText(self.tr("Microphone:"))
            form_layout.labelForField(self.stt_engine_combo).setText(
                self.tr("STT Engine:")
            )
            self.whisper_label.setText(self.tr("Whisper Model:"))
            self.vosk_label.setText(self.tr("VOSK Model:"))
            self.check_cuda_button.setText(self.tr("Check Now"))

        logger.debug("UnifiedSetupDialog retranslated.")

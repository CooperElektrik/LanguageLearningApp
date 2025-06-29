import os
import logging  # For LOG_LEVEL constants

# --- General Application Settings ---
APP_NAME = "LanguageLearningApp"
ORG_NAME = "CooperElektrik"  # Used for QStandardPaths, QSettings etc.

# --- File and Directory Names (relative to application root or MEIPASS) ---
MANIFEST_FILENAME = "manifest.yaml"
COURSES_DIR = "courses"  # The top-level directory containing all course folders
ASSETS_DIR = "assets"  # Directory for shared assets like sounds
IMAGES_DIR = os.path.join(
    ASSETS_DIR, "images"
)  # Directory for images like splash screen
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")  # Sub-directory for sound effects
LOCALIZATION_DIR = "localization"  # Directory containing .qm files
THEME_DIR = "ui/styles"  # Directory containing .qss files
LIGHT_THEME_FILE = "light_theme.qss"  # Specific light theme
DARK_THEME_FILE = "dark_theme.qss"  # Specific dark theme
FANCY_LIGHT_THEME_FILE = "fancy_light_theme.qss"  # Fancy theme
NAO_TOMORI_THEME_FILE = "nao_tomori_theme.qss"  # Waifu
FANCY_DARK_THEME_FILE = "fancy_dark_theme.qss"  # Fancy theme (Dark)
FANCY_MIDNIGHT_THEME_FILE = "fancy_midnight_theme.qss"  # Fancy midnight theme (Dark)
WINDOWS_95_FILE = "win95_theme.qss"  # Windows 95'ish theme
FANCY_WINDOWS_95_FILE = "fancy_win95_theme.qss"  # Windows 95'ish theme
TEMPLE_OS_FILE = "temple_os_theme.qss"  # Terry A. Davis
SPLASH_IMAGE_FILE = os.path.join(IMAGES_DIR, "splash.jpg")  # Splash screen image
AVAILABLE_THEMES = {
    "System": "system_default",
    "Light": LIGHT_THEME_FILE,
    "Fancy Light": FANCY_LIGHT_THEME_FILE,
    "Nao Tomori": NAO_TOMORI_THEME_FILE,
    "Dark": DARK_THEME_FILE,
    "Fancy Dark": FANCY_DARK_THEME_FILE,
    "Midnight": FANCY_MIDNIGHT_THEME_FILE,
    "Windows 95": WINDOWS_95_FILE,
    "Fancy Windows 95": FANCY_WINDOWS_95_FILE,
    "Temple OS": TEMPLE_OS_FILE,
}  # Name to filename mapping

# --- Sound Settings ---
SOUND_EFFECTS_ENABLED_DEFAULT = True
SOUND_VOLUME_DEFAULT = 50  # An integer from 0 to 100
SOUND_FILE_CORRECT = "correct.mp3"
SOUND_FILE_INCORRECT = "incorrect.mp3"
SOUND_FILE_COMPLETE = "complete.mp3"

# --- QSettings Keys ---
QSETTINGS_KEY_SOUND_ENABLED = "audio/sound_effects_enabled"
QSETTINGS_KEY_SOUND_VOLUME = "audio/sound_volume"
QSETTINGS_KEY_UI_THEME = "ui/theme"  # New key for storing selected theme
QSETTINGS_KEY_FONT_SIZE = "ui/font_size"
QSETTINGS_KEY_AUTOPLAY_AUDIO = "audio/autoplay_audio_enabled"
QSETTINGS_KEY_AUTOSHOW_HINTS = "ui/autoshow_hints_enabled"
QSETTINGS_KEY_GLOBAL_ONBOARDING_SEEN = (
    "onboarding/global_seen_v1"  # v1 for future updates
)
QSETTINGS_KEY_LOCALE = "ui/locale"
QSETTINGS_KEY_AUDIO_INPUT_DEVICE = "audio/input_device"
QSETTINGS_KEY_INITIAL_AUDIO_SETUP_DONE = "onboarding/initial_audio_setup_v1"
QSETTINGS_KEY_INITIAL_UI_SETUP_DONE = "onboarding/initial_ui_setup_v1"
# These are for Whisper Transcription
QSETTINGS_KEY_WHISPER_MODEL = "audio/whisper_model_selection"
WHISPER_MODELS_AVAILABLE = [
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "large-v3",
    "large-v3-turbo",
]  # Or include .en versions like "base.en"
WHISPER_MODEL_INFO = {
    "tiny": {
        "size": "~75 MB",
        "params": "39M",
        "device_rec": "CPU",
        "ptime": "Instant",
    },
    "tiny.en": {
        "size": "~75 MB",
        "params": "39M",
        "device_rec": "CPU",
        "ptime": "Instant",
    },
    "base": {
        "size": "~145 MB",
        "params": "74M",
        "device_rec": "CPU",
        "ptime": "Instant",
    },
    "base.en": {
        "size": "~145 MB",
        "params": "74M",
        "device_rec": "CPU",
        "ptime": "Instant",
    },
    "small": {
        "size": "~484 MB",
        "params": "244M",
        "device_rec": "CPU / GPU",
        "ptime": "Near-Instant",
    },
    "small.en": {
        "size": "~484 MB",
        "params": "244M",
        "device_rec": "CPU / GPU",
        "ptime": "Near-Instant",
    },
    "medium": {
        "size": "~1.53 GB",
        "params": "769M",
        "device_rec": "GPU",
        "ptime": "6~20s",
    },
    "large-v3": {
        "size": "~3.09 GB",
        "params": "1.54B",
        "device_rec": "GPU",
        "ptime": "40~120s",
    },
    "large-v3-turbo": {
        "size": "~1.62 GB",
        "params": "809M",
        "device_rec": "GPU",
        "ptime": "30~100s",
    },
}
WHISPER_MODEL_DEFAULT = "small"  # A good balance

# These are for STT Engine Selection
QSETTINGS_KEY_STT_ENGINE = "audio/stt_engine_selection"
STT_ENGINE_WHISPER = "whisper"
STT_ENGINE_VOSK = "vosk"
STT_ENGINES_AVAILABLE = [STT_ENGINE_WHISPER, STT_ENGINE_VOSK]
STT_ENGINE_DEFAULT = STT_ENGINE_WHISPER

# These are for VOSK Transcription
QSETTINGS_KEY_VOSK_MODEL = "audio/vosk_model_selection"
VOSK_MODELS_AVAILABLE = [
    "vosk-model-small-en-us-0.15",
    "vosk-model-en-us-0.22",
    "vosk-model-en-us-0.22-lgraph",
    "vosk-model-en-us-0.42-gigaspeech",
] # Example VOSK models, user might need to download them
VOSK_MODEL_INFO = {
    "vosk-model-small-en-us-0.15": {
        "size": "~48 MB",
        "lang": "en-us",
        "description": "Small English model, good for quick tests.",
    },
    "vosk-model-vn-0.4": {
        "size": "~80MB",
        "lang": "vi",
        "description": "Vietnamese model.",
    }
}
VOSK_MODEL_DEFAULT = "vosk-model-small-en-us-0.15" # A good default for initial setup


# --- UI Font Settings ---
DEFAULT_FONT_SIZE = 10  # Base font size in points
AUTOPLAY_AUDIO_DEFAULT = False  # Default for autoplaying audio in exercises
AUTOSHOW_HINTS_DEFAULT = False  # Default for automatically showing hints

# --- Locale Settings ---
# Set to a specific locale string (e.g., "vi", "fr_FR", "en_US") to override system locale for testing.
# Set to None to use the system's default locale.
FORCE_LOCALE = None  # Example: "vi" to force Vietnamese for testing
DEFAULT_LOCALE = "System"  # Represents using the system's locale or English fallback

# --- Logging Settings ---
# Valid levels: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
LOG_LEVEL = "DEBUG"
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s"
# For direct use with logging module:
LOG_LEVEL_INT = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

# --- Developer Mode Settings ---
DEVELOPER_MODE_DEFAULT = False
QSETTINGS_KEY_DEVELOPER_MODE = "developer/developer_mode_enabled"
ENV_VAR_DEVELOPER_MODE = "LINGUALEARN_DEV_MODE"  # Environment variable to activate dev mode (e.g., LINGUALEARN_DEV_MODE=1)


# --- Progress Data Settings ---
# Subdirectory within QStandardPaths.AppDataLocation/ORG_NAME/APP_NAME/ for progress files
PROGRESS_DATA_SUBDIR = "Progress"

# --- UI Defaults (examples, can be expanded) ---
DEFAULT_FONT_FAMILY = "Arial"
DEFAULT_FONT_SIZE_NORMAL = 10
DEFAULT_FONT_SIZE_LARGE = 12

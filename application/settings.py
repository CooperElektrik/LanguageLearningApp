import os
import logging  # For LOG_LEVEL constants

# --- General Application Settings ---
APP_NAME = "LinguaLearn"
ORG_NAME = "LinguaLearnProject"  # Used for QStandardPaths, QSettings etc.

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
WINDOWS_95_FILE = "win95_theme.qss"  # Windows 95'ish theme
TEMPLE_OS_FILE = "temple_os_theme.qss"  # Terry A. Davis
SPLASH_IMAGE_FILE = os.path.join(IMAGES_DIR, "splash.jpg")  # Splash screen image
AVAILABLE_THEMES = {
    "System": "system_default",
    "Light": LIGHT_THEME_FILE,
    "Dark": DARK_THEME_FILE,
    "Windows 95": WINDOWS_95_FILE,
    "Temple OS": TEMPLE_OS_FILE,
}  # Name to filename mapping

# --- Sound Settings ---
SOUND_EFFECTS_ENABLED_DEFAULT = True
SOUND_VOLUME_DEFAULT = 50  # An integer from 0 to 100
SOUND_FILE_CORRECT = "correct.wav"
SOUND_FILE_INCORRECT = "incorrect.wav"
SOUND_FILE_COMPLETE = "complete.wav"

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

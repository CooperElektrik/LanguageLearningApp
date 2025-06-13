import os
import logging # For LOG_LEVEL constants

# --- General Application Settings ---
APP_NAME = "LinguaLearn"
ORG_NAME = "LinguaLearnProject" # Used for QStandardPaths, QSettings etc.

# --- File and Directory Names (relative to application root or MEIPASS) ---
MANIFEST_FILENAME = "manifest.yaml"
COURSES_DIR = "courses"           # The top-level directory containing all course folders
ASSETS_DIR = "assets"             # Directory for shared assets like sounds
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds") # Sub-directory for sound effects
LOCALIZATION_DIR = "localization" # Directory containing .qm files
THEME_DIR = "ui/styles"           # Directory containing .qss files
DEFAULT_THEME_FILE = "win95_theme.qss" # Default theme file to load

# --- Sound Settings ---
SOUND_EFFECTS_ENABLED = False
SOUND_FILE_CORRECT = "correct.wav"
SOUND_FILE_INCORRECT = "incorrect.wav"
SOUND_FILE_COMPLETE = "complete.wav"

# --- Locale Settings ---
# Set to a specific locale string (e.g., "vi", "fr_FR", "en_US") to override system locale for testing.
# Set to None to use the system's default locale.
FORCE_LOCALE = None # Example: "vi" to force Vietnamese for testing

# --- Logging Settings ---
# Valid levels: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
LOG_LEVEL = "DEBUG"
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s"
# For direct use with logging module:
LOG_LEVEL_INT = getattr(logging, LOG_LEVEL.upper(), logging.INFO)


# --- Progress Data Settings ---
# Subdirectory within QStandardPaths.AppDataLocation/ORG_NAME/APP_NAME/ for progress files
PROGRESS_DATA_SUBDIR = "Progress"

# --- UI Defaults (examples, can be expanded) ---
DEFAULT_FONT_FAMILY = "Arial"
DEFAULT_FONT_SIZE_NORMAL = 10
DEFAULT_FONT_SIZE_LARGE = 12
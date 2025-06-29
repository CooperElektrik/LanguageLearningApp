import sys
import os
import logging
from typing import Optional

from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl, QSettings, QLocale, QTranslator, QCoreApplication
import settings

logger = logging.getLogger(__name__)

# This global variable will store the application's root directory.
_APP_ROOT_DIR = None
_sound_player = None
_DEVELOPER_MODE_CACHE: Optional[bool] = None
_audio_output = None


def get_stt_model_path(engine: str, model_name: str) -> str:
    """
    Constructs the expected local path for STT models (VOSK or Whisper).
    """
    if engine == settings.STT_ENGINE_VOSK:
        # Assuming VOSK models are downloaded into a 'vosk_models' subdirectory
        # within the application's models directory.
        return get_resource_path(os.path.join("models", "vosk_models", model_name))
    elif engine == settings.STT_ENGINE_WHISPER:
        # Whisper models are managed by faster_whisper, which uses 'application/models'
        # as its download_root. We just need the model name.
        return get_resource_path("models")
    else:
        return ""

def _init_sound_player():
    """Initializes the shared QMediaPlayer instance for sound effects."""
    global _sound_player, _audio_output
    if _sound_player is None:
        q_settings = QSettings()
        _sound_player = QMediaPlayer()
        _audio_output = QAudioOutput()
        _sound_player.setAudioOutput(_audio_output)

        # Set volume from saved settings
        volume_int = q_settings.value(
            settings.QSETTINGS_KEY_SOUND_VOLUME, settings.SOUND_VOLUME_DEFAULT, type=int
        )
        volume_float = float(volume_int) / 100.0
        _audio_output.setVolume(volume_float)
        logger.debug(f"Sound player initialized with volume: {volume_float}")


def play_sound(sound_filename: str):
    """Plays a sound effect if they are enabled in settings."""
    q_settings = QSettings()
    is_enabled = q_settings.value(
        settings.QSETTINGS_KEY_SOUND_ENABLED,
        settings.SOUND_EFFECTS_ENABLED_DEFAULT,
        type=bool,
    )

    if not is_enabled:
        return

    _init_sound_player()

    sound_path_relative = os.path.join(settings.SOUNDS_DIR, sound_filename)
    sound_path_abs = get_resource_path(sound_path_relative)

    if os.path.exists(sound_path_abs):
        _sound_player.setSource(QUrl.fromLocalFile(sound_path_abs))
        _sound_player.play()
    else:
        logger.warning(f"Sound file not found: {sound_path_abs}")


def update_sound_volume():
    """Updates the volume of the sound player based on saved settings."""
    if _audio_output:
        q_settings = QSettings()
        volume_int = q_settings.value(
            settings.QSETTINGS_KEY_SOUND_VOLUME, settings.SOUND_VOLUME_DEFAULT, type=int
        )
        volume_float = float(volume_int) / 100.0
        _audio_output.setVolume(volume_float)
        logger.debug(f"Sound volume updated to: {volume_float}")


def set_app_root_dir(app_root_dir: str):
    """
    Sets the application's root directory.
    This should be called once at application startup from the main script.
    The root directory is used as the base for resolving relative paths
    when the application is not running in a frozen (e.g., Nuitka/PyInstaller) state.

    Args:
        app_root_dir (str): The absolute path to the application's root directory.
                           Typically, this is the directory containing the main entry script.
    """
    global _APP_ROOT_DIR
    if _APP_ROOT_DIR is not None:
        logger.warning(
            f"Application root directory is being re-set. Old: {_APP_ROOT_DIR}, New: {app_root_dir}"
        )
    _APP_ROOT_DIR = os.path.abspath(app_root_dir)
    logger.debug(f"Application root directory set to: {_APP_ROOT_DIR}")


def get_app_root_dir() -> str:
    """
    Gets the previously set application's root directory.
    Raises an error if the root directory has not been set, unless running frozen.

    Returns:
        str: The absolute path to the application's root directory.

    Raises:
        RuntimeError: If the application is not frozen and set_app_root_dir() has not been called.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # For frozen apps, _MEIPASS is always the root.
        return sys._MEIPASS

    if _APP_ROOT_DIR is None:
        # Attempt a fallback for non-frozen, non-set scenarios (e.g., running a utility script directly)
        logger.warning("_APP_ROOT_DIR not set explicitly. Attempting fallback.")
        try:
            # Try to get the directory of the main application script.
            # This is more robust than __main__.__file__ for certain execution contexts.
            import application.main
            fallback_root = os.path.dirname(os.path.abspath(application.main.__file__))
            logger.info(
                f"Fallback _APP_ROOT_DIR set to: {fallback_root} (derived from application.main.__file__)"
            )
            return fallback_root
        except (AttributeError, KeyError, ImportError):
            try:
                # Fallback to __main__.__file__ if application.main is not available or doesn't have __file__
                main_module_file = sys.modules["__main__"].__file__
                fallback_root = os.path.dirname(os.path.abspath(main_module_file))
                logger.info(
                    f"Fallback _APP_ROOT_DIR set to: {fallback_root} (derived from __main__.__file__)"
                )
                return fallback_root
            except (AttributeError, KeyError):
                # If __main__.__file__ is not available (e.g., interactive interpreter), use current working directory.
                fallback_root = os.getcwd()
                logger.warning(
                    f"Could not derive _APP_ROOT_DIR from application.main or __main__.__file__. Fallback to current working directory: {fallback_root}"
                )
                return fallback_root
    return _APP_ROOT_DIR


def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource file or directory.

    This function correctly resolves paths whether the application is running
    from source files or as a frozen executable (e.g., created by Nuitka or PyInstaller).

    Args:
        relative_path (str): The path relative to the application root.
                             Examples: "assets/icon.png", "translations/app_en.qm"

    Returns:
        str: The absolute path to the resource.
    """
    # Sanitize relative_path to use OS-specific separators
    relative_path = os.path.normpath(relative_path)

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Application is frozen (e.g., Nuitka or PyInstaller bundle)
        # sys._MEIPASS is the path to the temporary directory where bundled files are extracted.
        # This temporary directory acts as the application root.
        base_path = sys._MEIPASS
    else:
        # Application is running from source files.
        # Use the application root directory set by set_app_root_dir().
        base_path = get_app_root_dir()

    absolute_path = os.path.join(base_path, relative_path)
    logger.debug(
        f"Resolved resource path: '{relative_path}' -> '{absolute_path}' (Base: '{base_path}')"
    )
    return absolute_path


def apply_stylesheet(app_or_widget, qss_file_path: str):
    """
    Loads and applies a QSS stylesheet to the given application or widget.
    Logs errors if the file is not found or cannot be applied.
    """
    if os.path.exists(qss_file_path):
        try:
            with open(qss_file_path, "r", encoding="utf-8") as f:
                style_sheet_content = f.read()
            app_or_widget.setStyleSheet(style_sheet_content)
            logger.info(f"Successfully applied stylesheet from: {qss_file_path}")
        except Exception as e:
            logger.error(f"Failed to apply stylesheet from {qss_file_path}: {e}")
    else:
        logger.error(f"Stylesheet file not found at: {qss_file_path}")


def get_available_locales() -> dict[str, str]:
    """
    Scans the localization directory for available .qm files and returns a dictionary
    mapping display names (e.g., "English", "Tiếng Việt") to locale codes (e.g., "en", "vi").
    Includes a "System" default.
    """
    locales = {
        settings.DEFAULT_LOCALE: settings.DEFAULT_LOCALE
    }  # e.g. {"System": "System"}
    localization_dir_abs = get_resource_path(settings.LOCALIZATION_DIR)

    if not os.path.isdir(localization_dir_abs):
        logger.warning(f"Localization directory not found: {localization_dir_abs}")
        return locales

    for filename in os.listdir(localization_dir_abs):
        if filename.startswith("app_") and filename.endswith(".qm"):
            locale_code_full = filename[
                len("app_") : -len(".qm")
            ]  # e.g., "en_US", "vi"
            locale_code_short = locale_code_full.split("_")[0]  # e.g., "en", "vi"

            # Get native language name for display
            try:
                locale_obj = QLocale(locale_code_full)
                native_lang_name = locale_obj.nativeLanguageName().capitalize()
                if (
                    native_lang_name and locale_code_short not in locales.values()
                ):  # Add if not already present by short code
                    locales[native_lang_name] = (
                        locale_code_short  # Store short code for loading
                    )
            except Exception as e:
                logger.warning(
                    f"Could not get native name for locale code {locale_code_full}: {e}"
                )
                locales[locale_code_full] = locale_code_short  # Fallback to code
    return locales


def setup_initial_translation(app: QCoreApplication) -> Optional[QTranslator]:
    """
    Sets up application translations based on saved preference or system default.
    Returns the loaded translator instance or None.
    """
    q_settings = QSettings()  # QCoreApplication.instance() should provide this context

    user_locale_pref = q_settings.value(
        settings.QSETTINGS_KEY_LOCALE, settings.DEFAULT_LOCALE, type=str
    )

    if user_locale_pref == settings.DEFAULT_LOCALE:  # "System"
        locale_name_to_load = (
            settings.FORCE_LOCALE if settings.FORCE_LOCALE else QLocale.system().name()
        )
    else:
        locale_name_to_load = user_locale_pref

    translator = QTranslator(app)
    qm_file_path = get_resource_path(
        os.path.join(settings.LOCALIZATION_DIR, f"app_{locale_name_to_load}.qm")
    )
    if not translator.load(qm_file_path):
        lang_name = locale_name_to_load.split("_")[
            0
        ]  # Try short version (e.g., "en" from "en_US")
        qm_file_path_short = get_resource_path(
            os.path.join(settings.LOCALIZATION_DIR, f"app_{lang_name}.qm")
        )
        translator.load(qm_file_path_short)  # Attempt to load short version

    if translator.isEmpty():
        logger.warning(
            f"Could not load translation file for '{locale_name_to_load}' (tried {qm_file_path}). Running in default (English)."
        )
        return None
    else:
        logger.info(
            f"Loaded translation file: {qm_file_path if os.path.exists(qm_file_path) else qm_file_path_short}"
        )

    app.installTranslator(translator)
    return translator


def is_developer_mode_active() -> bool:
    """
    Checks if developer mode is active.
    Priority:
    1. Environment variable (e.g., LINGUALEARN_DEV_MODE=1 or true).
    2. QSettings.
    3. Default value from settings.py.
    The result is cached for the current session after the first check.
    """
    global _DEVELOPER_MODE_CACHE
    if _DEVELOPER_MODE_CACHE is not None:
        return _DEVELOPER_MODE_CACHE

    # 1. Check environment variable
    env_value = os.environ.get(settings.ENV_VAR_DEVELOPER_MODE, "").strip().lower()
    if env_value in ["1", "true", "yes", "on"]:
        _DEVELOPER_MODE_CACHE = True
        # Persist to QSettings if activated by env var for this session's QSettings
        if (
            QCoreApplication.instance()
            and QCoreApplication.organizationName()
            and QCoreApplication.applicationName()
        ):
            app_settings = QSettings()
            app_settings.setValue(settings.QSETTINGS_KEY_DEVELOPER_MODE, True)
        return True
    if env_value in ["0", "false", "no", "off"]:  # Explicitly disabled by env var
        _DEVELOPER_MODE_CACHE = False
        if (
            QCoreApplication.instance()
            and QCoreApplication.organizationName()
            and QCoreApplication.applicationName()
        ):
            app_settings = QSettings()
            app_settings.setValue(settings.QSETTINGS_KEY_DEVELOPER_MODE, False)
        return False

    # 2. Check QSettings (only if QApplication is initialized with org/app name)
    if (
        QCoreApplication.instance()
        and QCoreApplication.organizationName()
        and QCoreApplication.applicationName()
    ):
        app_settings = QSettings()
        if app_settings.contains(settings.QSETTINGS_KEY_DEVELOPER_MODE):
            # QSettings stores bools correctly, but convertFromString might be used by some.
            val = app_settings.value(
                settings.QSETTINGS_KEY_DEVELOPER_MODE,
                settings.DEVELOPER_MODE_DEFAULT,
                type=bool,
            )
            _DEVELOPER_MODE_CACHE = val
            return val

    # 3. Default
    _DEVELOPER_MODE_CACHE = settings.DEVELOPER_MODE_DEFAULT
    return _DEVELOPER_MODE_CACHE

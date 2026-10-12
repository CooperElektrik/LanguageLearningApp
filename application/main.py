import logging
import os
import sys

from PySide6.QtCore import (
    QCoreApplication,
    QElapsedTimer,
    Qt,
)  # Qt for alignment flags, Timers, Buffer
from PySide6.QtGui import QPixmap  # For splash screen
from PySide6.QtWidgets import (
    QApplication,
    QSplashScreen,
)  # QMessageBox is no longer directly used here

# --- Start of Patched Section for PyInstaller Compatibility ---

# Path configuration MUST be done before local imports.
# This ensures that whether running from source or a PyInstaller bundle,
# the Python path is set up correctly to find the application's modules.

# Check if running in a PyInstaller bundle by detecting the `_MEIPASS` attribute.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    # In a bundled app, `sys._MEIPASS` points to the temporary folder
    # where all bundled files are extracted. This is our effective project root.
    _project_root = sys._MEIPASS
    # We assume the `application` folder is a subdirectory in the bundle.
    _application_dir = os.path.join(_project_root, "application")
else:
    # In a normal development environment, calculate paths relative to this script.
    _application_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(_application_dir)

# Add the project root to `sys.path`. This allows for robust absolute imports
# like `from application import settings`.
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# With `sys.path` correctly set, we can now import our application modules.
# We use a try-except to handle different ways the script might be run.
try:
    from . import settings, utils
except (ImportError, ModuleNotFoundError):
    # This fallback is for scenarios like running `main.py` directly from inside
    # the `application` directory, where the `application` package itself isn't
    # in the path. We add `_application_dir` to the path to make this work.
    import settings
    import utils

# Now that `utils` is imported, we can configure its required path.
utils.set_app_root_dir(
    _application_dir
)  # `utils.get_resource_path` needs this base for relative paths.

# --- End of Patched Section ---


def setup_logging():
    # Determine log level. Developer mode forces DEBUG.
    log_level_setting = settings.LOG_LEVEL.upper()
    effective_log_level_str = log_level_setting

    # Note: is_developer_mode_active() uses QSettings, which needs OrgName/AppName.
    # This is why QCoreApplication setup is done before calling setup_logging() in main().
    if utils.is_developer_mode_active():
        effective_log_level_str = "DEBUG"
        # Temporary print as logger is not fully configured yet.
        print(
            f"INFO: Developer mode active. Log level forced to DEBUG (was {log_level_setting})."
        )

    logging.basicConfig(
        level=getattr(logging, effective_log_level_str, logging.INFO),
        format=settings.LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger(__name__)
    return logger


import time  # Import time module for wall time measurement


def main():
    # Record the start time for wall time measurement
    start_time = time.perf_counter()

    # QApplication must be created before QPixmap for splash if GUI elements are used early.
    # However, for a simple splash, QPixmap can be loaded first.
    # For consistency and potential future needs (e.g., early dialogs), create QApplication first.
    app = QApplication(sys.argv)
    splash: QSplashScreen | None = None
    splash_timer: QElapsedTimer | None = None

    # Set Organization and Application Name EARLY for QSettings and other Qt features
    QCoreApplication.setOrganizationName(settings.ORG_NAME)
    QCoreApplication.setApplicationName(settings.APP_NAME)

    # Logger setup should happen early
    global logger  # Make logger accessible globally in this module after setup
    logger = (
        setup_logging()
    )  # Now setup_logging can safely use utils.is_developer_mode_active()
    # Log the path setup now that the logger is available.
    logger.debug(f"Project root '{_project_root}' is in sys.path.")

    # --- Splash Screen Setup ---
    try:
        splash_path_abs = utils.get_resource_path(settings.SPLASH_IMAGE_FILE)

        pixmap = QPixmap()
        if os.path.exists(splash_path_abs) and pixmap.load(splash_path_abs):
            logger.info("Loaded splash image.")
            splash = QSplashScreen(pixmap)
            splash_timer = QElapsedTimer()
            splash_timer.start()  # Start timing how long the splash is shown
            splash.show()
            splash.showMessage(
                "Application is starting...",  # This message could be made translatable later if needed
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                Qt.GlobalColor.white,  # Adjust color for visibility against your splash image
            )
            app.processEvents()  # Ensure splash screen is displayed and message is updated
        else:
            logger.warning(
                f"Splash image not found at: {splash_path_abs}. Proceeding without splash screen."
            )
    except Exception as e:
        logger.error(f"Error during splash screen setup: {e}", exc_info=True)
    # --- End Splash Screen Setup ---

    logger.info(f"{settings.APP_NAME} application starting...")

    # The MainWindow now handles the course selection and initialization internally.
    # With project root on sys.path, use absolute import for MainWindow
    try:
        from application.core.stt_manager import STTManager
        from application.ui.main_window import MainWindow
    except ImportError:  # Nuitka will complain without this
        from core.stt_manager import STTManager
        from ui.main_window import MainWindow

    if splash:
        splash.showMessage(
            "Loading main window...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            Qt.GlobalColor.white,
        )
        app.processEvents()

    stt_manager = STTManager()
    main_window = MainWindow(stt_manager=stt_manager)
    # Initial translation is now handled inside MainWindow's __init__

    if utils.is_developer_mode_active():
        current_title = main_window.windowTitle()
        main_window.setWindowTitle(f"{current_title} [DEV MODE]")
        logger.info("Developer Mode is active. UI indicates this in the window title.")

    main_window.show()
    logger.info("Application main window shown.")

    # Record the end time for startup wall time measurement
    startup_end_time = time.perf_counter()
    startup_elapsed_time = startup_end_time - start_time
    logger.info(
        f"Application startup wall time (until main window shown): {startup_elapsed_time:.2f} seconds."
    )
    exit_code = app.exec()

    # Record the end time and print the elapsed time
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f"Application total runtime (wall time): {elapsed_time:.2f} seconds.")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

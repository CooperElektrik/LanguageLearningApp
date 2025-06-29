import sys
import os
import logging
from PySide6.QtWidgets import (
    QApplication,
    QSplashScreen,
)  # QMessageBox is no longer directly used here
from PySide6.QtGui import QPixmap  # For splash screen
from PySide6.QtCore import (
    QCoreApplication,
    Qt,
    QElapsedTimer,
    QTimer,
    QBuffer,
    QIODevice,
)  # Qt for alignment flags, Timers, Buffer
from PIL import Image  # Import Pillow

from typing import Optional

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
    from . import settings
    from . import utils
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


import time # Import time module for wall time measurement

def main():
    # Record the start time for wall time measurement
    start_time = time.perf_counter()

    # QApplication must be created before QPixmap for splash if GUI elements are used early.
    # However, for a simple splash, QPixmap can be loaded first.
    # For consistency and potential future needs (e.g., early dialogs), create QApplication first.
    app = QApplication(sys.argv)
    splash: Optional[QSplashScreen] = None
    splash_timer: Optional[QElapsedTimer] = None

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
        # --- Splash Screen Setup ---
        # Define target size for splash screen
        target_width = 896
        target_height = target_width

        # Paths for original and optimized splash images
        original_splash_path_relative = settings.SPLASH_IMAGE_FILE
        optimized_splash_path_relative = settings.SPLASH_IMAGE_OPTIMIZED_FILE
        
        original_splash_path_abs = utils.get_resource_path(original_splash_path_relative)
        optimized_splash_path_abs = utils.get_resource_path(optimized_splash_path_relative)

        pixmap = QPixmap()
        splash_image_loaded = False

        # Try to load the optimized image first
        if os.path.exists(optimized_splash_path_abs):
            logger.debug(f"Attempting to load optimized splash image from: {optimized_splash_path_abs}")
            if pixmap.load(optimized_splash_path_abs):
                logger.info("Loaded optimized splash image.")
                splash_image_loaded = True
            else:
                logger.warning(f"Failed to load optimized splash image from {optimized_splash_path_abs}. Attempting to re-generate.")
        
        if not splash_image_loaded:
            # If optimized not found or failed to load, process the original
            logger.debug(f"Attempting to load original splash image from: {original_splash_path_abs}")
            try:
                pil_image = Image.open(original_splash_path_abs)
                
                # Resize the image while maintaining aspect ratio
                pil_image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
                logger.debug(f"Resized splash image to: {pil_image.size}")

                # Determine format based on original file extension for saving
                image_format = os.path.splitext(original_splash_path_abs)[1].lstrip(".").upper()
                save_format = image_format
                if image_format == "JPG":  # Pillow uses 'JPEG'
                    save_format = "JPEG"
                elif image_format not in ["PNG", "JPEG", "BMP", "GIF", "WEBP"]: # Added WEBP
                    logger.warning(
                        f"Unknown image format for splash: {os.path.splitext(original_splash_path_abs)[1]}. Defaulting to PNG for saving."
                    )
                    save_format = "PNG" # Default to PNG if format is unknown/unsupported

                # Save the optimized image for future use
                pil_image.save(optimized_splash_path_abs, format=save_format)
                logger.info(f"Saved optimized splash image to: {optimized_splash_path_abs}")

                # Load the newly saved optimized image into QPixmap
                if pixmap.load(optimized_splash_path_abs):
                    splash_image_loaded = True
                else:
                    logger.error(f"Failed to load newly optimized splash image from {optimized_splash_path_abs}.")

            except FileNotFoundError:
                logger.warning(
                    f"Original splash image not found: {original_splash_path_abs}. Skipping splash screen."
                )
            except Exception as e:
                logger.error(f"Error processing original splash image: {e}", exc_info=True)

        if splash_image_loaded and not pixmap.isNull():
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
            logger.warning("No splash image could be loaded or generated. Proceeding without splash screen.")
    except Exception as e:
        logger.error(f"Error during splash screen setup: {e}", exc_info=True)
    # --- End Splash Screen Setup ---

    logger.info(f"{settings.APP_NAME} application starting...")

    # The MainWindow now handles the course selection and initialization internally.
    # With project root on sys.path, use absolute import for MainWindow
    try:
        from application.ui.main_window import MainWindow
        from application.core.stt_manager import STTManager
    except ImportError:  # Nuitka will complain without this
        from ui.main_window import MainWindow
        from core.stt_manager import STTManager

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
    logger.info(f"Application startup wall time (until main window shown): {startup_elapsed_time:.2f} seconds.")
    exit_code = app.exec()

    # Record the end time and print the elapsed time
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f"Application total runtime (wall time): {elapsed_time:.2f} seconds.")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

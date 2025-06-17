import sys
import os
import logging
from PySide6.QtWidgets import QApplication, QSplashScreen # QMessageBox is no longer directly used here
from PySide6.QtGui import QPixmap # For splash screen
from PySide6.QtCore import QCoreApplication, Qt, QElapsedTimer, QTimer, QBuffer, QIODevice # Qt for alignment flags, Timers, Buffer
from PIL import Image # Import Pillow

from typing import Optional

try:
    from . import settings
    from . import utils
except ImportError:
    # Fallback for scenarios where main.py might be run in an unusual context
    # or if settings/utils are needed before sys.path is fully configured.
    import settings
    import utils 

# Determine the application directory and the project root
_application_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_application_dir)

utils.set_app_root_dir(_application_dir) # utils.get_resource_path needs the 'application' dir as its base for relative paths like "ui/styles"

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
    # logger is defined after setup_logging, so use print or basicConfig for early debug if needed
    # logging.debug(f"Added project root '{_project_root}' to sys.path for main application.")

def setup_logging():
    # Determine log level. Developer mode forces DEBUG.
    log_level_setting = settings.LOG_LEVEL.upper()
    effective_log_level_str = log_level_setting

    # Note: is_developer_mode_active() uses QSettings, which needs OrgName/AppName.
    # This is why QCoreApplication setup is done before calling setup_logging() in main().
    if utils.is_developer_mode_active():
        effective_log_level_str = "DEBUG"
        # Temporary print as logger is not fully configured yet.
        print(f"INFO: Developer mode active. Log level forced to DEBUG (was {log_level_setting}).")

    logging.basicConfig(
        level=getattr(logging, effective_log_level_str, logging.INFO),
        format=settings.LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger(__name__)
    return logger

def main():
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
    global logger # Make logger accessible globally in this module after setup
    logger = setup_logging() # Now setup_logging can safely use utils.is_developer_mode_active()
    if _project_root not in sys.path: # Log after logger is available
        logger.debug(f"Project root '{_project_root}' was already in sys.path or just added.")
    # --- Splash Screen Setup ---
    try:
        splash_image_path_relative = settings.SPLASH_IMAGE_FILE
        splash_image_path_abs = utils.get_resource_path(splash_image_path_relative)
        logger.debug(f"Attempting to load splash image from: {splash_image_path_abs}")

        # --- Load and Resize Image using Pillow ---
        pil_image = None
        try:
            pil_image = Image.open(splash_image_path_abs)
            # Define your desired splash screen size
            target_width = 600
            target_height = 400
            
            # Resize the image while maintaining aspect ratio
            pil_image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            logger.debug(f"Resized splash image to: {pil_image.size}")

            # Convert PIL Image to QPixmap
            # Need to save to a buffer first
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.ReadWrite)
            # Determine format based on original file extension
            image_format = os.path.splitext(splash_image_path_abs)[1].lstrip('.').upper()
            
            save_format = image_format
            if image_format == 'JPG': # Pillow uses 'JPEG'
                save_format = 'JPEG'
            elif image_format not in ['PNG', 'JPEG', 'BMP', 'GIF']: # Check against Pillow's common save formats
                 image_format = 'PNG' # Default to PNG if format is unknown/unsupported
                 logger.warning(f"Unknown image format for splash: {os.path.splitext(splash_image_path_abs)[1]}. Defaulting to PNG.")
                 save_format = 'PNG' # And for saving

            pil_image.save(buffer, format=save_format)
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.data(), image_format)
            buffer.close()
        except FileNotFoundError:
            logger.warning(f"Splash image not found or invalid: {splash_image_path_abs}. Skipping splash screen.")
            pixmap = QPixmap() # Create a null pixmap
        else:
            splash = QSplashScreen(pixmap)
            
            splash_timer = QElapsedTimer()
            splash_timer.start() # Start timing how long the splash is shown
            splash.show()
            splash.showMessage(
                "LinguaLearn is starting...", # This message could be made translatable later if needed
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                Qt.GlobalColor.white # Adjust color for visibility against your splash image
            )
            app.processEvents() # Ensure splash screen is displayed and message is updated
    except Exception as e:
        logger.error(f"Error during splash screen setup: {e}", exc_info=True)
    # --- End Splash Screen Setup ---

    logger.info(f"{settings.APP_NAME} application starting...")

    # The MainWindow now handles the course selection and initialization internally.
    # With project root on sys.path, use absolute import for MainWindow
    try:
        from application.ui.main_window import MainWindow
    except ImportError: # Nuitka will complain without this
        from ui.main_window import MainWindow
    
    if splash:
        splash.showMessage(
            "Loading main window...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            Qt.GlobalColor.white
        )
        app.processEvents()

    main_window = MainWindow()
    # Initial translation is now handled inside MainWindow's __init__

    if utils.is_developer_mode_active():
        current_title = main_window.windowTitle()
        main_window.setWindowTitle(f"{current_title} [DEV MODE]")
        logger.info("Developer Mode is active. UI indicates this in the window title.")
    
    # --- Finish Splash Screen ---
    if splash and splash_timer:
        elapsed_ms = splash_timer.elapsed()
        minimum_display_time_ms = 1000 # 1 second
        
        if elapsed_ms < minimum_display_time_ms:
            remaining_time = minimum_display_time_ms - elapsed_ms
            logger.debug(f"App loaded quickly ({elapsed_ms}ms). Waiting {remaining_time}ms for minimum splash display.")
            QTimer.singleShot(remaining_time, lambda: splash.finish(main_window))
        else:
            logger.debug(f"App loading took {elapsed_ms}ms. Minimum splash time met.")
        splash.finish(main_window) # Close splash when main window is ready

    main_window.show()
    logger.info("Application main window shown.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
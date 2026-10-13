import logging
import logging.handlers
import os
import sys
import time

from PySide6.QtCore import (
    QCoreApplication,
    QElapsedTimer,
    Qt,
    QTimer,
)  # Qt for alignment flags, Timers, Buffer
from PySide6.QtGui import QPixmap  # For splash screen
from PySide6.QtWidgets import (
    QApplication,
    QSplashScreen,
    QWidget,
)  # QMessageBox is no longer directly used here

# --- Start of Patched Section for PyInstaller Compatibility ---

# Path configuration MUST be done before local imports.
# This ensures that whether running from source or a PyInstaller bundle,
# the Python path is set up correctly to find the application's modules.

# Check if running in a PyInstaller bundle by detecting the `_MEIPASS` attribute.
_meipass = getattr(sys, "_MEIPASS", None)
if getattr(sys, "frozen", False) and _meipass:
    # In a bundled app, `sys._MEIPASS` points to the temporary folder
    # where all bundled files are extracted. This is our effective project root.
    _project_root = str(_meipass)
    # We assume the `application` folder is a subdirectory in the bundle.
    _application_dir = os.path.join(_project_root, "application")
else:
    # In a normal development environment, calculate paths relative to this script.
    _application_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(_application_dir)

# Add the project root and application directory to `sys.path`.
# This allows for robust absolute imports like `from application import settings`
# as well as internal imports like `import settings`, `from core...`, and `from ui...`.
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _application_dir not in sys.path:
    sys.path.insert(0, _application_dir)

# With `sys.path` correctly set, we can now import our application modules.
# We use a try-except to handle different ways the script might be run.
try:
    from . import settings, utils  # noqa: E402
except (ImportError, ModuleNotFoundError):
    # This fallback is for scenarios like running `main.py` directly from inside
    # the `application` directory, where the `application` package itself isn't
    # in the path.
    import settings  # noqa: E402
    import utils  # noqa: E402

# Ensure both bare names and package-qualified names point to the same module instance.
sys.modules.setdefault("settings", settings)
sys.modules.setdefault("utils", utils)
sys.modules.setdefault("application.settings", settings)
sys.modules.setdefault("application.utils", utils)

# Now that `utils` is imported, we can configure its required path.
utils.set_app_root_dir(
    _application_dir
)  # `utils.get_resource_path` needs this base for relative paths.

# --- End of Patched Section ---

logger = logging.getLogger(__name__)


def setup_logging():
    # Determine log level. Developer mode forces DEBUG.
    log_level_setting = settings.LOG_LEVEL.upper()
    effective_log_level_str = log_level_setting

    # Note: is_developer_mode_active() uses QSettings, which needs OrgName/AppName.
    # This is why QCoreApplication setup is done before calling setup_logging() in main().
    if utils.is_developer_mode_active():
        effective_log_level_str = "DEBUG"
        print(f"INFO: Developer mode active. Log level forced to DEBUG (was {log_level_setting}).")

    handlers = []
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))

    log_dir = utils.get_log_dir()
    log_file = os.path.join(log_dir, "app.log")
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handlers.append(file_handler)
    except Exception as e:
        print(f"WARNING: Could not initialize log file handler at {log_file}: {e}")

    logging.basicConfig(
        level=getattr(logging, effective_log_level_str, logging.INFO),
        format=settings.LOG_FORMAT,
        handlers=handlers,
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger


def install_crash_handler(log_dir: str):
    """Installs a global exception hook to capture crashes and alert users."""
    crash_dialog_open = False

    def handle_exception(exc_type, exc_value, exc_traceback):
        nonlocal crash_dialog_open
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        import traceback

        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logging.critical(f"Unhandled exception caught by global hook:\n{tb_str}")

        app = QApplication.instance()
        if app is not None and not crash_dialog_open:
            crash_dialog_open = True
            try:
                from PySide6.QtWidgets import QMessageBox

                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Icon.Critical)
                msg_box.setWindowTitle("Application Error")
                msg_box.setText("An unexpected error occurred in LanguageLearningApp.")
                msg_box.setInformativeText(
                    f"A crash log has been saved to:\n{log_dir}\n\nPlease share this traceback if reporting the issue."
                )
                msg_box.setDetailedText(tb_str)
                msg_box.exec()
            except Exception:
                pass
            finally:
                crash_dialog_open = False

    sys.excepthook = handle_exception


def finish_splash_screen(
    splash: QSplashScreen | None,
    splash_timer: QElapsedTimer | None,
    main_window: QWidget,
    minimum_display_time_ms: int = 1000,
) -> None:
    """Closes the splash screen once the main window is ready, honoring a minimum display time."""
    if not splash:
        return

    def _finish() -> None:
        try:
            splash.finish(main_window)
        except Exception as e:
            logger.debug(f"Error finishing splash screen: {e}")

    if splash_timer:
        elapsed_ms = splash_timer.elapsed()
        if elapsed_ms < minimum_display_time_ms:
            remaining_time = max(1, int(minimum_display_time_ms - elapsed_ms))
            logger.debug(
                f"App loaded quickly ({elapsed_ms}ms). Waiting {remaining_time}ms for minimum splash display."
            )
            QTimer.singleShot(remaining_time, _finish)
            return
        logger.debug(f"App loading took {elapsed_ms}ms. Minimum splash time met.")

    _finish()


def main():
    # Record the start time for wall time measurement
    start_time = time.perf_counter()

    # QApplication must be created before QPixmap for splash if GUI elements are used early.
    # However, for a simple splash, QPixmap can be loaded first.
    # For consistency and potential future needs (e.g., early dialogs), create QApplication first.
    app = QApplication(sys.argv)
    # Use Qt's Fusion style as the single, minimal look-and-feel baseline. It is
    # consistent across platforms and needs no custom stylesheet to look right.
    app.setStyle("Fusion")
    splash: QSplashScreen | None = None
    splash_timer: QElapsedTimer | None = None

    # Set Organization and Application Name EARLY for QSettings and other Qt features
    QCoreApplication.setOrganizationName(settings.ORG_NAME)
    QCoreApplication.setApplicationName(settings.APP_NAME)

    # Logger setup should happen early
    global logger  # Make logger accessible globally in this module after setup
    logger = setup_logging()  # Now setup_logging can safely use utils.is_developer_mode_active()
    install_crash_handler(utils.get_log_dir())
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
        from core.stt_manager import STTManager
        from ui.main_window import MainWindow
    except ImportError:  # Fallback for environments requiring package prefix
        from application.core.stt_manager import STTManager
        from application.ui.main_window import MainWindow

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

    # --- Finish Splash Screen ---
    finish_splash_screen(splash, splash_timer, main_window)

    exit_code = app.exec()

    # Record the end time and print the elapsed time
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f"Application total runtime (wall time): {elapsed_time:.2f} seconds.")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

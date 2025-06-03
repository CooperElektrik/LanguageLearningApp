# application/utils.py

import sys
import os
import logging

logger = logging.getLogger(__name__)

# This global variable will store the application's root directory.
# It's set by main.py (or another entry point) early in the application's lifecycle.
_APP_ROOT_DIR = None

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
        logger.warning(f"Application root directory is being re-set. Old: {_APP_ROOT_DIR}, New: {app_root_dir}")
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
            # Try to get the directory of the script that was initially run.
            # This assumes __main__ module has a __file__ attribute.
            main_module_file = sys.modules['__main__'].__file__
            fallback_root = os.path.dirname(os.path.abspath(main_module_file))
            logger.info(f"Fallback _APP_ROOT_DIR set to: {fallback_root} (derived from __main__.__file__)")
            return fallback_root
        except (AttributeError, KeyError):
            # If __main__.__file__ is not available (e.g., interactive interpreter), use current working directory.
            fallback_root = os.getcwd()
            logger.warning(f"Could not derive __main__.__file__. Fallback _APP_ROOT_DIR set to current working directory: {fallback_root}")
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
    logger.debug(f"Resolved resource path: '{relative_path}' -> '{absolute_path}' (Base: '{base_path}')")
    return absolute_path
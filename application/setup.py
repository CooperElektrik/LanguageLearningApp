import sys
from cx_Freeze import setup, Executable

# === Application Details ===
# Fetched from the app's own settings for consistency.
from settings import APP_NAME as LINGUALEARN_APP_NAME

APP_VERSION = "1.0"
APP_DESCRIPTION = (
    "An interactive language learning platform with course editing capabilities."
)
MAIN_SCRIPT = "main.py"
EXECUTABLE_NAME = LINGUALEARN_APP_NAME  # Use the name from settings for the final .exe

# === Platform-Specific Configuration ===
# For GUI applications on Windows, use "Win32GUI" to hide the console window.
base = None
if sys.platform == "win32":
    base = "Win32GUI"
    # Ensure the .exe extension for Windows
    if not EXECUTABLE_NAME.lower().endswith(".exe"):
        EXECUTABLE_NAME += ".exe"

# === Build Options ===
# This dictionary configures the build process.

build_exe_options = {
    # --- Exclude Unnecessary Modules ---
    # Corresponds to Nuitka's '--nofollow-import-to'.
    # Excludes large or unneeded parts of libraries to reduce final build size.
    "excludes": [
        "tkinter",
        "unittest",
        "email",
        "http",
        "xml",
        "pydoc_data",
        "curses",
        # Torch modules not needed for inference with faster-whisper
        "torch._dynamo",
        "torch._inductor",
        "torch.autograd",
        "torch.jit",
        "torch.optim",
        # Large parts of sympy are often not needed
        "sympy.geometry",
        "sympy.physics",
    ],
    # --- Include Data Files & Directories ---
    "include_files": [
        ("courses", "courses"),
        ("assets", "assets"),
        ("ui/styles", "ui/styles"),
        ("localization", "localization"),
    ],
    "packages": [
        "PySide6",
        "torch",
        "faster_whisper",
        "Levenshtein",
        "markdown",
        "yaml",
        "PIL",
    ],
    # --- Silent Build ---
    # Set to True to reduce console output during the build process.
    "silent": True,
    "optimize": 2,
}

# === Setup Configuration ===
# This section brings everything together for cx_Freeze.

setup(
    name=LINGUALEARN_APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            MAIN_SCRIPT,
            base=base,
            target_name=EXECUTABLE_NAME,
            icon="assets/icons/app_icon.ico",  # Specify an application icon
        )
    ],
)

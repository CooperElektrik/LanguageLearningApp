import sys
import os
import logging
from PySide6.QtWidgets import QApplication

# IMPORTANT: Adjust Python path to allow importing 'core' from the 'application' directory
# This assumes 'tools' and 'application' are siblings in the same parent directory.
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_script_dir, '..'))
application_dir = os.path.join(parent_dir, 'application')

if application_dir not in sys.path:
    sys.path.insert(0, application_dir)
    logging.info(f"Added '{application_dir}' to sys.path for core module imports.")

# Now, imports from 'application' (like 'core.models') should work
try:
    from tools.editor_window import EditorWindow
except ImportError:
    print("Try running the editor with `python -m tools.main_editor` instead.")

# Configure basic logging for the editor tool
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout) # Log to console
        # logging.FileHandler("editor.log") # Uncomment to log to a file
    ]
)
logger = logging.getLogger(__name__)


def main():
    app = QApplication(sys.argv)
    logger.info("LinguaLearn Course Editor starting...")

    editor = EditorWindow()
    editor.show()

    logger.info("Editor main window shown.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
import sys
import os
import logging
from PySide6.QtWidgets import QApplication

current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_script_dir, "..", ".."))

if project_root not in sys.path:
    sys.path.insert(0, project_root)
    logging.info(f"Added '{project_root}' to sys.path for project-wide module imports.")

try:
    from tools.editor_window import EditorWindow
except ImportError as e:
    logging.error(f"Failed to import core editor modules. Please ensure your Python environment is set up correctly. Error: {e}")
    print("If you are running this file directly, ensure your project root is in your Python path.")
    print(f"Consider running with `python -m application.tools.main_editor` from '{project_root}'")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    app = QApplication(sys.argv)
    logger.info("LL Course Editor starting...")

    editor = EditorWindow()
    editor.show()

    logger.info("Editor main window shown.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

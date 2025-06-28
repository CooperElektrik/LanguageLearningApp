import os
import sys
import logging
import subprocess
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QTextEdit,
    QPushButton,
    QLabel,
    QMessageBox,
    QListWidgetItem,
)
from PySide6.QtCore import Qt

from application import utils

logger = logging.getLogger(__name__)

class PygletScriptRunnerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Pyglet Script Runner"))
        self.setGeometry(200, 200, 1000, 700)

        self.script_dir = utils.get_resource_path(os.path.join("scripts"))

        self._setup_ui()
        self._populate_script_list()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)

        # Left Panel: Script List
        left_panel_layout = QVBoxLayout()
        warning_label = QLabel(self.tr("WARNING: Although this tools intended purpose is only to display cool things written in Pyglet, it can run arbitrary Python scripts.\n"
                                       "Only run scripts from trusted sources.\n"
                                       "Running untrusted scripts can compromise your system."))
        warning_label.setStyleSheet("color: red; font-weight: bold;")
        warning_label.setWordWrap(True)
        left_panel_layout.addWidget(warning_label)
        left_panel_layout.addWidget(QLabel(self.tr("Available Pyglet Scripts:")))
        self.script_list_widget = QListWidget()
        self.script_list_widget.currentItemChanged.connect(self._load_script_content)
        left_panel_layout.addWidget(self.script_list_widget)

        self.run_script_button = QPushButton(self.tr("Run Selected Script"))
        self.run_script_button.clicked.connect(self._run_selected_script)
        left_panel_layout.addWidget(self.run_script_button)

        main_layout.addLayout(left_panel_layout, 1) # 1/3 width

        # Right Panel: Script Content Display
        right_panel_layout = QVBoxLayout()
        right_panel_layout.addWidget(QLabel(self.tr("Script Content:")))
        self.script_content_editor = QTextEdit()
        self.script_content_editor.setReadOnly(True)
        self.script_content_editor.setFontFamily("Consolas") # Monospace font
        self.script_content_editor.setFontPointSize(10)
        right_panel_layout.addWidget(self.script_content_editor)

        main_layout.addLayout(right_panel_layout, 2) # 2/3 width

    def _populate_script_list(self):
        if not os.path.exists(self.script_dir):
            logger.warning(f"Pyglet script directory not found: {self.script_dir}")
            QMessageBox.warning(self, self.tr("Error"), self.tr(f"Pyglet script directory not found: {self.script_dir}"))
            return

        self.script_list_widget.clear()
        for filename in os.listdir(self.script_dir):
            if filename.endswith(".py"):
                item = QListWidgetItem(filename)
                item.setData(Qt.UserRole, os.path.join(self.script_dir, filename)) # Store full path
                self.script_list_widget.addItem(item)
        
        if self.script_list_widget.count() > 0:
            self.script_list_widget.setCurrentRow(0) # Select first item by default

    def _load_script_content(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        if current_item:
            script_path = current_item.data(Qt.UserRole)
            try:
                with open(script_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.script_content_editor.setText(content)
            except Exception as e:
                logger.error(f"Failed to read script {script_path}: {e}")
                self.script_content_editor.setText(self.tr(f"Error loading script: {e}"))
        else:
            self.script_content_editor.clear()

    def _run_selected_script(self):
        selected_item = self.script_list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, self.tr("No Script Selected"), self.tr("Please select a Pyglet script to run."))
            return

        script_path = selected_item.data(Qt.UserRole)
        logger.info(f"Attempting to run Pyglet script: {script_path}")
        try:
            # Run the script in a separate process
            # Using sys.executable ensures the script is run with the same Python interpreter
            # that is running the main application.
            subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            logger.error(f"Failed to launch Pyglet script {script_path}: {e}")
            QMessageBox.critical(self, self.tr("Error"), self.tr(f"Failed to launch Pyglet script: {e}"))

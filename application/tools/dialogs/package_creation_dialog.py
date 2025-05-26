from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QFileDialog, QFormLayout, QMessageBox)
from PySide6.QtCore import Qt, Signal

class PackageCreationDialog(QDialog):
    def __init__(self, parent=None, default_manifest_path: str = "", default_package_name_stem: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Create Course Package")
        self.setMinimumSize(400, 250)

        self.manifest_path = default_manifest_path
        self.output_dir = "" # Will default to manifest dir if not set
        self.package_name_override = default_package_name_stem
        
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Manifest File (pre-filled, read-only with browse for safety)
        manifest_layout = QHBoxLayout()
        self.manifest_path_input = QLineEdit(self.manifest_path)
        self.manifest_path_input.setReadOnly(True)
        # Allow browsing for manifest in case the default isn't what user wants to package
        manifest_browse_button = QPushButton("Browse Manifest...")
        manifest_browse_button.clicked.connect(self._select_manifest_file)
        manifest_layout.addWidget(QLabel("Manifest File:"))
        manifest_layout.addWidget(self.manifest_path_input)
        manifest_layout.addWidget(manifest_browse_button)
        main_layout.addLayout(manifest_layout)

        # Output Directory
        output_dir_layout = QHBoxLayout()
        self.output_dir_input = QLineEdit()
        output_dir_input_button = QPushButton("Browse...")
        output_dir_input_button.clicked.connect(self._select_output_directory)
        output_dir_layout.addWidget(QLabel("Output Directory:"))
        output_dir_layout.addWidget(self.output_dir_input)
        output_dir_layout.addWidget(output_dir_input_button)
        main_layout.addLayout(output_dir_layout)

        # Package Name Override
        name_layout = QHBoxLayout()
        self.package_name_input = QLineEdit(self.package_name_override)
        name_layout.addWidget(QLabel("Custom Package Name:"))
        name_layout.addWidget(self.package_name_input)
        main_layout.addLayout(name_layout)

        # Action Buttons
        button_layout = QHBoxLayout()
        package_button = QPushButton("Create Package")
        package_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch(1)
        button_layout.addWidget(package_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def _select_manifest_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Manifest File", self.manifest_path, "YAML Files (*.yaml *.yml)")
        if filepath:
            self.manifest_path_input.setText(filepath)
            self.manifest_path = filepath # Update internal var

    def _select_output_directory(self):
        dirpath = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.output_dir if self.output_dir else self.manifest_path)
        if dirpath:
            self.output_dir_input.setText(dirpath)

    def get_data(self) -> dict:
        return {
            "manifest_filepath": self.manifest_path_input.text(),
            "output_dir": self.output_dir_input.text() if self.output_dir_input.text() else None,
            "package_name_override": self.package_name_input.text() if self.package_name_input.text().strip() else None
        }
    
    def accept(self):
        # Basic validation before accepting
        data = self.get_data()
        if not data["manifest_filepath"]:
            QMessageBox.warning(self, "Missing Input", "Please select a Manifest file to package.")
            return
        
        super().accept()
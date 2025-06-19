from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QComboBox,
    QFormLayout,
    QMessageBox,
    QScrollArea,
    QWidget,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class CsvImportDialog(QDialog):
    def __init__(
        self, parent=None, current_unit_id: str = "", current_lesson_id: str = ""
    ):
        super().__init__(parent)
        self.setWindowTitle("Import Exercises from CSV")
        self.setMinimumSize(500, 400)

        self.csv_file_path = ""
        self.exercise_type = ""
        self.unit_id = current_unit_id
        self.unit_title = ""
        self.lesson_id = current_lesson_id
        self.lesson_title = ""
        self.custom_cols = {}

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        file_layout = QHBoxLayout()
        self.csv_path_input = QLineEdit()
        self.csv_path_input.setReadOnly(True)
        file_button = QPushButton("Browse CSV...")
        file_button.clicked.connect(self._select_csv_file)
        file_layout.addWidget(QLabel("CSV File:"))
        file_layout.addWidget(self.csv_path_input)
        file_layout.addWidget(file_button)
        main_layout.addLayout(file_layout)

        type_layout = QHBoxLayout()
        self_exercise_types = [
            "translate_to_target",
            "translate_to_source",
            "dictation",
            "multiple_choice_translation",
            "image_association",
            "listen_and_select",
            "sentence_jumble",
            "context_block",
        ]
        self.exercise_type_combo = QComboBox()
        self.exercise_type_combo.addItems(self_exercise_types)
        self.exercise_type_combo.currentIndexChanged.connect(self._update_column_inputs)
        type_layout.addWidget(QLabel("Exercise Type:"))
        type_layout.addWidget(self.exercise_type_combo)
        main_layout.addLayout(type_layout)

        target_group = QGroupBox("Target Unit/Lesson")
        target_layout = QFormLayout(target_group)
        self.unit_id_input = QLineEdit(self.unit_id)
        self.unit_title_input = QLineEdit(self.unit_title)
        self.lesson_id_input = QLineEdit(self.lesson_id)
        self.lesson_title_input = QLineEdit(self.lesson_title)
        target_layout.addRow("Unit ID:", self.unit_id_input)
        target_layout.addRow("Unit Title (if new):", self.unit_title_input)
        target_layout.addRow("Lesson ID:", self.lesson_id_input)
        target_layout.addRow("Lesson Title (if new):", self.lesson_title_input)
        main_layout.addWidget(target_group)

        self.column_mapping_group = QGroupBox("Custom Column Mapping (Optional)")
        self.column_mapping_layout = QFormLayout(self.column_mapping_group)
        main_layout.addWidget(self.column_mapping_group)
        self._update_column_inputs()

        button_layout = QHBoxLayout()
        import_button = QPushButton("Import")
        import_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch(1)
        button_layout.addWidget(import_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def _select_csv_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)"
        )
        if filepath:
            self.csv_path_input.setText(filepath)

    def _update_column_inputs(self):
        while self.column_mapping_layout.count() > 0:
            item = self.column_mapping_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count() > 0:
                    sub_item = item.layout().takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()

        current_type = self.exercise_type_combo.currentText()
        self.column_mapping_group.setTitle(
            f"Custom Column Mapping (for {current_type})"
        )

        if current_type in ["translate_to_target", "translate_to_source", "dictation"]:
            self.prompt_col_input = QLineEdit("prompt")
            self.answer_col_input = QLineEdit("answer")
            self.column_mapping_layout.addRow("Prompt Column:", self.prompt_col_input)
            self.column_mapping_layout.addRow("Answer Column:", self.answer_col_input)
            if current_type == "dictation":
                self.audio_file_col_input = QLineEdit("audio_file")
                self.column_mapping_layout.addRow(
                    "Audio File Column:", self.audio_file_col_input
                )

        elif current_type == "multiple_choice_translation":
            self.source_word_col_input = QLineEdit("source_word")
            self.correct_option_col_input = QLineEdit("correct_option")
            self.incorrect_options_cols_input = QLineEdit(
                "incorrect_option_1,incorrect_option_2,incorrect_option_3"
            )
            self.incorrect_options_prefix_input = QLineEdit("incorrect_option_")

            self.column_mapping_layout.addRow(
                "Source Word Column:", self.source_word_col_input
            )
            self.column_mapping_layout.addRow(
                "Correct Option Column:", self.correct_option_col_input
            )
            self.column_mapping_layout.addRow(
                "Incorrect Options (comma-separated names):",
                self.incorrect_options_cols_input,
            )
            self.column_mapping_layout.addRow(
                "Or Prefix (e.g., 'incorrect_option_'):",
                self.incorrect_options_prefix_input,
            )
        elif current_type == "image_association":
            self.prompt_col_input = QLineEdit("prompt")
            self.image_file_col_input = QLineEdit("image_file")
            self.correct_option_col_input = QLineEdit("correct_option")
            self.incorrect_options_cols_input = QLineEdit("incorrect_1,incorrect_2")
            self.column_mapping_layout.addRow("Prompt Column:", self.prompt_col_input)
            self.column_mapping_layout.addRow(
                "Image File Column:", self.image_file_col_input
            )
            self.column_mapping_layout.addRow(
                "Correct Option Column:", self.correct_option_col_input
            )
            self.column_mapping_layout.addRow(
                "Incorrect Options (comma-separated):",
                self.incorrect_options_cols_input,
            )
        elif current_type == "listen_and_select":
            self.prompt_col_input = QLineEdit("prompt")
            self.audio_file_col_input = QLineEdit("audio_file")
            self.correct_option_col_input = QLineEdit("correct_option")
            self.incorrect_options_cols_input = QLineEdit("incorrect_1,incorrect_2")
            self.column_mapping_layout.addRow("Prompt Column:", self.prompt_col_input)
            self.column_mapping_layout.addRow(
                "Audio File Column:", self.audio_file_col_input
            )
            self.column_mapping_layout.addRow(
                "Correct Option Column:", self.correct_option_col_input
            )
            self.column_mapping_layout.addRow(
                "Incorrect Options (comma-separated):",
                self.incorrect_options_cols_input,
            )
        elif current_type == "sentence_jumble":
            self.prompt_col_input = QLineEdit("prompt")
            self.words_col_input = QLineEdit("words")
            self.answer_col_input = QLineEdit("answer")
            self.column_mapping_layout.addRow("Prompt Column:", self.prompt_col_input)
            self.column_mapping_layout.addRow(
                "Words Column (space-separated):", self.words_col_input
            )
            self.column_mapping_layout.addRow(
                "Answer Column (full sentence):", self.answer_col_input
            )
        elif current_type == "context_block":
            self.title_col_input = QLineEdit("title")
            self.prompt_col_input = QLineEdit("prompt")
            self.column_mapping_layout.addRow("Title Column:", self.title_col_input)
            self.column_mapping_layout.addRow(
                "Content/Prompt Column:", self.prompt_col_input
            )

    def get_data(self) -> dict:
        data = {
            "csv_filepath": self.csv_path_input.text(),
            "exercise_type": self.exercise_type_combo.currentText(),
            "unit_id": self.unit_id_input.text(),
            "unit_title": self.unit_title_input.text(),
            "lesson_id": self.lesson_id_input.text(),
            "lesson_title": self.lesson_title_input.text(),
            "custom_cols": {},
        }

        current_type = self.exercise_type_combo.currentText()
        if current_type in ["translate_to_target", "translate_to_source", "dictation"]:
            data["custom_cols"]["prompt_col"] = self.prompt_col_input.text()
            data["custom_cols"]["answer_col"] = self.answer_col_input.text()
            if current_type == "dictation":
                data["custom_cols"]["audio_file_col"] = self.audio_file_col_input.text()
        elif current_type == "multiple_choice_translation":
            data["custom_cols"]["source_word_col"] = self.source_word_col_input.text()
            data["custom_cols"][
                "correct_option_col"
            ] = self.correct_option_col_input.text()
            data["custom_cols"]["incorrect_options_cols"] = [
                s.strip()
                for s in self.incorrect_options_cols_input.text().split(",")
                if s.strip()
            ]
            data["custom_cols"][
                "incorrect_options_prefix"
            ] = self.incorrect_options_prefix_input.text()

        elif current_type == "image_association":
            data["custom_cols"]["prompt_col"] = self.prompt_col_input.text()
            data["custom_cols"]["image_file_col"] = self.image_file_col_input.text()
            data["custom_cols"][
                "correct_option_col"
            ] = self.correct_option_col_input.text()
            data["custom_cols"]["incorrect_options_cols"] = [
                s.strip()
                for s in self.incorrect_options_cols_input.text().split(",")
                if s.strip()
            ]

        elif current_type == "listen_and_select":
            data["custom_cols"]["prompt_col"] = self.prompt_col_input.text()
            data["custom_cols"]["audio_file_col"] = self.audio_file_col_input.text()
            data["custom_cols"][
                "correct_option_col"
            ] = self.correct_option_col_input.text()
            data["custom_cols"]["incorrect_options_cols"] = [
                s.strip()
                for s in self.incorrect_options_cols_input.text().split(",")
                if s.strip()
            ]

        elif current_type == "sentence_jumble":
            data["custom_cols"]["prompt_col"] = self.prompt_col_input.text()
            data["custom_cols"]["words_col"] = self.words_col_input.text()
            data["custom_cols"]["answer_col"] = self.answer_col_input.text()

        elif current_type == "context_block":
            data["custom_cols"]["title_col"] = self.title_col_input.text()
            data["custom_cols"]["prompt_col"] = self.prompt_col_input.text()

        return data

    def accept(self):
        data = self.get_data()
        if not data["csv_filepath"]:
            QMessageBox.warning(self, "Missing Input", "Please select a CSV file.")
            return
        if not data["unit_id"]:
            QMessageBox.warning(self, "Missing Input", "Please provide a Unit ID.")
            return
        if not data["lesson_id"]:
            QMessageBox.warning(self, "Missing Input", "Please provide a Lesson ID.")
            return

        super().accept()

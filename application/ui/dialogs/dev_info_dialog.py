import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QDialogButtonBox,
    QPushButton,
)
from PySide6.QtCore import Qt
from typing import Optional, Any
import json  # For pretty printing dictionaries

from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from core.models import Exercise

logger = logging.getLogger(__name__)


def format_dict_for_display(data_dict: dict, indent=2) -> str:
    """Formats a dictionary into a pretty-printed JSON string."""
    try:
        return json.dumps(
            data_dict, indent=indent, ensure_ascii=False, default=str
        )  # default=str for non-serializable like datetime
    except Exception as e:
        logger.error(f"Error formatting dict to JSON: {e}")
        return str(data_dict)  # Fallback to plain string


class DevInfoDialog(QDialog):
    def __init__(
        self,
        course_manager: CourseManager,
        progress_manager: Optional[ProgressManager] = None,
        current_exercise: Optional[Exercise] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Developer Information"))
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFontFamily(
            "Consolas, Courier New, monospace"
        )  # Monospaced font for better dict display
        layout.addWidget(self.text_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self._populate_info(course_manager, progress_manager, current_exercise)

    def _populate_info(
        self,
        course_manager: CourseManager,
        progress_manager: Optional[ProgressManager],
        current_exercise: Optional[Exercise],
    ):
        info_str = []

        # --- Course Info ---
        info_str.append("=" * 30 + " COURSE INFORMATION " + "=" * 30)
        if course_manager.course:
            course_data = {
                "Course ID": course_manager.course.course_id,
                "Title": course_manager.course.title,
                "Target Language": course_manager.target_language,
                "Source Language": course_manager.source_language,
                "Version": course_manager.course.version,
                "Author": course_manager.course.author,
                "Manifest Path": course_manager.manifest_path,
                "Content File": course_manager.manifest_data.get("content_file", "N/A"),
                "Glossary File": course_manager.manifest_data.get(
                    "glossary_file", "N/A"
                ),
                "Number of Units": len(course_manager.course.units),
                "Total Exercises": len(course_manager.get_all_exercises()),
                "Total Glossary Entries": len(course_manager.glossary),
            }
            info_str.append(format_dict_for_display(course_data))
        else:
            info_str.append("No course loaded in CourseManager.")
        info_str.append("\n")

        # --- Current Exercise Info ---
        if current_exercise:
            info_str.append("=" * 25 + " CURRENT EXERCISE INFORMATION " + "=" * 25)
            exercise_details = {
                "Exercise ID": current_exercise.exercise_id,
                "Type": current_exercise.type,
                "Title (if any)": current_exercise.title,
                "Prompt": current_exercise.prompt,
                "Answer": current_exercise.answer,
                "Target Pron. Text": current_exercise.target_pronunciation_text,
                "Allowed Levenshtein": current_exercise.allowed_levenshtein_distance,
                "Explanation": current_exercise.explanation,
                "Audio File": current_exercise.audio_file,
                "Image File": current_exercise.image_file,
                "Options": (
                    [opt.to_dict() for opt in current_exercise.options]
                    if current_exercise.options
                    else None
                ),
                "Words (Jumble)": current_exercise.words,
                "Source Word (MCQ)": current_exercise.source_word,
                "Sentence Template (FIB)": current_exercise.sentence_template,
                "Correct Option (FIB)": current_exercise.correct_option,
                "Translation Hint": current_exercise.translation_hint,
                "Raw Data": current_exercise.raw_data,
            }
            # Filter out None values for cleaner display
            exercise_details_filtered = {
                k: v for k, v in exercise_details.items() if v is not None
            }
            info_str.append(format_dict_for_display(exercise_details_filtered))

            # --- SRS Data for Current Exercise ---
            if progress_manager:
                srs_data = progress_manager.get_exercise_srs_data(
                    current_exercise.exercise_id
                )
                info_str.append("-" * 20 + " SRS Data for Current Exercise " + "-" * 20)
                info_str.append(format_dict_for_display(srs_data))
            info_str.append("\n")
        elif (
            course_manager.course
        ):  # Only show this if a course is loaded but no exercise active
            info_str.append("No exercise currently active in the player view.\n")

        # --- Progress Manager Info ---
        if progress_manager:
            info_str.append("=" * 28 + " PROGRESS INFORMATION " + "=" * 28)
            progress_data = {
                "Course ID (Progress)": progress_manager.course_id,
                "Total XP": progress_manager.get_total_xp(),
                "Current Streak": progress_manager.get_current_streak(),
                "Last Study Date": progress_manager.last_study_date,
                "Progress File Path": progress_manager.progress_file,
                # "Exercise Notes Count": len(progress_manager.exercise_notes), # Example
            }
            info_str.append(format_dict_for_display(progress_data))
        elif course_manager.course:
            info_str.append("ProgressManager not initialized for this course yet.\n")

        self.text_edit.setPlainText("\n".join(info_str))

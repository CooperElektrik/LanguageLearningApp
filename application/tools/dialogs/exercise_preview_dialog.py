# application/tools/dialogs/exercise_preview_dialog.py

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
)

from application.core.models import Exercise
from application.tools.widgets.exercise_preview_widget import (
    ExercisePreviewWidget,
    MockCourseManager,
)

logger = logging.getLogger(__name__)


class ExercisePreviewDialog(QDialog):
    """
    Modal dialog wrapping ExercisePreviewWidget for ad-hoc exercise previewing.
    """

    def __init__(
        self,
        exercise: Exercise,
        course_languages: dict[str, str] | None = None,
        course_content_base_dir: str = "",
        parent=None,
        course_manager=None,
    ):
        if course_manager and not course_languages:
            course_languages = {
                "target": getattr(course_manager, "target_language", "Target Language"),
                "source": getattr(course_manager, "source_language", "Source Language"),
            }
            if hasattr(course_manager, "get_course_content_directory"):
                course_content_base_dir = course_manager.get_course_content_directory()

        super().__init__(parent)
        self.setWindowTitle(f"Preview: {exercise.type.replace('_', ' ').title()} Exercise")
        self.setMinimumSize(550, 420)

        self.exercise = exercise
        self.preview_widget = ExercisePreviewWidget(
            course_languages=course_languages,
            course_content_base_dir=course_content_base_dir,
            parent=self,
        )
        self.mock_course_manager = self.preview_widget.mock_course_manager

        self._setup_ui()
        self.preview_widget.update_preview(self.exercise)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.preview_widget, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

# application/tools/widgets/live_preview_pane.py

import logging

from application.core.models import Exercise

from .exercise_preview_widget import (
    ExercisePreviewWidget,
    MockCourseManager,
    create_preview_exercise_widget,
)

logger = logging.getLogger(__name__)


class LivePreviewPane(ExercisePreviewWidget):
    """
    Embedded real-time interactive preview pane for exercises in the Course Editor.
    Inherits from the reusable ExercisePreviewWidget.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("RightPreviewPane")

    def _show_answer(self):
        """Backwards compatibility alias."""
        self.show_answer()

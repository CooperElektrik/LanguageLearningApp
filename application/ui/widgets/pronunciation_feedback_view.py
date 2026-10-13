# application/ui/widgets/pronunciation_feedback_view.py

import difflib
import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

try:
    from application import settings as app_settings
except ImportError:
    import settings as app_settings

logger = logging.getLogger(__name__)


class PronunciationFeedbackView(QGroupBox):
    """
    Standalone visual feedback component for pronunciation practice.
    Displays:
    - Word-level confidence coloring (green/yellow/orange/red)
    - Side-by-side / diff comparison against the target sentence
    - Try Again and Submit actions
    """

    try_again_requested = Signal()
    submit_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle(self.tr("Your Results"))
        self.setObjectName("pronunciation_feedback_group")
        self._last_transcription = ""

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.feedback_browser = QTextBrowser()
        self.feedback_browser.setOpenExternalLinks(False)
        layout.addWidget(self.feedback_browser)

        action_layout = QHBoxLayout()
        self.try_again_button = QPushButton(self.tr("Try Again"))
        self.try_again_button.setObjectName("try_again_button")
        self.try_again_button.clicked.connect(self.try_again_requested.emit)

        self.submit_button = QPushButton(self.tr("Submit and Continue"))
        self.submit_button.setObjectName("submit_button")
        self.submit_button.clicked.connect(lambda: self.submit_requested.emit(self._last_transcription))

        action_layout.addStretch(1)
        action_layout.addWidget(self.try_again_button)
        action_layout.addWidget(self.submit_button)
        action_layout.addStretch(1)
        layout.addLayout(action_layout)

    def display_results(
        self,
        target_text: str,
        transcribed_text: str,
        words: list,
        engine: str,
        course_manager=None,
        **kwargs,
    ):
        self._last_transcription = (transcribed_text or "").strip()
        self.try_again_button.setEnabled(True)
        self.submit_button.setEnabled(True)

        if engine == app_settings.STT_ENGINE_VOSK:
            confidence_html = self.tr(
                "<i>VOSK does not provide word-level confidence.</i><br><b>Transcribed:</b> {0}"
            ).format(self._last_transcription)
        else:
            confidence_html = self._generate_confidence_html(words)

        diff_html = self._generate_diff_html(target_text, self._last_transcription, course_manager)

        combined_html = f"""
        <h3>{self.tr("Your Speech (colored by confidence)")}</h3>
        <p>{confidence_html}</p>
        <hr>
        <h3>{self.tr("Comparison with Target Text")}</h3>
        <p>{diff_html}</p>
        """
        self.feedback_browser.setHtml(combined_html)
        self.setVisible(True)

    def reset(self):
        self._last_transcription = ""
        self.feedback_browser.clear()
        self.setVisible(False)
        self.try_again_button.setEnabled(True)
        self.submit_button.setEnabled(True)

    def _generate_confidence_html(self, words: list) -> str:
        if not words:
            return f"<p><i>{self.tr('No speech detected or words could not be recognized.')}</i></p>"

        html_parts = []
        for word in words:
            prob = getattr(word, "probability", 0.0)
            if prob > 0.9:
                color = "#28a745"  # Green
            elif prob > 0.7:
                color = "#ffc107"  # Yellow
            elif prob > 0.5:
                color = "#fd7e14"  # Orange
            else:
                color = "#dc3545"  # Red

            w_text = getattr(word, "word", str(word))
            html_parts.append(
                f'<span style="background-color: {color}; color: white; padding: 2px 4px; border-radius: 3px; margin: 1px;">{w_text}</span>'
            )

        return " ".join(html_parts)

    def _generate_diff_html(self, target_str: str, user_str: str, course_manager=None) -> str:
        if course_manager and hasattr(course_manager, "_normalize_answer_for_comparison"):
            target_str_norm = course_manager._normalize_answer_for_comparison(target_str, for_pronunciation=True)
            user_str_norm = course_manager._normalize_answer_for_comparison(user_str, for_pronunciation=True)
        else:
            target_str_norm = target_str.lower().strip()
            user_str_norm = user_str.lower().strip()

        matcher = difflib.SequenceMatcher(None, target_str_norm.split(), user_str_norm.split())
        html_parts = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                html_parts.append(" ".join(matcher.a[i1:i2]))
            else:
                if tag in ("delete", "replace"):
                    deleted_text = " ".join(matcher.a[i1:i2])
                    html_parts.append(
                        f'<span style="background-color: #ffebee; color: #c62828; text-decoration: line-through; padding: 2px 4px; border-radius: 3px;">{deleted_text}</span>'
                    )
                if tag in ("insert", "replace"):
                    inserted_text = " ".join(matcher.b[j1:j2])
                    html_parts.append(
                        f'<span style="background-color: #e8f5e9; color: #2e7d32; font-weight: bold; padding: 2px 4px; border-radius: 3px;">{inserted_text}</span>'
                    )

        return " ".join(html_parts).replace("\n", "<br>")

    def reset_view(self):
        """Clears the feedback browser and resets state."""
        self._last_transcription = ""
        self.feedback_browser.clear()
        self.try_again_button.setEnabled(False)
        self.submit_button.setEnabled(False)

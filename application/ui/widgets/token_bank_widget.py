# application/ui/widgets/token_bank_widget.py

import logging
import random
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .flow_layout import FlowLayout

logger = logging.getLogger(__name__)


@dataclass
class Token:
    token_id: int
    text: str


class WordChip(QPushButton):
    """Clickable token chip used in the word bank and sentence building area."""

    def __init__(self, token_id: int, text: str, is_in_sentence: bool = False, parent=None):
        super().__init__(text, parent)
        self.token_id = token_id
        self.raw_text = text
        self.is_in_sentence = is_in_sentence
        self.setObjectName("sentence_word_button" if is_in_sentence else "word_bank_button")
        self.setCursor(Qt.PointingHandCursor)


class TokenBankWidget(QWidget):
    """
    Dedicated responsive token bank and sentence-building widget.
    Features:
    - Unique token identity (properly supports duplicate words in sentences).
    - Responsive FlowLayout so chips wrap cleanly on any screen width.
    - Click-to-place and click-to-return token mechanics.
    """

    sentence_changed = Signal(list)

    def __init__(self, words: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("TokenBankWidget")
        self._tokens: list[Token] = []
        self._sentence_tokens: list[Token] = []
        self._bank_chips: dict[int, WordChip] = {}
        self._sentence_chips: dict[int, WordChip] = {}

        self._setup_ui()
        if words:
            self.set_words(words)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # Sentence Construction Zone
        self.sentence_container = QFrame()
        self.sentence_container.setObjectName("sentence_jumble_container")
        self.sentence_layout = FlowLayout(self.sentence_container, margin=8, spacing=6)

        self.placeholder_label = QLabel(self.tr("Click words below to build your sentence."))
        self.placeholder_label.setObjectName("sentence_jumble_placeholder")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(self.placeholder_label)
        main_layout.addWidget(self.sentence_container)

        # Separator Line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)

        # Word Bank Zone
        self.word_bank_container = QFrame()
        self.word_bank_container.setObjectName("word_bank_container")
        self.word_bank_layout = FlowLayout(self.word_bank_container, margin=8, spacing=6)
        main_layout.addWidget(self.word_bank_container)

    def set_words(self, words: list[str], shuffle: bool = True):
        """Initializes the word bank with given words, assigning unique token IDs."""
        self.clear()
        shuffled = list(words)
        if shuffle:
            random.shuffle(shuffled)

        self._tokens = [Token(token_id=i, text=w) for i, w in enumerate(shuffled)]

        for token in self._tokens:
            chip = WordChip(token.token_id, token.text, is_in_sentence=False, parent=self.word_bank_container)
            chip.clicked.connect(lambda checked=False, tid=token.token_id: self.add_token_to_sentence(tid))
            self._bank_chips[token.token_id] = chip
            self.word_bank_layout.addWidget(chip)

        self._update_display()

    def add_token_to_sentence(self, token_id: int):
        token = next((t for t in self._tokens if t.token_id == token_id), None)
        if not token or token_id in [t.token_id for t in self._sentence_tokens]:
            return

        self._sentence_tokens.append(token)

        # Disable in bank
        if token_id in self._bank_chips:
            self._bank_chips[token_id].setEnabled(False)

        # Create chip in sentence
        sentence_chip = WordChip(token.token_id, token.text, is_in_sentence=True, parent=self.sentence_container)
        sentence_chip.clicked.connect(lambda checked=False, tid=token_id: self.remove_token_from_sentence(tid))
        self._sentence_chips[token_id] = sentence_chip
        self.sentence_layout.addWidget(sentence_chip)

        self._update_display()
        self.sentence_changed.emit(self.get_words())

    def remove_token_from_sentence(self, token_id: int):
        token = next((t for t in self._sentence_tokens if t.token_id == token_id), None)
        if not token:
            return

        self._sentence_tokens = [t for t in self._sentence_tokens if t.token_id != token_id]

        # Remove from sentence layout
        if token_id in self._sentence_chips:
            chip = self._sentence_chips.pop(token_id)
            self.sentence_layout.removeWidget(chip)
            chip.deleteLater()

        # Re-enable in bank
        if token_id in self._bank_chips:
            self._bank_chips[token_id].setEnabled(True)

        self._update_display()
        self.sentence_changed.emit(self.get_words())

    def clear(self):
        """Clears all tokens from sentence and bank."""
        self._tokens.clear()
        self._sentence_tokens.clear()

        for chip in self._sentence_chips.values():
            self.sentence_layout.removeWidget(chip)
            chip.deleteLater()
        self._sentence_chips.clear()

        for chip in self._bank_chips.values():
            self.word_bank_layout.removeWidget(chip)
            chip.deleteLater()
        self._bank_chips.clear()

        self._update_display()

    def reset(self):
        """Returns all tokens in the sentence back to the word bank."""
        for token in list(self._sentence_tokens):
            self.remove_token_from_sentence(token.token_id)

    def get_words(self) -> list[str]:
        return [t.text for t in self._sentence_tokens]

    def get_sentence(self) -> str:
        return " ".join(self.get_words())

    def _update_display(self):
        has_sentence = len(self._sentence_tokens) > 0
        self.placeholder_label.setVisible(not has_sentence)
        self.sentence_container.setVisible(has_sentence)

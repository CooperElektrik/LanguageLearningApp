import random
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer, Qt, QCoreApplication
from PySide6.QtGui import QFont


class AnimatedPlaceholder(QLabel):
    """
    A QLabel that cycles through a list of predefined motivational or
    instructional texts, animating the transition from one text to the next
    with a character-by-character substitution and deletion effect.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnimatedPlaceholder")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)

        self.messages = [
            self.tr("Select a lesson to begin your journey."),
            self.tr("Click 'Review Due' to strengthen your memory."),
            self.tr("Explore the glossary to learn new terms."),
            self.tr("Check your progress to see how far you've come."),
            self.tr("Consistency is the key to mastering a new language."),
            self.tr("Every lesson you complete is a step towards fluency."),
            self.tr("Don't be afraid to make mistakes; they are part of learning."),
        ]
        random.shuffle(self.messages)

        self.current_message_index = 0
        self.from_text = ""
        self.to_text = self.messages[self.current_message_index]
        self.current_text = ""

        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate_text_transition)
        self._animation_step = 0

        self._wait_timer = QTimer(self)
        self._wait_timer.setSingleShot(True)
        self._wait_timer.timeout.connect(self._start_animation)

        self._initial_delay_timer = QTimer(self)
        self._initial_delay_timer.setSingleShot(True)
        self._initial_delay_timer.timeout.connect(self._start_wait_timer)
        self._initial_delay_timer.start(500)

    def _start_wait_timer(self):
        """Initiates the waiting period before the next animation starts."""
        self.setText(self.to_text)
        self._wait_timer.start(5000)

    def _start_animation(self):
        """Sets up and begins the animation to the next message."""
        self.current_message_index = (
            self.current_message_index + 1
        ) % len(self.messages)
        self.from_text = self.to_text
        self.to_text = self.messages[self.current_message_index]
        self._animation_step = 0
        self._animation_timer.start(20)

    def _animate_text_transition(self):
        """
        Core animation logic that simulates a "Matrix-style" text transition.

        The animation proceeds in two main phases:
        1.  **Substitution/Growth Phase:** Characters from the `from_text` are
            replaced by random characters, and the string grows until its
            length matches `to_text`.
        2.  **Reveal Phase:** Random characters are progressively replaced by the
            correct characters from `to_text` until the message is fully revealed.
        """
        from_len = len(self.from_text)
        to_len = len(self.to_text)
        max_len = max(from_len, to_len)
        steps_for_transition = max_len
        steps_for_reveal = max_len

        if self._animation_step < steps_for_transition:
            # Phase 1: Deconstruct the old text with random characters
            progress = self._animation_step / steps_for_transition
            temp_text = ""
            for i in range(max_len):
                if i < from_len and i < to_len:
                    # Characters present in both from and to text
                    if i < progress * max_len:
                        temp_text += self._random_char()
                    else:
                        temp_text += self.from_text[i]
                elif i < from_len:
                    # Deleting characters from the old text
                    if (from_len - i) / from_len > progress:
                        temp_text += self.from_text[i]
                elif i < to_len:
                    # Adding space for the new text
                    if i < progress * max_len:
                        temp_text += self._random_char()
            self.setText(temp_text)

        elif self._animation_step < steps_for_transition + steps_for_reveal:
            # Phase 2: Reveal the new text
            reveal_step = self._animation_step - steps_for_transition
            progress = reveal_step / steps_for_reveal
            num_revealed = int(progress * to_len)

            revealed_part = self.to_text[:num_revealed]
            random_part = "".join(
                [self._random_char() for _ in range(to_len - num_revealed)]
            )
            self.setText(revealed_part + random_part)
        else:
            # Animation finished
            self._animation_timer.stop()
            self.setText(self.to_text)
            self._start_wait_timer()

        self._animation_step += 1

    def _random_char(self) -> str:
        """Returns a random character for the animation effect."""
        return random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

    def setVisible(self, visible: bool):
        """Overrides setVisible to control the animation timers."""
        super().setVisible(visible)
        if visible:
            self._initial_delay_timer.start(500)
        else:
            self._animation_timer.stop()
            self._wait_timer.stop()
            self._initial_delay_timer.stop()

    def tr(self, text, disambiguation=None, n=-1):
        """Enables translation of the widget's text content."""
        return QCoreApplication.translate("AnimatedPlaceholder", text, disambiguation, n)


"""
application/ui/widgets/audio_level_meter.py

Provides an animated microphone level meter widget for real-time visual feedback
during speech recording and pronunciation exercises.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class AudioLevelMeter(QWidget):
    """
    Renders an animated audio input level meter with RMS activity,
    peak level indicator, and voice activity feedback.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AudioLevelMeter")
        self.setFixedHeight(38)
        self.setMinimumWidth(220)

        self._current_level: float = 0.0  # 0.0 to 1.0
        self._target_level: float = 0.0
        self._peak_level: float = 0.0
        self._is_recording: bool = False

        # Decay animation timer (approx 30 FPS)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._update_animation)
        self._anim_timer.start()

    def set_recording(self, is_recording: bool):
        self._is_recording = is_recording
        if not is_recording:
            self._target_level = 0.0
            self._peak_level = 0.0
        self.update()

    def set_level(self, level: float):
        """Sets the normalized target audio level (0.0 to 1.0)."""
        clamped = max(0.0, min(1.0, float(level)))
        self._target_level = clamped
        if clamped > self._peak_level:
            self._peak_level = clamped

    @staticmethod
    def calculate_pcm_level(pcm_bytes: bytes) -> float:
        """Calculates normalized RMS level (0.0 to 1.0) from raw 16-bit PCM bytes."""
        if not pcm_bytes or len(pcm_bytes) < 2:
            return 0.0
        try:
            try:
                import numpy as np

                samples = np.frombuffer(pcm_bytes, dtype=np.int16)
                if len(samples) == 0:
                    return 0.0
                rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
            except ImportError:
                import struct

                num_samples = len(pcm_bytes) // 2
                if num_samples == 0:
                    return 0.0
                fmt = f"<{num_samples}h"
                samples = struct.unpack(fmt, pcm_bytes[: num_samples * 2])
                rms = math.sqrt(sum(s * s for s in samples) / num_samples)

            if rms > 10:
                db = 20 * math.log10(rms / 32768.0)
                # Map -50 dB ... -10 dB to 0.0 ... 1.0
                return max(0.0, min(1.0, (db + 50.0) / 40.0))
            return 0.0
        except Exception:
            return 0.0

    def process_pcm_bytes(self, pcm_bytes: bytes):
        """Calculates RMS level from raw 16-bit PCM bytes and updates level."""
        level = self.calculate_pcm_level(pcm_bytes)
        self.set_level(level)

    def _update_animation(self):
        if self._is_recording:
            # Smooth attack and decay
            if self._target_level > self._current_level:
                self._current_level += (self._target_level - self._current_level) * 0.4
            else:
                self._current_level -= (self._current_level - self._target_level) * 0.15

            # Slowly decay peak
            self._peak_level = max(0.0, self._peak_level - 0.02)
            self._peak_level = max(self._peak_level, self._current_level)
        else:
            self._current_level = max(0.0, self._current_level * 0.8)
            self._peak_level = max(0.0, self._peak_level * 0.8)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        margin_x = 8
        bar_height = 12
        bar_y = (h - bar_height) / 2 + 6
        bar_width = w - (margin_x * 2)

        # Draw status text above bar
        font = QFont(self.font())
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QColor("#a0a0b0"))

        if not self._is_recording:
            status_text = "Mic idle"
            painter.drawText(
                QRectF(margin_x, 0, bar_width, 16), Qt.AlignLeft | Qt.AlignVCenter, status_text
            )
        else:
            if self._current_level > 0.15:
                status_text = "Voice detected"
                painter.setPen(QColor("#4caf50"))
            else:
                status_text = "Listening... (speak into mic)"
                painter.setPen(QColor("#64b5f6"))
            painter.drawText(
                QRectF(margin_x, 0, bar_width, 16), Qt.AlignLeft | Qt.AlignVCenter, status_text
            )

        # Track background
        bg_rect = QRectF(margin_x, bar_y, bar_width, bar_height)
        bg_path = QPainterPath()
        bg_path.addRoundedRect(bg_rect, 6, 6)
        painter.fillPath(bg_path, QBrush(QColor(40, 40, 48)))

        # Border
        painter.setPen(QPen(QColor(60, 60, 72), 1))
        painter.drawPath(bg_path)

        # Filled level bar
        fill_width = bar_width * self._current_level
        if fill_width > 2:
            fill_rect = QRectF(margin_x, bar_y, fill_width, bar_height)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, 6, 6)

            gradient = QLinearGradient(margin_x, bar_y, margin_x + bar_width, bar_y)
            gradient.setColorAt(0.0, QColor("#4caf50"))  # Green
            gradient.setColorAt(0.65, QColor("#ffca28"))  # Amber/Yellow
            gradient.setColorAt(0.95, QColor("#f44336"))  # Red

            painter.fillPath(fill_path, QBrush(gradient))

        # Peak indicator line
        if self._peak_level > 0.05 and self._is_recording:
            peak_x = margin_x + (bar_width * self._peak_level)
            peak_x = min(peak_x, margin_x + bar_width - 2)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawLine(QPointF(peak_x, bar_y), QPointF(peak_x, bar_y + bar_height))

        painter.end()

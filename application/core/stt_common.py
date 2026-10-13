"""Shared speech-to-text plumbing for the Whisper and Vosk backends.

The two engines were structurally identical (a model-loader runnable, a
transcription runnable, an availability stub and Qt signals) but disagreed on
their ``finished`` payloads: Whisper emitted ``(segments, info)`` while Vosk
emitted a plain string.  That forced the UI to guess with
``isinstance(result, str)``.  Both backends now speak the same
:class:`TranscriptionResult` dialect.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Engine-agnostic transcription output."""

    text: str
    # Word objects exposing ``.word``/``.probability`` when the engine provides
    # them (Whisper does; Vosk does not).
    words: list[Any] = field(default_factory=list)
    engine: str = ""


class BaseModelLoader(QRunnable):
    """Common runnable shape for loading an STT model in the background."""

    def __init__(self, model_id: str):
        super().__init__()
        self.model_id = model_id
        self.signals = self.Signals()

    class Signals(QObject):
        finished = Signal(str, object)  # model_id, model_instance
        error = Signal(str, str)  # model_id, error_message


class BaseTranscriptionTask(QRunnable):
    """Common runnable shape for transcribing an audio file in the background.

    Subclasses implement :meth:`_run_transcription` and, if the backend can be
    missing, override :meth:`is_available`/:meth:`unavailable_message`.
    """

    def __init__(
        self,
        exercise_id: str,
        language_code: str | None = None,
        cleanup_paths: list[str] | None = None,
    ):
        super().__init__()
        self.exercise_id = exercise_id
        self.language_code = language_code
        self.cleanup_paths = cleanup_paths or []
        self.signals = self.Signals()

    class Signals(QObject):
        finished = Signal(str, object)  # exercise_id, TranscriptionResult
        error = Signal(str, str)  # exercise_id, error_message

    def is_available(self) -> bool:
        return True

    def unavailable_message(self) -> str:
        return "Speech-to-text engine is not available."

    def _run_transcription(self) -> TranscriptionResult:  # pragma: no cover
        raise NotImplementedError

    def run(self):
        try:
            if not self.is_available():
                self.signals.error.emit(self.exercise_id, self.unavailable_message())
                return
            try:
                result = self._run_transcription()
                self.signals.finished.emit(self.exercise_id, result)
            except Exception as e:
                logger.error(
                    f"Background Task: Error during transcription for "
                    f"{self.exercise_id}: {e}",
                    exc_info=True,
                )
                self.signals.error.emit(self.exercise_id, str(e))
        finally:
            import os
            for path in self.cleanup_paths:
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                        logger.debug(f"Cleaned up resampled audio file: {path}")
                except Exception as cleanup_err:
                    logger.warning(f"Could not remove temp file '{path}': {cleanup_err}")


def resample_audio(input_path: str, target_sr: int, engine_name: str) -> str | None:
    """Resamples an audio file to a target sample rate using PyAV and saves it.

    Args:
        input_path: Path to the input audio file.
        target_sr: The target sample rate (e.g., 16000).
        engine_name: The name of the STT engine (e.g., 'whisper' or 'vosk').

    Returns:
        The path to the resampled audio file, or None on failure.
    """
    logger.info(
        f"Resampling audio from '{input_path}' to {target_sr}Hz for {engine_name.capitalize()} using PyAV."
    )
    try:
        import av
        import numpy as np
        import soundfile as sf

        if engine_name == "whisper":
            output_path = input_path.replace(".wav", "_resampled_whisper.wav")
        else:
            output_path = input_path.replace(".wav", f"_resampled_vosk_{target_sr}.wav")

        with av.open(input_path) as in_container:
            in_stream = next(
                (s for s in in_container.streams if s.type == "audio"), None
            )
            if in_stream is None:
                logger.error(f"No audio streams found in {input_path}")
                return None

            resampler = av.AudioResampler(
                format="fltp",
                layout="mono",
                rate=target_sr,
            )

            resampled_frames = []
            for frame in in_container.decode(in_stream):
                if isinstance(frame, av.AudioFrame):
                    resampled_frames.extend(resampler.resample(frame))

            resampled_frames.extend(resampler.resample(None))

            if not resampled_frames:
                logger.error(
                    f"Resampling produced no frames for {input_path}. The file might be empty or corrupt."
                )
                return None

            resampled_audio_data = np.concatenate(
                [frame.to_ndarray().reshape(-1) for frame in resampled_frames]
            )

            sf.write(output_path, resampled_audio_data, target_sr)
            logger.info(f"Successfully saved resampled audio to '{output_path}'")
            return output_path

    except Exception as e:
        logger.error(
            f"Error during audio resampling for {engine_name.capitalize()}: {e}",
            exc_info=True,
        )
        return None

import logging
import os
import sys
from PySide6.QtCore import QObject, Signal, QRunnable
from typing import Optional, Tuple
import settings as app_settings
import utils

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel
    from huggingface_hub.errors import LocalEntryNotFoundError
    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    logger.warning("faster_whisper not found. Whisper STT will be unavailable.")
    _FASTER_WHISPER_AVAILABLE = False

    class WhisperModel:
        def __init__(self, *args, **kwargs):
            pass
        def transcribe(self, *args, **kwargs):
            raise NotImplementedError("faster_whisper is not installed.")

try:
    import torch # type: ignore
    _TORCH_AVAILABLE = True
except ImportError:
    logger.warning("PyTorch not found. Whisper will fall back to CPU or be unavailable.")
    _TORCH_AVAILABLE = False


class WhisperModelLoader(QRunnable):
    """
    A QRunnable task to load a Whisper model in a background thread.
    """

    def __init__(self, model_name: str, device: str, compute_type: str):
        super().__init__()
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.signals = self.Signals()

    class Signals(QObject):
        finished = Signal(str, object)  # model_name, model_instance
        error = Signal(str, str)  # model_name, error_message

    def run(self):
        if not _FASTER_WHISPER_AVAILABLE:
            self.signals.error.emit(self.model_name, "faster_whisper is not available.")
            return
        try:
            logger.info(
                f"Background Task: Loading Whisper model '{self.model_name}' on device '{self.device}' with compute_type '{self.compute_type}'. This might take a while on first use."
            )
            download_root = utils.get_stt_model_path(app_settings.STT_ENGINE_WHISPER, "") # Pass empty model_name as faster_whisper handles it
            try:
                logger.info(f"Background Task: Attempting to load local model at {download_root}")
                model_instance = WhisperModel(
                    self.model_name, device=self.device, compute_type=self.compute_type, download_root=download_root, local_files_only=True
                )
                logger.info("Background Task: Local model loaded.")
            except LocalEntryNotFoundError:
                model_instance = WhisperModel(
                    self.model_name, device=self.device, compute_type=self.compute_type, download_root=download_root, local_files_only=False
                )
                logger.info("Background Task: New model downloaded from HuggingFace.")
            logger.info(
                f"Background Task: Model '{self.model_name}' loaded successfully."
            )
            self.signals.finished.emit(self.model_name, model_instance)
        except Exception as e:
            logger.error(
                f"Background Task: Failed to load Whisper model '{self.model_name}': {e}",
                exc_info=True,
            )
            self.signals.error.emit(self.model_name, str(e))


class WhisperTranscriptionTask(QRunnable):
    """
    A QRunnable task to run transcription in a background thread.
    """

    def __init__(
        self,
        model: WhisperModel,
        audio_path: str,
        exercise_id: str,
        language_code: Optional[str] = None,
    ):
        super().__init__()
        self._model = model
        self.audio_path = audio_path
        self.exercise_id = exercise_id
        self.language_code = language_code
        self.signals = self.Signals()

    class Signals(QObject):
        finished = Signal(str, object, object)  # exercise_id, segments, info
        error = Signal(str, str)  # exercise_id, error_message

    def run(self):
        if not _FASTER_WHISPER_AVAILABLE:
            self.signals.error.emit(self.exercise_id, "faster_whisper is not available.")
            return
        try:
            lang_info = (
                f" with language '{self.language_code}'" if self.language_code else ""
            )
            logger.info(
                f"Background Task: Starting transcription for {self.audio_path}{lang_info}"
            )
            segments, info = self._model.transcribe(
                self.audio_path,
                beam_size=5,
                word_timestamps=True,
                temperature=0.7,
                language=self.language_code,
            )
            logger.info(
                f"Background Task: Transcription finished for {self.exercise_id}."
            )
            # Pass the generator objects directly. They will be consumed by the receiver.
            self.signals.finished.emit(self.exercise_id, segments, info)
        except Exception as e:
            logger.error(
                f"Background Task: Error during transcription for {self.exercise_id}: {e}",
                exc_info=True,
            )
            self.signals.error.emit(self.exercise_id, str(e))

def check_whisper_model_downloaded(model_name: str) -> bool:
    """Checks if a given Whisper model has been downloaded locally."""
    if not _FASTER_WHISPER_AVAILABLE:
        return False
    try:
        # faster_whisper's WhisperModel constructor checks for local files
        # by attempting to load them. If local_files_only=True and it fails,
        # it raises LocalEntryNotFoundError.
        # We don't need to actually load the model, just check if the files exist.
        # The download_root is where faster_whisper stores the models.
        download_root = utils.get_stt_model_path(app_settings.STT_ENGINE_WHISPER, "")
        # This will raise LocalEntryNotFoundError if the model is not found locally
        # when local_files_only is True.
        WhisperModel(model_name, device="cpu", compute_type="int8", download_root=download_root, local_files_only=True)
        return True
    except LocalEntryNotFoundError:
        return False
    except Exception as e:
        logger.warning(f"Error checking Whisper model {model_name} download status: {e}")
        return False

def get_best_whisper_device_config() -> Tuple[str, str]:
    """Determines the best available device (cuda or cpu) and corresponding compute type for Whisper."""
    if not _TORCH_AVAILABLE:
        logger.warning("PyTorch not available, falling back to CPU.")
        return "cpu", "int8"
    try:
        if torch.cuda.is_available():
            try:
                if torch.cuda.get_device_capability(0)[0] >= 7:
                    return "cuda", "float16"
            except Exception as e:
                logger.warning(
                    f"Could not determine CUDA device capability, falling back. Error: {e}"
                )
            return "cuda", "int8"
    except Exception as e:
        logger.warning(f"Error checking for CUDA availability: {e}, falling back to CPU.")
    return "cpu", "int8"

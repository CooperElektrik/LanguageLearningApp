import logging

import settings as app_settings
import utils

from .stt_common import BaseModelLoader, BaseTranscriptionTask, TranscriptionResult

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

    class LocalEntryNotFoundError(Exception):
        pass


try:
    import torch  # type: ignore

    _TORCH_AVAILABLE = True
except ImportError:
    logger.warning(
        "PyTorch not found. Whisper will fall back to CPU or be unavailable."
    )
    _TORCH_AVAILABLE = False
    torch = None  # type: ignore


class WhisperModelLoader(BaseModelLoader):
    """
    A QRunnable task to load a Whisper model in a background thread.
    """

    def __init__(self, model_name: str, device: str, compute_type: str):
        super().__init__(model_name)
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type

    def run(self):
        if not _FASTER_WHISPER_AVAILABLE:
            self.signals.error.emit(self.model_name, "faster_whisper is not available.")
            return
        try:
            logger.info(
                f"Background Task: Loading Whisper model '{self.model_name}' on device '{self.device}' with compute_type '{self.compute_type}'. This might take a while on first use."
            )
            download_root = utils.get_stt_model_path(
                app_settings.STT_ENGINE_WHISPER, ""
            )  # Pass empty model_name as faster_whisper handles it
            try:
                logger.info(
                    f"Background Task: Attempting to load local model at {download_root}"
                )
                model_instance = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=download_root,
                    local_files_only=True,
                )
                logger.info("Background Task: Local model loaded.")
            except LocalEntryNotFoundError:
                model_instance = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=download_root,
                    local_files_only=False,
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


class WhisperTranscriptionTask(BaseTranscriptionTask):
    """
    A QRunnable task to run Whisper transcription in a background thread.
    """

    def __init__(
        self,
        model: WhisperModel,
        audio_path: str,
        exercise_id: str,
        language_code: str | None = None,
    ):
        super().__init__(exercise_id, language_code)
        self._model = model
        self.audio_path = audio_path

    def is_available(self) -> bool:
        return _FASTER_WHISPER_AVAILABLE

    def unavailable_message(self) -> str:
        return "faster_whisper is not available."

    def _run_transcription(self) -> TranscriptionResult:
        lang_info = (
            f" with language '{self.language_code}'" if self.language_code else ""
        )
        logger.info(
            f"Background Task: Starting transcription for {self.audio_path}{lang_info}"
        )
        segments, _info = self._model.transcribe(
            self.audio_path,
            beam_size=app_settings.WHISPER_BEAM_SIZE,
            word_timestamps=True,
            temperature=app_settings.WHISPER_TEMPERATURE,
            language=self.language_code,
        )
        # Consume the segment generator here, on the worker thread, so the UI
        # thread only receives a plain result object.
        text_parts = []
        words = []
        for segment in segments:
            text_parts.append(segment.text)
            segment_words = getattr(segment, "words", None)
            if segment_words:
                words.extend(segment_words)
        logger.info(f"Background Task: Transcription finished for {self.exercise_id}.")
        return TranscriptionResult(
            text="".join(text_parts).strip(),
            words=words,
            engine=app_settings.STT_ENGINE_WHISPER,
        )


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
        WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            download_root=download_root,
            local_files_only=True,
        )
        return True
    except LocalEntryNotFoundError:
        return False
    except Exception as e:
        logger.warning(
            f"Error checking Whisper model {model_name} download status: {e}"
        )
        return False


def get_best_whisper_device_config() -> tuple[str, str]:
    """Determines the best available device (cuda or cpu) and corresponding compute type for Whisper."""
    if not _TORCH_AVAILABLE or torch is None:
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
        logger.warning(
            f"Error checking for CUDA availability: {e}, falling back to CPU."
        )
    return "cpu", "int8"

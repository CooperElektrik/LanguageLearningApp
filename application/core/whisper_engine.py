import logging
import os

import settings as app_settings
import utils

from .stt_common import (
    BaseModelLoader,
    BaseTranscriptionTask,
    TranscriptionResult,
    resample_audio,
)

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel, download_model  # type: ignore
    from huggingface_hub.errors import LocalEntryNotFoundError  # type: ignore

    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    logger.warning("faster_whisper not found. Whisper STT will be unavailable.")
    _FASTER_WHISPER_AVAILABLE = False

    class WhisperModel:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            raise NotImplementedError("faster_whisper is not installed.")

    def download_model(*args, **kwargs):  # type: ignore
        raise NotImplementedError("faster_whisper is not installed.")

    class LocalEntryNotFoundError(Exception):  # type: ignore
        pass


try:
    import torch  # type: ignore

    _TORCH_AVAILABLE = True
except ImportError:
    logger.warning("PyTorch not found. Whisper will fall back to CPU or be unavailable.")
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
                logger.info(f"Background Task: Attempting to load local model at {download_root}")
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
            logger.info(f"Background Task: Model '{self.model_name}' loaded successfully.")
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
        cleanup_paths: list[str] | None = None,
        target_samplerate: int | None = None,
        recorded_samplerate: int | None = None,
    ):
        super().__init__(exercise_id, language_code, cleanup_paths=cleanup_paths)
        self._model = model
        self.audio_path = audio_path
        self.target_samplerate = target_samplerate
        self.recorded_samplerate = recorded_samplerate

    def is_available(self) -> bool:
        return _FASTER_WHISPER_AVAILABLE

    def unavailable_message(self) -> str:
        return "faster_whisper is not available."

    def _run_transcription(self) -> TranscriptionResult:
        audio_file_to_use = self.audio_path
        # If resampling is required, do it in background thread
        if (
            self.target_samplerate
            and self.recorded_samplerate
            and self.recorded_samplerate != self.target_samplerate
        ):
            resampled = resample_audio(self.audio_path, self.target_samplerate, "whisper")
            if resampled:
                audio_file_to_use = resampled
                self.cleanup_paths.append(resampled)

        lang_info = f" with language '{self.language_code}'" if self.language_code else ""
        logger.info(f"Background Task: Starting transcription for {audio_file_to_use}{lang_info}")
        segments, _info = self._model.transcribe(
            audio_file_to_use,
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
        # Check if the model directory or files exist on disk in the cache path
        # rather than instantiating the full CTranslate2 model runtime.
        if os.path.isdir(model_name):
            return True

        download_root = utils.get_stt_model_path(app_settings.STT_ENGINE_WHISPER, "")
        if not download_root or not os.path.exists(download_root):
            return False

        if os.path.isdir(os.path.join(download_root, model_name)):
            return True

        # download_model with local_files_only=True verifies if cached files exist
        # without initializing the CTranslate2 model runtime.
        model_path = download_model(
            model_name,
            local_files_only=True,
            cache_dir=download_root,
        )
        return os.path.isdir(model_path)
    except (LocalEntryNotFoundError, ValueError, FileNotFoundError):
        return False
    except Exception as e:
        logger.warning(f"Error checking Whisper model {model_name} download status: {e}")
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
        logger.warning(f"Error checking for CUDA availability: {e}, falling back to CPU.")
    return "cpu", "int8"

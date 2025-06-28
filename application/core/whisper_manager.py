import logging
from PySide6.QtCore import QObject, Signal, QThread, QSettings, QRunnable, QThreadPool
from typing import Optional, Tuple
import settings as app_settings
import os
import sys

try:
    from faster_whisper import WhisperModel
    from huggingface_hub.errors import LocalEntryNotFoundError
    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("faster_whisper not found. Pronunciation exercises will be skipped.")
    _FASTER_WHISPER_AVAILABLE = False

    # Define a dummy WhisperModel for type hinting purposes when faster_whisper is not available
    class WhisperModel:
        def __init__(self, *args, **kwargs):
            pass
        def transcribe(self, *args, **kwargs):
            raise NotImplementedError("faster_whisper is not installed.")

try:
    import torch # type: ignore
    _TORCH_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("PyTorch not found. Whisper will fall back to CPU or be unavailable.")
    _TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


class ModelLoader(QRunnable):
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
            download_root = "application/models" if not hasattr(sys, "_MEIPASS") else os.path.join(sys._MEIPASS, "models")
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


class TranscriptionTask(QRunnable):
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


class WhisperManager(QObject):
    modelLoadingStarted = Signal(str)  # model_name
    modelLoadingFinished = Signal(str, bool)  # model_name, success
    modelUnloaded = Signal(str)  # model_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.q_settings = QSettings()
        self.thread_pool = QThreadPool.globalInstance()

        self._active_model_instance: Optional[WhisperModel] = None
        self._active_model_name_loaded: Optional[str] = None
        self._is_loading = False

        self.device, self.compute_type = self._get_best_device_config()
        logger.info(
            f"WhisperManager configured to use device='{self.device}' with compute_type='{self.compute_type}'."
        )

    def _get_best_device_config(self) -> Tuple[str, str]:
        """Determines the best available device (cuda or cpu) and corresponding compute type."""
        if not _TORCH_AVAILABLE:
            logger.warning("PyTorch not available, falling back to CPU.")
            return "cpu", "int8"
        try:
            if torch.cuda.is_available():
                # Check if the GPU supports float16, which is much faster.
                # This is a simplification; a more robust check would involve compute capability.
                # Most modern NVIDIA GPUs support float16.
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

    def get_selected_model_name(self) -> str:
        return self.q_settings.value(
            app_settings.QSETTINGS_KEY_WHISPER_MODEL,
            app_settings.WHISPER_MODEL_DEFAULT,
            type=str,
        )

    def get_loaded_model_name(self) -> Optional[str]:
        return self._active_model_name_loaded

    def is_loading(self) -> bool:
        return self._is_loading

    def load_model(self, model_name: str):
        if self._is_loading:
            logger.warning("Model loading already in progress.")
            return
        if self._active_model_name_loaded == model_name:
            logger.info(f"Model '{model_name}' is already loaded.")
            self.modelLoadingFinished.emit(model_name, True)
            return

        self.unload_model()  # Unload previous model first

        if not model_name or model_name.lower() == "none":
            self.modelLoadingFinished.emit(
                "None", True
            )  # Consider loading "None" a success
            return

        self._is_loading = True
        self.modelLoadingStarted.emit(model_name)

        loader_task = ModelLoader(model_name, self.device, self.compute_type)
        loader_task.signals.finished.connect(self._on_model_loaded)
        loader_task.signals.error.connect(self._on_model_load_error)
        self.thread_pool.start(loader_task)

    def _on_model_loaded(self, model_name: str, model_instance: WhisperModel):
        self._active_model_instance = model_instance
        self._active_model_name_loaded = model_name
        self._is_loading = False
        self.modelLoadingFinished.emit(model_name, True)

    def _on_model_load_error(self, model_name: str, error_message: str):
        self._is_loading = False
        self.modelLoadingFinished.emit(model_name, False)

    def unload_model(self):
        if self._active_model_instance:
            unloaded_model_name = self._active_model_name_loaded
            logger.info(f"Unloading Whisper model: {unloaded_model_name}")
            del self._active_model_instance
            self._active_model_instance = None
            self._active_model_name_loaded = None
            self.modelUnloaded.emit(unloaded_model_name)
            logger.info(f"Model '{unloaded_model_name}' unloaded.")

    def transcribe_audio(
        self, audio_path: str, exercise_id: str, language_code: Optional[str] = None
    ) -> Optional[TranscriptionTask]:
        if not self._active_model_instance:
            logger.error(
                f"Cannot transcribe: Whisper model '{self.get_selected_model_name()}' is not loaded."
            )
            return None

        task = TranscriptionTask(
            self._active_model_instance,
            audio_path,
            exercise_id,
            language_code=language_code,
        )
        # The caller will connect to the task's signals.
        self.thread_pool.start(task)
        return task

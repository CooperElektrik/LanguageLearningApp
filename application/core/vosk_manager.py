import logging
import os
import sys
import json
import queue
import sounddevice as sd
from PySide6.QtCore import QObject, Signal, QThread, QSettings, QRunnable, QThreadPool
from typing import Optional, Tuple
import settings as app_settings
import utils

try:
    from vosk import Model, KaldiRecognizer
    _VOSK_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("VOSK not found. VOSK STT will be unavailable.")
    _VOSK_AVAILABLE = False

    class Model:
        def __init__(self, *args, **kwargs):
            pass

    class KaldiRecognizer:
        def __init__(self, *args, **kwargs):
            pass
        def AcceptWaveform(self, *args, **kwargs):
            return False
        def Result(self):
            return json.dumps({"text": ""})

logger = logging.getLogger(__name__)

class ModelLoader(QRunnable):
    """
    A QRunnable task to load a VOSK model in a background thread.
    """
    def __init__(self, model_path: str):
        super().__init__()
        self.model_path = model_path
        self.signals = self.Signals()

    class Signals(QObject):
        finished = Signal(str, object)  # model_path, model_instance
        error = Signal(str, str)  # model_path, error_message

    def run(self):
        if not _VOSK_AVAILABLE:
            self.signals.error.emit(self.model_path, "VOSK is not available.")
            return
        try:
            logger.info(f"Background Task: Loading VOSK model from '{self.model_path}'.")
            # Resolve the actual model path using the utility function
            actual_model_path = utils.get_stt_model_path(app_settings.STT_ENGINE_VOSK, self.model_path)
            model_instance = Model(actual_model_path)
            logger.info(f"Background Task: Model '{self.model_path}' loaded successfully.")
            self.signals.finished.emit(self.model_path, model_instance)
        except Exception as e:
            logger.error(
                f"Background Task: Failed to load VOSK model '{self.model_path}': {e}",
                exc_info=True,
            )
            self.signals.error.emit(self.model_path, str(e))

class TranscriptionTask(QRunnable):
    """
    A QRunnable task to run transcription in a background thread using VOSK.
    """
    def __init__(
        self,
        model: Model,
        audio_path: str,
        exercise_id: str,
        samplerate: int,
        language_code: Optional[str] = None, # VOSK model is language specific, so this might not be used directly
    ):
        super().__init__()
        self._model = model
        self.audio_path = audio_path
        self.exercise_id = exercise_id
        self.samplerate = samplerate
        self.language_code = language_code
        self.signals = self.Signals()

    class Signals(QObject):
        finished = Signal(str, str)  # exercise_id, transcribed_text
        error = Signal(str, str)  # exercise_id, error_message

    def run(self):
        if not _VOSK_AVAILABLE:
            self.signals.error.emit(self.exercise_id, "VOSK is not available.")
            return
        try:
            logger.info(f"Background Task: Starting VOSK transcription for {self.audio_path}")

            # VOSK requires a KaldiRecognizer for transcription
            recognizer = KaldiRecognizer(self._model, self.samplerate)
            recognizer.SetWords(False) # We only need the text

            import soundfile as sf
            # Read audio file
            data, samplerate = sf.read(self.audio_path, dtype='int16')

            # Check if the samplerate of the audio file matches the model's samplerate
            if samplerate != self.samplerate:
                logger.warning(f"Audio file samplerate ({samplerate}) does not match VOSK model samplerate ({self.samplerate}). Resampling might be needed or model might not perform well.")
                # For now, we proceed, but in a real app, resampling might be necessary.

            # VOSK expects bytes
            if recognizer.AcceptWaveform(data.tobytes()):
                # Final result after processing the whole file
                final_result = json.loads(recognizer.Result())
                transcribed_text = final_result.get("text", "")
            else:
                # If not accepted, get partial result
                partial_result = json.loads(recognizer.PartialResult())
                transcribed_text = partial_result.get("partial", "")
                # If there's still a final result to be retrieved
                final_result = json.loads(recognizer.FinalResult())
                if final_result.get("text"):
                    transcribed_text = final_result.get("text", "")
                
            if not transcribed_text:
                logger.warning(f"VOSK transcription returned empty for {self.audio_path}. Attempting FinalResult.")
                final_result = json.loads(recognizer.FinalResult())
                transcribed_text = final_result.get("text", "")
            
            logger.info(f"VOSK transcription result for {self.exercise_id}: {transcribed_text}")

            logger.info(f"Background Task: VOSK transcription finished for {self.exercise_id}.")
            self.signals.finished.emit(self.exercise_id, transcribed_text)
        except Exception as e:
            logger.error(
                f"Background Task: Error during VOSK transcription for {self.exercise_id}: {e}",
                exc_info=True,
            )
            self.signals.error.emit(self.exercise_id, str(e))

class VoskManager(QObject):
    modelLoadingStarted = Signal(str)  # model_path
    modelLoadingFinished = Signal(str, bool)  # model_path, success
    modelUnloaded = Signal(str)  # model_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.q_settings = QSettings()
        self.thread_pool = QThreadPool.globalInstance()

        self._active_model_instance: Optional[Model] = None
        self._active_model_path_loaded: Optional[str] = None
        self._is_loading = False

        # Determine samplerate. For VOSK, this is crucial.
        # We'll try to get it from the default input device, similar to the example.
        try:
            device_info = sd.query_devices(sd.default.device[0], 'input')
            self.samplerate = int(device_info['default_samplerate'])
        except Exception as e:
            logger.warning(f"Could not determine default audio device samplerate: {e}. Using default 16000.")
            self.samplerate = 16000 # Default samplerate if detection fails

        logger.info(f"VoskManager configured with samplerate={self.samplerate}.")

    def get_selected_model_path(self) -> str:
        return self.q_settings.value(
            app_settings.QSETTINGS_KEY_VOSK_MODEL,
            app_settings.VOSK_MODEL_DEFAULT,
            type=str,
        )

    def get_loaded_model_path(self) -> Optional[str]:
        return self._active_model_path_loaded

    def is_loading(self) -> bool:
        return self._is_loading

    def load_model(self, model_path: str):
        if self._is_loading:
            logger.warning("VOSK model loading already in progress.")
            return
        if self._active_model_path_loaded == model_path:
            logger.info(f"VOSK model '{model_path}' is already loaded.")
            self.modelLoadingFinished.emit(model_path, True)
            return

        self.unload_model()  # Unload previous model first

        if not model_path or model_path.lower() == "none":
            self.modelLoadingFinished.emit("None", True)
            return

        self._is_loading = True
        self.modelLoadingStarted.emit(model_path)

        loader_task = ModelLoader(model_path)
        loader_task.signals.finished.connect(self._on_model_loaded)
        loader_task.signals.error.connect(self._on_model_load_error)
        self.thread_pool.start(loader_task)

    def _on_model_loaded(self, model_path: str, model_instance: Model):
        self._active_model_instance = model_instance
        self._active_model_path_loaded = model_path
        self._is_loading = False
        self.modelLoadingFinished.emit(model_path, True)

    def _on_model_load_error(self, model_path: str, error_message: str):
        self._is_loading = False
        self.modelLoadingFinished.emit(model_path, False)

    def unload_model(self):
        if self._active_model_instance:
            unloaded_model_path = self._active_model_path_loaded
            logger.info(f"Unloading VOSK model: {unloaded_model_path}")
            del self._active_model_instance
            self._active_model_instance = None
            self._active_model_path_loaded = None
            self.modelUnloaded.emit(unloaded_model_path)
            logger.info(f"Model '{unloaded_model_path}' unloaded.")

    def transcribe_audio(
        self, audio_path: str, exercise_id: str, language_code: Optional[str] = None
    ) -> Optional[TranscriptionTask]:
        if not self._active_model_instance:
            logger.error(
                f"Cannot transcribe: VOSK model '{self.get_selected_model_path()}' is not loaded."
            )
            return None

        task = TranscriptionTask(
            self._active_model_instance,
            audio_path,
            exercise_id,
            self.samplerate,
            language_code=language_code,
        )
        self.thread_pool.start(task)
        return task

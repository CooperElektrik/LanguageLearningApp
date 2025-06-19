# --- core/whisper_manager.py ---
import logging
from faster_whisper import WhisperModel
from PySide6.QtCore import QObject, Signal, QThread, QSettings
from typing import Optional, Tuple
import settings as app_settings
import os
import tempfile

logger = logging.getLogger(__name__)

# Directory to suggest for model storage (Faster Whisper uses HuggingFace cache by default)
# We don't need to manage model files directly if using default cache.
# MODEL_CACHE_DIR = os.path.join(
# QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation),
# app_settings.ORG_NAME,
# app_settings.APP_NAME,
# "whisper_models"
# )
# os.makedirs(MODEL_CACHE_DIR, exist_ok=True)


class TranscriptionTask(QObject):
    finished = Signal(str, str)  # exercise_id, transcription_text
    error = Signal(str, str)     # exercise_id, error_message
    progress = Signal(str, int, int) # exercise_id, step, total_steps (for future chunked transcription)
    
    # model is now passed as a loaded WhisperModel instance
    def __init__(self, model: WhisperModel, audio_path: str, exercise_id: str):
        super().__init__()
        self._model = model # Store the passed-in loaded model
        self.audio_path = audio_path
        self.exercise_id = exercise_id

    def run(self):
        try:
            if not self._model:
                self.error.emit(self.exercise_id, "Whisper model not provided to task.")
                return

            logger.info(f"Using pre-loaded Whisper model. Starting transcription for {self.audio_path}")
            
            segments, info = self._model.transcribe(self.audio_path, beam_size=5)
            
            transcription = ""
            for i, segment in enumerate(segments):
                transcription += segment.text + " "
            
            transcription = transcription.strip()
            logger.info(f"Transcription for {self.exercise_id}: '{transcription}' (Language: {info.language}, Probability: {info.language_probability})")
            self.finished.emit(self.exercise_id, transcription)
        except Exception as e:
            logger.error(f"Error during transcription for {self.exercise_id}: {e}", exc_info=True)
            self.error.emit(self.exercise_id, str(e))
        # Model is managed by WhisperManager, not unloaded here



class WhisperManager(QObject):
    model_loading_started = Signal(str) # model_name
    model_loading_finished = Signal(str, bool) # model_name, success
    model_unloaded = Signal(str) # model_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.q_settings = QSettings()
        self._current_thread: Optional[QThread] = None
        self._current_task: Optional[TranscriptionTask] = None

        self._active_model_instance: Optional[WhisperModel] = None
        self._active_model_name_loaded: Optional[str] = None
        
        # TODO: Get device and compute_type from settings or auto-detect
        self.device = "cuda" if app_settings.FORCE_LOCALE else "cpu" # Example, make configurable
        self.compute_type = "int8" # Example

    def get_selected_model_name(self) -> str:
        return self.q_settings.value(app_settings.QSETTINGS_KEY_WHISPER_MODEL, app_settings.WHISPER_MODEL_DEFAULT, type=str)

    def _load_model(self, model_name_to_load: str) -> Optional[WhisperModel]:
        if not model_name_to_load or model_name_to_load.lower() == "none":
            if self._active_model_instance: # Unload previous if exists
                logger.info(f"Unloading Whisper model: {self._active_model_name_loaded}")
                del self._active_model_instance
                self._active_model_instance = None
                self.model_unloaded.emit(self._active_model_name_loaded)
                self._active_model_name_loaded = None
            return None

        if self._active_model_instance and self._active_model_name_loaded == model_name_to_load:
            logger.debug(f"Whisper model '{model_name_to_load}' already loaded.")
            return self._active_model_instance

        # Unload previous model if different
        if self._active_model_instance:
            logger.info(f"Unloading previous Whisper model: {self._active_model_name_loaded}")
            del self._active_model_instance # CTranslate2 handles actual memory release
            self.model_unloaded.emit(self._active_model_name_loaded)

        self.model_loading_started.emit(model_name_to_load)
        logger.info(f"Loading Whisper model '{model_name_to_load}' on device '{self.device}' with compute_type '{self.compute_type}'. This might take a while on first use.")
        try:
            self._active_model_instance = WhisperModel(model_name_to_load, device=self.device, compute_type=self.compute_type)
            self._active_model_name_loaded = model_name_to_load
            logger.info(f"Whisper model '{model_name_to_load}' loaded successfully.")
            self.model_loading_finished.emit(model_name_to_load, True)
            return self._active_model_instance
        except Exception as e:
            logger.error(f"Failed to load Whisper model '{model_name_to_load}': {e}", exc_info=True)
            self.model_loading_finished.emit(model_name_to_load, False)
            self._active_model_instance = None
            self._active_model_name_loaded = None
            return None

    def transcribe_audio(self, audio_path: str, exercise_id: str) -> Tuple[Optional[QThread], Optional[TranscriptionTask]]:
        """
        Starts transcription in a new thread.
        Returns the thread and task object so the caller can connect to signals.
        """
        if self._current_thread and self._current_thread.isRunning():
            logger.warning("Transcription already in progress. Please wait.")
            # Optionally, queue tasks or return an error/signal
            return None, None

        target_model_name = self.get_selected_model_name()
        loaded_model = self._load_model(target_model_name) # This might block if model needs loading/changing

        if not loaded_model:
            logger.error(f"Cannot transcribe: Whisper model '{target_model_name}' not loaded.")
            # Caller should handle this, e.g., PronunciationExerciseWidget displays an error.
            return None, None

        self._current_thread = QThread()
        self._current_task = TranscriptionTask(loaded_model, audio_path, exercise_id)
        self._current_task.moveToThread(self._current_thread)

        self._current_thread.started.connect(self._current_task.run)
        self._current_task.finished.connect(self._on_transcription_part_done)
        self._current_task.error.connect(self._on_transcription_part_done) # Also stop thread on error
        
        # self._current_task.finished.connect(self._current_thread.quit) # Task emits finished
        # self._current_task.error.connect(self._current_thread.quit)
        # self._current_thread.finished.connect(self._current_thread.deleteLater)
        # self._current_task.finished.connect(self._current_task.deleteLater)


        self._current_thread.start()
        logger.info(f"Started transcription thread for exercise {exercise_id} using model {self._active_model_name_loaded}.")
        return self._current_thread, self._current_task

    def _on_transcription_part_done(self):
        """Cleans up the thread after task is finished or errored."""
        if self._current_thread:
            self._current_thread.quit()
            self._current_thread.wait(2000) # Wait a bit for thread to finish
            logger.debug(f"Transcription thread {self._current_thread} finished and cleaned up.")
            # self._current_thread.deleteLater() # Defer deletion
            # if self._current_task:
            #     self._current_task.deleteLater()
        self._current_thread = None
        self._current_task = None

    def stop_transcription(self): # Add a way to try and stop
        if self._current_thread and self._current_thread.isRunning():
            logger.info("Attempting to stop transcription thread...")
            # CTranslate2/Faster Whisper might not have a clean "interrupt" mid-transcription.
            # Best we can do is request quit and hope the task finishes soon.
            self._current_thread.quit() 
            self._current_thread.requestInterruption() # For cooperative interruption
            if not self._current_thread.wait(2000): # Wait for 2s
                 logger.warning("Transcription thread did not stop gracefully. It might still be running.")
            else:
                 logger.info("Transcription thread stopped.")
            self._current_thread = None
            self._current_task = None

    def unload_model_on_exit(self):
        """Explicitly unload the model, e.g., when the application is closing."""
        if self._active_model_instance:
            logger.info(f"Unloading active Whisper model '{self._active_model_name_loaded}' on exit.")
            del self._active_model_instance
            self._active_model_instance = None
            self.model_unloaded.emit(self._active_model_name_loaded)
            self._active_model_name_loaded = None
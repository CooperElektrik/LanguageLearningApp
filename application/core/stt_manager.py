import logging
from typing import Any

import settings as app_settings
from PySide6.QtCore import QObject, QRunnable, QSettings, QThreadPool, Signal

from .stt_common import resample_audio
from .vosk_manager import ModelLoader as VoskModelLoader  # Renamed to avoid conflict
from .vosk_manager import TranscriptionTask as VoskTranscriptionTask
from .whisper_engine import (
    WhisperModelLoader,
    WhisperTranscriptionTask,
    get_best_whisper_device_config,
)

logger = logging.getLogger(__name__)


class STTManager(QObject):
    modelLoadingStarted = Signal(str)  # model_name or model_path
    modelLoadingFinished = Signal(str, bool)  # model_name or model_path, success
    modelUnloaded = Signal(str)  # model_name or model_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.q_settings = QSettings()
        self.thread_pool = QThreadPool.globalInstance()

        self._active_whisper_model_instance: Any = None
        self._active_vosk_model_instance: Any = None
        self._active_model_name_loaded: str | None = (
            None  # Stores the name/path of the currently loaded model
        )
        self._is_loading = False

        self.whisper_device, self.whisper_compute_type = (
            get_best_whisper_device_config()
        )
        logger.info(
            f"Whisper configured to use device='{self.whisper_device}' with compute_type='{self.whisper_compute_type}'."
        )

        # Determine samplerate for Vosk
        try:
            import sounddevice as sd

            device_info = sd.query_devices(sd.default.device[0], "input")
            self.vosk_samplerate = int(device_info["default_samplerate"])
        except Exception as e:
            logger.warning(
                f"Could not determine default audio device samplerate for Vosk: {e}. Using default {app_settings.AUDIO_SAMPLE_RATE}."
            )
            self.vosk_samplerate = (
                app_settings.AUDIO_SAMPLE_RATE
            )  # Default if detection fails

        logger.info(f"Vosk configured with samplerate={self.vosk_samplerate}.")

    def get_selected_stt_engine(self) -> str:
        return str(
            self.q_settings.value(
                app_settings.QSETTINGS_KEY_STT_ENGINE,
                app_settings.STT_ENGINE_DEFAULT,
                type=str,
            )
        )

    def get_selected_whisper_model_name(self) -> str:
        return str(
            self.q_settings.value(
                app_settings.QSETTINGS_KEY_WHISPER_MODEL,
                app_settings.WHISPER_MODEL_DEFAULT,
                type=str,
            )
        )

    def get_selected_vosk_model_path(self) -> str:
        # This will need to be updated to reflect how VOSK models are selected/stored
        # For now, a placeholder.
        return str(
            self.q_settings.value(
                app_settings.QSETTINGS_KEY_VOSK_MODEL,
                app_settings.VOSK_MODEL_DEFAULT,
                type=str,
            )
        )

    def get_stt_model_name(self, engine: str) -> str | None:
        if engine == app_settings.STT_ENGINE_WHISPER:
            return self.get_selected_whisper_model_name()
        elif engine == app_settings.STT_ENGINE_VOSK:
            return self.get_selected_vosk_model_path()
        return None

    def get_loaded_model_name(self) -> str | None:
        return self._active_model_name_loaded

    def is_loading(self) -> bool:
        return self._is_loading

    def load_model(self):
        selected_engine = self.get_selected_stt_engine()
        model_to_load = self.get_stt_model_name(selected_engine)

        if not model_to_load or model_to_load.lower() == "none":
            logger.info(
                f"No model selected for {selected_engine} or 'None' specified. Skipping load."
            )
            self.modelLoadingFinished.emit("None", True)
            return

        if self._active_model_name_loaded == model_to_load:
            logger.info(f"Model '{model_to_load}' is already loaded. No action needed.")
            self.modelLoadingFinished.emit(model_to_load, True)
            return

        if self._is_loading:
            logger.warning("STT model loading is already in progress. Ignoring duplicate request.")
            return

        logger.info(
            f"Attempting to load STT model for engine: {selected_engine}, model: {model_to_load}"
        )
        self.unload_model()  # Unload any previously loaded model
        self._is_loading = True
        self.modelLoadingStarted.emit(model_to_load)

        if selected_engine == app_settings.STT_ENGINE_WHISPER:
            loader_task = WhisperModelLoader(
                model_to_load, self.whisper_device, self.whisper_compute_type
            )
            loader_task.signals.finished.connect(self._on_whisper_model_loaded)
            loader_task.signals.error.connect(self._on_whisper_model_load_error)
            self.thread_pool.start(loader_task)
        elif selected_engine == app_settings.STT_ENGINE_VOSK:
            loader_task = VoskModelLoader(model_to_load)
            loader_task.signals.finished.connect(self._on_vosk_model_loaded)
            loader_task.signals.error.connect(self._on_vosk_model_load_error)
            self.thread_pool.start(loader_task)
        else:
            logger.warning(
                f"Unknown STT engine selected: {selected_engine}. Cannot load model."
            )
            self.modelLoadingFinished.emit("Unknown", False)

    def _on_whisper_model_loaded(self, model_name: str, model_instance: object):
        self._active_whisper_model_instance = model_instance
        self._active_model_name_loaded = model_name
        self._is_loading = False
        self.modelLoadingFinished.emit(model_name, True)

    def _on_whisper_model_load_error(self, model_name: str, error_message: str):
        self._is_loading = False
        self.modelLoadingFinished.emit(model_name, False)

    def _on_vosk_model_loaded(self, model_path: str, model_instance: object):
        self._active_vosk_model_instance = model_instance
        self._active_model_name_loaded = model_path
        self._is_loading = False
        self.modelLoadingFinished.emit(model_path, True)

    def _on_vosk_model_load_error(self, model_path: str, error_message: str):
        self._is_loading = False
        self.modelLoadingFinished.emit(model_path, False)

    def unload_model(self):
        if self._active_whisper_model_instance:
            unloaded_model_name = self._active_model_name_loaded
            logger.info(f"Unloading Whisper model: {unloaded_model_name}")
            del self._active_whisper_model_instance
            self._active_whisper_model_instance = None
            self._active_model_name_loaded = None
            self.modelUnloaded.emit(unloaded_model_name)
            logger.info(f"Model '{unloaded_model_name}' unloaded.")
        elif self._active_vosk_model_instance:
            unloaded_model_path = self._active_model_name_loaded
            logger.info(f"Unloading VOSK model: {unloaded_model_path}")
            del self._active_vosk_model_instance
            self._active_vosk_model_instance = None
            self._active_model_name_loaded = None
            self.modelUnloaded.emit(unloaded_model_path)
            logger.info(f"Model '{unloaded_model_path}' unloaded.")

    @staticmethod
    def _resample_audio(input_path: str, target_sr: int, engine_name: str) -> str | None:
        """Resamples an audio file to a target sample rate using PyAV (delegates to stt_common)."""
        return resample_audio(input_path, target_sr, engine_name)


    def transcribe_audio(
        self,
        audio_path: str,
        recorded_samplerate: int,
        exercise_id: str,
        language_code: str | None = None,
    ) -> QRunnable | None:  # Return QRunnable for consistency
        selected_engine = self.get_selected_stt_engine()

        if selected_engine == "whisper":
            if not self._active_whisper_model_instance:
                logger.error(
                    f"Cannot transcribe: Whisper model '{self.get_selected_whisper_model_name()}' is not loaded."
                )
                return None

            task = WhisperTranscriptionTask(
                self._active_whisper_model_instance,
                audio_path,
                exercise_id,
                language_code=language_code,
                target_samplerate=app_settings.AUDIO_SAMPLE_RATE,
                recorded_samplerate=recorded_samplerate,
            )
            self.thread_pool.start(task)
            return task

        elif selected_engine == "vosk":
            if not self._active_vosk_model_instance:
                logger.error(
                    f"Cannot transcribe: VOSK model '{self.get_selected_vosk_model_path()}' is not loaded."
                )
                return None

            task = VoskTranscriptionTask(
                self._active_vosk_model_instance,
                audio_path,
                exercise_id,
                self.vosk_samplerate,
                language_code=language_code,
                recorded_samplerate=recorded_samplerate,
            )
            self.thread_pool.start(task)
            return task
        else:
            logger.error(
                f"Cannot transcribe: Unknown STT engine selected: {selected_engine}"
            )
            return None

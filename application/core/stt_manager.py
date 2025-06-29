import logging
from PySide6.QtCore import QObject, Signal, QSettings, QThreadPool, QRunnable
from typing import Optional
import settings as app_settings
import soundfile as sf
import av
import numpy as np

from .whisper_engine import WhisperModelLoader, WhisperTranscriptionTask, get_best_whisper_device_config
from .vosk_manager import ModelLoader as VoskModelLoader, TranscriptionTask as VoskTranscriptionTask # Renamed to avoid conflict

logger = logging.getLogger(__name__)

class STTManager(QObject):
    modelLoadingStarted = Signal(str)  # model_name or model_path
    modelLoadingFinished = Signal(str, bool)  # model_name or model_path, success
    modelUnloaded = Signal(str)  # model_name or model_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.q_settings = QSettings()
        self.thread_pool = QThreadPool.globalInstance()

        self._active_whisper_model_instance: Optional[object] = None # Use object for type hinting flexibility
        self._active_vosk_model_instance: Optional[object] = None
        self._active_model_name_loaded: Optional[str] = None # Stores the name/path of the currently loaded model
        self._is_loading = False

        self.whisper_device, self.whisper_compute_type = get_best_whisper_device_config()
        logger.info(
            f"Whisper configured to use device='{self.whisper_device}' with compute_type='{self.whisper_compute_type}'."
        )

        # Determine samplerate for Vosk
        try:
            import sounddevice as sd
            device_info = sd.query_devices(sd.default.device[0], 'input')
            self.vosk_samplerate = int(device_info['default_samplerate'])
        except Exception as e:
            logger.warning(f"Could not determine default audio device samplerate for Vosk: {e}. Using default 16000.")
            self.vosk_samplerate = 16000 # Default samplerate if detection fails

        logger.info(f"Vosk configured with samplerate={self.vosk_samplerate}.")

    def get_selected_stt_engine(self) -> str:
        return self.q_settings.value(
            app_settings.QSETTINGS_KEY_STT_ENGINE,
            app_settings.STT_ENGINE_DEFAULT,
            type=str,
        )

    def get_selected_whisper_model_name(self) -> str:
        return self.q_settings.value(
            app_settings.QSETTINGS_KEY_WHISPER_MODEL,
            app_settings.WHISPER_MODEL_DEFAULT,
            type=str,
        )

    def get_selected_vosk_model_path(self) -> str:
        # This will need to be updated to reflect how VOSK models are selected/stored
        # For now, a placeholder.
        return self.q_settings.value(
            app_settings.QSETTINGS_KEY_VOSK_MODEL,
            app_settings.VOSK_MODEL_DEFAULT,
            type=str,
        )

    def get_loaded_model_name(self) -> Optional[str]:
        return self._active_model_name_loaded

    def is_loading(self) -> bool:
        return self._is_loading

    def load_model(self):
        selected_engine = self.get_selected_stt_engine()
        logger.info(f"Attempting to load STT model for engine: {selected_engine}")
        model_to_load = None

        if selected_engine == "whisper":
            model_to_load = self.get_selected_whisper_model_name()
            if not model_to_load or model_to_load.lower() == "none":
                logger.info("No Whisper model selected or 'None' specified. Skipping load.")
                self.modelLoadingFinished.emit("None", True)
                return
            if self._active_model_name_loaded == model_to_load and self._active_whisper_model_instance:
                logger.info(f"Whisper model '{model_to_load}' is already loaded. No action needed.")
                self.modelLoadingFinished.emit(model_to_load, True)
                return
            logger.info(f"Loading Whisper model: {model_to_load}")
            self.unload_model() # Unload any previously loaded model
            self._is_loading = True
            self.modelLoadingStarted.emit(model_to_load)
            loader_task = WhisperModelLoader(model_to_load, self.whisper_device, self.whisper_compute_type)
            loader_task.signals.finished.connect(self._on_whisper_model_loaded)
            loader_task.signals.error.connect(self._on_whisper_model_load_error)
            self.thread_pool.start(loader_task)

        elif selected_engine == "vosk":
            model_to_load = self.get_selected_vosk_model_path()
            if not model_to_load or model_to_load.lower() == "none":
                logger.info("No Vosk model selected or 'None' specified. Skipping load.")
                self.modelLoadingFinished.emit("None", True)
                return
            if self._active_model_name_loaded == model_to_load and self._active_vosk_model_instance:
                logger.info(f"Vosk model '{model_to_load}' is already loaded. No action needed.")
                self.modelLoadingFinished.emit(model_to_load, True)
                return
            logger.info(f"Loading Vosk model: {model_to_load}")
            self.unload_model() # Unload any previously loaded model
            self._is_loading = True
            self.modelLoadingStarted.emit(model_to_load)
            loader_task = VoskModelLoader(model_to_load)
            loader_task.signals.finished.connect(self._on_vosk_model_loaded)
            loader_task.signals.error.connect(self._on_vosk_model_load_error)
            self.thread_pool.start(loader_task)
        else:
            logger.warning(f"Unknown STT engine selected: {selected_engine}. Cannot load model.")
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

    def _resample_audio(self, input_path: str, target_sr: int, engine_name: str) -> Optional[str]:
        """
        Resamples an audio file to a target sample rate using PyAV and saves it.

        Args:
            input_path (str): Path to the input audio file.
            target_sr (int): The target sample rate (e.g., 16000).
            engine_name (str): The name of the STT engine (e.g., "whisper" or "vosk"),
                               used for logging and file naming.

        Returns:
            Optional[str]: The path to the new resampled audio file, or None on failure.
        """
        logger.info(
            f"Resampling audio from '{input_path}' to {target_sr}Hz for {engine_name.capitalize()} using PyAV."
        )
        try:
            # Define a unique output path based on the engine and sample rate
            if engine_name == "whisper":
                output_path = input_path.replace(".wav", "_resampled_whisper.wav")
            else:
                output_path = input_path.replace(".wav", f"_resampled_vosk_{target_sr}.wav")

            # Use a 'with' statement for proper resource management
            with av.open(input_path) as in_container:
                # Find the first audio stream
                in_stream = next((s for s in in_container.streams if s.type == 'audio'), None)
                if in_stream is None:
                    logger.error(f"No audio streams found in {input_path}")
                    return None

                # Set up the resampler to convert to mono, float, with the target sample rate
                resampler = av.AudioResampler(
                    format="fltp",    # Output format: float, planar
                    layout="mono",   # Output layout: single channel
                    rate=target_sr,      # Output sample rate
                )

                resampled_frames = []
                # Decode all frames from the input stream and resample them
                for frame in in_container.decode(in_stream):
                    resampled_frames.extend(resampler.resample(frame))

                # **IMPORTANT**: Flush the resampler to get any buffered frames
                resampled_frames.extend(resampler.resample(None))

                if not resampled_frames:
                    logger.error(f"Resampling produced no frames for {input_path}. The file might be empty or corrupt.")
                    return None

                # Concatenate all resampled frames into a single numpy array
                # .to_ndarray() for fltp/mono gives a shape of (1, n_samples), so we reshape to a 1D array.
                resampled_audio_data = np.concatenate([frame.to_ndarray().reshape(-1) for frame in resampled_frames])

                # Write the resampled data to the new file
                sf.write(output_path, resampled_audio_data, target_sr)
                logger.info(f"Successfully saved resampled audio to '{output_path}'")
                return output_path

        except Exception as e:
            logger.error(f"Error during audio resampling for {engine_name.capitalize()}: {e}", exc_info=True)
            return None

    def transcribe_audio(
        self, audio_path: str, recorded_samplerate: int, exercise_id: str, language_code: Optional[str] = None
    ) -> Optional[QRunnable]: # Return QRunnable for consistency
        selected_engine = self.get_selected_stt_engine()

        if selected_engine == "whisper":
            if not self._active_whisper_model_instance:
                logger.error(
                    f"Cannot transcribe: Whisper model '{self.get_selected_whisper_model_name()}' is not loaded."
                )
                return None

            # Resample audio to 16kHz for Whisper if necessary
            target_sr = 16000
            if recorded_samplerate != target_sr:
                resampled_path = self._resample_audio(audio_path, target_sr, "whisper")
                if resampled_path is None:
                    # _resample_audio already logged the specific error
                    return None
                audio_path = resampled_path # Use the new resampled file path

            task = WhisperTranscriptionTask(
                self._active_whisper_model_instance,
                audio_path,
                exercise_id,
                language_code=language_code,
            )
            self.thread_pool.start(task)
            return task

        elif selected_engine == "vosk":
            if not self._active_vosk_model_instance:
                logger.error(
                    f"Cannot transcribe: VOSK model '{self.get_selected_vosk_model_path()}' is not loaded."
                )
                return None

            # Resample audio for Vosk if necessary
            if recorded_samplerate != self.vosk_samplerate:
                resampled_path = self._resample_audio(audio_path, self.vosk_samplerate, "vosk")
                if resampled_path is None:
                    # _resample_audio already logged the specific error
                    return None
                audio_path = resampled_path # Use the new resampled file path

            task = VoskTranscriptionTask(
                self._active_vosk_model_instance,
                audio_path,
                exercise_id,
                self.vosk_samplerate,
                language_code=language_code,
            )
            self.thread_pool.start(task)
            return task
        else:
            logger.error(f"Cannot transcribe: Unknown STT engine selected: {selected_engine}")
            return None
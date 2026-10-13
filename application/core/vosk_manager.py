import json
import logging
import os
import zipfile

import py7zr
import settings as app_settings
import utils

from .stt_common import (
    BaseModelLoader,
    BaseTranscriptionTask,
    TranscriptionResult,
    resample_audio,
)

try:
    from vosk import KaldiRecognizer, Model  # type: ignore

    _VOSK_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("VOSK not found. VOSK STT will be unavailable.")
    _VOSK_AVAILABLE = False

    class Model:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

    class KaldiRecognizer:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

        def SetWords(self, *args, **kwargs):
            pass

        def AcceptWaveform(self, *args, **kwargs):
            return False

        def Result(self):
            return json.dumps({"text": ""})

        def PartialResult(self):
            return json.dumps({"partial": ""})

        def FinalResult(self):
            return json.dumps({"text": ""})


logger = logging.getLogger(__name__)


class ModelLoader(BaseModelLoader):
    """
    A QRunnable task to load a VOSK model in a background thread.
    """

    def __init__(self, model_path: str):
        super().__init__(model_path)
        self.model_path = model_path
        logger.debug(f"VOSK ModelLoader task created for model: {model_path}")

    def run(self):
        if not _VOSK_AVAILABLE:
            error_msg = (
                "VOSK is not available. Please install vosk and its dependencies."
            )
            logger.error(error_msg)
            self.signals.error.emit(self.model_path, error_msg)
            return
        try:
            logger.info(
                f"Background Task: Attempting to load VOSK model '{self.model_path}'."
            )
            # Resolve the actual model path (expected directory)
            actual_model_dir = utils.get_stt_model_path(
                app_settings.STT_ENGINE_VOSK, self.model_path
            )

            if not os.path.exists(actual_model_dir):
                logger.info(
                    f"Model directory '{actual_model_dir}' not found. Checking for zip/7z archive."
                )
                # Construct potential archive file paths
                archive_paths = {
                    ".zip": actual_model_dir + ".zip",
                    ".7z": actual_model_dir + ".7z",
                }

                extracted = False
                for ext, archive_path in archive_paths.items():
                    if os.path.exists(archive_path):
                        logger.info(
                            f"Found VOSK model {ext} file: '{archive_path}'. Attempting extraction..."
                        )
                        try:
                            if ext == ".zip":
                                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                                    zip_ref.extractall(
                                        os.path.dirname(actual_model_dir)
                                    )
                            elif ext == ".7z":
                                with py7zr.SevenZipFile(
                                    archive_path, mode="r"
                                ) as sz_ref:
                                    sz_ref.extractall(
                                        path=os.path.dirname(actual_model_dir)
                                    )
                            logger.info(
                                f"Successfully extracted '{archive_path}' to '{os.path.dirname(actual_model_dir)}'."
                            )
                            extracted = True
                            break  # Stop after first successful extraction
                        except Exception as archive_e:
                            error_msg = f"Failed to extract VOSK model {ext} '{archive_path}': {archive_e}"
                            logger.error(error_msg, exc_info=True)
                            self.signals.error.emit(self.model_path, error_msg)
                            return

                if not extracted:
                    error_msg = f"VOSK model directory '{actual_model_dir}' not found and no corresponding archive files (.zip, .7z) were found. Please ensure the model is downloaded and placed correctly."
                    logger.error(error_msg)
                    self.signals.error.emit(self.model_path, error_msg)
                    return

            # If we reach here, the model directory should exist (either pre-existing or extracted)
            if not os.path.exists(actual_model_dir):
                error_msg = f"VOSK model directory '{actual_model_dir}' does not exist after extraction attempt. This indicates a problem with the extraction process."
                logger.error(error_msg)
                self.signals.error.emit(self.model_path, error_msg)
                return

            model_instance = Model(actual_model_dir)
            logger.info(
                f"Background Task: VOSK model '{self.model_path}' loaded successfully from '{actual_model_dir}'."
            )
            self.signals.finished.emit(self.model_path, model_instance)
        except Exception as e:
            error_msg = (
                f"Background Task: Failed to load VOSK model '{self.model_path}': {e}"
            )
            logger.error(error_msg, exc_info=True)
            self.signals.error.emit(self.model_path, error_msg)


class TranscriptionTask(BaseTranscriptionTask):
    """
    A QRunnable task to run transcription in a background thread using VOSK.
    """

    def __init__(
        self,
        model: Model,
        audio_path: str,
        exercise_id: str,
        samplerate: int,
        language_code: str | None = None,
        cleanup_paths: list[str] | None = None,
        recorded_samplerate: int | None = None,
    ):
        super().__init__(exercise_id, language_code, cleanup_paths=cleanup_paths)
        self._model = model
        self.audio_path = audio_path
        self.samplerate = samplerate
        self.recorded_samplerate = recorded_samplerate

    def is_available(self) -> bool:
        return _VOSK_AVAILABLE

    def unavailable_message(self) -> str:
        return "VOSK is not available."

    def _run_transcription(self) -> TranscriptionResult:
        audio_file_to_use = self.audio_path
        if (
            self.recorded_samplerate
            and self.recorded_samplerate != self.samplerate
        ):
            resampled = resample_audio(
                self.audio_path, self.samplerate, "vosk"
            )
            if resampled:
                audio_file_to_use = resampled
                self.cleanup_paths.append(resampled)

        logger.info(
            f"Background Task: Starting VOSK transcription for {audio_file_to_use}"
        )

        # VOSK requires a KaldiRecognizer for transcription
        recognizer = KaldiRecognizer(self._model, self.samplerate)
        recognizer.SetWords(False)  # We only need the text

        import soundfile as sf

        # Read audio file
        data, samplerate = sf.read(audio_file_to_use, dtype="int16")

        # Check if the samplerate of the audio file matches the model's samplerate
        if samplerate != self.samplerate:
            logger.warning(
                f"Audio file samplerate ({samplerate}) does not match VOSK model samplerate ({self.samplerate})."
            )
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
            logger.warning(
                f"VOSK transcription returned empty for {self.audio_path}. Attempting FinalResult."
            )
            final_result = json.loads(recognizer.FinalResult())
            transcribed_text = final_result.get("text", "")

        logger.info(
            f"VOSK transcription result for {self.exercise_id}: {transcribed_text}"
        )
        logger.info(
            f"Background Task: VOSK transcription finished for {self.exercise_id}."
        )
        return TranscriptionResult(
            text=transcribed_text, words=[], engine=app_settings.STT_ENGINE_VOSK
        )

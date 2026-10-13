# application/ui/widgets/audio_recording_controller.py

import logging
import os
import tempfile

import numpy as np
import soundfile as sf
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QSettings, QTimer, Signal
from PySide6.QtMultimedia import (
    QAudioDevice,
    QAudioFormat,
    QAudioSource,
    QMediaDevices,
)

try:
    from application import settings as app_settings
except ImportError:
    import settings as app_settings

logger = logging.getLogger(__name__)


class AudioRecordingController(QObject):
    """
    Headless controller managing audio capture hardware, real-time PCM level sampling,
    and temporary WAV file persistence.
    """

    recording_started = Signal()
    recording_stopped = Signal(str, int)  # file_path, samplerate
    pcm_samples_available = Signal(bytes)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._audio_recorder: QAudioSource | None = None
        self._audio_buffer: QByteArray | None = None
        self._qbuffer: QBuffer | None = None
        self._temp_audio_file: tempfile.NamedTemporaryFile | None = None
        self._is_recording = False

        self._level_sample_timer = QTimer(self)
        self._level_sample_timer.setInterval(50)
        self._level_sample_timer.timeout.connect(self._sample_audio_level)

    def is_recording(self) -> bool:
        return self._is_recording

    def _init_audio_recorder(self) -> bool:
        if self._audio_recorder:
            return True

        q_settings = QSettings()
        preferred_device_id_str = q_settings.value(
            app_settings.QSETTINGS_KEY_AUDIO_INPUT_DEVICE,
            "",
            type=str,
        )
        selected_device_info: QAudioDevice | None = None
        if preferred_device_id_str:
            for device in QMediaDevices.audioInputs():
                if device.id().toStdString() == preferred_device_id_str:
                    selected_device_info = device
                    logger.info(f"Using preferred audio input device: {selected_device_info.description()}")
                    break

        if not selected_device_info:
            default_device_info = QMediaDevices.defaultAudioInput()
            if not default_device_info.isNull():
                selected_device_info = default_device_info
                logger.info(f"Using system default audio input device: {selected_device_info.description()}")
            else:
                msg = "No audio input device found!"
                logger.error(msg)
                self.error_occurred.emit(msg)
                return False

        if selected_device_info and not selected_device_info.isNull():
            audio_format = QAudioFormat()
            audio_format.setSampleRate(int(selected_device_info.maximumSampleRate()))
            audio_format.setChannelCount(1)
            audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self._audio_recorder = QAudioSource(selected_device_info, audio_format, self)
            return True

        self.error_occurred.emit("No audio input device available.")
        return False

    def start_recording(self) -> bool:
        if not self._init_audio_recorder():
            return False

        self._cleanup_temp_file()
        self._temp_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self._temp_audio_file.close()

        self._audio_buffer = QByteArray()
        self._qbuffer = QBuffer(self._audio_buffer, self)
        self._qbuffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self._audio_recorder.start(self._qbuffer)
        self._is_recording = True
        self._level_sample_timer.start()

        self.recording_started.emit()
        logger.info("Audio recording started.")
        return True

    def stop_recording(self):
        if not self._is_recording or not self._audio_recorder:
            return

        self._level_sample_timer.stop()
        self._audio_recorder.stop()
        self._is_recording = False
        logger.info("Audio recording stopped.")

        if self._qbuffer and self._qbuffer.isOpen():
            self._qbuffer.close()

        if self._temp_audio_file and self._audio_buffer and self._audio_buffer.size() > 0:
            try:
                recorded_samplerate = self._audio_recorder.format().sampleRate()
                sf.write(
                    self._temp_audio_file.name,
                    np.frombuffer(self._audio_buffer.data(), dtype=np.int16),
                    recorded_samplerate,
                    format="WAV",
                    subtype="PCM_16",
                )
                logger.info(f"WAV audio saved to {self._temp_audio_file.name} at {recorded_samplerate} Hz")
                self.recording_stopped.emit(self._temp_audio_file.name, recorded_samplerate)
            except Exception as e:
                logger.error(f"Error saving audio to {self._temp_audio_file.name}: {e}")
                self.error_occurred.emit(f"Error saving audio: {e}")
            finally:
                self._audio_buffer = None
                self._qbuffer = None
        else:
            self.error_occurred.emit("No audio data recorded.")

    def _sample_audio_level(self):
        if self._is_recording and self._audio_buffer and self._audio_buffer.size() > 0:
            tail = self._audio_buffer.right(2048).data()
            self.pcm_samples_available.emit(tail)

    def _cleanup_temp_file(self):
        if self._temp_audio_file:
            try:
                if os.path.exists(self._temp_audio_file.name):
                    os.unlink(self._temp_audio_file.name)
            except Exception as e:
                logger.debug(f"Error removing temp audio file: {e}")
            self._temp_audio_file = None

    def cleanup(self):
        if self._is_recording:
            self.stop_recording()
        self._cleanup_temp_file()

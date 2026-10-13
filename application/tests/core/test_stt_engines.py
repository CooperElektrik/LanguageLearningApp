"""Both STT backends must emit the same TranscriptionResult payload.

Previously Whisper emitted ``(segments, info)`` and Vosk a bare string, and the
UI had to branch on ``isinstance(result, str)``. This pins the unified shape.
"""

import sys
import types

import pytest
from PySide6.QtCore import QCoreApplication

# These optional deps may be absent in a slim test environment; stub only if the
# real module is genuinely unavailable.
for _name in ("soundfile", "py7zr"):
    try:  # pragma: no cover - depends on environment
        __import__(_name)
    except ImportError:  # pragma: no cover
        _stub = types.ModuleType(_name)
        if _name == "soundfile":

            class _FakeAudio:
                def tobytes(self):
                    return b"\x00" * 3200

            _stub.read = lambda *a, **k: (_FakeAudio(), 16000)
        else:

            class _SevenZipFile:  # pragma: no cover - never used here
                def __init__(self, *a, **k):
                    pass

            _stub.SevenZipFile = _SevenZipFile
        sys.modules[_name] = _stub

from core import vosk_manager, whisper_engine  # noqa: E402
from core.stt_common import TranscriptionResult  # noqa: E402


@pytest.fixture(autouse=True)
def _qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class _FakeWord:
    def __init__(self, word, probability):
        self.word = word
        self.probability = probability


class _FakeSegment:
    def __init__(self, text, words):
        self.text = text
        self.words = words


class _FakeWhisperModel:
    def transcribe(self, *a, **k):
        return (
            iter(
                [
                    _FakeSegment("Hello ", [_FakeWord("Hello", 0.95)]),
                    _FakeSegment("world", [_FakeWord("world", 0.8)]),
                ]
            ),
            {"language": "en"},
        )


class _FakeRecognizer:
    def __init__(self, model, samplerate):
        pass

    def SetWords(self, flag):
        pass

    def AcceptWaveform(self, data):
        return True

    def Result(self):
        return '{"text": "xin chao"}'

    def PartialResult(self):
        return "{}"

    def FinalResult(self):
        return "{}"


def test_whisper_emits_transcription_result(monkeypatch):
    monkeypatch.setattr(whisper_engine, "_FASTER_WHISPER_AVAILABLE", True)
    task = whisper_engine.WhisperTranscriptionTask(
        _FakeWhisperModel(), "/tmp/a.wav", "ex1", language_code="en"
    )
    captured = {}
    task.signals.finished.connect(lambda eid, res: captured.update(eid=eid, res=res))
    task.run()

    assert captured["eid"] == "ex1"
    result = captured["res"]
    assert isinstance(result, TranscriptionResult)
    assert result.text == "Hello world"
    assert [w.word for w in result.words] == ["Hello", "world"]
    assert result.engine == "whisper"


def test_vosk_emits_transcription_result(monkeypatch):
    class _FakeAudio:
        def tobytes(self):
            return b"\x00" * 3200

    import soundfile as sf

    monkeypatch.setattr(sf, "read", lambda *a, **k: (_FakeAudio(), 16000))
    monkeypatch.setattr(vosk_manager, "_VOSK_AVAILABLE", True)
    monkeypatch.setattr(vosk_manager, "KaldiRecognizer", _FakeRecognizer)
    task = vosk_manager.TranscriptionTask(object(), "/tmp/a.wav", "ex2", 16000)
    captured = {}
    task.signals.finished.connect(lambda eid, res: captured.update(eid=eid, res=res))
    task.run()

    assert captured["eid"] == "ex2"
    result = captured["res"]
    assert isinstance(result, TranscriptionResult)
    assert result.text == "xin chao"
    assert result.words == []
    assert result.engine == "vosk"


def test_unavailable_engine_emits_error(monkeypatch):
    monkeypatch.setattr(whisper_engine, "_FASTER_WHISPER_AVAILABLE", False)
    task = whisper_engine.WhisperTranscriptionTask(
        _FakeWhisperModel(), "/tmp/a.wav", "ex3"
    )
    errors = []
    task.signals.error.connect(lambda eid, msg: errors.append((eid, msg)))
    task.run()
    assert errors == [("ex3", "faster_whisper is not available.")]

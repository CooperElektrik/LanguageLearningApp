"""Both STT backends must emit the same TranscriptionResult payload.

Previously Whisper emitted ``(segments, info)`` and Vosk a bare string, and the
UI had to branch on ``isinstance(result, str)``. This pins the unified shape.
"""

import os
import sys
import tempfile
import types
import zipfile
from unittest.mock import MagicMock

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

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

                def getnames(self):
                    return []

                def extractall(self, *a, **k):
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
    task = whisper_engine.WhisperTranscriptionTask(_FakeWhisperModel(), "/tmp/a.wav", "ex3")
    errors = []
    task.signals.error.connect(lambda eid, msg: errors.append((eid, msg)))
    task.run()
    assert errors == [("ex3", "faster_whisper is not available.")]


def test_check_whisper_model_downloaded_optimizations(monkeypatch):
    # 1. When faster_whisper is not available, returns False immediately
    monkeypatch.setattr(whisper_engine, "_FASTER_WHISPER_AVAILABLE", False)
    assert whisper_engine.check_whisper_model_downloaded("tiny") is False

    monkeypatch.setattr(whisper_engine, "_FASTER_WHISPER_AVAILABLE", True)

    # 2. When directory exists on disk directly, returns True without instantiating WhisperModel
    whisper_model_mock = MagicMock()
    monkeypatch.setattr(whisper_engine, "WhisperModel", whisper_model_mock)

    with tempfile.TemporaryDirectory() as tmpdir:
        assert whisper_engine.check_whisper_model_downloaded(tmpdir) is True
        assert not whisper_model_mock.called

    # 3. When download_root doesn't exist, returns False without calling download_model or WhisperModel
    download_model_mock = MagicMock()
    monkeypatch.setattr(whisper_engine, "download_model", download_model_mock)
    monkeypatch.setattr(
        "utils.get_stt_model_path",
        lambda engine, name: "/nonexistent/test/path/models",
    )

    assert whisper_engine.check_whisper_model_downloaded("tiny") is False
    assert not download_model_mock.called
    assert not whisper_model_mock.called

    # 4. When download_root exists and download_model finds cache, returns True without instantiating WhisperModel
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("utils.get_stt_model_path", lambda engine, name: tmpdir)
        download_model_mock.return_value = tmpdir

        assert whisper_engine.check_whisper_model_downloaded("tiny") is True
        assert download_model_mock.called
        assert not whisper_model_mock.called


def test_vosk_transcription_calls_final_result_at_most_once(monkeypatch):
    class CountingRecognizer:
        def __init__(self, model, samplerate):
            self.final_result_calls = 0

        def SetWords(self, flag):
            pass

        def AcceptWaveform(self, data):
            return False

        def PartialResult(self):
            return '{"partial": ""}'

        def FinalResult(self):
            self.final_result_calls += 1
            return '{"text": ""}'

    rec = CountingRecognizer(object(), 16000)

    class _FakeAudio:
        def tobytes(self):
            return b"\x00" * 3200

    import soundfile as sf

    monkeypatch.setattr(sf, "read", lambda *a, **k: (_FakeAudio(), 16000))
    monkeypatch.setattr(vosk_manager, "_VOSK_AVAILABLE", True)
    monkeypatch.setattr(vosk_manager, "KaldiRecognizer", lambda *a, **k: rec)

    task = vosk_manager.TranscriptionTask(object(), "/tmp/a.wav", "ex_vosk", 16000)
    result = task._run_transcription()

    assert result.text == ""
    assert rec.final_result_calls == 1


def test_vosk_extract_model_zip_safe_and_zip_slip():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Safe zip extraction
        safe_zip = os.path.join(tmpdir, "safe.zip")
        with zipfile.ZipFile(safe_zip, "w") as zf:
            zf.writestr("model_dir/test.txt", "sample content")

        safe_dest = os.path.join(tmpdir, "safe_out")
        vosk_manager.extract_model(safe_zip, safe_dest)
        assert os.path.exists(os.path.join(safe_dest, "model_dir", "test.txt"))

        # Malicious zip extraction (Zip Slip)
        bad_zip = os.path.join(tmpdir, "bad.zip")
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("../traversal.txt", "danger")

        bad_dest = os.path.join(tmpdir, "bad_out")
        with pytest.raises(ValueError, match="Malicious archive member detected"):
            vosk_manager.extract_model(bad_zip, bad_dest)


def test_vosk_extract_model_7z_safe_and_zip_slip(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Safe 7z extraction
        class SafeSevenZip:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def getnames(self):
                return ["model_dir/test.txt"]

            def extractall(self, path=None):
                target = os.path.join(path, "model_dir")
                os.makedirs(target, exist_ok=True)
                with open(os.path.join(target, "test.txt"), "w") as f:
                    f.write("sample content")

        monkeypatch.setattr(vosk_manager.py7zr, "SevenZipFile", SafeSevenZip)
        safe_7z = os.path.join(tmpdir, "model.7z")
        safe_dest = os.path.join(tmpdir, "safe_out_7z")
        vosk_manager.extract_model(safe_7z, safe_dest)
        assert os.path.exists(os.path.join(safe_dest, "model_dir", "test.txt"))

        # Malicious 7z extraction (Zip Slip simulation)
        class MaliciousSevenZip:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def getnames(self):
                return ["../../evil.txt"]

            def extractall(self, *a, **k):
                raise AssertionError("extractall should not be called on malicious archive")

        monkeypatch.setattr(vosk_manager.py7zr, "SevenZipFile", MaliciousSevenZip)
        bad_7z = os.path.join(tmpdir, "fake.7z")
        bad_dest = os.path.join(tmpdir, "bad_out_7z")
        with pytest.raises(ValueError, match="Malicious archive member detected"):
            vosk_manager.extract_model(bad_7z, bad_dest)

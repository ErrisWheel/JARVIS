from app.speech import (
    DEFAULT_VOICE,
    VOICE_CHOICES,
    normalize_speech_text,
    speech_status,
    synthesize_wav,
)


def test_default_voice_is_clear_american_male_and_faster():
    assert DEFAULT_VOICE == "am_michael"
    assert VOICE_CHOICES[DEFAULT_VOICE]["language"] == "en-us"
    import app.speech as speech
    assert speech.DEFAULT_SPEED == 1.12


def test_supported_english_voice_presets_are_whitelisted():
    assert set(VOICE_CHOICES) == {"bm_george", "bm_lewis", "am_michael", "am_adam"}
    assert VOICE_CHOICES["am_michael"]["language"] == "en-us"


def test_speech_text_removes_markdown_and_code():
    value = normalize_speech_text("## Result\n\n- **Ready.** See [the guide](https://example.com).\n```py\nprint('secret')\n```")
    assert "Result" in value
    assert "Ready." in value
    assert "the guide" in value
    assert "https://" not in value
    assert "print" not in value
    assert "code is on screen" in value.lower()


def test_empty_or_invalid_synthesis_input_is_rejected_before_model_load():
    try:
        synthesize_wav("   ")
    except ValueError as exc:
        assert "speakable text" in str(exc)
    else:
        raise AssertionError("Empty speech text should be rejected")

    try:
        synthesize_wav("Hello there.", voice="not-a-real-voice")
    except ValueError as exc:
        assert "Unknown local voice" in str(exc)
    else:
        raise AssertionError("Unsupported voice should be rejected")


def test_speech_status_is_local_and_reports_installation_state():
    status = speech_status()
    assert status["engine"] == "Kokoro-82M ONNX"
    assert status["default_voice"] == DEFAULT_VOICE
    assert status["available"] == (status["package_available"] and status["model_available"])
    assert len(status["voices"]) == 4


def test_wav_encoding_with_mock_local_engine(monkeypatch):
    import io
    import wave
    import numpy as np
    import app.speech as speech

    class FakeEngine:
        def create(self, text, voice, speed, lang):
            assert text == "Hello there."
            assert voice == "am_michael"
            assert speed == 1.12
            assert lang == "en-us"
            return np.array([0.0, 0.25, -0.25, 0.0], dtype=np.float32), 24000

    monkeypatch.setattr(speech, "_get_engine", lambda: FakeEngine())
    payload = speech.synthesize_wav("Hello there.", voice="am_michael", speed=1.12)
    with wave.open(io.BytesIO(payload), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 24000
        assert audio.getnframes() == 4


def test_status_audio_phrases_are_prepared_and_cached(monkeypatch):
    import app.speech as speech

    speech._status_audio_cache.clear()
    calls = []
    monkeypatch.setattr(speech, "speech_status", lambda: {"available": True})
    monkeypatch.setattr(
        speech, "synthesize_wav",
        lambda text, voice, speed: calls.append((text, voice, speed)) or text.encode("utf-8"),
    )

    speech.prewarm_status_audio()
    assert speech.get_status_audio("ack") == b"On it."
    assert speech.get_status_audio("working") == b"I'm still working through the details."
    assert len(calls) == 2
    speech._status_audio_cache.clear()


def test_status_audio_rejects_unknown_phrase():
    import app.speech as speech

    try:
        speech.get_status_audio("private-thought")
    except ValueError as exc:
        assert "Unknown voice status" in str(exc)
    else:
        raise AssertionError("Unknown status phrase should be rejected")


def test_status_audio_cache_separates_speech_rates(monkeypatch):
    import app.speech as speech

    speech._status_audio_cache.clear()
    calls = []
    monkeypatch.setattr(
        speech, "synthesize_wav",
        lambda text, voice, speed: calls.append((text, voice, speed)) or f"{text}:{speed}".encode(),
    )

    normal = speech.get_status_audio("ack", "am_michael", 1.0)
    fast = speech.get_status_audio("ack", "am_michael", 1.12)
    assert normal != fast
    assert len(calls) == 2
    speech._status_audio_cache.clear()

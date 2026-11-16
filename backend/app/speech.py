from __future__ import annotations

import importlib.util
import io
import logging
import re
import threading
import wave
from pathlib import Path

from .config import TTS_MODEL_DIR

log = logging.getLogger("jarvis.speech")

MODEL_PATH = TTS_MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = TTS_MODEL_DIR / "voices-v1.0.bin"
DEFAULT_VOICE = "am_michael"
DEFAULT_SPEED = 1.12
MAX_SPEECH_CHARS = 1400
STATUS_UTTERANCES = {
    "ack": "On it.",
    "working": "I'm still working through the details.",
}

VOICE_CHOICES = {
    "bm_george": {"label": "George · British male", "language": "en-gb"},
    "bm_lewis": {"label": "Lewis · British male", "language": "en-gb"},
    "am_michael": {"label": "Michael · Clear American male", "language": "en-us"},
    "am_adam": {"label": "Adam · American male", "language": "en-us"},
}

_engine = None
_engine_lock = threading.RLock()
_synthesis_lock = threading.Lock()
_status_audio_cache: dict[tuple[str, str, float], bytes] = {}
_status_cache_lock = threading.RLock()


def speech_status() -> dict:
    package_available = importlib.util.find_spec("kokoro_onnx") is not None
    model_available = MODEL_PATH.is_file() and VOICES_PATH.is_file()
    return {
        "available": package_available and model_available,
        "package_available": package_available,
        "model_available": model_available,
        "engine": "Kokoro-82M ONNX",
        "default_voice": DEFAULT_VOICE,
        "voices": [
            {"id": voice_id, **details}
            for voice_id, details in VOICE_CHOICES.items()
        ],
        "max_characters": MAX_SPEECH_CHARS,
        "default_speed": DEFAULT_SPEED,
        "speed_min": 0.85,
        "speed_max": 1.15,
    }


def normalize_speech_text(text: str) -> str:
    """Convert assistant text to clean spoken prose without reading markup or code."""
    value = str(text or "")
    value = re.sub(r"```[\s\S]*?```", " The code is on screen. ", value)
    value = re.sub(r"```[\s\S]*$", " The code is on screen. ", value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\((?:https?://)?[^)]+\)", r"\1", value)
    value = re.sub(r"https?://\S+", "that link", value)
    value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", value, flags=re.MULTILINE)
    value = re.sub(r"\*\*(.*?)\*\*|__(.*?)__", lambda m: m.group(1) or m.group(2) or "", value)
    value = re.sub(r"(?<!\w)[*_~>#]+|[*_~]+(?!\w)", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _get_engine():
    global _engine
    if not MODEL_PATH.is_file() or not VOICES_PATH.is_file():
        raise RuntimeError(
            "The local Kokoro voice model is not installed. Run scripts\\Install-Neural-Voice.ps1 from F:\\JARVIS."
        )
    with _engine_lock:
        if _engine is None:
            try:
                from kokoro_onnx import Kokoro
            except ImportError as exc:
                raise RuntimeError(
                    "Kokoro dependencies are missing. Run scripts\\Install-Neural-Voice.ps1 from F:\\JARVIS."
                ) from exc
            log.info("Loading local Kokoro neural voice model from %s", TTS_MODEL_DIR)
            _engine = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
            log.info("Kokoro neural voice model loaded")
    return _engine


def synthesize_wav(text: str, voice: str = DEFAULT_VOICE, speed: float = DEFAULT_SPEED) -> bytes:
    """Generate one local WAV utterance. No network calls are made by this function."""
    normalized = normalize_speech_text(text)
    if not normalized:
        raise ValueError("There is no speakable text in this response segment.")
    if len(normalized) > MAX_SPEECH_CHARS:
        raise ValueError(f"Speech segment exceeds {MAX_SPEECH_CHARS} characters; split it into shorter sentences.")
    if voice not in VOICE_CHOICES:
        raise ValueError("Unknown local voice preset.")
    try:
        speed_value = max(0.85, min(float(speed), 1.15))
    except (TypeError, ValueError):
        speed_value = DEFAULT_SPEED

    engine = _get_engine()
    language = VOICE_CHOICES[voice]["language"]
    # Keep ONNX synthesis serialized; the shared Kokoro session is reused across turns.
    with _synthesis_lock:
        samples, sample_rate = engine.create(
            normalized,
            voice=voice,
            speed=speed_value,
            lang=language,
        )

    import numpy as np

    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    if audio.size == 0:
        raise RuntimeError("Kokoro returned an empty audio buffer.")
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(np.abs(audio)))
    if peak > 1.0:
        audio = audio / peak * 0.98
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(sample_rate))
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()

def prewarm_status_audio() -> None:
    """Prepare short, factual progress utterances so they can play immediately."""
    if not speech_status()["available"]:
        return
    for key, text in STATUS_UTTERANCES.items():
        cache_key = (DEFAULT_VOICE, key, DEFAULT_SPEED)
        with _status_cache_lock:
            if cache_key in _status_audio_cache:
                continue
        try:
            audio = synthesize_wav(text, DEFAULT_VOICE, DEFAULT_SPEED)
            with _status_cache_lock:
                _status_audio_cache[cache_key] = audio
            log.info("Prepared local voice status phrase: %s", key)
        except Exception:
            log.exception("Could not pre-render local voice status phrase: %s", key)


def get_status_audio(key: str, voice: str = DEFAULT_VOICE, speed: float = DEFAULT_SPEED) -> bytes:
    """Return pre-rendered local status audio, or synthesize it for another preset."""
    if key not in STATUS_UTTERANCES:
        raise ValueError("Unknown voice status phrase.")
    if voice not in VOICE_CHOICES:
        raise ValueError("Unknown local voice preset.")
    try:
        speed_value = max(0.85, min(float(speed), 1.15))
    except (TypeError, ValueError):
        speed_value = DEFAULT_SPEED
    cache_key = (voice, key, speed_value)
    with _status_cache_lock:
        cached = _status_audio_cache.get(cache_key)
    if cached is not None:
        return cached
    audio = synthesize_wav(STATUS_UTTERANCES[key], voice, speed_value)
    with _status_cache_lock:
        _status_audio_cache[cache_key] = audio
    return audio


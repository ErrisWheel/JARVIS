from __future__ import annotations

import collections
import logging
import math
import queue
import re
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Literal

log = logging.getLogger("jarvis.voice")
FRAME_SAMPLES = 1280  # 80 ms at 16 kHz
SAMPLE_RATE = 16000
WAKE_THRESHOLD = 0.65
WAKE_CONSECUTIVE_FRAMES = 2
VOICE_RMS_THRESHOLD = 260.0
VAD_START_FRAMES = 2
END_SILENCE_SECONDS = 0.70
NO_COMMAND_TIMEOUT_SECONDS = 3.0
MAX_COMMAND_SECONDS = 22.0
FOLLOWUP_WINDOW_MAX_SECONDS = 25.0
FOLLOWUP_START_FRAMES = 2
MIN_SPEECH_SECONDS = 0.32

# Conversation mode intentionally uses a conservative first-phrase classifier.
# It cannot know who a speaker is addressing with certainty, so obvious social
# vocatives and reported speech are filtered before direct questions/commands.
SOCIAL_VOCATIVE = re.compile(
    r"^(?:(?:hey|hi|hello)\s+)?(?:friend|friends|guys|everyone|folks|team)[,\s]+",
    re.IGNORECASE,
)
REPORTED_SPEECH = re.compile(
    r"^(?:i said|i told (?:him|her|them|my friend)|he said|she said|they said|my friend said|someone asked)\b",
    re.IGNORECASE,
)
DIRECT_ADDRESS = re.compile(r"^(?:hey\s+)?jarvis\b[\s,.:;!?-]*", re.IGNORECASE)
DIRECT_REQUEST_START = re.compile(
    r"^(?:can|could|would|will|do|does|did|is|are|what|why|how|when|where|who|which|should|may|might|tell|show|explain|help|find|search|look up|check|open|close|start|stop|run|calculate|write|create|build|fix|make|update|change|summari[sz]e|compare|repeat|continue|play|pause|remember|forget|turn|set|switch|give|read|translate|define|describe|inspect|analy[sz]e|review|test)\b",
    re.IGNORECASE,
)
DIRECT_SECOND_PERSON = re.compile(
    r"^(?:i need you to|i want you to|i'd like you to|could you|can you|would you|will you|do me a favor|please|i was wondering if you|i wanted to ask you)\b",
    re.IGNORECASE,
)
DIRECT_FOLLOWUP = re.compile(
    r"^(?:and|also|but|so|okay|ok|yeah|yes|wait|right)[,\s]+(?:what|why|how|when|where|which|can|could|tell|show|explain|then|also)\b",
    re.IGNORECASE,
)


def clean_wake_phrase(text: str) -> str:
    """Remove a leading wake phrase from recognized text, not arbitrary mentions."""
    return DIRECT_ADDRESS.sub("", text.strip()).strip()


def clean_after_detected_wake_phrase(text: str) -> str:
    """After a confirmed audio wake event, keep only what follows the last call phrase."""
    cleaned = text.strip()
    matches = list(re.finditer(r"\bhey\s+jarvis\b[\s,.:;!?-]*", cleaned, flags=re.IGNORECASE))
    if matches:
        return cleaned[matches[-1].end():].strip()
    return clean_wake_phrase(cleaned)


def extract_conversation_request(text: str) -> tuple[str, bool]:
    """Return (command, directed) for hands-free conversation mode.

    A clear wake phrase anywhere in the utterance is an explicit call. Otherwise,
    accept direct question/command forms and reject ordinary statements, obvious
    friend-directed greetings, and reported speech. This is a local heuristic, not
    speaker identification; ambiguous utterances cannot be classified perfectly.
    """
    candidate = re.sub(r"\s+", " ", text).strip()
    if not candidate:
        return "", False
    # An explicit call always wins, even when the utterance starts by addressing
    # a friend: "Hey friend ... hey JARVIS, show me" is still a direct call.
    explicit_calls = list(re.finditer(r"\bhey\s+jarvis\b[\s,.:;!?-]*|^jarvis\b[\s,.:;!?-]*", candidate, re.IGNORECASE))
    if explicit_calls:
        tail = candidate[explicit_calls[-1].end():].strip()
        return (tail or "Yes?"), True

    if SOCIAL_VOCATIVE.match(candidate) or REPORTED_SPEECH.match(candidate):
        return candidate, False

    normalized = re.sub(r"^[\s,.;:!?-]+", "", candidate).strip()
    normalized = re.sub(r"^(?:hey|okay|alright|so|um|uh|well)[,\s]+", "", normalized, flags=re.IGNORECASE).strip()
    if DIRECT_SECOND_PERSON.match(normalized) or DIRECT_FOLLOWUP.match(normalized):
        return candidate, True
    if DIRECT_REQUEST_START.match(normalized):
        # Interrogative starts are accepted as questions; task verbs are direct commands.
        return candidate, True
    return candidate, False


def is_likely_directed_followup(text: str) -> bool:
    """Compatibility helper retained for the wake-only follow-up mode."""
    _, directed = extract_conversation_request(text)
    return directed


class VoiceListener:
    """Opt-in local microphone listener with continuous VAD conversation and wake-only modes."""

    def __init__(self, root: Path, model_dir: Path, transcribe: Callable[[str], dict]):
        self.root = root
        self.model_dir = model_dir
        self.transcribe = transcribe
        self._lock = threading.RLock()
        self._events_lock = threading.Lock()
        self._events: collections.deque[dict] = collections.deque(maxlen=64)
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._speaking = threading.Event()
        # Keep up to three complete utterances while Whisper is processing one.
        # This prevents the continuous listener from silently dropping every
        # interruption or follow-up that arrives during transcription.
        self._audio_queue: queue.Queue[tuple[list, Literal["wake", "conversation"]]] = queue.Queue(maxsize=3)
        self._processor_thread: threading.Thread | None = None
        self._thread: threading.Thread | None = None
        self._state = "off"
        self._error: str | None = None
        self._device_index: int | None = None
        self._device_name: str | None = None
        self._followup_until = 0.0
        self._mode: Literal["wake", "conversation"] = "conversation"
        self._input_level = 0.0
        self._input_dbfs = -90.0
        self._input_rms = 0.0
        self._voice_threshold = VOICE_RMS_THRESHOLD
        self._signal_detected = False

    def emit(self, event: dict) -> None:
        event["timestamp"] = time.time()
        with self._events_lock:
            self._events.append(event)

    def pop_events(self) -> list[dict]:
        with self._events_lock:
            items = list(self._events)
            self._events.clear()
        return items

    def status(self) -> dict:
        with self._lock:
            alive = bool(self._thread and self._thread.is_alive())
            return {
                "state": self._state,
                "enabled": alive and not self._stop.is_set(),
                "error": self._error,
                "device_index": self._device_index,
                "device_name": self._device_name,
                "mode": self._mode,
                "speaking": self._speaking.is_set(),
                "wake_phrase": "Hey Jarvis",
                "threshold": WAKE_THRESHOLD,
                "conversation_followup": max(0.0, round(self._followup_until - time.monotonic(), 1)),
                "input_level": round(self._input_level, 1),
                "input_dbfs": round(self._input_dbfs, 1),
                "input_rms": round(self._input_rms, 1),
                "input_threshold": round(self._voice_threshold, 1),
                "input_threshold_level": round(max(0.0, min(100.0, ((20.0 * math.log10(max(1.0, self._voice_threshold) / 32768.0)) + 60.0) * (100.0 / 51.0))), 1),
                "input_signal": self._signal_detected,
                "queue_depth": self._audio_queue.qsize(),
            }

    @staticmethod
    def list_devices() -> dict:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            default_input = sd.default.device[0] if sd.default.device else None
            items = []
            for index, device in enumerate(devices):
                if int(device.get("max_input_channels", 0)) > 0:
                    items.append({
                        "index": index,
                        "name": str(device.get("name", f"Input {index}")),
                        "channels": int(device.get("max_input_channels", 0)),
                        "default": index == default_input,
                    })
            return {"items": items, "default_input": default_input}
        except Exception as exc:
            raise RuntimeError(f"Could not enumerate microphone devices: {exc}") from exc

    def start(self, device_index: int | None = None, mode: Literal["wake", "conversation"] = "conversation") -> dict:
        if mode not in ("wake", "conversation"):
            raise ValueError("Voice mode must be 'wake' or 'conversation'.")
        with self._lock:
            if self._thread and self._thread.is_alive():
                if self._mode == mode and self._device_index == device_index:
                    return self.status()
                raise RuntimeError("The microphone listener is already running. Stop it before changing mode or device.")
            if self._processor_thread and self._processor_thread.is_alive():
                raise RuntimeError("The previous voice transcription is still shutting down. Wait briefly, then start the listener again.")
            while True:
                try:
                    self._audio_queue.get_nowait()
                    self._audio_queue.task_done()
                except queue.Empty:
                    break
            self._stop.clear()
            self._pause.clear()
            self._speaking.clear()
            self._error = None
            self._device_index = device_index
            self._device_name = None
            self._mode = mode
            self._state = "starting"
            self._thread = threading.Thread(target=self._run, name="JARVIS-Conversation" if mode == "conversation" else "JARVIS-WakeWord", daemon=True)
            self._thread.start()
            return self.status()

    def pause(self) -> dict:
        self._pause.set()
        self._set_state("paused")
        return self.status()

    def resume(self, follow_up_seconds: float = 0.0) -> dict:
        if self._thread and self._thread.is_alive() and not self._stop.is_set():
            duration = max(0.0, min(float(follow_up_seconds), FOLLOWUP_WINDOW_MAX_SECONDS))
            self._followup_until = time.monotonic() + duration if duration else 0.0
            self._pause.clear()
            self._set_state("conversation" if duration else "listening")
        return self.status()

    def set_speaking(self, speaking: bool) -> dict:
        if speaking:
            self._speaking.set()
            if self._mode == "conversation" and self._state not in ("capturing", "transcribing", "error", "off"):
                self._set_state("speaking")
        else:
            self._speaking.clear()
            if self._mode == "conversation" and self._thread and self._thread.is_alive() and not self._pause.is_set():
                if self._state == "speaking":
                    self._set_state("listening")
        return self.status()

    def stop(self) -> dict:
        self._stop.set()
        self._pause.clear()
        self._speaking.clear()
        self._followup_until = 0.0
        with self._lock:
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        # Discard utterances that were waiting when the user disabled listening.
        while True:
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.task_done()
            except queue.Empty:
                break
        processor = self._processor_thread
        if processor and processor.is_alive():
            processor.join(timeout=2.0)
        with self._lock:
            if not (self._thread and self._thread.is_alive()):
                self._state = "off"
                self._device_name = None
            return self.status()

    def _set_state(self, state: str, error: str | None = None) -> None:
        with self._lock:
            self._state = state
            self._error = error
        self.emit({"type": "state", "state": state, "error": error})

    def _run(self) -> None:
        try:
            import numpy as np
            import sounddevice as sd

            model = None
            if self._mode == "wake":
                from openwakeword.model import Model
                wake_path = self.model_dir / "hey_jarvis_v0.1.onnx"
                mel_path = self.model_dir / "melspectrogram.onnx"
                embedding_path = self.model_dir / "embedding_model.onnx"
                missing = [str(path) for path in (wake_path, mel_path, embedding_path) if not path.is_file()]
                if missing:
                    raise RuntimeError("Wake-word model files are missing: " + ", ".join(missing) + ". Run scripts\\Install-Voice-Model.ps1 again.")
                model = Model(
                    wakeword_models=[str(wake_path)], inference_framework="onnx", vad_threshold=0.0,
                    melspec_model_path=str(mel_path), embedding_model_path=str(embedding_path),
                )

            device = self._device_index
            if device is not None:
                self._device_name = str(sd.query_devices(device).get("name", f"Input {device}"))
            else:
                default_input = sd.default.device[0] if sd.default.device else None
                if default_input is not None:
                    self._device_name = str(sd.query_devices(default_input).get("name", "Default input"))

            if self._stop.is_set():
                return
            self._processor_thread = threading.Thread(
                target=self._process_pending_commands, args=(np,),
                name="JARVIS-TranscriptionQueue", daemon=True,
            )
            self._processor_thread.start()
            pre_roll: collections.deque = collections.deque(maxlen=12)  # 0.96 seconds
            self._set_state("listening")
            log.info("Voice listener started; mode=%s; device=%s", self._mode, self._device_name or "system default")

            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME_SAMPLES, device=device) as stream:
                above_threshold = 0
                capturing = False
                captured: list = []
                capture_started = 0.0
                last_voice_at = 0.0
                speech_seen = False
                noise_floor = 100.0
                captured_during_speech = False
                while not self._stop.is_set():
                    audio, overflowed = stream.read(FRAME_SAMPLES)
                    frame = np.asarray(audio, dtype=np.int16).reshape(-1)
                    if frame.size != FRAME_SAMPLES:
                        continue
                    if overflowed:
                        log.warning("Microphone input overflow; a small amount of audio may have been dropped")
                    now = time.monotonic()
                    rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
                    threshold = max(VOICE_RMS_THRESHOLD, min(1300.0, noise_floor * 2.8))
                    dbfs = 20.0 * math.log10(max(1.0, rms) / 32768.0)
                    level_target = max(0.0, min(100.0, (dbfs + 60.0) * (100.0 / 51.0)))
                    with self._lock:
                        smoothing = 0.42 if level_target > self._input_level else 0.20
                        self._input_level += (level_target - self._input_level) * smoothing
                        self._input_dbfs = dbfs
                        self._input_rms = rms
                        self._voice_threshold = threshold
                        self._signal_detected = rms >= threshold

                    if self._pause.is_set():
                        capturing = False
                        captured = []
                        pre_roll.clear()
                        above_threshold = 0
                        if model is not None:
                            model.reset()
                        if self._state != "paused":
                            self._set_state("paused")
                        continue
                    if self._state == "paused":
                        self._set_state("listening")

                    if not capturing:
                        pre_roll.append(frame.copy())
                        if rms < threshold * 0.75:
                            noise_floor = (noise_floor * 0.96) + (rms * 0.04)
                        if self._mode == "wake":
                            prediction = model.predict(frame) if model is not None else {}
                            score = max((float(value) for value in prediction.values()), default=0.0)
                            above_threshold = above_threshold + 1 if score >= WAKE_THRESHOLD else 0
                            if above_threshold >= WAKE_CONSECUTIVE_FRAMES:
                                capturing = True
                                captured = list(pre_roll)
                                capture_started = now
                                speech_seen = False
                                last_voice_at = now
                                captured_during_speech = False
                                above_threshold = 0
                                if model is not None:
                                    model.reset()
                                self._set_state("capturing")
                                self.emit({"type": "wake", "message": "Wake phrase detected. Listening for your request."})
                            continue

                        above_threshold = above_threshold + 1 if rms >= threshold else 0
                        if above_threshold >= VAD_START_FRAMES:
                            capturing = True
                            captured = list(pre_roll)
                            capture_started = now - (len(captured) * FRAME_SAMPLES / SAMPLE_RATE)
                            speech_seen = True
                            last_voice_at = now
                            captured_during_speech = self._speaking.is_set()
                            above_threshold = 0
                            self._set_state("capturing")
                            self.emit({"type": "speech_start", "message": "Speech detected."})
                            if captured_during_speech:
                                self._speaking.clear()
                                self.emit({"type": "barge_in", "message": "User speech detected while JARVIS was speaking."})
                        continue

                    captured.append(frame.copy())
                    if rms >= threshold:
                        speech_seen = True
                        last_voice_at = now
                    elapsed = now - capture_started
                    silence_elapsed = now - last_voice_at
                    should_finish = (
                        (speech_seen and silence_elapsed >= END_SILENCE_SECONDS)
                        or (not speech_seen and elapsed >= NO_COMMAND_TIMEOUT_SECONDS)
                        or elapsed >= MAX_COMMAND_SECONDS
                    )
                    if should_finish:
                        duration = len(captured) * FRAME_SAMPLES / SAMPLE_RATE
                        if speech_seen and duration >= MIN_SPEECH_SECONDS:
                            frames_copy = list(captured)
                            try:
                                self._audio_queue.put_nowait((frames_copy, self._mode))
                                self.emit({"type": "utterance_queued", "message": "Voice request queued for local transcription."})
                            except queue.Full:
                                self.emit({"type": "ignored_busy", "message": "The local transcription queue is full. Please wait for JARVIS to catch up."})
                        elif self._mode == "wake":
                            self.emit({"type": "empty", "message": "I heard the wake phrase, but no command followed."})
                        captured = []
                        pre_roll.clear()
                        capturing = False
                        speech_seen = False
                        above_threshold = 0
                        self._set_state("speaking" if self._speaking.is_set() else "listening")

        except Exception as exc:
            log.exception("Voice listener failed")
            self._set_state("error", f"{type(exc).__name__}: {exc}")
        finally:
            self._stop.set()
            with self._lock:
                self._input_level = 0.0
                self._signal_detected = False
                if self._state != "error":
                    self._state = "off"
                self._thread = None

    def _process_pending_commands(self, np) -> None:
        """Transcribe queued utterances sequentially while capture stays live."""
        while not self._stop.is_set():
            try:
                frames, mode = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                if not self._stop.is_set():
                    self._process_command(frames, np, mode)
            finally:
                self._audio_queue.task_done()

    def _process_command(self, frames: list, np, mode: Literal["wake", "conversation"]) -> None:
        import tempfile

        temp_dir = self.root / "cache" / "temp"
        temp_path: str | None = None
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
            audio = np.concatenate(frames).astype(np.int16, copy=False)
            self.emit({"type": "transcription_start", "message": "Transcribing locally."})
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".wav", prefix="jarvis-voice-live-", dir=temp_dir, delete=False) as temp:
                temp_path = temp.name
            with wave.open(temp_path, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes(audio.tobytes())

            result = self.transcribe(temp_path)
            if self._stop.is_set():
                return
            raw_text = result.get("text", "").strip()
            if mode == "wake":
                command = clean_after_detected_wake_phrase(raw_text)
                directed = True
            else:
                command, directed = extract_conversation_request(raw_text)

            if not directed:
                self.emit({"type": "ignored", "message": "Nearby speech was not recognized as a direct request."})
                log.debug("Ignored non-directed speech in conversation mode; transcript discarded.")
                return
            if command:
                log.info("Voice command accepted (mode=%s, language=%s)", mode, result.get("language"))
                self.emit({"type": "command", "text": command, "language": result.get("language"), "mode": mode})
            else:
                self.emit({"type": "empty", "message": "I heard you call me, but did not catch a command."})
        except Exception as exc:
            log.exception("Voice command transcription failed")
            self.emit({"type": "error", "message": f"Voice transcription failed: {type(exc).__name__}: {exc}"})
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)
            if self._thread and self._thread.is_alive() and not self._pause.is_set():
                self._set_state("speaking" if self._speaking.is_set() else "listening")

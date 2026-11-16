import tempfile
from pathlib import Path
from app.learning import detect_low_risk_preference
from app.security import safe_import_path


def test_preference_capture_is_narrow():
    assert detect_low_risk_preference("I prefer concise answers.") == "User preference/context: concise answers"
    assert detect_low_risk_preference("The sky is blue.") is None
    assert detect_low_risk_preference("My bank account is 123456") is None


def test_import_path_rejects_parent_traversal(monkeypatch):
    import app.security as sec
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        imports = root / "imports"
        imports.mkdir()
        monkeypatch.setattr(sec, "ROOT", root)
        monkeypatch.setattr(sec, "IMPORTS_DIR", imports)
        assert safe_import_path("notes.txt").parent == imports
        try:
            safe_import_path("../outside.txt")
        except ValueError:
            pass
        else:
            raise AssertionError("Parent traversal was not rejected")


def test_wake_phrase_cleaning_only_removes_leading_address():
    from app.voice_listener import clean_wake_phrase
    assert clean_wake_phrase("Hey Jarvis, what time is it?") == "what time is it?"
    assert clean_wake_phrase("JARVIS please open the dashboard") == "please open the dashboard"
    assert clean_wake_phrase("I named my AI JARVIS") == "I named my AI JARVIS"


def test_style_profile_learns_aggregate_signals_without_saving_raw_text():
    from app.learning import update_style_profile, style_prompt

    profile = None
    for sample in [
        "bro can you fix this shit, make it faster lol",
        "yeah, keep it short and just give me the commands",
        "can you explain this in Taglish naman, mabilis lang",
    ]:
        profile = update_style_profile(profile, sample)

    assert profile is not None
    assert profile["samples"] == 3
    assert profile["tone"] == "casual and direct"
    assert "Taglish" in profile["language"]
    assert "bro can you fix" not in str(profile)
    prompt = style_prompt(profile)
    assert "aggregate patterns" in prompt
    assert "raw messages are stored" in prompt


def test_style_profile_skips_sensitive_messages():
    from app.learning import update_style_profile

    assert update_style_profile(None, "My password is hunter2, talk casually") is None


def test_voice_listener_can_open_a_followup_conversation_window():
    from pathlib import Path
    from app.voice_listener import VoiceListener

    class AliveThread:
        @staticmethod
        def is_alive():
            return True

    listener = VoiceListener(Path('.'), Path('models'), lambda _path: {"text": ""})
    listener._thread = AliveThread()
    result = listener.resume(17)
    assert result["state"] == "conversation"
    assert 0 < result["conversation_followup"] <= 17


def test_detected_wake_phrase_keeps_only_the_command_after_it():
    from app.voice_listener import clean_after_detected_wake_phrase

    assert clean_after_detected_wake_phrase("I built an AI. Want to see it work? Hey Jarvis, show me the dashboard") == "show me the dashboard"
    assert clean_after_detected_wake_phrase("Hey Jarvis, what time is it?") == "what time is it?"
    # The wake detector, not this text cleaner, decides whether audio really called JARVIS.
    assert clean_after_detected_wake_phrase("I named my AI JARVIS") == "I named my AI JARVIS"


def test_style_learning_setting_persists_locally(tmp_path, monkeypatch):
    import app.database as database

    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "jarvis-test.sqlite3")
    database.init_db()
    assert database.get_setting("style_learning_enabled") == "1"
    database.set_setting("style_learning_enabled", "0")
    assert database.get_setting("style_learning_enabled") == "0"


def test_followup_intent_gate_filters_ordinary_conversation():
    from app.voice_listener import is_likely_directed_followup

    assert is_likely_directed_followup("What about the other option?")
    assert is_likely_directed_followup("Can you explain that again?")
    assert is_likely_directed_followup("And how does that work?")
    assert not is_likely_directed_followup("I built an AI and named it JARVIS")
    assert not is_likely_directed_followup("Hey friend, did you see that?")


def test_chat_stream_relays_local_ollama_deltas(monkeypatch):
    import asyncio
    import json
    import app.main as main

    class FakeResponse:
        is_error = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def aiter_lines(self):
            yield json.dumps({"message": {"content": "Hello"}, "done": False})
            yield json.dumps({"message": {"content": " there."}, "done": False})
            yield json.dumps({"done": True, "eval_count": 2})

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(main, "_build_chat_messages", lambda _request: [{"role": "system", "content": "test"}])
    async def fake_resolve_team(_client, requested_model):
        from app.model_team import ModelTeam
        return ModelTeam(primary=requested_model, reviewer=None, installed=(requested_model,))

    monkeypatch.setattr(main, "_resolve_local_model_team", fake_resolve_team)
    async def fake_unload_models():
        return []

    monkeypatch.setattr(main, "_unload_active_ollama_models", fake_unload_models)
    monkeypatch.setattr(main, "_record_completed_chat", lambda _request, _answer: False)
    monkeypatch.setattr(main, "recent_messages", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "relevant_memories", lambda *_args, **_kwargs: [])

    async def run():
        response = await main.chat_stream(main.ChatRequest(message="Say hello", model="qwen3:8b"))
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    output = asyncio.run(run())
    assert '"node": "input"' in output
    assert '"node": "memory"' in output
    assert '"node": "model"' in output
    assert '"node": "response"' in output
    assert '"text": "Hello"' in output
    assert '"text": " there."' in output
    assert '"type": "done"' in output
    assert '"answer": "Hello there."' in output


def test_style_profile_honors_explicit_style_feedback():
    from app.learning import update_style_profile

    profile = update_style_profile(None, "Stop sounding formal and talk like me. Keep it concise and be witty.")
    assert profile is not None
    assert profile["tone"] == "casual and direct"
    assert "brief" in profile["brevity"]
    assert "witty" in profile["humor"]


def test_voice_mode_prompt_is_written_for_spoken_replies(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "_style_learning_enabled", lambda: False)
    monkeypatch.setattr(main, "relevant_memories", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "recent_messages", lambda *_args, **_kwargs: [])
    messages = main._build_chat_messages(main.ChatRequest(message="Hello", voice_mode=True))
    prompt = messages[0]["content"]
    assert "Voice conversation mode" in prompt
    assert "short spoken sentences" in prompt
    assert "Avoid Markdown tables" in prompt


def test_profanity_tolerance_is_aggregated_not_toggled_by_one_clean_message():
    from app.learning import update_style_profile

    profile = update_style_profile(None, "bro this shit is wild, fix it")
    profile = update_style_profile(profile, "can you also check this for me please")
    assert profile is not None
    assert "acceptable" in profile["profanity_tolerance"]


def test_voice_mode_prompt_does_not_narrate_private_reasoning(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "_style_learning_enabled", lambda: False)
    monkeypatch.setattr(main, "relevant_memories", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "recent_messages", lambda *_args, **_kwargs: [])
    messages = main._build_chat_messages(main.ChatRequest(message="Explain this", voice_mode=True))
    prompt = messages[0]["content"]
    assert "short, natural spoken clauses" in prompt
    assert "Do not reveal private chain-of-thought" in prompt


def test_local_voice_status_endpoint_returns_wav(monkeypatch):
    import asyncio
    import app.main as main

    monkeypatch.setattr(main, "speech_status", lambda: {"available": True})
    monkeypatch.setattr(main, "_require_tool_permission", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "get_status_audio", lambda key, voice, speed: b"RIFF-test-wav")
    response = asyncio.run(main.tts_status_audio("ack", main.DEFAULT_VOICE))
    assert response.media_type == "audio/wav"
    assert response.body == b"RIFF-test-wav"


def test_conversation_mode_accepts_direct_requests_without_wake_phrase():
    from app.voice_listener import extract_conversation_request

    assert extract_conversation_request("Can you hear me?") == ("Can you hear me?", True)
    assert extract_conversation_request("What time is it?") == ("What time is it?", True)
    assert extract_conversation_request("Please explain this again") == ("Please explain this again", True)
    assert extract_conversation_request("Hey, can you check my code?") == ("Hey, can you check my code?", True)


def test_conversation_mode_ignores_ordinary_friend_conversation_and_name_mentions():
    from app.voice_listener import extract_conversation_request

    assert not extract_conversation_request("I built an AI and named it JARVIS")[1]
    assert not extract_conversation_request("Hey friend, did you see that?")[1]
    assert not extract_conversation_request("I was telling my friend about JARVIS")[1]
    assert not extract_conversation_request("The weather is nice today")[1]
    assert not extract_conversation_request("Hello")[1]


def test_conversation_mode_recognizes_explicit_call_inside_longer_utterance():
    from app.voice_listener import extract_conversation_request

    assert extract_conversation_request("I built an AI. Want to see it work? Hey Jarvis, show me the dashboard") == ("show me the dashboard", True)
    assert extract_conversation_request("Hey friend, I built an AI. Want to see it work? Hey Jarvis, show me the dashboard") == ("show me the dashboard", True)
    assert extract_conversation_request("Hey Jarvis") == ("Yes?", True)


def test_voice_transcription_queue_processes_follow_up_utterances(tmp_path):
    import threading
    import time
    from pathlib import Path

    import numpy as np
    from app.voice_listener import VoiceListener

    transcribed = []

    def fake_transcribe(path):
        transcribed.append(Path(path).read_bytes()[:4])
        return {"text": "Can you hear me?", "language": "en"}

    listener = VoiceListener(tmp_path, tmp_path / "models", fake_transcribe)
    listener._stop.clear()
    listener._audio_queue.put_nowait(([np.zeros(2560, dtype=np.int16)], "conversation"))
    listener._audio_queue.put_nowait(([np.ones(2560, dtype=np.int16)], "conversation"))
    worker = threading.Thread(target=listener._process_pending_commands, args=(np,), daemon=True)
    worker.start()

    deadline = time.monotonic() + 3
    while len(transcribed) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    listener._stop.set()
    worker.join(timeout=1)

    commands = [event for event in listener.pop_events() if event.get("type") == "command"]
    assert len(transcribed) == 2
    assert len(commands) == 2


def test_voice_listener_speaking_flag_can_be_set_and_cleared():
    from pathlib import Path
    from app.voice_listener import VoiceListener

    listener = VoiceListener(Path('.'), Path('models'), lambda _path: {"text": ""})
    assert listener.set_speaking(True)["speaking"] is True
    assert listener.set_speaking(False)["speaking"] is False


def test_voice_listener_status_exposes_live_microphone_meter():
    from pathlib import Path
    from app.voice_listener import VoiceListener

    listener = VoiceListener(Path('.'), Path('models'), lambda _path: {"text": ""})
    listener._input_level = 43.5
    listener._input_dbfs = -37.2
    listener._input_rms = 450.0
    listener._signal_detected = True
    listener._audio_queue.put_nowait(([], "conversation"))

    status = listener.status()
    assert status["input_level"] == 43.5
    assert status["input_dbfs"] == -37.2
    assert status["input_rms"] == 450.0
    assert status["input_signal"] is True
    assert status["queue_depth"] == 1
    assert 0 <= status["input_threshold_level"] <= 100


def test_answer_explanation_is_a_grounded_summary_not_hidden_chain_of_thought():
    from app.main import _build_explanation_messages

    messages = _build_explanation_messages(
        "Why is the result 42?",
        "The result is 42.",
        [{"category": "project", "content": "The input value was 6."}],
        [{"role": "user", "content": "We are discussing a local calculation."}],
    )
    system = messages[0]["content"].lower()
    payload = messages[1]["content"]
    assert "not private hidden chain-of-thought" in system
    assert "never invent web searches" in system
    assert '"recent_conversation_context"' in payload
    assert '"saved_memory_excerpts"' in payload
    assert "The input value was 6." in payload


def test_self_development_protects_protocol_and_security_files():
    from app import self_development

    for path in (
        "backend/app/main.py",
        "backend/app/security.py",
        "backend/app/config.py",
        "backend/app/self_development.py",
        "scripts/Start-JARVIS.ps1",
    ):
        try:
            self_development._project_path(path)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Protected path was accepted: {path}")


def test_self_development_rejects_path_traversal_and_non_allowlisted_files():
    from app import self_development

    for path in ("../main.py", "backend/app/../../main.py", "backend/app/main.py"):
        try:
            self_development._project_path(path)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Unsafe path was accepted: {path}")


def test_self_development_validates_python_syntax_and_rejects_shell_or_network_code():
    from app import self_development

    self_development._validate_candidate("backend/app/learning.py", "from __future__ import annotations\nimport re\n\ndef sample(value: str) -> str:\n    return re.sub('x', 'y', value)\n")
    for source in (
        "import subprocess\nsubprocess.run(['cmd.exe'])\n",
        "import httpx\n",
        "value = eval('1 + 1')\n",
        "def broken(:\n    pass\n",
    ):
        try:
            self_development._validate_candidate("backend/app/learning.py", source)
        except (ValueError, SyntaxError):
            pass
        else:
            raise AssertionError("Unsafe or invalid Python proposal was accepted")


def test_self_development_apply_requires_exact_confirmation_and_can_rollback(tmp_path, monkeypatch):
    from app import self_development

    root = tmp_path / "JARVIS"
    source = root / "frontend" / "src" / "Hologram.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export const marker = 'before';\n", encoding="utf-8")
    dev_dir = root / "data" / "self_development"
    dev_dir.mkdir(parents=True)
    monkeypatch.setattr(self_development, "ROOT", root)
    monkeypatch.setattr(self_development, "SELF_DEVELOPMENT_DIR", dev_dir)

    old = source.read_text(encoding="utf-8")
    new = "export const marker = 'after';\n"
    proposal = {
        "id": "a" * 32,
        "goal": "Change the harmless marker text",
        "summary": "Test proposal",
        "warnings": [],
        "created_at": "2026-11-03T00:00:00+00:00",
        "status": "pending",
        "changes": [{
            "path": "frontend/src/Hologram.tsx",
            "reason": "Test",
            "old_sha256": self_development._sha256(old),
            "new_sha256": self_development._sha256(new),
            "old_content": old,
            "new_content": new,
            "diff": "",
        }],
    }
    self_development.save_proposal(proposal)
    try:
        self_development.apply_proposal(proposal["id"], "yes")
    except PermissionError:
        pass
    else:
        raise AssertionError("Proposal applied without exact operator confirmation")

    applied = self_development.apply_proposal(proposal["id"], f"APPLY:{proposal['id']}")
    assert applied["status"] == "applied"
    assert source.read_text(encoding="utf-8") == new
    restored = self_development.rollback_proposal(proposal["id"], f"RESTORE:{proposal['id']}")
    assert restored["status"] == "rolled_back"
    assert source.read_text(encoding="utf-8") == old

from app.model_team import (
    add_peer_review,
    build_reviewer_messages,
    resolve_model_team,
    should_use_peer_review,
)


def test_default_team_selects_qwen35_lead_and_qwen3_reviewer():
    team = resolve_model_team([
        "qwen3.5:9b", "qwen2.5vl:7b", "qwen3:8b"
    ])
    assert team.primary == "qwen3.5:9b"
    assert team.reviewer == "qwen3:8b"
    assert "qwen2.5vl:7b" in team.installed


def test_requested_model_is_respected_and_reviewer_is_distinct():
    team = resolve_model_team(["qwen3.5:9b", "qwen3:8b"], requested_primary="qwen3:8b")
    assert team.primary == "qwen3:8b"
    assert team.reviewer == "qwen3.5:9b"


def test_vision_model_is_not_selected_for_text_chat():
    team = resolve_model_team(["qwen2.5vl:7b", "qwen3.5:9b"], requested_primary="qwen2.5vl:7b")
    assert team.primary == "qwen3.5:9b"
    assert team.reviewer is None


def test_single_text_model_falls_back_to_single_member_team():
    team = resolve_model_team(["qwen3.5:9b", "qwen2.5vl:7b"])
    assert team.primary == "qwen3.5:9b"
    assert team.reviewer is None


def test_acknowledgements_skip_review_but_real_requests_use_it():
    assert should_use_peer_review("Thanks, Jarvis!") is False
    assert should_use_peer_review("Can you explain how microservices communicate?") is True


def test_review_is_inserted_before_current_user_message():
    messages = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "earlier"},
        {"role": "assistant", "content": "prior answer"},
        {"role": "user", "content": "current task"},
    ]
    reviewer = build_reviewer_messages(messages)
    assert reviewer[-1]["role"] == "user"
    assert "current task" in reviewer[-1]["content"]
    combined = add_peer_review(messages, "Check edge cases.", "qwen3:8b")
    assert combined[-1]["content"] == "current task"
    assert combined[-2]["role"] == "system"
    assert "qwen3:8b" in combined[-2]["content"]


def test_gpu_scheduler_is_shared_by_text_vision_and_image_generation():
    import app.main as main

    assert main.LOCAL_INFERENCE_LOCK is main.IMAGE_GENERATION_LOCK
    routes = {route.path for route in main.app.routes}
    assert "/api/model-team" in routes


def test_conversation_restore_reports_missing_images_without_fetching_them(tmp_path, monkeypatch):
    import app.main as main

    available_name = f"{'a' * 32}.png"
    missing_name = f"{'b' * 32}.png"
    output_dir = tmp_path / "generated" / "images"
    output_dir.mkdir(parents=True)
    (output_dir / available_name).write_bytes(b"png placeholder")

    monkeypatch.setattr(main, "ROOT", tmp_path)
    monkeypatch.setattr(main, "IMAGE_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(main, "recent_messages", lambda *_args, **_kwargs: [
        {"role": "assistant", "content": f"[[JARVIS_IMAGE:{available_name}]]\nImage one"},
        {"role": "assistant", "content": f"[[JARVIS_IMAGE:{missing_name}]]\nImage two"},
    ])

    result = main.get_conversation("main")
    assert result["messages"][0]["image_filename"] == available_name
    assert result["messages"][0]["image_available"] is True
    assert result["messages"][1]["image_filename"] == missing_name
    assert result["messages"][1]["image_available"] is False


def test_speech_request_normalizes_browser_state_instead_of_raising_422():
    import app.main as main
    from app.speech import DEFAULT_SPEED, DEFAULT_VOICE

    request = main.SpeechRequest(text=None, voice=None, speed=8.0)
    assert request.text == ""
    assert request.voice == DEFAULT_VOICE
    assert request.speed == 1.15

    fallback = main.SpeechRequest(text=123, voice=123, speed="not-a-number")
    assert fallback.text == "123"
    assert fallback.voice == "123"
    assert fallback.speed == DEFAULT_SPEED


def test_kokoro_value_error_returns_explanatory_client_error_not_generic_422(monkeypatch):
    import asyncio
    import app.main as main
    from fastapi import HTTPException

    monkeypatch.setattr(main, "speech_status", lambda: {"available": True})
    # This test targets Kokoro's ValueError mapping; permission enforcement is
    # covered separately and should not mask the exception being asserted here.
    monkeypatch.setattr(main, "_require_tool_permission", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "synthesize_wav", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("phoneme conversion failed")))

    async def run():
        return await main.tts_synthesize(main.SpeechRequest(text="A short test sentence.", voice="am_michael", speed=1.0))

    try:
        asyncio.run(run())
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "phoneme conversion failed" in exc.detail
    else:
        raise AssertionError("A failing Kokoro engine should return an explanatory HTTP error")


def test_streamed_chat_runs_reviewer_then_lead_with_an_unload_between(monkeypatch):
    import asyncio
    import json
    import app.main as main
    from app.model_team import ModelTeam

    calls = []

    class FakeStreamResponse:
        is_error = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def aiter_lines(self):
            yield json.dumps({"message": {"content": "Final answer."}, "done": False})
            yield json.dumps({"done": True, "done_reason": "stop", "eval_count": 12})

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, _method, _url, json=None):
            calls.append(f"lead:{json['model']}")
            return FakeStreamResponse()

    async def resolve_team(_client, _requested):
        return ModelTeam(
            primary="qwen3.5:9b", reviewer="qwen3:8b",
            installed=("qwen3.5:9b", "qwen3:8b", "qwen2.5vl:7b"),
        )

    async def unload():
        calls.append("unload")
        return []

    async def review(_client, model, _messages):
        calls.append(f"review:{model}")
        return "Check the response against the request."

    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(main, "_resolve_local_model_team", resolve_team)
    monkeypatch.setattr(main, "_unload_active_ollama_models", unload)
    monkeypatch.setattr(main, "_run_model_peer_review", review)
    monkeypatch.setattr(main, "_build_chat_messages", lambda _request: [
        {"role": "system", "content": "Local assistant policy."},
        {"role": "user", "content": "Explain the architecture and compare the options."},
    ])
    monkeypatch.setattr(main, "recent_messages", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "relevant_memories", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "capture_explicit_instruction", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "_record_completed_chat", lambda *_args, **_kwargs: False)

    async def run():
        request = main.ChatRequest(message="Explain the architecture and compare the options.", model="qwen3.5:9b")
        response = await main.chat_stream(request)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    output = asyncio.run(run())
    assert calls[0] == "unload"
    assert calls[1] == "review:qwen3:8b"
    assert calls[2] == "unload"
    assert calls[3] == "lead:qwen3.5:9b"
    assert '"type": "done"' in output

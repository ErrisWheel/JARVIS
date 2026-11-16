from __future__ import annotations

import asyncio
import json
import zipfile
from io import BytesIO
from pathlib import Path


def test_task_router_separates_full_file_from_continuation_and_simple_chat():
    from app.task_router import classify_task, should_auto_continue

    simple = classify_task("Can you hear me?")
    whole = classify_task("Now send the whole JavaScript file")
    continuation = classify_task("Continue from here")

    assert simple.kind == "conversation"
    assert simple.num_predict <= 1024
    assert whole.whole_file is True
    assert whole.num_predict >= 4096
    assert whole.max_continuations >= 2
    assert continuation.continuation is True
    assert continuation.code_task is True
    assert should_auto_continue(whole, "length", 0)
    assert not should_auto_continue(whole, "stop", 0)
    research = classify_task("Research and compare the architecture of these two approaches in detail, including limitations.")
    assert research.complex is True
    assert should_auto_continue(research, "length", 0)
    assert classify_task("Finish it in one go").continuation is True


def test_continuation_directive_uses_the_saved_user_code_anchor():
    from app.task_router import continuation_directive

    directive = continuation_directive(
        "continue from here",
        {"last_user_code_anchor": 'card.className = "col-md-4 mb-4";'},
    )
    assert "CONTINUE IN PLACE" in directive
    assert 'card.className = "col-md-4 mb-4";' in directive
    assert "never repeat it" in directive


def test_whole_file_request_overrides_continuation_mode():
    from app.task_router import continuation_directive

    directive = continuation_directive("Continue, but send the whole JavaScript file")
    assert "COMPLETE FILE" in directive
    assert "CONTINUE IN PLACE" not in directive


def test_persistent_instruction_capture_and_priority(tmp_path, monkeypatch):
    import app.database as database
    import app.operator_instructions as instructions

    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "jarvis-instructions.sqlite3")
    database.init_db()
    assert instructions.capture_explicit_instruction("don't use emojis ever")['category'] == "emoji"
    assert instructions.capture_explicit_instruction("not funny")['category'] == "humor"
    prompt = instructions.instruction_prompt()
    assert "Never use emojis" in prompt
    assert "Do not make jokes" in prompt
    assert database.delete_operator_instruction("emoji") is True
    assert "Never use emojis" not in instructions.instruction_prompt()


def test_instruction_capture_does_not_store_unrelated_messages(tmp_path, monkeypatch):
    import app.database as database
    import app.operator_instructions as instructions

    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "jarvis-instructions.sqlite3")
    database.init_db()
    # Defaults are seeded once from the operator's previously supplied corrections.
    assert "Never use emojis" in instructions.instruction_prompt()
    assert instructions.capture_explicit_instruction("I saw an emoji in that message") is None
    database.delete_operator_instruction("emoji")
    database.init_db()
    # A deliberate removal is respected; defaults do not silently reappear.
    assert "Never use emojis" not in instructions.instruction_prompt()


def test_conversation_state_preserves_code_anchor_across_followups(tmp_path, monkeypatch):
    import app.database as database

    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "jarvis-state.sqlite3")
    database.init_db()
    database.update_conversation_state(
        "main", "card.className = \\\"col-md-4 mb-4\\\";", "partial response",
        last_user_code_anchor='card.className = "col-md-4 mb-4";', task_kind="coding",
    )
    database.update_conversation_state("main", "continue from here", "next lines")
    state = database.get_conversation_state("main")
    assert state["last_user_code_anchor"] == 'card.className = "col-md-4 mb-4";'
    assert state["last_user_request"] == "continue from here"
    assert state["last_assistant_tail"] == "next lines"


def test_code_export_extracts_named_files_and_refuses_path_escape(tmp_path, monkeypatch):
    import app.file_exports as exports

    root = tmp_path / "JARVIS"
    export_dir = root / "generated" / "exports"
    root.mkdir()
    monkeypatch.setattr(exports, "ROOT", root)
    monkeypatch.setattr(exports, "EXPORTS_DIR", export_dir)

    markdown = '''**index.html**\n```html\n<html></html>\n```\n\n**script.js**\n```javascript\nconsole.log("ok");\n```\n'''
    payload, filename, files = exports.build_code_export(markdown)
    assert filename.startswith("jarvis-code-")
    assert files == ["index.html", "script.js"]
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        assert archive.read("index.html").decode() == "<html></html>\n"
        assert archive.read("script.js").decode() == 'console.log("ok");\n'
        assert "README-GENERATED-BY-JARVIS.txt" in archive.namelist()

    unsafe = '''```javascript file="../../outside.js"\nalert(1);\n```'''
    _, _, unsafe_files = exports.build_code_export(unsafe)
    assert unsafe_files == ["outside.js"]
    assert not (tmp_path / "outside.js").exists()


def test_code_export_rejects_oversized_or_unclosed_blocks():
    from app.file_exports import extract_code_files

    try:
        extract_code_files("```js\n" + ("x" * 81000) + "\n```")
    except ValueError as exc:
        assert "per-file" in str(exc)
    else:
        raise AssertionError("Oversized source was accepted")
    try:
        extract_code_files("```js\nconsole.log('unfinished');")
    except ValueError as exc:
        assert "No complete" in str(exc)
    else:
        raise AssertionError("Unclosed code fence was accepted")


def test_chat_prompt_prioritizes_explicit_operator_instructions(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "_style_learning_enabled", lambda: False)
    monkeypatch.setattr(main, "relevant_memories", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "recent_messages", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "get_conversation_state", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(main, "instruction_prompt", lambda: "\\nPERSISTENT OPERATOR INSTRUCTIONS: Never use emojis.")
    prompt = main._build_chat_messages(main.ChatRequest(message="Hello"))[0]["content"]
    assert "BEHAVIORAL PRIORITY" in prompt
    assert "explicit operator instructions" in prompt.lower()
    assert "Never use emojis" in prompt


def test_streaming_chat_automatically_continues_when_ollama_reports_length(monkeypatch):
    import app.main as main

    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
            self.is_error = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def aiter_lines(self):
            yield json.dumps({"message": {"content": self.payload}, "done": False})
            if len(calls) == 1:
                yield json.dumps({"done": True, "done_reason": "length", "eval_count": 4096})
            else:
                yield json.dumps({"message": {"content": "\nrenderProducts();"}, "done": False})
                yield json.dumps({"done": True, "done_reason": "stop", "eval_count": 25})

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, _method, _url, json=None):
            calls.append(json)
            return FakeResponse("function renderProducts() {" if len(calls) == 1 else "")

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
    monkeypatch.setattr(main, "capture_explicit_instruction", lambda *_args, **_kwargs: None)

    async def run():
        request = main.ChatRequest(message="Send the complete JavaScript file", model="qwen3:8b")
        response = await main.chat_stream(request)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    output = asyncio.run(run())
    assert len(calls) == 2
    assert calls[0]["options"]["num_predict"] >= 4096
    assert "Continue exactly after the final character" in calls[1]["messages"][-1]["content"]
    assert 'function renderProducts() {' in output
    assert 'renderProducts();' in output
    assert '"incomplete": false' in output


def test_operator_defaults_are_seeded_once_and_remain_removable(tmp_path, monkeypatch):
    import app.database as database

    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "jarvis-defaults.sqlite3")
    database.init_db()
    items = {item["category"]: item["instruction"] for item in database.get_operator_instructions()}
    assert "Never use emojis" in items["emoji"]
    assert "Do not make jokes" in items["humor"]
    assert database.delete_operator_instruction("emoji") is True
    database.init_db()
    assert "emoji" not in {item["category"] for item in database.get_operator_instructions()}


def test_auto_continuation_rebases_to_compact_context_and_preserves_original_request():
    from app.main import _continuation_messages

    messages = [
        {"role": "system", "content": "system policy"},
        {"role": "user", "content": "older request 1"},
        {"role": "assistant", "content": "older answer 1"},
        {"role": "user", "content": "older request 2"},
        {"role": "assistant", "content": "older answer 2"},
        {"role": "user", "content": "older request 3"},
        {"role": "assistant", "content": "older answer 3"},
        {"role": "user", "content": "Create the complete ecommerce script with these requirements."},
    ]
    compact = _continuation_messages(messages, "const products = [", round_index=0)
    assert compact[0]["content"] == "system policy"
    assert compact[-3]["content"] == "Create the complete ecommerce script with these requirements."
    assert compact[-2] == {"role": "assistant", "content": "const products = ["}
    assert len(compact) < len(messages) + 2
    assert compact[-1]["role"] == "user"


def test_short_code_revision_inherits_active_coding_task():
    from app.task_router import classify_task, continuation_directive

    state = {"task_kind": "coding", "last_assistant_tail": "addButton.onclick = () => addToCart(product);"}
    profile = classify_task("Use addEventListener instead.", state)
    assert profile.code_task is True
    assert profile.continuation is True
    directive = continuation_directive("Use addEventListener instead.", state)
    assert "CONTINUE IN PLACE" in directive
    assert "addButton.onclick" in directive


def test_unrelated_question_does_not_inherit_active_code_task():
    from app.task_router import classify_task

    state = {"task_kind": "coding", "last_assistant_tail": "const total = 0;"}
    profile = classify_task("Can you hear me?", state)
    assert profile.kind == "conversation"
    assert profile.code_task is False
    assert profile.continuation is False

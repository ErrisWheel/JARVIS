from __future__ import annotations

import json
from pathlib import Path

import pytest


def _init_isolated_store(tmp_path, monkeypatch):
    import app.database as database
    import app.platform_store as store

    db_path = tmp_path / "jarvis.sqlite3"
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", db_path)
    monkeypatch.setattr(store, "ROOT", tmp_path)
    database.init_db()
    store.init_platform_store()
    return database, store


def test_semantic_memory_links_are_persisted_and_return_graph(tmp_path, monkeypatch):
    database, store = _init_isolated_store(tmp_path, monkeypatch)
    first = database.create_memory("JARVIS is a local-first assistant", "project", "user-confirmed", "offline")
    second = database.create_memory("The assistant uses local models without cloud calls", "project", "user-confirmed", "local inference")
    store.memory_vector_upsert(first, "test-embed", [1.0, 0.0, 0.0])
    store.memory_vector_upsert(second, "test-embed", [0.98, 0.02, 0.0])
    assert store.replace_memory_links("test-embed", [(first, second, 0.995)]) == 1
    graph = store.list_memory_graph("test-embed")
    assert {node["id"] for node in graph["nodes"]} == {first, second}
    assert graph["edges"] == [{"source": first, "target": second, "similarity": 0.995}]


def test_memory_mutation_cleans_stale_semantic_relationships(tmp_path, monkeypatch):
    database, store = _init_isolated_store(tmp_path, monkeypatch)
    first = database.create_memory("old local assistant fact", "project", "user-confirmed")
    second = database.create_memory("related local assistant fact", "project", "user-confirmed")
    store.memory_vector_upsert(first, "test-embed", [1.0, 0.0])
    store.memory_vector_upsert(second, "test-embed", [0.99, 0.01])
    store.replace_memory_links("test-embed", [(first, second, 0.999)])
    assert database.update_memory(first, "edited memory content", "project", "edited")
    assert store.list_memory_graph("test-embed")["edges"] == []
    store.memory_vector_upsert(first, "test-embed", [1.0, 0.0])
    store.replace_memory_links("test-embed", [(first, second, 0.999)])
    assert database.delete_memory(second)
    graph = store.list_memory_graph("test-embed")
    assert len(graph["nodes"]) == 1
    assert graph["edges"] == []


def test_local_skill_manifests_are_read_as_data_not_executed(tmp_path, monkeypatch):
    _, store = _init_isolated_store(tmp_path, monkeypatch)
    skill_dir = tmp_path / "skills" / "safe-skill"
    skill_dir.mkdir(parents=True)
    marker = tmp_path / "SHOULD_NOT_EXIST.txt"
    (skill_dir / "manifest.json").write_text(json.dumps({
        "id": "safe-skill", "name": "Safe Skill", "description": "Uses safe local capabilities.",
        "capabilities": ["local_chat", "memory_search", "shell_execution"],
        "prompt_template": "Review supplied text only."
    }), encoding="utf-8")
    (skill_dir / "execute.py").write_text(f"from pathlib import Path; Path({str(marker)!r}).write_text('bad')", encoding="utf-8")
    items = store.list_skill_manifests()
    assert len(items) == 1
    assert items[0]["id"] == "safe-skill"
    assert items[0]["capabilities"] == ["local_chat", "memory_search"]
    assert not marker.exists()


def test_workspace_archive_state_does_not_delete_conversations(tmp_path, monkeypatch):
    database, store = _init_isolated_store(tmp_path, monkeypatch)
    workspace = store.create_workspace("Programming")
    conversation = store.create_conversation(workspace["id"], "Build a local tool")
    assert store.update_workspace(workspace["id"], archived=True)
    assert store.get_conversation_meta(conversation["conversation_id"])["workspace_id"] == workspace["id"]
    assert store.get_workspace(workspace["id"])["archived"] == 1
    assert store.update_workspace(workspace["id"], archived=False)


def test_permission_helper_fails_closed_for_missing_or_disabled_capability(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.platform_store, "list_permissions", lambda: [{"capability": "memory_search", "enabled": 0}])
    assert main._tool_permission_enabled("memory_search") is False
    with pytest.raises(main.HTTPException) as error:
        main._require_tool_permission("memory_search")
    assert error.value.status_code == 403
    monkeypatch.setattr(main.platform_store, "list_permissions", lambda: [{"capability": "memory_search", "enabled": 1}])
    assert main._tool_permission_enabled("memory_search") is True


def test_memory_retrieval_and_graph_are_scoped_to_the_conversation_workspace(tmp_path, monkeypatch):
    database, store = _init_isolated_store(tmp_path, monkeypatch)
    research = store.create_workspace("Research")
    conversation = store.create_conversation(research["id"], "Research chat")
    personal_memory = database.create_memory("The project uses a local offline database", "personal", "user-confirmed", "offline", "default")
    research_memory = database.create_memory("Research notes mention a local offline database", "research", "user-confirmed", "offline", research["id"])

    assert [item["id"] for item in database.relevant_memories("offline database", workspace_id="default")] == [personal_memory]
    assert [item["id"] for item in database.relevant_memories("offline database", workspace_id=research["id"])] == [research_memory]
    assert store.conversation_workspace_id(conversation["conversation_id"]) == research["id"]
    assert database.memory_count(research["id"]) == 1


def test_archived_workspace_memories_remain_readable_but_new_conversations_are_blocked(tmp_path, monkeypatch):
    database, store = _init_isolated_store(tmp_path, monkeypatch)
    workspace = store.create_workspace("Archived Project")
    conversation = store.create_conversation(workspace["id"], "Old project chat")
    memory_id = database.create_memory("Keep this historical workspace note", "project", "user-confirmed", "history", workspace["id"])
    assert store.update_workspace(workspace["id"], archived=True)
    assert store.conversation_workspace_id(conversation["conversation_id"]) == workspace["id"]
    assert database.relevant_memories("historical workspace note", workspace_id=store.conversation_workspace_id(conversation["conversation_id"]))[0]["id"] == memory_id
    with pytest.raises(ValueError):
        store.create_conversation(workspace["id"], "Should not create")

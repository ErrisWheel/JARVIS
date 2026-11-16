from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_memory_fts_index_tracks_insert_update_and_delete(tmp_path, monkeypatch):
    import app.database as database
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "memory.sqlite3")
    database.init_db()
    memory_id = database.create_memory("JARVIS uses local GPU scheduling", "project", "user-confirmed", "RTX offline")
    assert database.relevant_memories("local GPU scheduling", 5)[0]["id"] == memory_id
    assert database.update_memory(memory_id, "JARVIS uses local full text retrieval", "project", "SQLite FTS5")
    updated = database.relevant_memories("SQLite full text", 5)
    assert updated and updated[0]["id"] == memory_id
    assert database.delete_memory(memory_id)
    assert database.relevant_memories("SQLite full text", 5) == []


def test_resource_policy_adapts_to_games_and_low_vram(monkeypatch):
    import app.monitor as monitor
    monkeypatch.setattr(monitor, "detect_game_process", lambda: {"detected": True, "processes": ["valorant-win64-shipping.exe"]})
    normal_memory = SimpleNamespace(available=12 * 1024 ** 3)
    gaming = monitor.resource_policy({"available": True, "vram_total_mb": 16384, "vram_used_mb": 7000, "temperature_c": 65}, normal_memory)
    assert gaming["mode"] == "gaming"
    assert gaming["keep_alive"] == "0s"
    assert gaming["allow_prewarm"] is False
    assert gaming["cpu_only"] is True
    assert gaming["inference_device"] == "cpu"
    monkeypatch.setattr(monitor, "detect_game_process", lambda: {"detected": False, "processes": []})
    constrained = monitor.resource_policy({"available": True, "vram_total_mb": 16384, "vram_used_mb": 15000, "temperature_c": 88}, normal_memory)
    assert constrained["mode"] == "conserve"
    assert constrained["keep_alive"] == "0s"
    assert constrained["cpu_only"] is True


def test_voice_gate_rejects_low_level_echo_during_tts():
    from app.voice_listener import adaptive_voice_gate
    idle_threshold, idle_frames = adaptive_voice_gate(140.0, False)
    speaking_threshold, speaking_frames = adaptive_voice_gate(140.0, True)
    assert speaking_threshold > idle_threshold
    assert speaking_frames == idle_frames + 1


def test_safe_import_path_rejects_symlink_escape(tmp_path, monkeypatch):
    import app.security as security
    root = tmp_path / "project"
    imports = root / "imports"
    outside = tmp_path / "outside"
    imports.mkdir(parents=True)
    outside.mkdir()
    target = outside / "secret.txt"
    target.write_text("not allowed", encoding="utf-8")
    link = imports / "shortcut.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not available in this environment")
    monkeypatch.setattr(security, "ROOT", root)
    monkeypatch.setattr(security, "IMPORTS_DIR", imports)
    with pytest.raises(ValueError, match="Symbolic links"):
        security.safe_import_path("shortcut.txt")


def test_resource_policy_does_not_force_cpu_when_host_ram_is_low(monkeypatch):
    import app.monitor as monitor
    monkeypatch.setattr(monitor, "detect_game_process", lambda: {"detected": True, "processes": ["valorant.exe"]})
    low_memory = SimpleNamespace(available=5 * 1024 ** 3)
    policy = monitor.resource_policy(
        {"available": True, "vram_total_mb": 16384, "vram_used_mb": 7000, "temperature_c": 65},
        low_memory,
    )
    assert policy["mode"] == "gaming"
    assert policy["cpu_only"] is False
    assert policy["inference_device"] == "ollama-auto"
    assert "RAM is too low" in policy["reason"]


def test_ollama_model_options_force_cpu_only_when_policy_requires_it(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "resource_policy", lambda: {"cpu_only": True})
    assert main._model_options({"num_ctx": 4096, "temperature": 0.2}) == {
        "num_ctx": 4096, "temperature": 0.2, "num_gpu": 0,
    }


def test_ollama_model_options_keep_automatic_placement_in_normal_mode(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "resource_policy", lambda: {"cpu_only": False})
    assert main._model_options({"num_ctx": 4096}) == {"num_ctx": 4096}


def test_sdxl_image_generation_is_paused_during_gaming_but_poster_rendering_is_not(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "resource_policy", lambda: {"gaming_detected": True})
    with pytest.raises(main.HTTPException) as error:
        main._require_image_generation_capacity(False)
    assert error.value.status_code == 409
    main._require_image_generation_capacity(True)


def test_link_or_junction_detector_handles_missing_junction_api(tmp_path):
    import app.security as security
    plain = tmp_path / "plain"
    plain.mkdir()
    assert security._is_link_or_junction(plain) is False
    assert security._is_link_or_junction(tmp_path / "missing") is False

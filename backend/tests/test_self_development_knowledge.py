from pathlib import Path
import pytest

from app import self_development


def test_operator_coding_knowledge_is_saved_and_used_as_context(tmp_path, monkeypatch):
    root = tmp_path / "JARVIS"
    root.mkdir()
    store = root / "data" / "self_development"
    monkeypatch.setattr(self_development, "ROOT", root)
    monkeypatch.setattr(self_development, "SELF_DEVELOPMENT_DIR", store)
    monkeypatch.setattr(self_development, "KNOWLEDGE_FILE", store / "coding_knowledge.json")

    first = self_development.add_coding_knowledge(
        "Keep UI components small, use strict TypeScript types, and preserve existing workflows.",
        "project convention",
    )
    assert first["source"] == "operator-approved"
    assert len(self_development.list_coding_knowledge()) == 1
    context = self_development.coding_knowledge_context()
    assert context[0]["category"] == "project convention"
    assert "preserve existing workflows" in context[0]["content"]
    assert self_development.delete_coding_knowledge(first["id"]) is True
    assert self_development.list_coding_knowledge() == []


def test_coding_knowledge_rejects_secrets_and_duplicate_lessons(tmp_path, monkeypatch):
    root = tmp_path / "JARVIS"
    root.mkdir()
    store = root / "data" / "self_development"
    monkeypatch.setattr(self_development, "ROOT", root)
    monkeypatch.setattr(self_development, "SELF_DEVELOPMENT_DIR", store)
    monkeypatch.setattr(self_development, "KNOWLEDGE_FILE", store / "coding_knowledge.json")

    lesson = "Use typed interfaces and avoid introducing runtime dependencies."
    self_development.add_coding_knowledge(lesson)
    with pytest.raises(ValueError, match="already saved"):
        self_development.add_coding_knowledge(lesson)
    with pytest.raises(ValueError, match="credential"):
        self_development.add_coding_knowledge("Never hardcode api_key=super-secret-value in code")


def test_python_self_development_rejects_builtin_file_and_runtime_escape_paths():
    for source in (
        "def bad():\n    return open('C:/secrets.txt').read()\n",
        "def bad():\n    return globals()\n",
        "def bad(value):\n    return value.__class__\n",
        "def bad():\n    return eval('1+1')\n",
    ):
        with pytest.raises(ValueError):
            self_development._validate_candidate("backend/app/learning.py", source)


def test_image_intent_is_a_pure_allowlisted_file():
    assert "frontend/src/imageIntent.ts" in self_development.EDITABLE_FILES
    source = Path(__file__).resolve().parents[2] / "frontend" / "src" / "imageIntent.ts"
    self_development._validate_candidate("frontend/src/imageIntent.ts", source.read_text(encoding="utf-8"))


def test_self_development_cannot_target_main_ui_or_protocol_files():
    for path in (
        "backend/app/main.py",
        "backend/app/security.py",
        "backend/app/self_development.py",
        "backend/app/imagegen_worker.py",
        "frontend/src/App.tsx",
        "frontend/src/DevelopmentLab.tsx",
        "frontend/src/api.ts",
        "scripts/Install-Image-Generation.ps1",
    ):
        with pytest.raises(ValueError):
            self_development._project_path(path)

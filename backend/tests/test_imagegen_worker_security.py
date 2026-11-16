from pathlib import Path

from app import imagegen_worker


def test_image_worker_rejects_symlink_request_file(tmp_path, monkeypatch, capsys):
    root = tmp_path / "JARVIS"
    request_dir = root / "cache" / "imagegen"
    request_dir.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    link = request_dir / "request.json"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        return

    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setattr("sys.argv", ["imagegen_worker.py", str(link)])
    assert imagegen_worker.main() == 2
    assert "regular request file" in capsys.readouterr().err


def test_image_worker_rejects_request_outside_project_cache(tmp_path, monkeypatch, capsys):
    root = tmp_path / "JARVIS"
    (root / "cache" / "imagegen").mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setattr("sys.argv", ["imagegen_worker.py", str(outside)])
    assert imagegen_worker.main() == 2
    assert "outside the JARVIS image-generation cache" in capsys.readouterr().err

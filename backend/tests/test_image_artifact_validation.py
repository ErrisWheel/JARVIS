from __future__ import annotations

import asyncio
import importlib.util
import json
import shutil
import struct
import sys
import zlib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app import main
from app.poster_reference import build_element_discovery_poster


WORKER_SOURCE = Path(__file__).resolve().parents[1] / "app" / "imagegen_worker.py"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _write_test_png(path: Path, *, width: int = 64, height: int = 64, padded: bool = False) -> None:
    """Create a valid RGB PNG without requiring Pillow in the backend test env."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = b"\x00" + bytes((8, 18, 30)) * width  # PNG filter byte + RGB pixels
    raw_pixels = row * height
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunks = [
        _png_chunk(b"IHDR", header),
        _png_chunk(b"IDAT", zlib.compress(raw_pixels, level=6)),
    ]
    # A harmless text metadata chunk makes this fixture exceed the backend's
    # 2 KB artifact-size threshold while remaining a valid PNG.
    if padded:
        chunks.append(_png_chunk(b"tEXt", b"Comment\x00" + b"fixture-padding-" * 256))
    chunks.append(_png_chunk(b"IEND", b""))
    path.write_bytes(PNG_SIGNATURE + b"".join(chunks))


def test_svg_validator_parses_text_after_large_artistic_decoration_prefix(tmp_path):
    """Decorative SVG artwork may precede text by more than the old 2 KB limit."""
    svg = tmp_path / "high-density-poster.svg"
    ornaments = "".join(
        f'<circle cx="{index + 10}" cy="40" r="4" fill="none" stroke="#6cc"/>'
        f'<path d="M{index} 10l5 5" stroke="#e98"/>'
        for index in range(180)
    )
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="2048">'
        f'{ornaments}<text x="80" y="100">Poster title</text>'
        '</svg>',
        encoding="utf-8",
    )
    assert svg.read_text(encoding="utf-8").find("<text") > 2048
    assert main._validate_generated_svg(svg) == (True, "SVG XML, text and artwork verified")


def test_svg_validator_rejects_malformed_or_textless_files(tmp_path):
    malformed = tmp_path / "malformed.svg"
    malformed.write_text("<svg><path></svg>" + (" " * 1200), encoding="utf-8")
    ok, message = main._validate_generated_svg(malformed)
    assert not ok
    assert "SVG validation failed" in message

    textless = tmp_path / "textless.svg"
    textless.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<circle cx="5" cy="5" r="4"/>'
        '</svg>' + (' ' * 1200),
        encoding="utf-8",
    )
    ok, message = main._validate_generated_svg(textless)
    assert not ok
    assert "no editable text" in message


def test_png_validator_checks_signature_and_file_size(tmp_path):
    png = tmp_path / "valid.png"
    _write_test_png(png, padded=True)
    ok, message = main._validate_generated_png(png)
    assert ok
    assert message == "PNG artifact verified"

    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(b"not a png" * 400)
    ok, message = main._validate_generated_png(invalid)
    assert not ok
    assert "signature is invalid" in message


def test_refine_stream_accepts_high_density_artsy_poster_and_returns_saved_files(tmp_path, monkeypatch):
    """Exercise the real imagegen-environment subprocess and artifact hand-off."""
    worker_python = main.IMAGEGEN_PYTHON
    if not worker_python.is_file():
        # Developer/CI fallback: run the renderer in the current interpreter
        # only when Pillow is present. Production uses the isolated imagegen env.
        if importlib.util.find_spec("PIL") is None:
            pytest.skip("The isolated JARVIS image-generation Python environment is not installed")
        worker_python = Path(sys.executable)

    root = tmp_path / "JARVIS"
    image_dir = root / "generated" / "images"
    image_dir.mkdir(parents=True)
    request_dir = root / "cache" / "imagegen"
    request_dir.mkdir(parents=True)
    worker_target = root / "backend" / "app" / "imagegen_worker.py"
    worker_target.parent.mkdir(parents=True)
    shutil.copy2(WORKER_SOURCE, worker_target)

    previous_name = "0123456789abcdef0123456789abcdef.png"
    _write_test_png(image_dir / previous_name, width=96, height=96)
    source_prompt = (
        "Create a detailed educational timeline about the discovery of these elements: "
        "Md, F, Cl, Br, I, At, Ts, Yb, No and He, including discoverers, institutions and science visuals."
    )
    original_data = build_element_discovery_poster(source_prompt)
    assert original_data is not None
    original_data.update({
        "design_variant": "timeline",
        "visual_style": "default",
        "visual_density": "normal",
        "design_seed": 123,
        "design_notes": "",
    })

    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "IMAGE_OUTPUT_DIR", image_dir)
    monkeypatch.setattr(main, "IMAGEGEN_PYTHON", worker_python)
    monkeypatch.setattr(main, "IMAGE_GENERATION_LOCK", asyncio.Lock())
    monkeypatch.setattr(main, "add_message", lambda *args, **kwargs: None)
    main._save_poster_manifest(previous_name, original_data, source_prompt)

    request = main.ImageGenerateRequest(
        prompt="REFINE EXISTING POSTER: put artsy designs on blank parts.",
        conversation_id="main",
        poster=True,
        design_variant="timeline",
        poster_operation="refine",
        previous_poster_filename=previous_name,
        poster_source_prompt=source_prompt,
        poster_design_notes="put artsy designs on blank parts",
        poster_visual_style="artsy",
        poster_visual_density="high",
        design_seed=20261110,
    )

    async def collect_events():
        events = []
        async for line in main._image_generation_stream(request):
            events.append(json.loads(line))
        return events

    events = asyncio.run(collect_events())
    complete = next((event for event in events if event.get("type") == "complete"), None)
    error = next((event for event in events if event.get("type") == "error"), None)
    assert error is None, error
    assert complete is not None

    new_png = image_dir / complete["filename"]
    new_svg = image_dir / complete["svg_filename"]
    assert new_png.is_file() and new_png.stat().st_size > 2048
    assert new_svg.is_file() and new_svg.stat().st_size > 2048
    assert main._validate_generated_png(new_png)[0]
    assert main._validate_generated_svg(new_svg)[0]
    # The artsy SVG has enough edge ornamentation to move the first text node
    # beyond the old validator's 2 KB inspection window.
    assert new_svg.read_text(encoding="utf-8").find("<text") > 2048
    ET.parse(new_svg)

def test_generated_svg_endpoint_accepts_text_after_large_artwork_prefix(tmp_path, monkeypatch):
    """The public download route must use the same full-document validator as generation."""
    filename = "a" * 32 + ".svg"
    ornaments = "".join(
        f'<circle cx="{index + 10}" cy="40" r="4" fill="none" stroke="#6cc"/>'
        f'<path d="M{index} 10l5 5" stroke="#e98"/>'
        for index in range(180)
    )
    target = tmp_path / filename
    target.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="2048" '
        'viewBox="0 0 1536 2048">'
        f'{ornaments}<text x="80" y="100">Poster title</text><rect x="5" y="5" width="4" height="4"/>'
        '</svg>',
        encoding="utf-8",
    )
    assert target.read_text(encoding="utf-8").find("<text") > 2048
    monkeypatch.setattr(main, "_ensure_safe_image_directory", lambda _path: tmp_path)

    response = main.get_generated_svg(filename)

    assert Path(response.path) == target
    assert response.media_type == "image/svg+xml"


def test_legacy_image_endpoint_returns_the_requested_nonposter_dimensions(tmp_path, monkeypatch):
    """The retained non-stream endpoint must report the canvas it actually rendered."""
    project_root = tmp_path / "JARVIS"
    project_root.mkdir()
    image_dir = project_root / "generated" / "images"
    image_python = tmp_path / "python.exe"
    image_python.write_bytes(b"test")
    model_dir = project_root / "ai" / "models" / "sdxl"
    model_dir.mkdir(parents=True)
    (model_dir / "model_index.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(main, "ROOT", project_root)
    monkeypatch.setattr(main, "IMAGE_OUTPUT_DIR", image_dir)
    monkeypatch.setattr(main, "IMAGEGEN_PYTHON", image_python)
    monkeypatch.setattr(main, "IMAGE_MODEL_DIR", model_dir)
    monkeypatch.setattr(main, "IMAGE_GENERATION_LOCK", asyncio.Lock())
    monkeypatch.setattr(main, "add_message", lambda *_args, **_kwargs: None)

    async def no_unload():
        return []

    def fake_worker(request_file: Path):
        payload = json.loads(request_file.read_text(encoding="utf-8"))
        _write_test_png(
            image_dir / payload["filename"],
            width=payload["width"],
            height=payload["height"],
            padded=True,
        )
        return 0, "", ""

    monkeypatch.setattr(main, "_unload_active_ollama_models", no_unload)
    monkeypatch.setattr(main, "_run_image_worker", fake_worker)

    request = main.ImageGenerateRequest(
        prompt="A detailed landscape mountain scene",
        conversation_id="test",
        width=768,
        height=576,
        poster=False,
    )
    result = asyncio.run(main.generate_local_image(request))

    assert result["width"] == 768
    assert result["height"] == 576


def test_generic_diagram_request_is_coerced_to_sdxl_even_from_stale_frontend():
    request = main.ImageGenerateRequest(
        prompt=(
            "Create a polished, detailed vertical portrait educational diagram from the supplied material. "
            "Source material to represent:\nExplicit poster subject from the operator: wayang kulit puppet"
        ),
        conversation_id="test-diagram-routing",
        width=1536,
        height=2048,
        poster=True,
    )

    changed = main._normalize_image_request_mode(request)

    assert changed is True
    assert request.poster is False
    assert request.prompt == "wayang kulit puppet"
    assert (request.width, request.height) == (768, 1024)
    assert request.poster_source_prompt is None
    assert request.previous_poster_filename is None


def test_explicit_educational_poster_request_keeps_typography_renderer():
    request = main.ImageGenerateRequest(
        prompt="Create a polished educational poster with a labeled diagram of wayang kulit puppet.",
        conversation_id="test-poster-routing",
        width=1536,
        height=2048,
        poster=True,
    )

    changed = main._normalize_image_request_mode(request)

    assert changed is False
    assert request.poster is True
    assert (request.width, request.height) == (1536, 2048)


def test_fastapi_version_matches_frontend_release_version():
    package = json.loads((main.ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert main.app.version == package["version"] == "0.1.43"


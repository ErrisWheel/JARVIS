from __future__ import annotations

import asyncio
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from app import main
from app.poster_reference import build_element_discovery_poster


WORKER_SOURCE = Path(__file__).resolve().parents[1] / "app" / "imagegen_worker.py"


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
    Image.effect_noise((512, 512), 100).convert("RGB").save(png)
    ok, message = main._validate_generated_png(png)
    assert ok
    assert message == "PNG artifact verified"

    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(b"not a png" * 400)
    ok, message = main._validate_generated_png(invalid)
    assert not ok
    assert "signature is invalid" in message


def test_refine_stream_accepts_high_density_artsy_poster_and_returns_saved_files(tmp_path, monkeypatch):
    """Exercise the real subprocess stream and the SVG validation hand-off."""
    root = tmp_path / "JARVIS"
    image_dir = root / "generated" / "images"
    image_dir.mkdir(parents=True)
    request_dir = root / "cache" / "imagegen"
    request_dir.mkdir(parents=True)
    worker_target = root / "backend" / "app" / "imagegen_worker.py"
    worker_target.parent.mkdir(parents=True)
    shutil.copy2(WORKER_SOURCE, worker_target)

    previous_name = "0123456789abcdef0123456789abcdef.png"
    Image.new("RGB", (1536, 2048), (8, 18, 30)).save(image_dir / previous_name)
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
    monkeypatch.setattr(main, "IMAGEGEN_PYTHON", Path(sys.executable))
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

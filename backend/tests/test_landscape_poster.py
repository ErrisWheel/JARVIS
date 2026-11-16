from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")

from app import imagegen_worker, main
from app.poster_reference import build_element_discovery_poster


BRIEF = (
    "Create an educational chronological timeline of the elements: "
    "Md (Mendelevium), F (Fluorine), Cl (Chlorine), Br (Bromine), "
    "I (Iodine), At (Astatine), Ts (Tennessine), Yb (Ytterbium), "
    "No (Nobelium), and He (Helium). Include discovery history and institutions."
)


def _poster_data(orientation: str) -> dict:
    data = build_element_discovery_poster(BRIEF)
    assert data is not None
    data.update({
        "orientation": orientation,
        "design_variant": "museum",
        "visual_style": "museum",
        "visual_density": "rich",
        "design_seed": 72631,
    })
    return data


def test_landscape_poster_png_and_svg_are_true_16_by_9(tmp_path: Path):
    png = tmp_path / "poster.png"
    svg = tmp_path / "poster.svg"
    data = _poster_data("landscape")

    size = imagegen_worker._render_educational_poster(data, png)
    imagegen_worker._write_educational_poster_svg(data, svg)

    assert size == (1920, 1080)
    assert main._validate_generated_png(png, (1920, 1080)) == (True, "PNG artifact verified (1920x1080)")
    valid_svg, detail = main._validate_generated_svg(svg, (1920, 1080))
    assert valid_svg, detail
    root = ET.parse(svg).getroot()
    assert root.attrib["viewBox"] == "0 0 1920 1080"
    assert png.stat().st_size > 2_048
    assert svg.stat().st_size > 1_024


def test_portrait_poster_remains_portrait(tmp_path: Path):
    png = tmp_path / "poster-portrait.png"
    svg = tmp_path / "poster-portrait.svg"
    data = _poster_data("portrait")

    size = imagegen_worker._render_educational_poster(data, png)
    imagegen_worker._write_educational_poster_svg(data, svg)

    assert size == (1536, 2048)
    assert main._validate_generated_png(png, (1536, 2048))[0]
    assert main._validate_generated_svg(svg, (1536, 2048))[0]


def test_canvas_validation_rejects_wrong_orientation(tmp_path: Path):
    png = tmp_path / "portrait.png"
    svg = tmp_path / "portrait.svg"
    data = _poster_data("portrait")
    imagegen_worker._render_educational_poster(data, png)
    imagegen_worker._write_educational_poster_svg(data, svg)

    valid_png, png_error = main._validate_generated_png(png, (1920, 1080))
    valid_svg, svg_error = main._validate_generated_svg(svg, (1920, 1080))
    assert not valid_png and "canvas mismatch" in png_error
    assert not valid_svg and "canvas mismatch" in svg_error


def test_landscape_request_schema_accepts_exact_wide_canvas():
    request = main.ImageGenerateRequest(
        prompt="Create a wide educational poster about discoveries.",
        poster=True,
        orientation="landscape",
        width=1920,
        height=1080,
    )
    assert request.orientation == "landscape"
    assert (request.width, request.height) == (1920, 1080)


def test_expected_canvas_uses_declared_poster_orientation_even_for_legacy_defaults():
    landscape = main.ImageGenerateRequest(
        prompt="Create a wide science poster.", poster=True, orientation="landscape",
    )
    portrait = main.ImageGenerateRequest(
        prompt="Create a portrait science poster.", poster=True, orientation="portrait",
    )
    ordinary_wide = main.ImageGenerateRequest(
        prompt="A realistic robot in a city.", width=1024, height=576, orientation="landscape",
    )
    assert main._expected_generated_image_size(landscape) == (1920, 1080)
    assert main._expected_generated_image_size(portrait) == (1536, 2048)
    assert main._expected_generated_image_size(ordinary_wide) == (1024, 576)


def test_worker_cli_saves_landscape_png_and_svg_without_loading_sdxl(tmp_path: Path, monkeypatch):
    """The real worker entry point must honor poster orientation without GPU inference."""
    import json
    import os
    import shutil
    import subprocess
    import sys
    import uuid

    root = tmp_path / "JARVIS"
    request_dir = root / "cache" / "imagegen"
    request_dir.mkdir(parents=True)
    worker_target = root / "backend" / "app" / "imagegen_worker.py"
    worker_target.parent.mkdir(parents=True)
    shutil.copy2(Path(imagegen_worker.__file__), worker_target)

    filename = f"{uuid.uuid4().hex}.png"
    data = _poster_data("landscape")
    request_path = request_dir / f"{uuid.uuid4().hex}.json"
    request_path.write_text(json.dumps({
        "prompt": BRIEF,
        "filename": filename,
        "width": 1920,
        "height": 1080,
        "steps": 25,
        "seed": 42,
        "poster": True,
        "orientation": "landscape",
        "poster_data": data,
    }), encoding="utf-8")

    env = os.environ.copy()
    env["JARVIS_ROOT"] = str(root)
    completed = subprocess.run(
        [sys.executable, str(worker_target), str(request_path)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    saved_events = [
        json.loads(line) for line in completed.stdout.splitlines()
        if line.strip().startswith("{") and json.loads(line).get("type") == "saved"
    ]
    assert saved_events, completed.stdout
    assert saved_events[-1]["width"] == 1920
    assert saved_events[-1]["height"] == 1080
    png = root / "generated" / "images" / filename
    svg = png.with_suffix(".svg")
    assert main._validate_generated_png(png, (1920, 1080))[0]
    assert main._validate_generated_svg(svg, (1920, 1080))[0]

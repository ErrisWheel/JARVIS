import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


WORKER = Path(__file__).resolve().parents[1] / "app" / "imagegen_worker.py"


def _sample_poster_data():
    return {
        "title": "A SAMPLE SCIENCE POSTER",
        "subtitle": "Ten short entries with actual text rendering",
        "items": [
            {"label": f"E{i}", "title": f"Example item {i}", "date": f"Year {1900 + i}",
             "detail": "A factual sentence is laid out with a normal font, not drawn by a diffusion model."}
            for i in range(1, 11)
        ],
        "footer": "Test fixture only.",
    }


def test_poster_renderer_writes_print_sized_png(tmp_path):
    pytest.importorskip("PIL")
    spec = importlib.util.spec_from_file_location("jarvis_imagegen_worker", WORKER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    output = tmp_path / "poster.png"
    width, height = module._render_educational_poster(_sample_poster_data(), output)

    from PIL import Image
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.size == (1536, 2048)
        assert (width, height) == image.size
    assert output.stat().st_size > 10_000


def test_worker_poster_mode_does_not_require_sdxl_model_or_cuda(tmp_path):
    pytest.importorskip("PIL")
    root = tmp_path / "jarvis-root"
    request_dir = root / "cache" / "imagegen"
    request_dir.mkdir(parents=True)
    request_file = request_dir / "poster-request.json"
    output_name = "0123456789abcdef0123456789abcdef.png"
    payload = {
        "prompt": "Create a readable educational poster from the supplied sample facts.",
        "filename": output_name,
        "width": 768,
        "height": 1024,
        "steps": 25,
        "seed": -1,
        "poster": True,
        "poster_data": _sample_poster_data(),
    }
    request_file.write_text(json.dumps(payload), encoding="utf-8")
    env = os.environ.copy()
    env["JARVIS_ROOT"] = str(root)

    completed = subprocess.run(
        [sys.executable, str(WORKER), str(request_file)],
        capture_output=True, text=True, env=env, check=False, timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    events = [json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")]
    saved = next(event for event in events if event.get("type") == "saved")
    assert saved["renderer"] == "typographic_poster"
    assert saved["width"] == 1536
    assert saved["height"] == 2048
    png_path = root / "generated" / "images" / output_name
    svg_path = png_path.with_suffix(".svg")
    assert png_path.is_file()
    assert svg_path.is_file()
    svg_text = svg_path.read_text(encoding="utf-8")
    assert "<svg" in svg_text and "<text" in svg_text and "<path" in svg_text
    # The temporary project deliberately has no ai/models/sdxl-base-1.0 folder.
    assert not (root / "ai" / "models" / "sdxl-base-1.0").exists()


def test_chronological_poster_entries_sort_by_explicit_year_only():
    from app.main import _sort_poster_data_for_chronology

    data = {"items": [
        {"title": "Later", "date": "1886"},
        {"title": "Earlier", "date": "1774"},
        {"title": "Unknown", "date": "date not stated"},
    ]}

    result = _sort_poster_data_for_chronology("Create a chronological discovery timeline", data)

    assert [item["title"] for item in result["items"]] == ["Earlier", "Later", "Unknown"]


def test_non_timeline_poster_preserves_source_order():
    from app.main import _sort_poster_data_for_chronology

    data = {"items": [{"title": "Second", "date": "1900"}, {"title": "First", "date": "1800"}]}

    result = _sort_poster_data_for_chronology("Create a science poster", data)

    assert [item["title"] for item in result["items"]] == ["Second", "First"]


def test_element_discovery_poster_has_detailed_cards_and_custom_visuals(tmp_path):
    pytest.importorskip("PIL")
    spec = importlib.util.spec_from_file_location("jarvis_imagegen_worker_element", WORKER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    from app.poster_reference import build_element_discovery_poster

    data = build_element_discovery_poster(
        "Create a chronological timeline of discovery and organization of these elements: Md, F, Cl, Br, I, At, Ts, Yb, No, He"
    )
    assert data is not None
    output = tmp_path / "element-discovery.png"
    width, height = module._render_educational_poster(data, output)

    from PIL import Image
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.size == (1536, 2048)
        # More than a plain card template: the artwork, labels, data panels and
        # backgrounds create a large set of distinct rendered colors.
        assert len(image.convert("RGB").getcolors(maxcolors=1_000_000) or []) > 100
    assert (width, height) == (1536, 2048)



def test_element_poster_writes_editable_vector_svg(tmp_path):
    pytest.importorskip("PIL")
    spec = importlib.util.spec_from_file_location("jarvis_imagegen_worker_svg", WORKER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    from app.poster_reference import build_element_discovery_poster
    data = build_element_discovery_poster(
        "Create a detailed poster about the following chemical elements: "
        "Md (Mendelevium), F (Fluorine), Cl (Chlorine), Br (Bromine), I (Iodine), "
        "At (Astatine), Ts (Tennessine), Yb (Ytterbium), No (Nobelium), and He (Helium)."
    )
    assert data is not None and len(data["items"]) == 10
    output = tmp_path / "elements.svg"
    module._write_educational_poster_svg(data, output)
    import xml.etree.ElementTree as ET
    root = ET.parse(output).getroot()
    assert root.tag.endswith("svg")
    text_content = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("text"))
    assert "Chlorine" in text_content and "Tennessine" in text_content
    assert "atomic" in text_content.lower() or "GROUP" in text_content


@pytest.mark.parametrize("variant", ["cards", "timeline", "orbit", "blueprint", "museum", "fieldnotes", "collage"])
def test_redesign_variants_write_distinct_png_and_editable_svg(tmp_path, variant):
    pytest.importorskip("PIL")
    spec = importlib.util.spec_from_file_location(f"jarvis_redesign_worker_{variant}", WORKER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    from app.poster_reference import build_element_discovery_poster
    data = build_element_discovery_poster(
        "Create a chronological timeline of discovery and organization of these elements: "
        "Md (Mendelevium), F (Fluorine), Cl (Chlorine), Br (Bromine), I (Iodine), "
        "At (Astatine), Ts (Tennessine), Yb (Ytterbium), No (Nobelium), and He (Helium)."
    )
    assert data is not None
    data["design_variant"] = variant
    png = tmp_path / f"{variant}.png"
    svg = tmp_path / f"{variant}.svg"
    width, height = module._render_educational_poster(data, png)
    module._write_educational_poster_svg(data, svg)

    from PIL import Image
    with Image.open(png) as image:
        assert image.size == (1536, 2048)
        assert image.format == "PNG"
    assert (width, height) == (1536, 2048)
    import xml.etree.ElementTree as ET
    root = ET.parse(svg).getroot()
    text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("text"))
    assert root.tag.endswith("svg")
    assert "Chlorine" in text and "Tennessine" in text
    assert len(text) > 800


def test_all_seven_design_families_produce_different_compositions(tmp_path):
    pytest.importorskip("PIL")
    spec = importlib.util.spec_from_file_location("jarvis_visual_diversity_worker", WORKER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    from app.poster_reference import build_element_discovery_poster
    from PIL import Image
    import hashlib

    data = build_element_discovery_poster(
        "Create a chronological timeline of discovery and organization of these elements: "
        "Md (Mendelevium), F (Fluorine), Cl (Chlorine), Br (Bromine), I (Iodine), "
        "At (Astatine), Ts (Tennessine), Yb (Ytterbium), No (Nobelium), and He (Helium)."
    )
    digests = set()
    for index, variant in enumerate(("cards", "timeline", "orbit", "blueprint", "museum", "fieldnotes", "collage")):
        payload = dict(data)
        payload.update({"design_variant": variant, "design_seed": 9000 + index, "visual_density": "high"})
        png = tmp_path / f"{variant}.png"
        svg = tmp_path / f"{variant}.svg"
        module._render_educational_poster(payload, png)
        module._write_educational_poster_svg(payload, svg)
        with Image.open(png) as rendered:
            digests.add(hashlib.sha256(rendered.convert("RGB").tobytes()).hexdigest())
        assert svg.is_file() and "<text" in svg.read_text(encoding="utf-8")
    assert len(digests) == 7, "Each supported composition family must render a distinct image."


def test_refinement_inspects_the_existing_png_and_adds_decorations_in_empty_margins(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    spec = importlib.util.spec_from_file_location("jarvis_refine_inspection_worker", WORKER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    from app.poster_reference import build_element_discovery_poster
    from PIL import Image

    root = tmp_path / "JARVIS"
    images = root / "generated" / "images"
    images.mkdir(parents=True)
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    previous_name = "0123456789abcdef0123456789abcdef.png"
    previous = images / previous_name
    Image.new("RGB", (1536, 2048), (8, 18, 30)).save(previous)
    data = build_element_discovery_poster(
        "Create a chronological timeline of discovery and organization of these elements: "
        "Md, F, Cl, Br, I, At, Ts, Yb, No, He"
    )
    data.update({
        "design_variant": "timeline", "poster_operation": "refine",
        "_previous_image_filename": previous_name,
        "design_notes": "Add artsy scientific elements to empty spaces",
        "visual_style": "artsy", "visual_density": "high", "design_seed": 20261110,
    })
    profile = module._inspect_previous_poster_image(data)
    assert profile and profile["width"] == 1536 and profile["height"] == 2048
    assert isinstance(profile["edge_empty_zones"], list)
    output = images / "fedcba9876543210fedcba9876543210.png"
    module._render_educational_poster(data, output)
    assert output.is_file() and output.stat().st_size > 10_000

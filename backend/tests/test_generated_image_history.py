from pathlib import Path

from app import main


def test_history_restores_verified_png_svg_and_original_poster_prompt(tmp_path, monkeypatch):
    root = tmp_path / "project"
    image_dir = root / "generated" / "images"
    image_dir.mkdir(parents=True)
    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "IMAGE_OUTPUT_DIR", image_dir)

    filename = "0123456789abcdef0123456789abcdef.png"
    svg_name = filename[:-4] + ".svg"
    (image_dir / filename).write_bytes(b"not decoded here; this endpoint only checks file existence")
    (image_dir / svg_name).write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>poster</text></svg>', encoding="utf-8")
    prompt = "Create a detailed educational poster about the periodic table and element discovery."
    messages = [
        {"role": "user", "content": f"Generate an image: {prompt}"},
        {"role": "assistant", "content": f"[[JARVIS_IMAGE:{filename}]]\n[[JARVIS_POSTER_DESIGN:timeline]]\nRendered locally with precise typography."},
    ]
    monkeypatch.setattr(main, "recent_messages", lambda _conversation_id, limit=100: [dict(item) for item in messages])

    history = main.get_conversation("main")["messages"]
    image_message = history[1]
    assert image_message["image_available"] is True
    assert image_message["svg_available"] is True
    assert image_message["poster"] is True
    assert image_message["design_variant"] == "timeline"
    assert image_message["image_prompt"] == prompt

    manifest = main.list_generated_images()
    assert filename in manifest["png"]
    assert svg_name in manifest["svg"]


def test_history_and_manifest_mark_model_invented_missing_filenames_unavailable(tmp_path, monkeypatch):
    root = tmp_path / "project"
    image_dir = root / "generated" / "images"
    image_dir.mkdir(parents=True)
    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "IMAGE_OUTPUT_DIR", image_dir)

    invented = "f1e3b9c7d2a4508f91234567890fedcb.png"
    messages = [
        {"role": "user", "content": "Generate an image: a detailed poster"},
        {"role": "assistant", "content": f"[[JARVIS_IMAGE:{invented}]]\nRendered locally with precise typography."},
    ]
    monkeypatch.setattr(main, "recent_messages", lambda _conversation_id, limit=100: [dict(item) for item in messages])

    image_message = main.get_conversation("main")["messages"][1]
    manifest = main.list_generated_images()
    assert image_message["image_available"] is False
    assert invented not in manifest["png"]
    assert image_message["svg_available"] is False


def test_poster_manifest_restores_exact_content_for_followup_refinement(tmp_path, monkeypatch):
    import asyncio

    root = tmp_path / "project"
    image_dir = root / "generated" / "images"
    image_dir.mkdir(parents=True)
    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "IMAGE_OUTPUT_DIR", image_dir)

    filename = "0123456789abcdef0123456789abcdef.png"
    source_prompt = "Create an educational poster with ten named chemical elements and their discovery history."
    original = {
        "title": "ORIGINAL SCIENCE POSTER",
        "subtitle": "Original subtitle",
        "intro": "Original introductory explanation",
        "items": [{"label": "Cl", "title": "Chlorine", "date": "1774", "detail": "Scheele produced chlorine."}],
        "key_takeaways": ["Preserve the exact factual copy."],
        "footer": "Original conclusion",
        "sources": "Original source note",
        "design_variant": "timeline",
        "visual_style": "default",
        "visual_density": "normal",
        "design_seed": 123,
        "design_notes": "",
    }
    main._save_poster_manifest(filename, original, source_prompt)

    async def unexpected_rebuild(_prompt):
        raise AssertionError("A saved poster manifest should be used instead of rebuilding content.")

    monkeypatch.setattr(main, "_generate_poster_content", unexpected_rebuild)
    request = main.ImageGenerateRequest(
        prompt="REFINE: add more decorative science illustrations to empty spaces.",
        conversation_id="main",
        poster=True,
        poster_operation="refine",
        previous_poster_filename=filename,
        poster_source_prompt=source_prompt,
        poster_design_notes="Add more visuals in empty spaces",
        poster_visual_style="artsy",
        poster_visual_density="high",
        design_variant="timeline",
        design_seed=456,
    )
    revised = asyncio.run(main._prepare_poster_data(request))
    assert revised["title"] == original["title"]
    assert revised["items"][0]["detail"] == original["items"][0]["detail"]
    assert revised["poster_operation"] == "refine"
    assert revised["_previous_image_filename"] == filename
    assert revised["visual_style"] == "artsy"
    assert revised["visual_density"] == "high"
    assert revised["design_seed"] == 456

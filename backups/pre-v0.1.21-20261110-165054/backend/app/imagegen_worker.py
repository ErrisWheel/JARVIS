"""Isolated, offline-only Stable Diffusion XL worker for local image creation."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from collections import deque
from typing import Callable


def _emit_event(event: dict) -> None:
    """Write one machine-readable progress event to stdout for the API stream."""
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


def _enable_vae_memory_saving(pipe) -> tuple[str, ...]:
    """Enable optional VAE memory helpers across Diffusers API versions."""
    vae = getattr(pipe, "vae", None)
    enabled: list[str] = []
    options = (
        ("slicing", "enable_slicing", "enable_vae_slicing"),
        ("tiling", "enable_tiling", "enable_vae_tiling"),
    )
    for label, vae_method_name, legacy_method_name in options:
        method = getattr(vae, vae_method_name, None) if vae is not None else None
        if not callable(method):
            method = getattr(pipe, legacy_method_name, None)
        if not callable(method):
            print(f"VAE {label} optimization is unavailable; continuing without it", file=sys.stderr, flush=True)
            continue
        try:
            method()
            enabled.append(label)
        except Exception as exc:
            print(f"VAE {label} optimization could not be enabled: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    return tuple(enabled)


def _build_step_callback(
    total_steps: int,
    started_at: float,
    *,
    clock: Callable[[], float] = time.monotonic,
    emit: Callable[[dict], None] = _emit_event,
):
    """Build an SDXL callback with a rolling, measured ETA (never a guessed countdown)."""
    last_step_at = started_at
    recent_step_durations: deque[float] = deque(maxlen=5)

    def on_step_end(_pipe, step_index: int, _timestep, callback_kwargs: dict) -> dict:
        nonlocal last_step_at
        now = clock()
        completed = min(total_steps, max(0, int(step_index) + 1))
        duration = max(0.0, now - last_step_at)
        last_step_at = now
        if completed > 0:
            recent_step_durations.append(duration)
        average_step = (sum(recent_step_durations) / len(recent_step_durations)) if recent_step_durations else None
        eta = average_step * max(0, total_steps - completed) if average_step is not None else None
        elapsed = max(0.0, now - started_at)
        emit({
            "type": "progress",
            "stage": "generating",
            "label": "Generating image",
            "step": completed,
            "total_steps": total_steps,
            "percent": round(completed * 100 / total_steps),
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": round(eta, 1) if eta is not None else None,
            "step_seconds": round(duration, 2),
        })
        return callback_kwargs

    return on_step_end


def _load_poster_font(size: int, bold: bool = False):
    """Load a common system font without bundling font binaries with JARVIS."""
    from PIL import ImageFont

    candidates: list[Path] = []
    if os.name == "nt":
        fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        names = ("arialbd.ttf", "segoeuib.ttf", "calibrib.ttf") if bold else ("arial.ttf", "segoeui.ttf", "calibri.ttf")
        candidates.extend(fonts / name for name in names)
    else:
        names = ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf") if bold else ("DejaVuSans.ttf", "LiberationSans-Regular.ttf")
        candidates.extend(Path("/usr/share/fonts/truetype/dejavu") / name for name in names)
        candidates.extend(Path("/usr/share/fonts/truetype/liberation2") / name for name in names)
    for candidate in candidates:
        if candidate.is_file():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap_poster_text(draw, text: str, font, max_width: int, max_lines: int | None = None) -> list[str]:
    words = str(text or "").split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = word
            if max_lines is not None and len(lines) >= max_lines:
                break
        else:
            current = candidate
    else:
        if current:
            lines.append(current)
        return lines

    # The content contract is bounded, but this final ellipsis also protects
    # against an unexpectedly long single token or a future font substitution.
    if current:
        candidate = current.rstrip(" .")
        while candidate and draw.textlength(candidate + "…", font=font) > max_width:
            candidate = candidate[:-1]
        lines.append((candidate + "…") if candidate else "…")
    return lines[:max_lines] if max_lines is not None else lines


def _render_educational_poster(poster_data: dict, output_path: Path) -> tuple[int, int]:
    """Render a crisp, print-sized educational poster with real text glyphs.

    SDXL is intentionally not used for poster typography. Diffusion models do not
    reliably reproduce exact spelling, numbers, chemical symbols, or dense copy.
    """
    from PIL import Image, ImageDraw, ImageFilter

    width, height = 1536, 2048
    margin = 92
    background = Image.new("RGB", (width, height), (7, 17, 31))
    draw = ImageDraw.Draw(background)

    # Restrained vertical gradient: visual richness without texture behind text.
    top = (7, 18, 33)
    bottom = (13, 39, 57)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line((0, y, width, y), fill=color)

    # Low-contrast scientific orbit motif kept in the margins/header only.
    orbit_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    orbit = ImageDraw.Draw(orbit_layer)
    orbit.ellipse((width - 530, -260, width + 110, 380), outline=(54, 178, 204, 42), width=5)
    orbit.ellipse((width - 440, -170, width + 20, 290), outline=(54, 178, 204, 30), width=3)
    orbit.ellipse((width - 485, -80, width - 15, 180), outline=(255, 168, 87, 32), width=3)
    orbit.ellipse((margin - 170, height - 360, margin + 180, height - 10), outline=(54, 178, 204, 24), width=4)
    background = Image.alpha_composite(background.convert("RGBA"), orbit_layer).convert("RGB")
    draw = ImageDraw.Draw(background)

    accent = (91, 221, 232)
    accent_warm = (255, 177, 98)
    primary = (239, 247, 250)
    secondary = (171, 194, 207)
    muted = (113, 143, 160)

    kicker_font = _load_poster_font(22, True)
    title_font = _load_poster_font(76, True)
    subtitle_font = _load_poster_font(30, False)
    card_title_font = _load_poster_font(34, True)
    date_font = _load_poster_font(22, True)
    body_font = _load_poster_font(24, False)
    label_font = _load_poster_font(56, True)
    index_font = _load_poster_font(17, True)
    footer_font = _load_poster_font(18, True)

    title = str(poster_data.get("title", "Educational Poster")).strip()[:100] or "Educational Poster"
    subtitle = str(poster_data.get("subtitle", "")).strip()[:180]
    footer = str(poster_data.get("footer", "")).strip()[:180]
    items = poster_data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 12:
        raise ValueError("Poster requires between 1 and 12 structured items")

    draw.text((margin, 88), "J.A.R.V.I.S.  /  LEARNING SERIES", font=kicker_font, fill=accent)
    title_lines = _wrap_poster_text(draw, title, title_font, width - (margin * 2), 2)
    title_y = 145
    for line in title_lines:
        draw.text((margin, title_y), line, font=title_font, fill=primary, stroke_width=0)
        title_y += 88
    if subtitle:
        subtitle_lines = _wrap_poster_text(draw, subtitle, subtitle_font, width - (margin * 2), 2)
        for line in subtitle_lines:
            draw.text((margin, title_y + 4), line, font=subtitle_font, fill=secondary)
            title_y += 42
    header_bottom = max(385, title_y + 48)
    draw.rounded_rectangle((margin, header_bottom, width - margin, header_bottom + 5), radius=3, fill=(45, 91, 112))
    draw.rounded_rectangle((margin, header_bottom, margin + 170, header_bottom + 5), radius=3, fill=accent)

    columns = 2 if len(items) > 4 else 1
    rows = (len(items) + columns - 1) // columns
    gap_x = 26
    gap_y = 22
    content_top = header_bottom + 45
    footer_y = height - 100
    cards_bottom_limit = height - 172
    card_width = (width - margin * 2 - gap_x * (columns - 1)) // columns
    available_height = cards_bottom_limit - content_top - gap_y * (rows - 1)
    card_height = min(292, max(210, available_height // rows))

    for index, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            raise ValueError("Poster item must be an object")
        label = str(raw_item.get("label", "")).strip()[:24]
        item_title = str(raw_item.get("title", "")).strip()[:100]
        date = str(raw_item.get("date", "")).strip()[:48]
        detail = str(raw_item.get("detail", "")).strip()[:220]
        if not item_title:
            raise ValueError("Poster item title cannot be empty")

        col = index % columns
        row = index // columns
        x = margin + col * (card_width + gap_x)
        y = content_top + row * (card_height + gap_y)
        x2 = x + card_width
        y2 = y + card_height

        draw.rounded_rectangle((x, y, x2, y2), radius=24, fill=(13, 34, 52), outline=(38, 76, 96), width=2)
        draw.rounded_rectangle((x + 1, y + 22, x + 7, y2 - 22), radius=3, fill=accent if index % 2 == 0 else accent_warm)
        draw.ellipse((x + 27, y + 27, x + 70, y + 70), fill=(27, 61, 79), outline=(70, 128, 147), width=2)
        number = f"{index + 1:02d}"
        number_box = draw.textbbox((0, 0), number, font=index_font)
        draw.text((x + 48 - (number_box[2] - number_box[0]) / 2, y + 39), number, font=index_font, fill=accent)

        label_x = x + 28
        label_area_width = 142
        if label:
            label_font_current = label_font if len(label) <= 3 else _load_poster_font(34, True)
            label_lines = _wrap_poster_text(draw, label, label_font_current, label_area_width, 2)
            label_y = y + 116 if len(label_lines) == 1 else y + 100
            for label_line in label_lines:
                draw.text((label_x, label_y), label_line, font=label_font_current, fill=primary)
                label_y += 48
        else:
            draw.text((label_x + 18, y + 124), number, font=label_font, fill=primary)

        divider_x = x + 184
        draw.line((divider_x, y + 30, divider_x, y2 - 30), fill=(47, 86, 105), width=2)
        text_x = divider_x + 28
        text_width = card_width - (text_x - x) - 26
        title_lines_item = _wrap_poster_text(draw, item_title, card_title_font, text_width, 2)
        item_y = y + 34
        for line in title_lines_item:
            draw.text((text_x, item_y), line, font=card_title_font, fill=primary)
            item_y += 42
        if date:
            date_line = (_wrap_poster_text(draw, date, date_font, max(80, text_width - 34), 1) or [date])[0]
            date_width = min(text_width, int(draw.textlength(date_line, font=date_font)) + 34)
            pill_y = item_y + 8
            draw.rounded_rectangle((text_x, pill_y, text_x + date_width, pill_y + 38), radius=13, fill=(25, 67, 83))
            draw.text((text_x + 17, pill_y + 6), date_line, font=date_font, fill=accent_warm)
            item_y = pill_y + 52
        else:
            item_y += 12
        if detail:
            body_lines = _wrap_poster_text(draw, detail, body_font, text_width, 3)
            line_height = 34
            max_bottom = y2 - 24
            max_lines = max(1, (max_bottom - item_y) // line_height)
            if len(body_lines) > max_lines:
                body_lines = _wrap_poster_text(draw, detail, body_font, text_width, int(max_lines))
            for line in body_lines:
                draw.text((text_x, item_y), line, font=body_font, fill=secondary)
                item_y += line_height

    footer_text = footer or "LOCALLY RENDERED  •  PRECISE TEXT  •  NO DIFFUSION-GENERATED LETTERING"
    footer_width = width - margin * 2
    footer_lines = _wrap_poster_text(draw, footer_text, footer_font, footer_width, 1)
    draw.line((margin, height - 132, width - margin, height - 132), fill=(37, 75, 94), width=2)
    if footer_lines:
        draw.text((margin, footer_y - 3), footer_lines[0], font=footer_font, fill=muted)
    draw.text((width - margin - 190, footer_y - 3), "JARVIS  /  LOCAL", font=footer_font, fill=accent)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    background.save(output_path, format="PNG", optimize=True, compress_level=7)
    with output_path.open("rb") as image_file:
        if image_file.read(8) != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("Poster renderer did not produce a valid PNG")
    return width, height


def main() -> int:
    try:
        root = Path(os.environ.get("JARVIS_ROOT", "")).resolve(strict=True)
    except (OSError, RuntimeError):
        print("JARVIS_ROOT must point to the installed project directory", file=sys.stderr)
        return 2

    request_candidate = Path(sys.argv[1]) if len(sys.argv) == 2 else None
    if request_candidate is None or request_candidate.is_symlink():
        print("A regular request file is required", file=sys.stderr)
        return 2
    try:
        request_path = request_candidate.resolve(strict=True)
    except OSError:
        print("A regular request file is required", file=sys.stderr)
        return 2

    request_root_path = root / "cache" / "imagegen"
    request_root_path.mkdir(parents=True, exist_ok=True)
    if request_root_path.is_symlink():
        print("Image request directory cannot be a symbolic link", file=sys.stderr)
        return 2
    request_root = request_root_path.resolve()
    if not request_path.is_file():
        print("A regular request file is required", file=sys.stderr)
        return 2
    try:
        request_path.relative_to(request_root)
    except ValueError:
        print("Request file is outside the JARVIS image-generation cache", file=sys.stderr)
        return 2

    model_dir_path = root / "ai" / "models" / "sdxl-base-1.0"
    output_dir_path = root / "generated" / "images"
    output_dir_path.mkdir(parents=True, exist_ok=True)
    if model_dir_path.is_symlink() or output_dir_path.is_symlink():
        print("Model and output directories cannot be symbolic links", file=sys.stderr)
        return 2
    model_dir = model_dir_path.resolve()
    output_dir = output_dir_path.resolve()
    try:
        model_dir.relative_to(root)
        output_dir.relative_to(root)
    except ValueError:
        print("Image model or output directory resolves outside the JARVIS project", file=sys.stderr)
        return 2

    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        prompt = str(request.get("prompt", "")).strip()
        filename = str(request.get("filename", ""))
        width = int(request.get("width", 1024))
        height = int(request.get("height", 1024))
        steps = int(request.get("steps", 25))
        seed = int(request.get("seed", -1))
        poster = bool(request.get("poster", False))
        poster_data = request.get("poster_data")
    except Exception as exc:
        print(f"Invalid image-generation request: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if not 8 <= len(prompt) <= 2400:
        print("Prompt must contain between 8 and 2400 characters", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[0-9a-f]{32}\.png", filename):
        print("Invalid output filename", file=sys.stderr)
        return 2
    if width not in {512, 768, 1024} or height not in {512, 768, 1024}:
        print("Unsupported image dimensions", file=sys.stderr)
        return 2
    if not 10 <= steps <= 35:
        print("Inference steps must be between 10 and 35", file=sys.stderr)
        return 2
    if poster:
        if not isinstance(poster_data, dict):
            print("Poster mode requires validated structured poster_data", file=sys.stderr)
            return 2
        try:
            _emit_event({"type": "stage", "stage": "rendering_poster", "label": "Typesetting readable poster", "percent": 50, "eta_seconds": None})
            output_path = output_dir / filename
            rendered_width, rendered_height = _render_educational_poster(poster_data, output_path)
            if not output_path.is_file() or output_path.stat().st_size < 2048:
                raise RuntimeError("Poster renderer did not save a valid PNG")
            _emit_event({
                "type": "progress", "stage": "rendering_poster", "label": "Poster typography complete",
                "step": 1, "total_steps": 1, "percent": 100, "elapsed_seconds": 0.0, "eta_seconds": 0.0,
            })
            _emit_event({"type": "saved", "filename": filename, "width": rendered_width,
                         "height": rendered_height, "size_bytes": output_path.stat().st_size,
                         "renderer": "typographic_poster"})
            return 0
        except Exception as exc:
            print(f"Poster rendering failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            _emit_event({"type": "worker_error", "error": f"{type(exc).__name__}: {exc}"})
            return 1

    if not (model_dir / "model_index.json").is_file():
        print("The local SDXL model is not installed", file=sys.stderr)
        return 3

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    try:
        import torch
        from diffusers import StableDiffusionXLPipeline

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable in the image-generation environment")
        torch.backends.cuda.matmul.allow_tf32 = True

        _emit_event({"type": "stage", "stage": "loading_model", "label": "Loading local SDXL model", "percent": 0, "eta_seconds": None})
        pipe = StableDiffusionXLPipeline.from_pretrained(
            str(model_dir),
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True,
            local_files_only=True,
        )
        try:
            pipe.set_progress_bar_config(disable=True)
        except Exception:
            pass

        _emit_event({"type": "stage", "stage": "preparing_gpu", "label": "Preparing RTX GPU", "percent": 0, "eta_seconds": None})
        pipe.to("cuda")
        _enable_vae_memory_saving(pipe)
        generator = None if seed < 0 else torch.Generator(device="cuda").manual_seed(seed)

        _emit_event({"type": "stage", "stage": "generating", "label": "Generating image", "percent": 0, "step": 0, "total_steps": steps, "elapsed_seconds": 0, "eta_seconds": None})
        generation_started = time.monotonic()
        callback = _build_step_callback(steps, generation_started)
        result = pipe(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=6.5,
            generator=generator,
            callback_on_step_end=callback,
        )

        _emit_event({"type": "stage", "stage": "saving", "label": "Saving verified PNG", "percent": 100, "elapsed_seconds": round(time.monotonic() - generation_started, 1), "eta_seconds": 0})
        output_path = output_dir / filename
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(output_path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as image_file:
            result.images[0].save(image_file, format="PNG", optimize=True)
            image_file.flush()
            os.fsync(image_file.fileno())

        if not output_path.is_file() or output_path.stat().st_size < 2048:
            raise RuntimeError("SDXL returned without saving a valid PNG file")
        with output_path.open("rb") as image_file:
            if image_file.read(8) != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError("Saved image does not have a valid PNG signature")

        _emit_event({"type": "saved", "filename": filename, "width": width, "height": height,
                     "seed": seed if seed >= 0 else None, "size_bytes": output_path.stat().st_size})
        del result, pipe
        torch.cuda.empty_cache()
        return 0
    except Exception as exc:
        print(f"Image generation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        _emit_event({"type": "worker_error", "error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

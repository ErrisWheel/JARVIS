"""Isolated, offline-only Stable Diffusion XL worker for local image creation."""
from __future__ import annotations

import json
import html
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


def _draw_element_motif(draw, key: str, cx: int, cy: int) -> None:
    """Draw a compact, element-specific scientific vignette in vector primitives."""
    ink = (122, 196, 213)
    bright = (93, 221, 232)
    warm = (255, 177, 98)
    purple = (184, 145, 235)
    green = (129, 219, 168)
    pale = (220, 239, 245)

    if key == "chlorine_flask":
        draw.line((cx - 15, cy - 28, cx - 8, cy + 5, cx - 25, cy + 25, cx - 25, cy + 31, cx + 25, cy + 31, cx + 25, cy + 25, cx + 8, cy + 5, cx + 15, cy - 28), fill=ink, width=4)
        draw.line((cx - 14, cy - 28, cx + 14, cy - 28), fill=pale, width=4)
        draw.polygon([(cx - 20, cy + 20), (cx + 20, cy + 20), (cx + 23, cy + 29), (cx - 23, cy + 29)], fill=(73, 155, 100))
        for ox, oy, r in [(-20, -36, 5), (0, -45, 4), (21, -38, 6)]:
            draw.ellipse((cx + ox - r, cy + oy - r, cx + ox + r, cy + oy + r), outline=green, width=3)
    elif key == "iodine_crystals":
        for pts in [
            [(cx - 28, cy + 25), (cx - 22, cy - 18), (cx - 8, cy - 34), (cx - 3, cy + 25)],
            [(cx - 3, cy + 25), (cx + 5, cy - 27), (cx + 21, cy - 38), (cx + 24, cy + 25)],
            [(cx + 18, cy + 25), (cx + 30, cy - 8), (cx + 39, cy + 4), (cx + 34, cy + 25)],
        ]:
            draw.polygon(pts, fill=(61, 46, 105), outline=purple)
            draw.line((pts[0], pts[2]), fill=(217, 183, 255), width=2)
    elif key == "bromine_vial":
        draw.rounded_rectangle((cx - 23, cy - 30, cx + 23, cy + 32), radius=8, outline=ink, width=4)
        draw.rectangle((cx - 15, cy + 5, cx + 15, cy + 26), fill=(174, 78, 39))
        draw.rounded_rectangle((cx - 10, cy - 42, cx + 10, cy - 28), radius=3, fill=pale)
        draw.line((cx - 15, cy + 5, cx + 15, cy + 5), fill=warm, width=3)
        draw.line((cx - 12, cy - 16, cx - 12, cy - 2), fill=(255, 215, 178), width=3)
    elif key == "helium_spectrum":
        draw.ellipse((cx - 33, cy - 30, cx + 21, cy + 24), fill=(255, 188, 83), outline=warm, width=3)
        for angle in range(0, 360, 45):
            import math
            a = math.radians(angle)
            draw.line((cx - 6 + 34 * math.cos(a), cy - 3 + 34 * math.sin(a), cx - 6 + 43 * math.cos(a), cy - 3 + 43 * math.sin(a)), fill=warm, width=3)
        for i, color in enumerate([(100, 174, 255), (166, 133, 240), (91, 221, 232), (121, 221, 163), (255, 210, 99)]):
            draw.line((cx + 18, cy + 16 + i * 5, cx + 53, cy + 16 + i * 5), fill=color, width=3)
    elif key == "ytterbium_ore":
        draw.polygon([(cx - 38, cy + 24), (cx - 28, cy - 9), (cx - 8, cy - 32), (cx + 5, cy - 10), (cx + 24, cy - 28), (cx + 39, cy + 24)], fill=(57, 83, 88), outline=green)
        draw.line((cx - 8, cy - 32, cx - 3, cy + 22), fill=(184, 217, 185), width=3)
        draw.line((cx + 24, cy - 28, cx + 12, cy + 20), fill=(130, 203, 184), width=3)
        draw.ellipse((cx - 18, cy + 2, cx - 6, cy + 14), fill=warm)
    elif key == "fluorine_cell":
        draw.line((cx - 28, cy - 32, cx - 28, cy + 20, cx - 17, cy + 31, cx + 17, cy + 31, cx + 28, cy + 20, cx + 28, cy - 32), fill=ink, width=4)
        draw.line((cx - 28, cy + 9, cx + 28, cy + 9), fill=(90, 154, 174), width=3)
        draw.line((cx - 12, cy - 42, cx - 12, cy + 23), fill=warm, width=4)
        draw.line((cx + 12, cy - 42, cx + 12, cy + 23), fill=bright, width=4)
        draw.line((cx - 12, cy - 42, cx - 12, cy - 51), fill=warm, width=3)
        draw.line((cx + 12, cy - 42, cx + 12, cy - 51), fill=bright, width=3)
        for ox, oy in [(-18, -7), (4, -2), (18, -15)]:
            draw.ellipse((cx + ox - 4, cy + oy - 4, cx + ox + 4, cy + oy + 4), outline=pale, width=2)
    elif key == "astatine_nucleus":
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=warm)
        draw.ellipse((cx - 36, cy - 16, cx + 36, cy + 16), outline=ink, width=3)
        draw.ellipse((cx - 16, cy - 36, cx + 16, cy + 36), outline=purple, width=3)
        draw.ellipse((cx + 29, cy - 4, cx + 37, cy + 4), fill=bright)
        draw.ellipse((cx - 4, cy - 37, cx + 4, cy - 29), fill=purple)
    elif key == "mendelevium_cyclotron":
        draw.ellipse((cx - 42, cy - 31, cx + 42, cy + 31), outline=ink, width=4)
        draw.ellipse((cx - 28, cy - 20, cx + 28, cy + 20), outline=(61, 111, 137), width=3)
        draw.arc((cx - 37, cy - 30, cx + 37, cy + 30), start=200, end=330, fill=warm, width=5)
        draw.ellipse((cx + 31, cy - 4, cx + 39, cy + 4), fill=warm)
        draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=bright)
    elif key == "nobelium_accelerator":
        for offset in (-18, 0, 18):
            draw.line((cx - 48, cy + offset, cx + 18, cy + offset), fill=ink if offset else bright, width=3)
        draw.polygon([(cx + 16, cy - 10), (cx + 28, cy), (cx + 16, cy + 10)], fill=warm)
        draw.ellipse((cx + 27, cy - 20, cx + 47, cy + 20), outline=purple, width=3)
        draw.ellipse((cx + 33, cy - 6, cx + 41, cy + 6), fill=warm)
    elif key == "tennessine_collision":
        draw.line((cx - 45, cy - 26, cx - 4, cy - 3), fill=bright, width=5)
        draw.line((cx - 45, cy + 26, cx - 4, cy + 3), fill=warm, width=5)
        draw.line((cx + 45, cy - 26, cx + 4, cy - 3), fill=purple, width=5)
        draw.line((cx + 45, cy + 26, cx + 4, cy + 3), fill=green, width=5)
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=pale)
        for dx, dy in [(-19, -19), (19, -19), (-19, 19), (19, 19), (0, -33), (0, 33)]:
            draw.line((cx + dx * 0.55, cy + dy * 0.55, cx + dx, cy + dy), fill=warm, width=3)


def _render_element_discovery_poster(poster_data: dict, output_path: Path) -> tuple[int, int]:
    """Render a curated ten-element history with descriptions and scientific vignettes."""
    from PIL import Image, ImageDraw

    width, height = 1536, 2048
    margin = 72
    image = Image.new("RGB", (width, height), (7, 17, 31))
    draw = ImageDraw.Draw(image)
    top, bottom = (7, 18, 33), (13, 39, 57)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line((0, y, width, y), fill=color)

    # Decorative orbital marks remain outside the body-copy region.
    draw.ellipse((width - 400, -185, width + 70, 285), outline=(24, 74, 94), width=4)
    draw.ellipse((width - 350, -135, width + 20, 235), outline=(68, 75, 88), width=2)
    draw.ellipse((-165, height - 320, 160, height + 5), outline=(20, 67, 86), width=3)

    primary = (239, 247, 250)
    secondary = (179, 202, 214)
    muted = (112, 145, 163)
    accent = (91, 221, 232)
    warm = (255, 177, 98)
    category_colors = {
        "halogen": (87, 211, 225),
        "noble_gas": (255, 185, 100),
        "lanthanoid": (126, 215, 162),
        "actinoid": (186, 150, 232),
    }

    kicker = _load_poster_font(20, True)
    title_font = _load_poster_font(58, True)
    subtitle_font = _load_poster_font(23, False)
    chip_font = _load_poster_font(14, True)
    card_title_font = _load_poster_font(27, True)
    date_font = _load_poster_font(16, True)
    discoverer_font = _load_poster_font(14, True)
    detail_font = _load_poster_font(15, False)
    symbol_font = _load_poster_font(58, True)
    number_font = _load_poster_font(14, True)
    class_font = _load_poster_font(12, True)
    footer_font = _load_poster_font(13, False)
    intro_font = _load_poster_font(14, False)

    title = str(poster_data.get("title", "ELEMENT DISCOVERY & ORGANIZATION")).strip()
    subtitle = str(poster_data.get("subtitle", "")).strip()
    intro = str(poster_data.get("intro", "")).strip()
    items = poster_data.get("items")
    if not isinstance(items, list) or not 2 <= len(items) <= 10:
        raise ValueError("Element discovery poster requires between 2 and 10 entries")

    draw.text((margin, 48), "J.A.R.V.I.S.  /  CHEMISTRY LEARNING SERIES", font=kicker, fill=accent)
    title_lines = _wrap_poster_text(draw, title, title_font, width - 2 * margin, 2)
    title_y = 91
    for line in title_lines:
        draw.text((margin, title_y), line, font=title_font, fill=primary)
        title_y += 66
    if subtitle:
        draw.text((margin, title_y + 1), subtitle, font=subtitle_font, fill=secondary)
    intro_y = title_y + 36
    intro_lines = _wrap_poster_text(draw, intro, intro_font, width - 2 * margin, 2) if intro else []
    for line in intro_lines:
        draw.text((margin, intro_y), line, font=intro_font, fill=muted)
        intro_y += 19
    rule_y = max(264, intro_y + 12 if intro_lines else 264)
    draw.rounded_rectangle((margin, rule_y, width - margin, rule_y + 4), radius=2, fill=(42, 89, 112))
    draw.rounded_rectangle((margin, rule_y, margin + 150, rule_y + 4), radius=2, fill=accent)

    chips = poster_data.get("category_chips", [])
    if chips:
        chip_y = rule_y + 22
        chip_x = margin
        chip_gap = 12
        for chip in chips:
            category = str(chip.get("category", "halogen"))
            label = f"{chip.get('label', category.upper())}  ·  {chip.get('count', 0)}"
            text_w = int(draw.textlength(label, font=chip_font))
            pill_w = min(470, text_w + 28)
            if chip_x + pill_w > width - margin:
                break
            color = category_colors.get(category, accent)
            draw.rounded_rectangle((chip_x, chip_y, chip_x + pill_w, chip_y + 34), radius=12, fill=(13, 38, 55), outline=color, width=2)
            draw.text((chip_x + 14, chip_y + 9), label, font=chip_font, fill=color)
            chip_x += pill_w + chip_gap

    columns = 2
    rows = (len(items) + 1) // 2
    card_gap_x, card_gap_y = 22, 17
    content_top = rule_y + 82
    footer_line_y = 1902
    card_width = (width - 2 * margin - card_gap_x) // columns
    card_height = min(294, (footer_line_y - content_top - card_gap_y * (rows - 1)) // rows)

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("Element poster entry is invalid")
        col, row = index % columns, index // columns
        x = margin + col * (card_width + card_gap_x)
        y = content_top + row * (card_height + card_gap_y)
        x2, y2 = x + card_width, y + card_height
        category = str(item.get("category", "halogen"))
        color = category_colors.get(category, accent)
        draw.rounded_rectangle((x, y, x2, y2), radius=20, fill=(13, 34, 52), outline=(38, 76, 96), width=2)
        draw.rounded_rectangle((x + 1, y + 18, x + 7, y2 - 18), radius=3, fill=color)
        draw.line((x + 164, y + 20, x + 164, y2 - 20), fill=(47, 86, 105), width=2)

        atomic_number = str(item.get("atomic_number", ""))
        if atomic_number:
            draw.ellipse((x + 22, y + 18, x + 61, y + 57), fill=(27, 61, 79), outline=color, width=2)
            number_box = draw.textbbox((0, 0), atomic_number, font=number_font)
            draw.text((x + 41 - (number_box[2] - number_box[0]) / 2, y + 29), atomic_number, font=number_font, fill=color)

        _draw_element_motif(draw, str(item.get("visual", "")), x + 91, y + 100)
        symbol = str(item.get("label", "")).strip()
        sym_box = draw.textbbox((0, 0), symbol, font=symbol_font)
        draw.text((x + 91 - (sym_box[2] - sym_box[0]) / 2, y + 148), symbol, font=symbol_font, fill=primary)

        text_x = x + 188
        text_width = card_width - (text_x - x) - 20
        name = str(item.get("title", "")).strip()
        date = str(item.get("date", "")).strip()
        discoverer = str(item.get("discoverer", "")).strip()
        detail = str(item.get("detail", "")).strip()
        classification = str(item.get("classification", "")).strip()
        if not name or not date or not discoverer or not detail or not classification:
            raise ValueError(f"Incomplete reference data for element {symbol or index + 1}")

        draw.text((text_x, y + 20), name, font=card_title_font, fill=primary)
        date_width = min(text_width, int(draw.textlength(date, font=date_font)) + 24)
        draw.rounded_rectangle((text_x, y + 60, text_x + date_width, y + 89), radius=10, fill=(25, 67, 83))
        draw.text((text_x + 12, y + 67), date, font=date_font, fill=warm)

        discoverer_lines = _wrap_poster_text(draw, discoverer, discoverer_font, text_width, 2)
        d_y = y + 101
        for line in discoverer_lines:
            draw.text((text_x, d_y), line, font=discoverer_font, fill=color)
            d_y += 20
        institution = str(item.get("institution", "")).strip()
        if institution:
            institution_font = _load_poster_font(12, True)
            institution_lines = _wrap_poster_text(draw, institution, institution_font, text_width, 1)
            if institution_lines:
                draw.text((text_x, d_y + 1), institution_lines[0], font=institution_font, fill=(139, 190, 204))
                d_y += 19

        detail_lines = _wrap_poster_text(draw, detail, detail_font, text_width, 3)
        body_y = max(y + 164, d_y + 5)
        body_line_height = 18
        max_body_lines = max(1, min(3, (y2 - 50 - body_y) // body_line_height))
        if len(detail_lines) > max_body_lines:
            detail_lines = _wrap_poster_text(draw, detail, detail_font, text_width, int(max_body_lines))
        for line in detail_lines:
            draw.text((text_x, body_y), line, font=detail_font, fill=secondary)
            body_y += body_line_height

        class_text = classification.upper()
        class_w = min(text_width, int(draw.textlength(class_text, font=class_font)) + 20)
        class_y = y2 - 36
        draw.rounded_rectangle((text_x, class_y, text_x + class_w, class_y + 23), radius=8, fill=(19, 45, 62), outline=color, width=1)
        draw.text((text_x + 10, class_y + 5), class_text, font=class_font, fill=color)

    # Explicitly explain how the historical discoveries map to today's table.
    draw.line((margin, footer_line_y, width - margin, footer_line_y), fill=(37, 75, 94), width=2)
    note = str(poster_data.get("footer", "")).strip()
    sources = str(poster_data.get("sources", "")).strip()
    note_lines = _wrap_poster_text(draw, note, footer_font, width - 2 * margin, 1)
    source_lines = _wrap_poster_text(draw, sources, footer_font, width - 2 * margin, 1)
    if note_lines:
        draw.text((margin, footer_line_y + 15), note_lines[0], font=footer_font, fill=secondary)
    if source_lines:
        draw.text((margin, footer_line_y + 40), source_lines[0], font=footer_font, fill=muted)
    brand = "JARVIS  /  LOCAL"
    brand_font = _load_poster_font(14, True)
    draw.text((width - margin - int(draw.textlength(brand, font=brand_font)), height - 42), brand, font=brand_font, fill=accent)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True, compress_level=7)
    with output_path.open("rb") as image_file:
        if image_file.read(8) != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("Element poster renderer did not produce a valid PNG")
    return width, height


def _draw_generic_poster_motif(draw, key: str, cx: int, cy: int, color=(91, 221, 232)) -> None:
    """Draw a small topic-relevant vector-style icon for non-element posters."""
    pale = (220, 239, 245)
    warm = (255, 177, 98)
    key = str(key or "auto").lower()
    if key in {"atom", "atomic", "spectrum"}:
        draw.ellipse((cx - 36, cy - 14, cx + 36, cy + 14), outline=color, width=3)
        draw.ellipse((cx - 14, cy - 36, cx + 14, cy + 36), outline=pale, width=3)
        draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=warm)
        draw.ellipse((cx + 28, cy - 3, cx + 34, cy + 3), fill=pale)
    elif key in {"molecule", "chemistry", "network"}:
        nodes = [(-27, 16), (0, -23), (28, 16)]
        draw.line((cx - 27, cy + 16, cx, cy - 23, cx + 28, cy + 16), fill=color, width=5)
        for dx, dy in nodes:
            draw.ellipse((cx + dx - 9, cy + dy - 9, cx + dx + 9, cy + dy + 9), fill=warm if dx == 0 else pale, outline=color, width=2)
    elif key in {"lab", "flask", "microscope"}:
        draw.line((cx - 12, cy - 36, cx + 12, cy - 36), fill=pale, width=4)
        draw.line((cx - 7, cy - 36, cx - 7, cy - 4, cx - 29, cy + 27, cx - 29, cy + 34, cx + 29, cy + 34, cx + 29, cy + 27, cx + 7, cy - 4, cx + 7, cy - 36), fill=color, width=4)
        draw.polygon([(cx - 23, cy + 20), (cx + 23, cy + 20), (cx + 28, cy + 31), (cx - 28, cy + 31)], fill=(69, 140, 155))
    elif key in {"timeline", "history", "process"}:
        draw.line((cx - 39, cy, cx + 34, cy), fill=color, width=4)
        draw.polygon([(cx + 34, cy - 8), (cx + 46, cy), (cx + 34, cy + 8)], fill=color)
        for dx in (-28, 0, 25):
            draw.ellipse((cx + dx - 7, cy - 7, cx + dx + 7, cy + 7), fill=warm if dx == 0 else pale)
    elif key in {"chart", "graph", "statistics"}:
        draw.line((cx - 36, cy + 34, cx - 36, cy - 32, cx + 38, cy - 32), fill=pale, width=3)
        draw.rectangle((cx - 24, cy + 5, cx - 10, cy + 30), fill=color)
        draw.rectangle((cx - 2, cy - 10, cx + 12, cy + 30), fill=warm)
        draw.rectangle((cx + 20, cy - 27, cx + 34, cy + 30), fill=pale)
    elif key in {"cell", "biology", "microbiology"}:
        draw.ellipse((cx - 39, cy - 32, cx + 39, cy + 32), outline=color, width=4)
        draw.ellipse((cx - 11, cy - 10, cx + 11, cy + 10), fill=warm, outline=pale, width=2)
        for dx, dy in [(-24, -12), (24, 10), (0, 24)]:
            draw.ellipse((cx + dx - 4, cy + dy - 4, cx + dx + 4, cy + dy + 4), fill=pale)
    elif key in {"book", "education", "document"}:
        draw.polygon([(cx - 37, cy - 25), (cx - 5, cy - 18), (cx - 5, cy + 30), (cx - 37, cy + 22)], outline=color, fill=(20, 52, 68))
        draw.polygon([(cx + 37, cy - 25), (cx + 5, cy - 18), (cx + 5, cy + 30), (cx + 37, cy + 22)], outline=color, fill=(20, 52, 68))
        draw.line((cx, cy - 18, cx, cy + 31), fill=pale, width=3)
    elif key in {"map", "globe", "geography"}:
        draw.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), outline=color, width=4)
        draw.arc((cx - 17, cy - 34, cx + 17, cy + 34), 90, 270, fill=pale, width=3)
        draw.arc((cx - 17, cy - 34, cx + 17, cy + 34), -90, 90, fill=pale, width=3)
        draw.line((cx - 31, cy, cx + 31, cy), fill=pale, width=2)
    else:
        # Safe, reusable fallback: an orbital/connection motif, not a blank badge.
        draw.ellipse((cx - 36, cy - 14, cx + 36, cy + 14), outline=color, width=3)
        draw.ellipse((cx - 14, cy - 36, cx + 14, cy + 36), outline=pale, width=3)
        draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=warm)



def _inspect_previous_poster_image(poster_data: dict) -> dict | None:
    """Read the real previous PNG for refinement; return safe visual-layout hints."""
    filename = str(poster_data.get("_previous_image_filename", ""))
    if not re.fullmatch(r"[0-9a-f]{32}\.png", filename):
        return None
    root_value = os.environ.get("JARVIS_ROOT", "").strip()
    if not root_value:
        return None
    try:
        root = Path(root_value).resolve(strict=True)
        output_dir = root / "generated" / "images"
        if output_dir.is_symlink():
            return None
        output_dir = output_dir.resolve(strict=True)
        output_dir.relative_to(root)
        path = output_dir / filename
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 50 * 1024 * 1024:
            return None
        from PIL import Image, ImageStat
        with Image.open(path) as source:
            source.verify()
        with Image.open(path) as source:
            image = source.convert("RGB")
            width, height = image.size
            thumbnail = image.resize((32, 44))
            stat = ImageStat.Stat(thumbnail)
            average = tuple(int(value) for value in stat.mean[:3])
            # Inspect low-detail cells only along the outer 12% margins. Those
            # are safe candidates for decorative additions and do not cover copy.
            empty_zones: list[tuple[int, int]] = []
            tile_w = max(1, width // 32)
            tile_h = max(1, height // 44)
            for gy in range(5, 39, 3):
                for gx in (0, 31):
                    crop = image.crop((gx*tile_w, gy*tile_h, min(width,(gx+1)*tile_w), min(height,(gy+1)*tile_h))).resize((8,8))
                    tile_stat = ImageStat.Stat(crop)
                    if max(tile_stat.stddev) < 18:
                        empty_zones.append((int((gx+0.5)*width/32), int((gy+0.5)*height/44)))
            return {
                "width": width,
                "height": height,
                "average_rgb": average,
                "edge_empty_zones": empty_zones[:24],
                "edge_empty_zone_count": len(empty_zones),
            }
    except Exception as exc:
        print(f"Previous poster visual inspection skipped: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return None


def _render_landscape_poster_layout(poster_data: dict, output_path: Path) -> tuple[int, int]:
    """Render an education-first 16:9 landscape poster with a serpentine timeline."""
    import random
    from PIL import Image, ImageDraw

    width, height = 1920, 1080
    variant = str(poster_data.get("design_variant", "cards")).lower()
    style = str(poster_data.get("visual_style", "default")).lower()
    density = str(poster_data.get("visual_density", "normal")).lower()
    seed = int(poster_data.get("design_seed", 0) or 0)
    rng = random.Random(seed)
    paper_mode = variant in {"museum", "fieldnotes"} or style in {"vintage", "museum", "watercolor"}
    technical_mode = variant == "blueprint" or style == "technical"
    artsy_mode = variant == "collage" or style in {"artsy", "collage", "watercolor"}
    if paper_mode:
        bg, panel, edge = (246,240,225), (255,252,243), (194,177,146)
        primary, secondary, muted = (43,49,52), (78,82,78), (121,112,96)
        accent, warm, rail = (43,119,119), (177,91,54), (194,177,146)
    elif technical_mode:
        bg, panel, edge = (5,22,43), (9,35,62), (49,109,143)
        primary, secondary, muted = (224,243,255), (168,209,230), (104,164,196)
        accent, warm, rail = (76,207,224), (255,190,105), (39,98,135)
    elif artsy_mode:
        bg, panel, edge = (24,25,42), (39,39,60), (98,87,126)
        primary, secondary, muted = (250,244,237), (217,211,224), (160,155,179)
        accent, warm, rail = (122,219,205), (255,153,121), (78,76,111)
    else:
        bg, panel, edge = (7,17,31), (13,34,52), (38,76,96)
        primary, secondary, muted = (239,247,250), (179,202,214), (112,145,163)
        accent, warm, rail = (91,221,232), (255,177,98), (42,89,112)

    items = poster_data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 12:
        raise ValueError("Landscape educational poster requires between 1 and 12 entries")

    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    # Subtle visual treatment varies by design family while leaving the content grid clear.
    if technical_mode:
        for gx in range(0, width, 32): draw.line((gx, 0, gx, height), fill=(12,47,77), width=1)
        for gy in range(0, height, 32): draw.line((0, gy, width, gy), fill=(12,47,77), width=1)
        draw.rectangle((24,24,width-24,height-24), outline=edge, width=2)
    elif paper_mode:
        draw.rectangle((22,22,width-22,height-22), outline=rail, width=3)
        draw.rectangle((34,34,width-34,height-34), outline=(218,205,179), width=1)
        if variant == "fieldnotes":
            for gy in range(270,990,26): draw.line((46,gy,width-46,gy), fill=(226,218,199), width=1)
    else:
        for n in range(24 if density == "high" else 12):
            x = rng.choice([rng.randint(22,150), rng.randint(width-150,width-22)])
            y = rng.randint(210,1020)
            r = rng.randint(5,20)
            draw.ellipse((x-r,y-r,x+r,y+r), outline=accent if n%2==0 else warm, width=2)
            if artsy_mode:
                draw.arc((x-r*2,y-r*2,x+r*2,y+r*2), start=rng.randint(0,120), end=rng.randint(180,350), fill=rail, width=2)

    # Header and information hierarchy.
    kicker_font = _load_poster_font(15, True)
    title_font = _load_poster_font(45, True)
    subtitle_font = _load_poster_font(19, False)
    intro_font = _load_poster_font(14, False)
    chip_font = _load_poster_font(11, True)
    draw.text((58,42), "J.A.R.V.I.S.  /  EDUCATIONAL VISUAL SERIES", font=kicker_font, fill=accent)
    title = str(poster_data.get("title", "EDUCATIONAL DISCOVERY TIMELINE")).strip()[:110]
    title_lines = _wrap_poster_text(draw, title, title_font, 1800, 1)
    draw.text((58,72), title_lines[0] if title_lines else "EDUCATIONAL DISCOVERY TIMELINE", font=title_font, fill=primary)
    subtitle = str(poster_data.get("subtitle", "")).strip()
    draw.text((60,128), _wrap_poster_text(draw, subtitle, subtitle_font, 1770, 1)[0] if subtitle else "", font=subtitle_font, fill=secondary)
    intro = str(poster_data.get("intro", "")).strip()
    draw.text((60,160), _wrap_poster_text(draw, intro, intro_font, 1780, 2)[0] if intro else "", font=intro_font, fill=muted)

    chips = poster_data.get("category_chips", [])
    chip_x = 60
    for chip in chips[:5] if isinstance(chips, list) else []:
        if not isinstance(chip, dict): continue
        label = f"{chip.get('label', chip.get('category','').upper())}  /  {chip.get('count','')}"
        chip_w = min(310, int(draw.textlength(label, font=chip_font))+22)
        if chip_x + chip_w > width-60: break
        draw.rounded_rectangle((chip_x,198,chip_x+chip_w,224), radius=8, fill=panel, outline=accent, width=1)
        draw.text((chip_x+10,204), label, font=chip_font, fill=accent)
        chip_x += chip_w+9

    margin, gap_x = 54, 14
    card_w = (width - 2*margin - 4*gap_x)//5
    card_h = 330
    row_y = (260, 635)
    # Chronology snakes left-to-right across row one, then right-to-left across row two.
    node_y = (250, 625)
    centers = [margin + col*(card_w+gap_x) + card_w//2 for col in range(5)]
    for row in range(2):
        y = node_y[row]
        draw.line((centers[0],y,centers[-1],y), fill=rail, width=4)
        for col,cx in enumerate(centers):
            draw.ellipse((cx-8,y-8,cx+8,y+8), fill=bg, outline=accent if col%2==0 else warm, width=3)
    # Turn connector at the right edge, then route the second row in reverse order.
    draw.line((centers[-1],node_y[0],width-28,node_y[0],width-28,612,centers[-1],612), fill=rail, width=3)
    draw.polygon([(centers[-1]-9,612),(centers[-1]+8,603),(centers[-1]+8,621)], fill=warm)

    category_colors = {
        "halogen": (74,162,181), "noble_gas": (203,137,64),
        "lanthanoid": (82,151,112), "actinoid": (150,112,184),
    }
    date_font = _load_poster_font(13, True)
    atomic_font = _load_poster_font(11, True)
    symbol_font = _load_poster_font(47, True)
    name_font = _load_poster_font(19, True)
    meta_font = _load_poster_font(11, True)
    detail_font = _load_poster_font(12, False)
    significance_font = _load_poster_font(11, True)
    class_font = _load_poster_font(10, True)

    for index, raw in enumerate(items):
        if not isinstance(raw, dict): raise ValueError("Landscape poster entry must be an object")
        row = 0 if index < 5 else 1
        sequence_col = index if row == 0 else index-5
        col = sequence_col if row == 0 else 4-sequence_col
        x = margin + col*(card_w+gap_x)
        y = row_y[row]
        x2, y2 = x+card_w, y+card_h
        color = category_colors.get(str(raw.get("category", "")), accent if index%2==0 else warm)
        label = str(raw.get("label", "")).strip()[:12]
        atomic = str(raw.get("atomic_number", "")).strip()[:6]
        name = str(raw.get("title", "")).strip()[:80] or label or f"Entry {index+1}"
        date = str(raw.get("date", "")).strip()[:42] or f"EVENT {index+1:02d}"
        discoverer = str(raw.get("discoverer", "")).strip()
        location = str(raw.get("location", "")).strip()
        institution = str(raw.get("institution", "")).strip()
        meta = "  ·  ".join(v for v in (discoverer, location, institution) if v)
        explanation = " ".join(v for v in (str(raw.get("method", "")).strip(), str(raw.get("detail", "")).strip()) if v)
        significance = str(raw.get("significance", "")).strip()
        classification = str(raw.get("classification", "")).strip()
        visual = str(raw.get("visual", "auto"))
        draw.rounded_rectangle((x,y,x2,y2), radius=14 if variant not in {"fieldnotes","museum"} else 7,
                               fill=panel, outline=color if variant in {"museum","collage"} else edge, width=2)
        if variant == "blueprint":
            draw.line((x+12,y+12,x+62,y+12), fill=accent, width=2)
            draw.line((x+12,y+12,x+12,y+34), fill=accent, width=2)
        elif variant == "museum":
            draw.rectangle((x+12,y+12,x2-12,y+17), fill=color)
        elif variant == "fieldnotes":
            for rule_y in range(y+172,y2-12,22): draw.line((x+12,rule_y,x2-12,rule_y), fill=(226,218,199), width=1)
            draw.rectangle((x+14,y-4,x2-14,y+5), fill=warm)
        elif variant == "collage":
            draw.polygon([(x2-52,y+20),(x2-20,y+20),(x2-20,y+52)], fill=warm)
        # Date and atomic number are always prominent; content remains text-first and unclipped.
        draw.text((x+16,y+16), date, font=date_font, fill=warm if not paper_mode else accent)
        draw.text((x+16,y+40), f"ATOMIC NO. {atomic}" if atomic else f"ENTRY {index+1:02d}", font=atomic_font, fill=muted)
        if label:
            draw.text((x+16,y+113), label, font=symbol_font, fill=primary)
        motif_x, motif_y = x2-60, y+100
        motif = _draw_element_motif if visual in {"chlorine_flask","iodine_crystals","bromine_vial","helium_spectrum","ytterbium_ore","fluorine_cell","astatine_nucleus","mendelevium_cyclotron","nobelium_accelerator","tennessine_collision"} else _draw_generic_poster_motif
        motif(draw, visual, motif_x, motif_y) if motif is _draw_element_motif else motif(draw, visual, motif_x, motif_y, color)
        name_x = x+16
        draw.text((name_x,y+70), name, font=name_font, fill=primary)
        meta_lines = _wrap_poster_text(draw, meta, meta_font, card_w-30, 2)
        meta_y = y+164
        for li,line in enumerate(meta_lines): draw.text((x+16,meta_y+li*15), line, font=meta_font, fill=color)
        desc_y = meta_y + max(1,len(meta_lines))*15 + 5
        desc_lines = _wrap_poster_text(draw, explanation, detail_font, card_w-30, 4)
        for li,line in enumerate(desc_lines):
            if desc_y+li*16 > y+270: break
            draw.text((x+16,desc_y+li*16), line, font=detail_font, fill=secondary)
        sig_y = y+286
        sig_lines = _wrap_poster_text(draw, significance, significance_font, card_w-30, 2)
        for li,line in enumerate(sig_lines):
            if sig_y+li*14 > y+314: break
            draw.text((x+16,sig_y+li*14), line, font=significance_font, fill=warm)
        if classification:
            class_text = classification.upper()[:42]
            cw = min(card_w-28, int(draw.textlength(class_text,font=class_font))+18)
            draw.rounded_rectangle((x+14,y2-25,x+14+cw,y2-7), radius=6, fill=bg, outline=color, width=1)
            draw.text((x+22,y2-23), class_text, font=class_font, fill=color)

    footer_y = 1000
    draw.line((56,footer_y,width-56,footer_y), fill=rail, width=2)
    footer = str(poster_data.get("footer", "")).strip()
    sources = str(poster_data.get("sources", "")).strip()
    foot_font = _load_poster_font(10, False)
    footer_line = _wrap_poster_text(draw, footer, foot_font, 1120, 1)
    source_line = _wrap_poster_text(draw, sources, foot_font, 1780, 1)
    if footer_line: draw.text((58,1007), footer_line[0], font=foot_font, fill=secondary)
    if source_line: draw.text((58,1025), source_line[0], font=foot_font, fill=muted)
    draw.text((width-330,1025), "CHRONOLOGY  /  ROW 1 →  ·  ROW 2 ←", font=foot_font, fill=accent)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return width, height


def _write_landscape_poster_svg(poster_data: dict, output_path: Path) -> None:
    """Write the landscape companion SVG using the same card geometry as the PNG."""
    import xml.etree.ElementTree as ET
    width, height = 1920, 1080
    variant = str(poster_data.get("design_variant", "cards")).lower()
    style = str(poster_data.get("visual_style", "default")).lower()
    paper_mode = variant in {"museum","fieldnotes"} or style in {"vintage","museum","watercolor"}
    technical_mode = variant == "blueprint" or style == "technical"
    artsy_mode = variant == "collage" or style in {"artsy","collage","watercolor"}
    if paper_mode:
        bg,panel,primary,secondary,muted,accent,warm,edge = "#f6f0e1","#fffcf3","#2b3134","#4e524e","#796f60","#2b7777","#b15b36","#c2b192"
    elif technical_mode:
        bg,panel,primary,secondary,muted,accent,warm,edge = "#05162b","#09233e","#e0f3ff","#a8d1e6","#68a4c4","#4ccfe0","#ffbe69","#316d8f"
    elif artsy_mode:
        bg,panel,primary,secondary,muted,accent,warm,edge = "#18192a","#27273c","#faf4ed","#d9d3e0","#a09bb3","#7adbc4","#ff9979","#62577e"
    else:
        bg,panel,primary,secondary,muted,accent,warm,edge = "#07111f","#0d2234","#eff7fa","#b3cad6","#7091a3","#5bdde8","#ffb162","#264c60"
    category_colors = {"halogen":"#57b8c7","noble_gas":"#cb8940","lanthanoid":"#529770","actinoid":"#9670b8"}
    items = poster_data.get("items")
    if not isinstance(items,list) or not 1 <= len(items) <= 12:
        raise ValueError("Landscape SVG poster requires between 1 and 12 items")
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="poster-title poster-desc">',
        f'<title id="poster-title">{_svg_escape(poster_data.get("title","Educational poster"))}</title>',
        f'<desc id="poster-desc">16:9 landscape educational poster, chronological reading order in two connected rows.</desc>',
        f'<rect width="{width}" height="{height}" fill="{bg}"/>',
        '<g font-family="Inter, Segoe UI, Arial, sans-serif">',
    ]
    if technical_mode:
        for gx in range(0,width,32): out.append(f'<path d="M{gx} 0V{height}" stroke="#0c2f4d" stroke-width="1"/>')
        for gy in range(0,height,32): out.append(f'<path d="M0 {gy}H{width}" stroke="#0c2f4d" stroke-width="1"/>')
        out.append(f'<rect x="24" y="24" width="{width-48}" height="{height-48}" fill="none" stroke="{edge}" stroke-width="2"/>')
    elif paper_mode:
        out.append(f'<rect x="22" y="22" width="{width-44}" height="{height-44}" fill="none" stroke="{edge}" stroke-width="3"/><rect x="34" y="34" width="{width-68}" height="{height-68}" fill="none" stroke="#dacdb3"/>')
    out.append(f'<text x="58" y="53" font-size="15" font-weight="700" letter-spacing="2" fill="{accent}">J.A.R.V.I.S. / EDUCATIONAL VISUAL SERIES</text>')
    title = str(poster_data.get("title","EDUCATIONAL DISCOVERY TIMELINE"))[:110]
    out.append(f'<text x="58" y="116" font-size="45" font-weight="800" fill="{primary}">{_svg_escape(title)}</text>')
    subtitle = str(poster_data.get("subtitle",""))[:180]
    intro = str(poster_data.get("intro",""))[:260]
    if subtitle: out.append(f'<text x="60" y="151" font-size="19" fill="{secondary}">{_svg_escape(subtitle)}</text>')
    if intro: out.append(f'<text x="60" y="180" font-size="14" fill="{muted}">{_svg_escape(intro)}</text>')
    margin,gap_x=54,14; card_w=(width-2*margin-4*gap_x)//5; card_h=330; row_y=(260,635); node_y=(250,625)
    centers=[margin+col*(card_w+gap_x)+card_w//2 for col in range(5)]
    for y in node_y:
        out.append(f'<path d="M{centers[0]} {y}H{centers[-1]}" stroke="{edge}" stroke-width="4"/>')
        for col,cx in enumerate(centers): out.append(f'<circle cx="{cx}" cy="{y}" r="8" fill="{bg}" stroke="{accent if col%2==0 else warm}" stroke-width="3"/>')
    out.append(f'<path d="M{centers[-1]} {node_y[0]}H{width-28}V612H{centers[-1]}" fill="none" stroke="{edge}" stroke-width="3"/><path d="M{centers[-1]-9} 612l17-9v18z" fill="{warm}"/>')
    date_font=13; meta_font=11; detail_font=12; class_font=10
    for index,raw in enumerate(items):
        if not isinstance(raw,dict): raise ValueError("Landscape SVG poster entry must be an object")
        row=0 if index<5 else 1; sequence_col=index if row==0 else index-5; col=sequence_col if row==0 else 4-sequence_col
        x=margin+col*(card_w+gap_x); y=row_y[row]; color=category_colors.get(str(raw.get("category","")),accent if index%2==0 else warm)
        label=str(raw.get("label", ""))[:12]; atomic=str(raw.get("atomic_number", ""))[:6]; name=str(raw.get("title",f"Entry {index+1}"))[:80]
        date=str(raw.get("date",f"EVENT {index+1:02d}"))[:42]
        meta="  ·  ".join(v for v in (str(raw.get("discoverer","")),str(raw.get("location","")),str(raw.get("institution",""))) if v)
        explanation=" ".join(v for v in (str(raw.get("method","")),str(raw.get("detail",""))) if v)
        significance=str(raw.get("significance","")); classification=str(raw.get("classification","")); visual=str(raw.get("visual","auto"))
        rx=7 if variant in {"museum","fieldnotes"} else 14
        border=color if variant in {"museum","collage"} else edge
        out.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="{rx}" fill="{panel}" stroke="{border}" stroke-width="2"/>')
        out.append(f'<text x="{x+16}" y="{y+30}" font-size="{date_font}" font-weight="700" fill="{warm if not paper_mode else accent}">{_svg_escape(date)}</text>')
        out.append(f'<text x="{x+16}" y="{y+54}" font-size="11" fill="{muted}">{"ATOMIC NO. "+_svg_escape(atomic) if atomic else "ENTRY "+str(index+1).zfill(2)}</text>')
        out.append(f'<text x="{x+16}" y="{y+91}" font-size="19" font-weight="750" fill="{primary}">{_svg_escape(name)}</text>')
        if label: out.append(f'<text x="{x+16}" y="{y+145}" font-size="47" font-weight="800" fill="{primary}">{_svg_escape(label)}</text>')
        out.append(_svg_motif(visual,x+card_w-60,y+111,color))
        for li,line in enumerate(_svg_wrap(meta,45,2)):
            out.append(f'<text x="{x+16}" y="{y+177+li*15}" font-size="{meta_font}" font-weight="650" fill="{color}">{_svg_escape(line)}</text>')
        desc_y=y+211+max(0,min(1,len(_svg_wrap(meta,45,2))-1))*15
        for li,line in enumerate(_svg_wrap(explanation,45,4)):
            out.append(f'<text x="{x+16}" y="{desc_y+li*16}" font-size="{detail_font}" fill="{secondary}">{_svg_escape(line)}</text>')
        for li,line in enumerate(_svg_wrap(significance,45,2)):
            out.append(f'<text x="{x+16}" y="{y+294+li*14}" font-size="11" font-weight="700" fill="{warm}">{_svg_escape(line)}</text>')
        if classification:
            out.append(f'<text x="{x+16}" y="{y+320}" font-size="{class_font}" font-weight="700" fill="{color}">{_svg_escape(classification.upper()[:42])}</text>')
    out.append(f'<path d="M56 1000H{width-56}" stroke="{edge}" stroke-width="2"/>')
    footer=str(poster_data.get("footer",""))[:180]; sources=str(poster_data.get("sources",""))[:260]
    if footer: out.append(f'<text x="58" y="1018" font-size="10" fill="{secondary}">{_svg_escape(footer)}</text>')
    if sources: out.append(f'<text x="58" y="1037" font-size="10" fill="{muted}">{_svg_escape(sources)}</text>')
    out.append(f'<text x="{width-330}" y="1037" font-size="10" fill="{accent}">CHRONOLOGY / ROW 1 → · ROW 2 ←</text>')
    out.append('</g></svg>')
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text("\n".join(out),encoding="utf-8")
    ET.parse(output_path)


def _render_redesigned_poster_layout(poster_data: dict, output_path: Path) -> tuple[int, int]:
    """Render one of seven distinct educational-poster compositions with real typography."""
    import random
    from PIL import Image, ImageDraw

    if str(poster_data.get("orientation", "portrait")).lower() == "landscape":
        return _render_landscape_poster_layout(poster_data, output_path)

    width, height = 1536, 2048
    variants = {"cards", "timeline", "orbit", "blueprint", "museum", "fieldnotes", "collage"}
    variant = str(poster_data.get("design_variant", "cards")).lower()
    if variant not in variants:
        raise ValueError(f"Unsupported educational poster design: {variant}")

    style = str(poster_data.get("visual_style", "default")).lower()
    density = str(poster_data.get("visual_density", "normal")).lower()
    notes = str(poster_data.get("design_notes", "")).lower()
    operation = str(poster_data.get("poster_operation", "new")).lower()
    previous_profile = _inspect_previous_poster_image(poster_data) if operation == "refine" else None
    seed = int(poster_data.get("design_seed", 0) or 0)
    rng = random.Random(seed)

    paper_mode = variant in {"museum", "fieldnotes"} or style in {"vintage", "museum", "watercolor"}
    technical_mode = variant == "blueprint" or style == "technical"
    artsy_mode = variant == "collage" or style in {"artsy", "collage", "watercolor"}

    if paper_mode:
        bg = (246, 240, 225) if style != "watercolor" else (239, 242, 232)
        panel = (255, 252, 243)
        panel_edge = (194, 177, 146)
        primary, secondary, muted = (43, 49, 52), (78, 82, 78), (121, 112, 96)
        accent, warm, line = (43, 119, 119), (177, 91, 54), (194, 177, 146)
    elif technical_mode:
        bg, panel, panel_edge = (5, 22, 43), (9, 35, 62), (49, 109, 143)
        primary, secondary, muted = (224, 243, 255), (168, 209, 230), (104, 164, 196)
        accent, warm, line = (76, 207, 224), (255, 190, 105), (39, 98, 135)
    elif artsy_mode:
        bg, panel, panel_edge = (24, 25, 42), (39, 39, 60), (98, 87, 126)
        primary, secondary, muted = (250, 244, 237), (217, 211, 224), (160, 155, 179)
        accent, warm, line = (122, 219, 205), (255, 153, 121), (78, 76, 111)
    else:
        bg, panel, panel_edge = (7, 17, 31), (13, 34, 52), (38, 76, 96)
        primary, secondary, muted = (239, 247, 250), (179, 202, 214), (112, 145, 163)
        accent, warm, line = (91, 221, 232), (255, 177, 98), (42, 89, 112)

    category_colors = {
        "halogen": (74, 162, 181),
        "noble_gas": (203, 137, 64),
        "lanthanoid": (82, 151, 112),
        "actinoid": (150, 112, 184),
    }
    items = poster_data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 12:
        raise ValueError("Educational poster requires between 1 and 12 entries")

    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)

    # Composition-specific page treatments stay behind the content.
    if technical_mode:
        for gx in range(0, width, 32):
            draw.line((gx, 0, gx, height), fill=(12, 47, 77), width=1)
        for gy in range(0, height, 32):
            draw.line((0, gy, width, gy), fill=(12, 47, 77), width=1)
        for inset in (28, 42):
            draw.rectangle((inset, inset, width-inset, height-inset), outline=(35, 103, 143), width=1)
        draw.text((width-260, 46), "PLATE / SCIENCE ARCHIVE", fill=muted, font=_load_poster_font(13, True))
    elif paper_mode:
        draw.rectangle((22, 22, width-22, height-22), outline=line, width=3)
        draw.rectangle((34, 34, width-34, height-34), outline=(218, 205, 179), width=1)
        if variant == "fieldnotes":
            for yline in range(310, 1870, 28):
                draw.line((56, yline, width-56, yline), fill=(226, 218, 199), width=1)
            for ypin in range(350, 1860, 86):
                draw.ellipse((38, ypin, 49, ypin+11), outline=(166, 151, 128), width=2)
        else:
            draw.rectangle((58, 58, width-58, 68), fill=accent)
            draw.rectangle((58, height-82, width-58, height-72), fill=warm)
    else:
        # Edge ornaments create a distinct visual identity without obscuring text.
        for n in range(16 if density == "high" else 8):
            x = rng.choice([rng.randint(24, 68), rng.randint(width-68, width-24)])
            y = rng.randint(240, height-160)
            radius = rng.randint(5, 18)
            color = accent if n % 2 == 0 else warm
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline=color, width=2)
            draw.line((x, y+radius+4, x+rng.randint(-24, 24), y+radius+rng.randint(16, 44)), fill=line, width=2)

    # Hand-placed scientific decoration in negative space. A seeded design seed
    # makes every render reproducible, while new requests receive a fresh seed.
    decoration_count = 18 if density == "high" else 10 if density == "rich" else 4
    if artsy_mode:
        decoration_count += 10
    if "empty" in notes or "visual" in notes or "artsy" in notes:
        decoration_count += 8
    decoration_positions = list(previous_profile.get("edge_empty_zones", [])) if previous_profile else []
    for n in range(decoration_count):
        if n < len(decoration_positions):
            x, y = decoration_positions[n]
        else:
            x = rng.choice([rng.randint(48, 125), rng.randint(width-125, width-48)])
            y = rng.randint(250, height-150)
        size = rng.randint(12, 36)
        color = [accent, warm, line, category_colors["actinoid"]][n % 4]
        kind = n % 4
        if kind == 0:
            draw.ellipse((x-size, y-size, x+size, y+size), outline=color, width=2)
            draw.ellipse((x-4, y-4, x+4, y+4), fill=color)
        elif kind == 1:
            draw.arc((x-size, y-size, x+size, y+size), start=25, end=300, fill=color, width=3)
        elif kind == 2:
            draw.line((x-size, y-size, x+size, y+size), fill=color, width=2)
            draw.line((x-size, y+size, x+size, y-size), fill=color, width=2)
        else:
            draw.polygon([(x, y-size), (x+size, y), (x, y+size), (x-size, y)], outline=color)

    # Header and typographic hierarchy.
    kicker_font = _load_poster_font(16, True)
    title_font = _load_poster_font(52, True)
    subtitle_font = _load_poster_font(21, False)
    intro_font = _load_poster_font(14, False)
    item_title_font = _load_poster_font(21 if variant in {"orbit", "fieldnotes"} else 24, True)
    date_font = _load_poster_font(13, True)
    metadata_font = _load_poster_font(12, True)
    detail_font = _load_poster_font(12 if variant in {"orbit", "fieldnotes"} else 13, False)
    significance_font = _load_poster_font(11, True)
    symbol_font = _load_poster_font(38, True)
    number_font = _load_poster_font(10, True)
    footer_font = _load_poster_font(11, False)

    kicker = "J.A.R.V.I.S.  /  EDUCATIONAL VISUAL SERIES"
    draw.text((72, 42), kicker, font=kicker_font, fill=accent)
    title = str(poster_data.get("title", "EDUCATIONAL POSTER")).strip()[:110]
    title_y = 84
    for title_line in _wrap_poster_text(draw, title, title_font, 1380, 2):
        draw.text((72, title_y), title_line, font=title_font, fill=primary)
        title_y += 59
    subtitle = str(poster_data.get("subtitle", "")).strip()
    for line_text in _wrap_poster_text(draw, subtitle, subtitle_font, 1380, 1):
        draw.text((74, title_y+2), line_text, font=subtitle_font, fill=secondary)
        title_y += 28
    intro = str(poster_data.get("intro", "")).strip()
    for line_text in _wrap_poster_text(draw, intro, intro_font, 1380, 2):
        draw.text((74, title_y+2), line_text, font=intro_font, fill=muted)
        title_y += 18

    chips = poster_data.get("category_chips", [])
    chip_x = 72
    chip_y = max(248, title_y+12)
    chip_font = _load_poster_font(11, True)
    for chip in chips[:4] if isinstance(chips, list) else []:
        if not isinstance(chip, dict):
            continue
        category = str(chip.get("category", ""))
        color = category_colors.get(category, accent)
        label_text = f"{chip.get('label', category.upper())}  /  {chip.get('count', '')}"
        pill_w = min(410, int(draw.textlength(label_text, font=chip_font))+24)
        draw.rounded_rectangle((chip_x, chip_y, chip_x+pill_w, chip_y+27), radius=8, fill=panel, outline=color, width=2)
        draw.text((chip_x+10, chip_y+7), label_text, font=chip_font, fill=color)
        chip_x += pill_w+10
        if chip_x > 1380:
            break

    content_top, footer_y = 320, 1880
    count = len(items)
    grid_mode = variant in {"cards", "fieldnotes", "museum"}
    orbit_mode = variant == "orbit"
    collage_mode = variant == "collage"
    if grid_mode:
        rows = (count+1)//2
        gap_x, gap_y = 24, 18
        card_w = (width-144-gap_x)//2
        card_h = (footer_y-content_top-gap_y*(rows-1))//rows
    else:
        gap = 12 if density == "high" else 9
        card_h = min(150, max(118, (footer_y-content_top-gap*(count-1))//count))
        card_w = 680 if orbit_mode else 1290

    spine_x = width//2
    if variant in {"timeline", "orbit", "blueprint"}:
        if variant == "orbit":
            draw.line((spine_x, content_top+20, spine_x, footer_y-15), fill=line, width=5)
        elif variant == "timeline":
            draw.line((112, content_top+10, 112, footer_y-20), fill=line, width=5)
        else:
            draw.line((104, content_top+5, 104, footer_y-10), fill=accent, width=2)
            for ytick in range(content_top+10, footer_y-20, 40):
                draw.line((88, ytick, 120, ytick), fill=warm, width=1)

    for index, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValueError("Poster item must be an object")
        category = str(raw.get("category", ""))
        color = category_colors.get(category, accent if index%2 == 0 else warm)
        label = str(raw.get("label", "")).strip()[:16]
        atomic = str(raw.get("atomic_number", "")).strip()[:8]
        name = str(raw.get("title", "")).strip()[:100] or label or f"Entry {index+1}"
        date = str(raw.get("date", "")).strip()[:50] or f"EVENT {index+1:02d}"
        meta = " · ".join(str(raw.get(key, "")).strip() for key in ("discoverer", "location", "institution") if str(raw.get(key, "")).strip())
        explanation = " ".join(str(raw.get(key, "")).strip() for key in ("method", "detail") if str(raw.get(key, "")).strip())
        significance = str(raw.get("significance", "")).strip()
        classification = str(raw.get("classification", "")).strip()
        visual = str(raw.get("visual", "auto"))
        motif_fn = _draw_element_motif if visual in {"chlorine_flask", "iodine_crystals", "bromine_vial", "helium_spectrum", "ytterbium_ore", "fluorine_cell", "astatine_nucleus", "mendelevium_cyclotron", "nobelium_accelerator", "tennessine_collision"} else _draw_generic_poster_motif

        if grid_mode:
            row, col = divmod(index, 2)
            x = 72 + col*(card_w+gap_x)
            y = content_top + row*(card_h+gap_y)
            draw.rounded_rectangle((x, y, x+card_w, y+card_h), radius=16 if variant != "fieldnotes" else 8, fill=panel, outline=color if variant == "museum" else panel_edge, width=2)
            if variant == "fieldnotes":
                for rule_y in range(y+96, y+card_h-10, 24):
                    draw.line((x+16, rule_y, x+card_w-16, rule_y), fill=(226, 218, 199), width=1)
                draw.rectangle((x+18, y-4, x+card_w-18, y+9), fill=warm)
            elif variant == "museum":
                draw.rectangle((x+14, y+14, x+card_w-14, y+18), fill=color)
            else:
                draw.rounded_rectangle((x+14, y+14, x+card_w-14, y+card_h-14), radius=12, outline=line, width=1)
            draw.text((x+20, y+20), date, font=date_font, fill=warm if not paper_mode else accent)
            draw.text((x+20, y+42), f"{label}  /  ATOMIC NO. {atomic}".strip(" /"), font=number_font, fill=muted)
            draw.text((x+20, y+64), name, font=item_title_font, fill=primary)
            motif_fn(draw, visual, x+card_w-74, y+88, color) if motif_fn is _draw_generic_poster_motif else motif_fn(draw, visual, x+card_w-74, y+88)
            text_w = card_w-160
            meta_lines = _wrap_poster_text(draw, meta, metadata_font, text_w, 2)
            for li, line_text in enumerate(meta_lines):
                draw.text((x+20, y+96+li*15), line_text, font=metadata_font, fill=color)
            desc_lines = _wrap_poster_text(draw, explanation, detail_font, text_w, 3)
            for li, line_text in enumerate(desc_lines):
                draw.text((x+20, y+130+li*16), line_text, font=detail_font, fill=secondary)
            if significance:
                sig_lines = _wrap_poster_text(draw, significance, significance_font, text_w, 1)
                if sig_lines:
                    draw.text((x+20, y+card_h-21), sig_lines[0], font=significance_font, fill=warm)
        else:
            y = content_top + index*(card_h + (12 if density == "high" else 9))
            if orbit_mode:
                side_left = index % 2 == 0
                x = 48 if side_left else 808
                card_w = 680
                connector_x = x+card_w if side_left else x
                ymid = y+card_h//2
                draw.line((connector_x, ymid, spine_x, ymid), fill=color, width=3)
                draw.ellipse((spine_x-10, ymid-10, spine_x+10, ymid+10), fill=bg, outline=color, width=4)
            elif collage_mode:
                x = 72 if index%2 == 0 else 205
                card_w = 1388 if index%2 == 0 else 1190
                ymid = y+card_h//2
                # Loose geometric underlay makes each panel feel collaged, not boxed.
                draw.polygon([(x-10,y+18),(x+card_w-16,y-7),(x+card_w+10,y+card_h-12),(x+6,y+card_h+8)], fill=(50, 45, 73))
            else:
                x = 174
                card_w = 1290
                ymid = y+card_h//2
                marker_x = 104 if variant == "blueprint" else 112
                draw.line((marker_x, ymid, x, ymid), fill=color, width=3)
                draw.ellipse((marker_x-10, ymid-10, marker_x+10, ymid+10), fill=bg, outline=color, width=3)
            draw.rounded_rectangle((x, y, x+card_w, y+card_h), radius=18 if not paper_mode else 8, fill=panel, outline=color if variant in {"museum", "collage"} else panel_edge, width=2)
            if variant == "blueprint":
                # Corner ticks and micro-measurements read as a technical plate.
                draw.line((x+14,y+14,x+70,y+14), fill=accent, width=2)
                draw.line((x+14,y+14,x+14,y+34), fill=accent, width=2)
                draw.text((x+card_w-150,y+10), f"SPEC / {index+1:02d}", font=number_font, fill=muted)
            if collage_mode:
                draw.ellipse((x+card_w-55,y+20,x+card_w-18,y+57), outline=warm, width=3)
                draw.line((x+card_w-72,y+58,x+card_w-20,y+58), fill=accent, width=3)
            left_col = x+18
            draw.text((left_col,y+10), date, font=date_font, fill=warm if not paper_mode else accent)
            if atomic:
                draw.text((left_col,y+34), f"ATOMIC NO. {atomic}", font=number_font, fill=muted)
            if label:
                draw.text((x+88,y+76), label, font=symbol_font, fill=primary, anchor="mm")
            motif_fn(draw, visual, x+220, y+card_h//2, color) if motif_fn is _draw_generic_poster_motif else motif_fn(draw, visual, x+220, y+card_h//2)
            tx=x+292
            text_w=card_w-320
            draw.text((tx,y+14), name, font=item_title_font, fill=primary)
            if classification:
                draw.text((x+card_w-350,y+16), classification.upper()[:52], font=number_font, fill=color)
            meta_lines=_wrap_poster_text(draw,meta,metadata_font,text_w,1)
            for li,line_text in enumerate(meta_lines):
                draw.text((tx,y+43+li*14),line_text,font=metadata_font,fill=color)
            desc_lines=_wrap_poster_text(draw,explanation,detail_font,text_w,2)
            for li,line_text in enumerate(desc_lines):
                draw.text((tx,y+63+li*15),line_text,font=detail_font,fill=secondary)
            sig_lines=_wrap_poster_text(draw,significance,significance_font,text_w,1)
            if sig_lines:
                draw.text((tx,y+card_h-17),sig_lines[0],font=significance_font,fill=warm)

    footer = str(poster_data.get("footer", "")).strip()
    sources = str(poster_data.get("sources", "")).strip()
    draw.line((72, footer_y, width-72, footer_y), fill=line, width=2)
    footer_lines = _wrap_poster_text(draw, footer, footer_font, width-144, 1)
    source_lines = _wrap_poster_text(draw, sources, footer_font, width-144, 1)
    if footer_lines:
        draw.text((72, footer_y+15), footer_lines[0], font=footer_font, fill=secondary)
    if source_lines:
        draw.text((72, footer_y+38), source_lines[0], font=footer_font, fill=muted)

    # A final visible visual-language marker is deliberately seeded from the job.
    # It prevents consecutive same-layout requests from producing byte-identical artwork.
    if variant in {"cards", "fieldnotes", "museum"}:
        accent_x = width-95
        for n in range(5):
            radius = 8 + ((seed >> (n*3)) & 15)
            draw.ellipse((accent_x-radius, 190+ n*24-radius, accent_x+radius, 190+n*24+radius), outline=accent if n%2==0 else warm, width=2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True, compress_level=7)
    with output_path.open("rb") as stream:
        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("Educational poster renderer did not produce a valid PNG")
    return width, height


def _write_redesigned_poster_svg(poster_data: dict, output_path: Path) -> None:
    """Write an editable SVG with the same seven composition families as the PNG."""
    import random
    import xml.etree.ElementTree as ET

    if str(poster_data.get("orientation", "portrait")).lower() == "landscape":
        _write_landscape_poster_svg(poster_data, output_path)
        return

    width, height = 1536, 2048
    variants = {"cards", "timeline", "orbit", "blueprint", "museum", "fieldnotes", "collage"}
    variant = str(poster_data.get("design_variant", "cards")).lower()
    if variant not in variants:
        raise ValueError(f"Unsupported educational SVG design: {variant}")
    style = str(poster_data.get("visual_style", "default")).lower()
    density = str(poster_data.get("visual_density", "normal")).lower()
    notes = str(poster_data.get("design_notes", "")).lower()
    operation = str(poster_data.get("poster_operation", "new")).lower()
    previous_profile = _inspect_previous_poster_image(poster_data) if operation == "refine" else None
    seed = int(poster_data.get("design_seed", 0) or 0)
    rng = random.Random(seed)
    paper_mode = variant in {"museum", "fieldnotes"} or style in {"vintage", "museum", "watercolor"}
    technical_mode = variant == "blueprint" or style == "technical"
    artsy_mode = variant == "collage" or style in {"artsy", "collage", "watercolor"}
    if paper_mode:
        bg, panel, primary, secondary, muted, accent, warm, line = "#f6f0e1", "#fffdf4", "#2b3134", "#4e524e", "#796f60", "#2b7777", "#b15b36", "#c2b192"
        edge = "#c2b192"
    elif technical_mode:
        bg, panel, primary, secondary, muted, accent, warm, line = "#05162b", "#09233e", "#e0f3ff", "#a8d1e6", "#68a4c4", "#4ccfe0", "#ffbe69", "#276287"
        edge = "#316d8f"
    elif artsy_mode:
        bg, panel, primary, secondary, muted, accent, warm, line = "#18192a", "#27273c", "#faf4ed", "#d9d3e0", "#a09bb3", "#7adbc4", "#ff9979", "#4e4c6f"
        edge = "#62577e"
    else:
        bg, panel, primary, secondary, muted, accent, warm, line = "#07111f", "#0d2234", "#eff7fa", "#b3cad6", "#7091a3", "#5bdde8", "#ffb162", "#2a596e"
        edge = "#264c60"
    category_colors = {"halogen":"#57b8c7", "noble_gas":"#cb8940", "lanthanoid":"#529770", "actinoid":"#9670b8"}
    items = poster_data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 12:
        raise ValueError("Educational SVG poster requires between 1 and 12 items")

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="poster-title poster-desc">',
        f'<title id="poster-title">{_svg_escape(poster_data.get("title", "Educational poster"))}</title>',
        f'<desc id="poster-desc">{_svg_escape(variant)} educational infographic. Editable vector text and decorative scientific illustrations.</desc>',
        f'<rect width="{width}" height="{height}" fill="{bg}"/>',
        '<g font-family="Inter, Segoe UI, Arial, sans-serif">',
    ]
    if technical_mode:
        for gx in range(0,width,32): out.append(f'<path d="M{gx} 0V{height}" stroke="#0c2f4d" stroke-width="1"/>')
        for gy in range(0,height,32): out.append(f'<path d="M0 {gy}H{width}" stroke="#0c2f4d" stroke-width="1"/>')
        out.append(f'<rect x="28" y="28" width="1480" height="1992" fill="none" stroke="{edge}"/>')
    elif paper_mode:
        out.extend([f'<rect x="22" y="22" width="1492" height="2004" fill="none" stroke="{line}" stroke-width="3"/>', f'<rect x="34" y="34" width="1468" height="1980" fill="none" stroke="#dacdb3"/>'])
        if variant == "fieldnotes":
            for gy in range(310,1870,28): out.append(f'<path d="M56 {gy}H1480" stroke="#e2dac7" stroke-width="1"/>')
            for gy in range(350,1860,86): out.append(f'<circle cx="43" cy="{gy+5}" r="5" fill="none" stroke="#a69780" stroke-width="2"/>')
    # Safe-area decorative motifs are unique per seed and kept at page edges.
    decoration_count = 18 if density == "high" else 10 if density == "rich" else 4
    if artsy_mode: decoration_count += 10
    if "empty" in notes or "visual" in notes or "artsy" in notes: decoration_count += 8
    svg_decoration_positions = list(previous_profile.get("edge_empty_zones", [])) if previous_profile else []
    for n in range(decoration_count):
        if n < len(svg_decoration_positions):
            x, y = svg_decoration_positions[n]
        else:
            x = rng.choice([rng.randint(48,125), rng.randint(width-125,width-48)])
            y = rng.randint(250,height-150)
        radius = rng.randint(7,21)
        color = (accent,warm,line,category_colors["actinoid"])[n%4]
        out.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="none" stroke="{color}" stroke-width="2"/>')
        out.append(f'<path d="M{x-radius-5} {y+radius+5}l{radius+10} {radius+10}" stroke="{line}" stroke-width="2"/>')
    out.append(f'<text x="72" y="48" font-size="16" font-weight="700" letter-spacing="2" fill="{accent}">J.A.R.V.I.S. / EDUCATIONAL VISUAL SERIES</text>')
    title_lines = _svg_wrap(str(poster_data.get("title", "EDUCATIONAL POSTER")), 42, 2)
    for i,line_text in enumerate(title_lines): out.append(f'<text x="72" y="{112+i*60}" font-size="52" font-weight="800" fill="{primary}">{_svg_escape(line_text)}</text>')
    subtitle_y = 172 + max(0,len(title_lines)-1)*60
    for i,line_text in enumerate(_svg_wrap(str(poster_data.get("subtitle", "")), 100, 1)): out.append(f'<text x="74" y="{subtitle_y+i*28}" font-size="21" fill="{secondary}">{_svg_escape(line_text)}</text>')
    intro_y = subtitle_y + 28
    for i,line_text in enumerate(_svg_wrap(str(poster_data.get("intro", "")), 150, 2)): out.append(f'<text x="74" y="{intro_y+i*18}" font-size="14" fill="{muted}">{_svg_escape(line_text)}</text>')
    category_y = 260
    chip_x = 72
    for chip in poster_data.get("category_chips", [])[:4]:
        if not isinstance(chip,dict): continue
        category=str(chip.get("category","")); color=category_colors.get(category,accent)
        text_value=f'{chip.get("label",category.upper())} / {chip.get("count","")}'
        pill_w=min(410,max(150,len(text_value)*7+22))
        out.append(f'<rect x="{chip_x}" y="{category_y}" width="{pill_w}" height="27" rx="8" fill="{panel}" stroke="{color}" stroke-width="2"/><text x="{chip_x+10}" y="{category_y+18}" font-size="11" font-weight="700" fill="{color}">{_svg_escape(text_value)}</text>')
        chip_x += pill_w+10
    content_top, footer_y = 320,1880
    count=len(items); grid_mode=variant in {"cards","fieldnotes","museum"}; orbit_mode=variant=="orbit"; collage_mode=variant=="collage"
    if grid_mode:
        rows=(count+1)//2; gap_x,gap_y=24,18; card_w=(width-144-gap_x)//2; card_h=(footer_y-content_top-gap_y*(rows-1))//rows
    else:
        gap=12 if density=="high" else 9; card_h=min(150,max(118,(footer_y-content_top-gap*(count-1))//count)); card_w=680 if orbit_mode else 1290
    spine_x=width//2
    if variant in {"timeline","orbit","blueprint"}:
        if variant=="orbit": out.append(f'<path d="M{spine_x} {content_top+20}V{footer_y-15}" stroke="{line}" stroke-width="5"/>')
        else: out.append(f'<path d="M{104 if variant=="blueprint" else 112} {content_top+10}V{footer_y-20}" stroke="{accent if variant=="blueprint" else line}" stroke-width="4"/>')
    for index,item in enumerate(items):
        if not isinstance(item,dict): raise ValueError("SVG poster entry must be an object")
        category=str(item.get("category","")); color=category_colors.get(category,accent if index%2==0 else warm)
        label=str(item.get("label","")).strip()[:16]; atomic=str(item.get("atomic_number","")).strip()[:8]
        name=str(item.get("title","")).strip()[:100] or label or f"Entry {index+1}"
        date=str(item.get("date","")).strip()[:50] or f"EVENT {index+1:02d}"
        meta=" · ".join(str(item.get(k,"")).strip() for k in ("discoverer","location","institution") if str(item.get(k,"")).strip())
        explanation=" ".join(str(item.get(k,"")).strip() for k in ("method","detail") if str(item.get(k,"")).strip())
        significance=str(item.get("significance","")).strip(); classification=str(item.get("classification","")).strip(); visual=str(item.get("visual","auto"))
        if grid_mode:
            row,col=divmod(index,2); x=72+col*(card_w+gap_x); y=content_top+row*(card_h+gap_y)
            out.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="12" fill="{panel}" stroke="{color if variant=="museum" else edge}" stroke-width="2"/>')
            if variant=="fieldnotes":
                for gy in range(y+96,y+card_h-10,24): out.append(f'<path d="M{x+16} {gy}H{x+card_w-16}" stroke="#e2dac7"/>')
                out.append(f'<rect x="{x+18}" y="{y-4}" width="{card_w-36}" height="13" fill="{warm}"/>')
            out.append(f'<text x="{x+20}" y="{y+34}" font-size="13" font-weight="700" fill="{accent}">{_svg_escape(date)}</text><text x="{x+20}" y="{y+55}" font-size="10" fill="{muted}">{_svg_escape(label)} / ATOMIC NO. {_svg_escape(atomic)}</text><text x="{x+20}" y="{y+81}" font-size="21" font-weight="750" fill="{primary}">{_svg_escape(name)}</text>')
            out.append(_svg_motif(visual,x+card_w-74,y+92,color))
            for i,line_text in enumerate(_svg_wrap(meta,70,2)): out.append(f'<text x="{x+20}" y="{y+105+i*14}" font-size="11" font-weight="650" fill="{color}">{_svg_escape(line_text)}</text>')
            for i,line_text in enumerate(_svg_wrap(explanation,80,3)): out.append(f'<text x="{x+20}" y="{y+139+i*15}" font-size="11" fill="{secondary}">{_svg_escape(line_text)}</text>')
            for i,line_text in enumerate(_svg_wrap(significance,80,1)): out.append(f'<text x="{x+20}" y="{y+card_h-18+i*13}" font-size="10" font-weight="700" fill="{warm}">{_svg_escape(line_text)}</text>')
        else:
            y=content_top+index*(card_h+(12 if density=="high" else 9))
            if orbit_mode:
                left=index%2==0; x=48 if left else 808; card_w=680; start=x+card_w if left else x
                out.append(f'<path d="M{start} {y+card_h//2}H{spine_x}" stroke="{color}" stroke-width="3"/><circle cx="{spine_x}" cy="{y+card_h//2}" r="10" fill="{bg}" stroke="{color}" stroke-width="4"/>')
            elif collage_mode:
                x=72 if index%2==0 else 205; card_w=1388 if index%2==0 else 1190
                out.append(f'<path d="M{x-8} {y+16}L{x+card_w-12} {y-7}L{x+card_w+8} {y+card_h-12}L{x+7} {y+card_h+8}Z" fill="#322d49"/>')
            else:
                x=174; card_w=1290; marker_x=104 if variant=="blueprint" else 112
                out.append(f'<path d="M{marker_x} {y+card_h//2}H{x}" stroke="{color}" stroke-width="3"/><circle cx="{marker_x}" cy="{y+card_h//2}" r="10" fill="{bg}" stroke="{color}" stroke-width="3"/>')
            out.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="12" fill="{panel}" stroke="{color if variant in {"museum","collage"} else edge}" stroke-width="2"/>')
            if variant=="blueprint": out.append(f'<path d="M{x+14} {y+14}h56 M{x+14} {y+14}v20" stroke="{accent}" stroke-width="2"/><text x="{x+card_w-150}" y="{y+22}" font-size="10" fill="{muted}">SPEC / {index+1:02d}</text>')
            if collage_mode: out.append(f'<circle cx="{x+card_w-37}" cy="{y+38}" r="18" fill="none" stroke="{warm}" stroke-width="3"/>')
            out.append(f'<text x="{x+18}" y="{y+28}" font-size="13" font-weight="700" fill="{accent}">{_svg_escape(date)}</text><text x="{x+18}" y="{y+52}" font-size="10" fill="{muted}">ATOMIC NO. {_svg_escape(atomic)}</text><text x="{x+88}" y="{y+79}" font-size="40" font-weight="800" fill="{primary}">{_svg_escape(label)}</text>')
            out.append(_svg_motif(visual,x+220,y+card_h//2,color))
            tx=x+292; text_w=120 if variant=="orbit" else 118
            out.append(f'<text x="{tx}" y="{y+33}" font-size="23" font-weight="750" fill="{primary}">{_svg_escape(name)}</text>')
            if classification: out.append(f'<text x="{x+card_w-350}" y="{y+18}" font-size="10" font-weight="700" fill="{color}">{_svg_escape(classification.upper()[:52])}</text>')
            for i,line_text in enumerate(_svg_wrap(meta,text_w,1)): out.append(f'<text x="{tx}" y="{y+56+i*15}" font-size="11" font-weight="650" fill="{color}">{_svg_escape(line_text)}</text>')
            for i,line_text in enumerate(_svg_wrap(explanation,text_w,2)): out.append(f'<text x="{tx}" y="{y+79+i*15}" font-size="11" fill="{secondary}">{_svg_escape(line_text)}</text>')
            for i,line_text in enumerate(_svg_wrap(significance,text_w,1)): out.append(f'<text x="{tx}" y="{y+card_h-12+i*13}" font-size="10" font-weight="700" fill="{warm}">{_svg_escape(line_text)}</text>')
    out.append(f'<path d="M72 {footer_y}H1464" stroke="{line}" stroke-width="2"/>')
    for i,line_text in enumerate(_svg_wrap(str(poster_data.get("footer","")),150,1)): out.append(f'<text x="72" y="{footer_y+20+i*14}" font-size="11" fill="{secondary}">{_svg_escape(line_text)}</text>')
    for i,line_text in enumerate(_svg_wrap(str(poster_data.get("sources","")),155,1)): out.append(f'<text x="72" y="{footer_y+42+i*14}" font-size="10" fill="{muted}">{_svg_escape(line_text)}</text>')
    out.append('</g></svg>')
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text("\n".join(out),encoding="utf-8")
    ET.parse(output_path)



def _render_educational_poster(poster_data: dict, output_path: Path) -> tuple[int, int]:
    """Render all structured educational posters through the same design engine."""
    data = dict(poster_data)
    data.setdefault("design_variant", "cards")
    return _render_redesigned_poster_layout(data, output_path)


def _svg_escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _svg_wrap(value: object, limit: int, max_lines: int) -> list[str]:
    words = str(value or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if current and len(candidate) > limit:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
        else:
            current = candidate
    else:
        if current:
            lines.append(current)
        return lines
    if current:
        clipped = current.rstrip(" .")
        lines.append((clipped[:max(1, limit - 1)] + "…") if len(clipped) >= limit else clipped + "…")
    return lines[:max_lines]


def _svg_motif(key: str, cx: int, cy: int, color: str) -> str:
    k = str(key or "auto").lower()
    pale, warm, purple, green = "#dceff5", "#ffb162", "#b891e8", "#81dba8"
    if k == "chlorine_flask" or k in {"lab", "flask", "chemistry"}:
        return f'<path d="M{cx-13} {cy-34}h26m-7 0v34l25 38v8h-62v-8l25-38v-34" fill="#16394a" stroke="{color}" stroke-width="4"/><path d="M{cx-27} {cy+23}h54l14 25h-82z" fill="#397e69" opacity=".9"/><g fill="none" stroke="{pale}" stroke-width="3"><circle cx="{cx-24}" cy="{cy-40}" r="5"/><circle cx="{cx+4}" cy="{cy-51}" r="4"/><circle cx="{cx+24}" cy="{cy-39}" r="6"/></g>'
    if k == "iodine_crystals" or k in {"crystal", "crystals"}:
        return f'<g fill="#3d2e69" stroke="{purple}" stroke-width="3"><path d="M{cx-42} {cy+35}l8-58 18-25 8 83z"/><path d="M{cx-10} {cy+35}l11-68 20-23 5 91z"/><path d="M{cx+18} {cy+35}l12-42 14-10 5 52z"/></g><path d="M{cx-34} {cy-23}l12 57m16-54 10 54" stroke="#d9c4ff" stroke-width="2"/>'
    if k == "bromine_vial" or k in {"vial", "test_tube"}:
        return f'<rect x="{cx-26}" y="{cy-31}" width="52" height="76" rx="10" fill="#183346" stroke="{color}" stroke-width="4"/><rect x="{cx-17}" y="{cy+7}" width="34" height="28" rx="4" fill="#ae4e27"/><rect x="{cx-12}" y="{cy-45}" width="24" height="17" rx="4" fill="{pale}"/><path d="M{cx-17} {cy+7}h34" stroke="{warm}" stroke-width="3"/>'
    if k == "helium_spectrum" or k in {"spectrum", "telescope"}:
        lines = ''.join(f'<line x1="{cx+20}" y1="{cy-22+i*11}" x2="{cx+65}" y2="{cy-22+i*11}" stroke="{c}" stroke-width="4"/>' for i,c in enumerate(["#64aeff",purple,"#5bdde8",green,"#ffd263"]))
        return f'<circle cx="{cx-10}" cy="{cy-4}" r="35" fill="#ffbc53" stroke="{warm}" stroke-width="3"/>{lines}'
    if k == "ytterbium_ore" or k in {"ore", "mineral", "rock"}:
        return f'<path d="M{cx-48} {cy+38}l12-48 26-30 18 26 23-25 30 77z" fill="#385358" stroke="{green}" stroke-width="3"/><path d="M{cx-10} {cy-40}l8 76m29-51-15 51" stroke="#b8d9b9" stroke-width="3"/><circle cx="{cx-22}" cy="{cy+14}" r="7" fill="{warm}"/>'
    if k == "fluorine_cell" or k in {"electrolysis", "battery", "cell"}:
        return f'<path d="M{cx-37} {cy-31}v58l12 15h50l12-15v-58" fill="#17394a" stroke="{color}" stroke-width="4"/><path d="M{cx-37} {cy+4}h74" stroke="#5a9aae" stroke-width="3"/><path d="M{cx-15} {cy-48}v69m30-69v69" stroke="{warm}" stroke-width="4"/><circle cx="{cx-20}" cy="{cy-4}" r="4" fill="{pale}"/><circle cx="{cx+17}" cy="{cy-16}" r="4" fill="{pale}"/>'
    if k == "astatine_nucleus" or k in {"atom", "atomic", "nucleus"}:
        return f'<ellipse cx="{cx}" cy="{cy}" rx="43" ry="19" fill="none" stroke="{color}" stroke-width="3"/><ellipse cx="{cx}" cy="{cy}" rx="20" ry="43" fill="none" stroke="{purple}" stroke-width="3" transform="rotate(35 {cx} {cy})"/><circle cx="{cx}" cy="{cy}" r="10" fill="{warm}"/><circle cx="{cx+40}" cy="{cy-10}" r="5" fill="{pale}"/>'
    if k in {"mendelevium_cyclotron", "nobelium_accelerator", "accelerator", "particle_accelerator"}:
        return f'<ellipse cx="{cx}" cy="{cy}" rx="48" ry="34" fill="none" stroke="{color}" stroke-width="4"/><ellipse cx="{cx}" cy="{cy}" rx="31" ry="21" fill="none" stroke="#3d6f89" stroke-width="3"/><path d="M{cx-49} {cy-22}a48 34 0 0 1 78 0" fill="none" stroke="{warm}" stroke-width="5"/><circle cx="{cx+34}" cy="{cy-16}" r="6" fill="{warm}"/><circle cx="{cx}" cy="{cy}" r="6" fill="#5bdde8"/>'
    if k == "tennessine_collision" or k in {"collision", "fusion", "particle_collision"}:
        return f'<g stroke-width="5" fill="none"><path d="M{cx-52} {cy-30}L{cx-5} {cy-4}" stroke="#5bdde8"/><path d="M{cx-52} {cy+30}L{cx-5} {cy+4}" stroke="{warm}"/><path d="M{cx+52} {cy-30}L{cx+5} {cy-4}" stroke="{purple}"/><path d="M{cx+52} {cy+30}L{cx+5} {cy+4}" stroke="{green}"/></g><circle cx="{cx}" cy="{cy}" r="11" fill="{pale}"/><g stroke="{warm}" stroke-width="3">{''.join(f'<path d="M{cx} {cy}l{dx} {dy}"/>' for dx,dy in [(-28,-28),(28,-28),(-28,28),(28,28),(0,-43),(0,43)])}</g>'
    if k in {"molecule", "network", "concept_map"}:
        return f'<g stroke="{color}" stroke-width="5"><path d="M{cx-34} {cy+22}L{cx} {cy-28}L{cx+36} {cy+22}" fill="none"/></g><g fill="{pale}" stroke="{color}" stroke-width="3"><circle cx="{cx-34}" cy="{cy+22}" r="10"/><circle cx="{cx}" cy="{cy-28}" r="12"/><circle cx="{cx+36}" cy="{cy+22}" r="10"/></g>'
    if k in {"timeline", "history", "process"}:
        return f'<path d="M{cx-48} {cy}h91l-12-10m12 10-12 10" fill="none" stroke="{color}" stroke-width="4"/><g fill="{warm}"><circle cx="{cx-30}" cy="{cy}" r="7"/><circle cx="{cx}" cy="{cy}" r="7"/><circle cx="{cx+30}" cy="{cy}" r="7"/></g>'
    # Fallback icon is an atom, keeping all cards visually meaningful.
    return f'<ellipse cx="{cx}" cy="{cy}" rx="43" ry="18" fill="none" stroke="{color}" stroke-width="3"/><ellipse cx="{cx}" cy="{cy}" rx="18" ry="43" fill="none" stroke="{pale}" stroke-width="3" transform="rotate(35 {cx} {cy})"/><circle cx="{cx}" cy="{cy}" r="9" fill="{warm}"/>'


def _write_educational_poster_svg(poster_data: dict, output_path: Path) -> None:
    """Write an editable SVG companion for every structured poster design."""
    data = dict(poster_data)
    data.setdefault("design_variant", "cards")
    _write_redesigned_poster_svg(data, output_path)


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

    if not 8 <= len(prompt) <= 12000:
        print("Prompt must contain between 8 and 12000 characters", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[0-9a-f]{32}\.png", filename):
        print("Invalid output filename", file=sys.stderr)
        return 2
    allowed_widths = {512, 768, 1024, 1536, 1920}
    allowed_heights = {512, 576, 768, 1024, 1080, 1536, 2048}
    if width not in allowed_widths or height not in allowed_heights or (not poster and width * height > 1_100_000):
        print("Unsupported image dimensions or pixel budget", file=sys.stderr)
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
            svg_path = output_path.with_suffix(".svg")
            _write_educational_poster_svg(poster_data, svg_path)
            if not svg_path.is_file() or svg_path.stat().st_size < 1024:
                raise RuntimeError("Poster renderer did not save a valid vector SVG")
            _emit_event({
                "type": "progress", "stage": "rendering_poster", "label": "Poster typography complete",
                "step": 1, "total_steps": 1, "percent": 100, "elapsed_seconds": 0.0, "eta_seconds": 0.0,
            })
            _emit_event({"type": "saved", "filename": filename, "width": rendered_width,
                         "height": rendered_height, "size_bytes": output_path.stat().st_size,
                         "renderer": "typographic_poster", "svg_filename": svg_path.name,
                         "svg_size_bytes": svg_path.stat().st_size})
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

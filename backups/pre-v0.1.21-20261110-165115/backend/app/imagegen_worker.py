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


def _render_educational_poster(poster_data: dict, output_path: Path) -> tuple[int, int]:
    """Render a crisp, print-sized educational poster with real text glyphs."""
    if poster_data.get("layout") == "element_discovery":
        return _render_element_discovery_poster(poster_data, output_path)

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
        visual_key = str(raw_item.get("visual", "auto"))
        _draw_generic_poster_motif(draw, visual_key, x + 95, y + 105, accent if index % 2 == 0 else accent_warm)
        label_x = x + 28
        label_area_width = 142
        if label:
            label_font_current = label_font if len(label) <= 3 else _load_poster_font(30, True)
            label_lines = _wrap_poster_text(draw, label, label_font_current, label_area_width, 2)
            label_y = y + 185 if len(label_lines) == 1 else y + 166
            for label_line in label_lines:
                draw.text((label_x, label_y), label_line, font=label_font_current, fill=primary)
                label_y += 38
        else:
            number = f"{index + 1:02d}"
            number_box = draw.textbbox((0, 0), number, font=index_font)
            draw.text((x + 95 - (number_box[2] - number_box[0]) / 2, y + 220), number, font=index_font, fill=accent)

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
        metadata = [
            " · ".join(part for part in [str(raw_item.get("discoverer", "")).strip(), str(raw_item.get("location", "")).strip()] if part),
            str(raw_item.get("institution", "")).strip(),
            str(raw_item.get("method", "")).strip(),
        ]
        metadata_font = _load_poster_font(16, True)
        for metadata_text in metadata:
            if not metadata_text or item_y > y2 - 92:
                continue
            metadata_lines = _wrap_poster_text(draw, metadata_text, metadata_font, text_width, 1)
            if metadata_lines:
                draw.text((text_x, item_y), metadata_lines[0], font=metadata_font, fill=accent)
                item_y += 24
        if detail:
            body_font_current = _load_poster_font(18, False)
            body_lines = _wrap_poster_text(draw, detail, body_font_current, text_width, 2)
            line_height = 24
            for line in body_lines:
                if item_y > y2 - 55:
                    break
                draw.text((text_x, item_y), line, font=body_font_current, fill=secondary)
                item_y += line_height
        significance = str(raw_item.get("significance", "")).strip()
        if significance and item_y < y2 - 42:
            significance_font = _load_poster_font(15, True)
            sig_lines = _wrap_poster_text(draw, significance, significance_font, text_width, 1)
            if sig_lines:
                draw.text((text_x, item_y + 2), sig_lines[0], font=significance_font, fill=accent_warm)

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
    """Write a true editable vector SVG companion (real text and vector artwork)."""
    width, height = 1536, 2048
    items = poster_data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 12:
        raise ValueError("SVG poster requires between 1 and 12 entries")
    colors = {"halogen":"#57d3e1", "noble_gas":"#ffb964", "lanthanoid":"#7ed7a2", "actinoid":"#ba96e8"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="poster-title poster-desc">',
        '<title id="poster-title">' + _svg_escape(poster_data.get("title", "Educational poster")) + '</title>',
        '<desc id="poster-desc">Editable educational infographic created locally by JARVIS. Text and illustrations are vector elements.</desc>',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#071221"/><stop offset="1" stop-color="#0d2739"/></linearGradient><pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M48 0H0V48" fill="none" stroke="#1a4055" stroke-width="1" opacity=".35"/></pattern></defs>',
        '<rect width="1536" height="2048" fill="url(#bg)"/><rect width="1536" height="2048" fill="url(#grid)" opacity=".28"/>',
        '<g font-family="Inter, Segoe UI, Arial, sans-serif">',
        '<text x="72" y="58" font-size="20" font-weight="700" letter-spacing="3" fill="#5bdde8">J.A.R.V.I.S.  /  EDUCATIONAL VISUAL SERIES</text>',
    ]
    title = str(poster_data.get("title", "EDUCATIONAL POSTER"))
    for idx, line in enumerate(_svg_wrap(title, 42, 2)):
        parts.append(f'<text x="72" y="{135 + idx*70}" font-size="56" font-weight="800" fill="#eff7fa">{_svg_escape(line)}</text>')
    subtitle = str(poster_data.get("subtitle", ""))
    for idx, line in enumerate(_svg_wrap(subtitle, 100, 2)):
        parts.append(f'<text x="72" y="{225 + idx*34}" font-size="23" fill="#b3cad6">{_svg_escape(line)}</text>')
    intro = str(poster_data.get("intro", ""))
    if intro:
        for idx, line in enumerate(_svg_wrap(intro, 145, 2)):
            parts.append(f'<text x="72" y="{290 + idx*27}" font-size="17" fill="#9eb9c8">{_svg_escape(line)}</text>')
    chips = poster_data.get("category_chips", [])
    chip_x, chip_y = 72, 326 if not intro else 365
    for chip in chips[:4] if isinstance(chips, list) else []:
        c = colors.get(str(chip.get("category", "")), "#5bdde8")
        label = f'{chip.get("label", chip.get("category", "CATEGORY"))} · {chip.get("count", "")}'
        w = min(430, max(180, 18 + len(label)*9))
        parts.append(f'<rect x="{chip_x}" y="{chip_y}" width="{w}" height="34" rx="12" fill="#102b3d" stroke="{c}" stroke-width="2"/><text x="{chip_x+14}" y="{chip_y+23}" font-size="14" font-weight="700" fill="{c}">{_svg_escape(label)}</text>')
        chip_x += w + 12
        if chip_x > 1300:
            break
    content_top = 385 if not intro else 420
    footer_top = 1905
    columns = 2 if len(items) > 4 else 1
    rows = (len(items) + columns - 1) // columns
    gap_x, gap_y, margin = 22, 16, 72
    card_w = (width - margin*2 - gap_x*(columns-1)) // columns
    card_h = min(294, (footer_top - content_top - gap_y*(rows-1)) // rows)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        col, row = index % columns, index // columns
        x, y = margin + col*(card_w+gap_x), content_top + row*(card_h+gap_y)
        category = str(item.get("category", ""))
        accent = colors.get(category, "#5bdde8" if index % 2 == 0 else "#ffb162")
        parts.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="22" fill="#0d2234" stroke="#264c60" stroke-width="2"/><rect x="{x}" y="{y+18}" width="7" height="{card_h-36}" rx="3" fill="{accent}"/>')
        # Sequence and topic-specific vector illustration.
        parts.append(f'<circle cx="{x+43}" cy="{y+40}" r="20" fill="#1b3d4f" stroke="{accent}" stroke-width="2"/><text x="{x+43}" y="{y+46}" text-anchor="middle" font-size="13" font-weight="700" fill="{accent}">{index+1:02d}</text>')
        visual = str(item.get("visual", "auto"))
        parts.append(_svg_motif(visual, x+94, y+125, accent))
        label = str(item.get("label", "")).strip()
        if label:
            parts.append(f'<text x="{x+94}" y="{y+218}" text-anchor="middle" font-size="42" font-weight="800" fill="#eff7fa">{_svg_escape(label)}</text>')
        atomic = str(item.get("atomic_number", "")).strip()
        if atomic:
            parts.append(f'<text x="{x+94}" y="{y+247}" text-anchor="middle" font-size="13" fill="#90aebb">ATOMIC NO. {_svg_escape(atomic)}</text>')
        tx = x+188
        text_width = card_w - (tx-x) - 24
        item_title = str(item.get("title", "")).strip()
        for li, line in enumerate(_svg_wrap(item_title, 42, 2)):
            parts.append(f'<text x="{tx}" y="{y+38+li*28}" font-size="22" font-weight="750" fill="#eff7fa">{_svg_escape(line)}</text>')
        date = str(item.get("date", "")).strip()
        title_y = y+38+min(2,len(_svg_wrap(item_title,42,2)))*28
        if date:
            dw = min(text_width, max(130, len(date)*8+28))
            parts.append(f'<rect x="{tx}" y="{title_y+5}" width="{dw}" height="28" rx="9" fill="#194353"/><text x="{tx+12}" y="{title_y+24}" font-size="14" font-weight="700" fill="#ffb162">{_svg_escape(date)}</text>')
        cursor_y = title_y + 56
        metadata = []
        for key, prefix in (("discoverer", "DISCOVERER"), ("location", "LOCATION"), ("institution", "INSTITUTION")):
            value = str(item.get(key, "")).strip()
            if value:
                metadata.append((prefix, value))
        # Curated element data historically combines discoverer and location in one field.
        for prefix, value in metadata:
            line = f"{prefix}: {value}"
            for mi, wrapped in enumerate(_svg_wrap(line, 52, 1)):
                if cursor_y > y+card_h-76:
                    break
                parts.append(f'<text x="{tx}" y="{cursor_y}" font-size="13" font-weight="650" fill="{accent}">{_svg_escape(wrapped)}</text>')
                cursor_y += 18
        method = str(item.get("method", "")).strip()
        detail = str(item.get("detail", "")).strip()
        significance = str(item.get("significance", "")).strip()
        combined = " ".join(part for part in (method, detail, significance) if part)
        for di, wrapped in enumerate(_svg_wrap(combined, 57, 3)):
            if cursor_y > y+card_h-45:
                break
            parts.append(f'<text x="{tx}" y="{cursor_y+3}" font-size="13" fill="#b3cad6">{_svg_escape(wrapped)}</text>')
            cursor_y += 18
        classification = str(item.get("classification", "")).strip()
        if classification:
            class_text = classification.upper()
            cw = min(text_width, max(120, len(class_text)*7+22))
            parts.append(f'<rect x="{tx}" y="{y+card_h-32}" width="{cw}" height="22" rx="7" fill="#132d3e" stroke="{accent}" stroke-width="1"/><text x="{tx+10}" y="{y+card_h-17}" font-size="11" font-weight="700" fill="{accent}">{_svg_escape(class_text)}</text>')
    parts.append(f'<path d="M72 {footer_top}H1464" stroke="#254b5e" stroke-width="2"/>')
    footer = str(poster_data.get("footer", ""))
    for idx, line in enumerate(_svg_wrap(footer, 145, 1)):
        parts.append(f'<text x="72" y="{footer_top+29+idx*19}" font-size="14" fill="#c0d3dc">{_svg_escape(line)}</text>')
    takeaways = poster_data.get("key_takeaways", [])
    if isinstance(takeaways, list) and takeaways:
        takeaway = "KEY TAKEAWAY: " + " · ".join(str(x) for x in takeaways[:3])
        for idx, line in enumerate(_svg_wrap(takeaway, 145, 1)):
            parts.append(f'<text x="72" y="{footer_top+54+idx*18}" font-size="12" fill="#5bdde8">{_svg_escape(line)}</text>')
    sources = str(poster_data.get("sources", "")).strip()
    for idx, line in enumerate(_svg_wrap(sources, 150, 1)):
        parts.append(f'<text x="72" y="{height-34-idx*16}" font-size="11" fill="#7895a6">{_svg_escape(line)}</text>')
    parts.append('<text x="1464" y="2000" text-anchor="end" font-size="13" font-weight="700" letter-spacing="2" fill="#5bdde8">JARVIS / LOCAL SVG</text>')
    parts.append('</g></svg>')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")
    content = output_path.read_text(encoding="utf-8")
    if not content.startswith("<svg") and "<svg " not in content[:500]:
        raise RuntimeError("Vector poster output is not a valid SVG document")
    if "<text" not in content or "<path" not in content:
        raise RuntimeError("Vector poster is missing editable text or vector artwork")


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

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

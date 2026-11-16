from __future__ import annotations

import subprocess
from typing import Any

import psutil


GAME_PROCESS_MARKERS = (
    "valorant-win64-shipping", "valorant.exe", "cs2.exe", "counter-strike",
    "minecraft", "r5apex.exe", "apex_legends", "fortniteclient",
    "overwatch.exe", "destiny2.exe", "eldenring.exe", "gta5.exe", "cyberpunk2077",
    "witcher3.exe", "dota2.exe", "league of legends.exe", "rainbowsix.exe",
    "helldivers2.exe", "bg3.exe", "baldurs gate 3", "starfield.exe",
)


def _number(value: str):
    value = value.strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def gpu_stats() -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        line = result.stdout.strip().splitlines()[0]
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 7:
            raise ValueError("Unexpected nvidia-smi output")
        return {
            "available": True, "name": parts[0], "utilization_percent": _number(parts[1]),
            "vram_used_mb": _number(parts[2]), "vram_total_mb": _number(parts[3]),
            "temperature_c": _number(parts[4]), "power_w": _number(parts[5]),
            "power_limit_w": _number(parts[6]),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def detect_game_process() -> dict[str, Any]:
    """Inspect process names only; do not enumerate paths, windows, or user files."""
    matches: list[str] = []
    try:
        for process in psutil.process_iter(attrs=["name"]):
            try:
                name = str((process.info or {}).get("name") or "").casefold()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            if name and any(marker in name for marker in GAME_PROCESS_MARKERS):
                if name not in matches:
                    matches.append(name)
                if len(matches) >= 4:
                    break
    except Exception:
        pass
    return {"detected": bool(matches), "processes": matches}


def resource_policy(gpu: dict[str, Any] | None = None, vm: Any | None = None) -> dict[str, Any]:
    """Return conservative local inference scheduling advice from live resource pressure."""
    gpu = gpu if gpu is not None else gpu_stats()
    vm = vm if vm is not None else psutil.virtual_memory()
    games = detect_game_process()
    available_ram_gb = round(float(vm.available) / (1024 ** 3), 2)
    free_vram_mb = None
    if gpu.get("available") and gpu.get("vram_total_mb") is not None and gpu.get("vram_used_mb") is not None:
        free_vram_mb = max(0, round(float(gpu["vram_total_mb"]) - float(gpu["vram_used_mb"]), 1))

    low_vram = free_vram_mb is not None and free_vram_mb < 2800
    hot_gpu = gpu.get("temperature_c") is not None and float(gpu["temperature_c"]) >= 86
    low_ram = available_ram_gb < 3.5
    constrained = low_ram or low_vram or hot_gpu

    # The 9B primary model needs several GB of host memory. Only force CPU
    # inference when there is a reasonable RAM reserve; otherwise report the
    # limitation rather than moving a large model into an already pressured OS.
    cpu_only = (games["detected"] or low_vram or hot_gpu) and available_ram_gb >= 8.0

    if games["detected"]:
        mode = "gaming"
        keep_alive = "0s"
        reason = (
            "A recognized game is active. Ollama is restricted to CPU inference and releases model weights after each request."
            if cpu_only else
            "A game is active, but available system RAM is too low for a safe CPU-only model fallback; GPU scheduling is constrained to short residency."
        )
    elif constrained:
        mode = "conserve"
        keep_alive = "0s"
        reason = (
            "VRAM or GPU temperature is under pressure; use CPU inference and release model weights after each request."
            if cpu_only else
            "System memory, VRAM, or GPU temperature is under pressure; release model allocations after each request."
        )
    else:
        mode = "normal"
        keep_alive = "10m"
        reason = "Resources are within normal limits; short model reuse is enabled for conversational responsiveness."

    return {
        "mode": mode,
        "gaming_detected": games["detected"],
        "game_processes": games["processes"],
        "available_ram_gb": available_ram_gb,
        "free_vram_mb": free_vram_mb,
        "keep_alive": keep_alive,
        "allow_prewarm": mode == "normal",
        "cpu_only": cpu_only,
        "inference_device": "cpu" if cpu_only else "ollama-auto",
        "reason": reason,
        "policy": "adaptive-sequential",
    }


def system_stats() -> dict[str, Any]:
    cpu = psutil.cpu_percent(interval=0.15)
    vm = psutil.virtual_memory()
    gpu = gpu_stats()
    return {
        "cpu_percent": cpu,
        "ram_total_gb": round(vm.total / (1024 ** 3), 2),
        "ram_used_gb": round((vm.total - vm.available) / (1024 ** 3), 2),
        "ram_percent": vm.percent,
        "gpu": gpu,
        "resource_policy": resource_policy(gpu, vm),
    }

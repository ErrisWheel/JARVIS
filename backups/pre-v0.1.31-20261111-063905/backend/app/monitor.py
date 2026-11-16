import subprocess
import psutil
from typing import Any


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


def system_stats() -> dict[str, Any]:
    cpu = psutil.cpu_percent(interval=0.15)
    vm = psutil.virtual_memory()
    return {
        "cpu_percent": cpu,
        "ram_total_gb": round(vm.total / (1024 ** 3), 2),
        "ram_used_gb": round((vm.total - vm.available) / (1024 ** 3), 2),
        "ram_percent": vm.percent,
        "gpu": gpu_stats(),
    }

"""GPU/CPU detection and live stats for Whisper segmentation."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

_prefer_device = os.environ.get("WHISPER_DEVICE", "cuda").strip().lower()


def resolve_whisper_device() -> tuple[str, dict[str, Any]]:
    """Pick cuda when available (unless WHISPER_DEVICE=cpu)."""
    info: dict[str, Any] = {
        "device": "cpu",
        "requested": _prefer_device,
        "cuda_available": False,
        "gpu_name": None,
        "cuda_version": None,
        "torch_version": None,
        "hint": None,
    }

    has_nvidia_smi = shutil.which("nvidia-smi") is not None
    if has_nvidia_smi:
        smi_name = _nvidia_gpu_name()
        if smi_name:
            info["gpu_name"] = smi_name

    try:
        import torch

        info["torch_version"] = torch.__version__
        info["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["cuda_version"] = torch.version.cuda
            info["gpu_name"] = torch.cuda.get_device_name(0)
            if _prefer_device != "cpu":
                info["device"] = "cuda"
                return "cuda", info
        elif has_nvidia_smi and _prefer_device != "cpu":
            info["hint"] = (
                "NVIDIA GPU detected but PyTorch CUDA is unavailable. "
                "Reinstall CUDA PyTorch: pip install torch --index-url "
                "https://download.pytorch.org/whl/cu128"
            )
    except ImportError:
        if has_nvidia_smi and _prefer_device != "cpu":
            info["hint"] = "Install PyTorch with CUDA support for GPU transcription."

    return "cpu", info


def _nvidia_gpu_name() -> str | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode == 0:
            name = result.stdout.strip().split("\n")[0].strip()
            return name or None
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _nvidia_smi_stats() -> dict[str, int | str | None]:
    stats: dict[str, int | str | None] = {
        "gpu_util_percent": None,
        "gpu_memory_used_mb": None,
        "gpu_memory_total_mb": None,
    }
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode != 0:
            return stats
        parts = [part.strip() for part in result.stdout.strip().split(",")]
        if len(parts) >= 3:
            stats["gpu_util_percent"] = int(parts[0])
            stats["gpu_memory_used_mb"] = int(parts[1])
            stats["gpu_memory_total_mb"] = int(parts[2])
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return stats


def gpu_snapshot() -> dict[str, Any] | None:
    """Lightweight GPU-only snapshot for the global activity indicator.

    Returns None when no NVIDIA GPU/driver is available so callers can simply
    omit GPU info rather than rendering empty fields.
    """
    stats = _nvidia_smi_stats()
    util = stats.get("gpu_util_percent")
    mem_used = stats.get("gpu_memory_used_mb")
    mem_total = stats.get("gpu_memory_total_mb")
    name = _nvidia_gpu_name()
    if util is None and mem_total is None and name is None:
        return None
    return {
        "name": name,
        "utilization_percent": util,
        "memory_used_mb": mem_used,
        "memory_total_mb": mem_total,
    }


def sample_hardware_stats(active_device: str, device_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Snapshot CPU/RAM and (when on CUDA) GPU utilization."""
    base = dict(device_info or {})
    stats: dict[str, Any] = {
        "device": active_device,
        "gpu_name": base.get("gpu_name"),
        "cuda_available": base.get("cuda_available", False),
        "cuda_version": base.get("cuda_version"),
        "torch_version": base.get("torch_version"),
        "hint": base.get("hint"),
        "gpu_util_percent": None,
        "gpu_memory_used_mb": None,
        "gpu_memory_total_mb": None,
        "torch_memory_used_mb": None,
        "cpu_percent": None,
        "ram_used_mb": None,
        "ram_total_mb": None,
    }

    try:
        import psutil

        stats["cpu_percent"] = int(psutil.cpu_percent(interval=None))
        vm = psutil.virtual_memory()
        stats["ram_used_mb"] = int((vm.total - vm.available) / (1024 * 1024))
        stats["ram_total_mb"] = int(vm.total / (1024 * 1024))
    except ImportError:
        pass
    except Exception:
        pass

    if active_device == "cuda":
        stats.update(_nvidia_smi_stats())
        try:
            import torch

            if torch.cuda.is_available():
                stats["torch_memory_used_mb"] = int(torch.cuda.memory_allocated(0) / (1024 * 1024))
                if not stats.get("gpu_name"):
                    stats["gpu_name"] = torch.cuda.get_device_name(0)
        except Exception:
            pass

    return stats

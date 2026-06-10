"""GPU detection and resource management utilities."""

import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def get_gpu_info() -> dict[str, Any]:
    """Detect GPU information using nvidia-smi.

    Returns:
        Dictionary with GPU model, memory, CUDA version, and utilization.
        Returns fallback dict if no GPU is available.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.free,memory.used,utilization.gpu,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        gpus = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                gpus.append(
                    {
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_total_mb": float(parts[2]),
                        "memory_free_mb": float(parts[3]),
                        "memory_used_mb": float(parts[4]),
                        "utilization_percent": float(parts[5]),
                        "driver_version": parts[6] if len(parts) > 6 else "unknown",
                    }
                )

        cuda_version = "unknown"
        try:
            cuda_result = subprocess.run(
                ["nvcc", "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            for line in cuda_result.stdout.split("\n"):
                if "release" in line:
                    cuda_version = line.strip()
                    break
        except Exception:
            pass

        return {
            "available": True,
            "cuda_version": cuda_version,
            "gpus": gpus,
            "recommended_batch_size": _recommend_batch_size(gpus),
        }

    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return {
            "available": False,
            "cuda_version": "none",
            "gpus": [],
            "recommended_batch_size": 1,
            "reason": "nvidia-smi not found or no NVIDIA GPU available",
        }


def _recommend_batch_size(gpus: list[dict]) -> int:
    """Recommend batch size based on GPU memory.

    Args:
        gpus: List of GPU info dictionaries.

    Returns:
        Recommended batch size (1 for CPU fallback).
    """
    if not gpus:
        return 1

    max_memory = max(gpu["memory_total_mb"] for gpu in gpus)

    if max_memory >= 80000:  # A100 80GB
        return 4
    if max_memory >= 40000:  # A100 40GB / A6000
        return 2
    if max_memory >= 24000:  # RTX 4090 / A5000
        return 2
    if max_memory >= 16000:  # RTX 4080 / V100
        return 1
    return 1


def check_gpu_available(min_memory_mb: float = 1000.0) -> dict[str, Any]:
    """Check if GPU with minimum memory is available.

    Args:
        min_memory_mb: Minimum free memory required in MB.

    Returns:
        Status dict with 'available' bool and details.
    """
    info = get_gpu_info()
    if not info["available"]:
        return {
            "available": False,
            "reason": info.get("reason", "No GPU detected"),
        }

    suitable_gpus = [
        gpu
        for gpu in info["gpus"]
        if gpu["memory_free_mb"] >= min_memory_mb
    ]

    if suitable_gpus:
        return {
            "available": True,
            "gpus": suitable_gpus,
            "best_gpu": max(suitable_gpus, key=lambda g: g["memory_free_mb"]),
        }

    return {
        "available": False,
        "reason": f"No GPU with >= {min_memory_mb}MB free memory",
        "gpus": info["gpus"],
    }

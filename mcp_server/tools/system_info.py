"""System information and health check tools."""

import logging
import shutil
import subprocess
from typing import Any

from mcp_server.utils.gpu_utils import get_gpu_info, check_gpu_available

logger = logging.getLogger(__name__)


def health_check() -> dict[str, Any]:
    """Perform comprehensive health check of the protein design environment.

    Returns:
        Structured dict with CUDA status, GPU info, tool availability,
        conda environment, and disk space.
    """
    result: dict[str, Any] = {
        "status": "healthy",
        "cuda": {"available": False},
        "gpu": get_gpu_info(),
        "tools": {},
        "disk": {},
        "conda": {"active": False, "env_name": None},
    }

    # Check CUDA
    try:
        cuda_result = subprocess.run(
            ["nvcc", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        result["cuda"]["available"] = cuda_result.returncode == 0
        if cuda_result.returncode == 0:
            for line in cuda_result.stdout.split("\n"):
                if "release" in line:
                    result["cuda"]["version"] = line.strip()
                    break
    except Exception as exc:
        result["cuda"]["error"] = str(exc)

    # Check tool availability
    tools_to_check = {
        "python": ["python", "--version"],
        "conda": ["conda", "--version"],
        "docker": ["docker", "--version"],
    }

    for name, cmd in tools_to_check.items():
        tool_path = shutil.which(cmd[0])
        if tool_path:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                result["tools"][name] = {
                    "installed": True,
                    "path": tool_path,
                    "version": proc.stdout.strip() or proc.stderr.strip(),
                }
            except Exception as exc:
                result["tools"][name] = {
                    "installed": True,
                    "path": tool_path,
                    "error": str(exc),
                }
        else:
            result["tools"][name] = {"installed": False}

    # Check protein design tools
    try:
        from mcp_server.tools.tool_installer import check_all_tools
        tool_status = check_all_tools()
        result["protein_tools"] = tool_status
        if not tool_status.get("all_ready", False):
            result["status"] = "degraded"
            missing = [t for t, s in tool_status.get("tools", {}).items() if not s.get("installed")]
            result.setdefault("warnings", []).append(
                f"Missing tools: {', '.join(missing)}. "
                "Use check_all_tools or configure_tool_path to set them up."
            )
    except Exception as exc:
        result["protein_tools"] = {"error": str(exc)}

    # Check conda environment
    try:
        conda_info = subprocess.run(
            ["conda", "info", "--envs"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if conda_info.returncode == 0:
            result["conda"]["active"] = True
            # Try to get current env name
            env_result = subprocess.run(
                ["conda", "info", "--base"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if env_result.returncode == 0:
                result["conda"]["base_path"] = env_result.stdout.strip()
    except Exception:
        pass

    # Check disk space
    try:
        disk = shutil.disk_usage("/tmp")
        result["disk"] = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "usage_percent": round(disk.used / disk.total * 100, 1),
        }
    except Exception as exc:
        result["disk"]["error"] = str(exc)

    # Overall status
    if not result["gpu"]["available"]:
        result["status"] = "degraded"
        result["warnings"] = ["No GPU detected. Protein design tools will run slowly or fail."]

    return result


def get_gpu_status() -> dict[str, Any]:
    """Get detailed GPU status.

    Returns:
        GPU info with availability check.
    """
    gpu_info = get_gpu_info()
    availability = check_gpu_available(min_memory_mb=1000.0)

    # Add GPU architecture recommendations
    recommendations = []
    if gpu_info.get("available"):
        for gpu in gpu_info.get("gpus", []):
            arch = gpu.get("compute_capability", "")
            name = gpu.get("name", "").lower()
            if arch.startswith(("7.", "6.", "5.")) or "v100" in name:
                recommendations.append({
                    "gpu": gpu.get("name"),
                    "compute_capability": arch,
                    "recommended_env": {
                        "XLA_FLAGS": "--xla_gpu_cuda_data_dir=/usr/local/cuda",
                        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
                    },
                    "reason": "Older GPU architecture detected. XLA_FLAGS may be needed for JAX/TensorFlow.",
                })
            elif arch.startswith(("8.", "9.")):
                recommendations.append({
                    "gpu": gpu.get("name"),
                    "compute_capability": arch,
                    "recommended_env": {
                        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
                    },
                    "reason": "Modern GPU architecture. Standard settings should work.",
                })

    return {
        "gpu": gpu_info,
        "suitable_for_design": availability["available"],
        "recommendations": recommendations,
        **availability,
    }

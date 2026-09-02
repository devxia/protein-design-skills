#!/usr/bin/env python3
"""PreToolUse hook: GPU resource safety check before tool execution.

Blocking policy:
- Blocking (exit 2) only applies to GPU-required tools (see
  ``GPU_REQUIRED_TOOLS`` below) when a GPU is present but its free memory is
  below the threshold. CPU-capable tools (ESMFold, OmegaFold, Boltz, ...)
  are downgraded to a warning because upstream tools fall back to CPU
  themselves — the hook must not refuse on their behalf.
- Missing GPU (probe returns an empty list) is always warning-only: CPU
  fallback is the upstream tool's own behaviour.
- Probe failure (nvidia-smi unavailable) fails open (allow with warning).

Exit codes:
  0 = allow execution
  2 = block execution (stderr explains why)
  other = fail-open (allow execution with warning)
"""
import json
import shutil
import subprocess
import sys
import traceback
from typing import Any
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from protein_design.utils import (
    get_hook_invoked_runner,
    hook_advisory_output,
    probe_gpus,
    read_hook_input,
)


# Tools that require a GPU in practice (per skills/ hardware notes):
# - run_rfdiffusion: structure-generation — "No GPU? Use Google Colab"
# - run_alphafold3:  install-guide — NVIDIA GPU with 8GB+ VRAM required
# - run_chai1:       chai1-validation — "CUDA GPU with bfloat16 support"
# - run_openfold3:   structure-validation alternatives table — GPU "Yes"
# - run_protenix:    protenix-validation — "CUDA-compatible GPU"
# - run_colabfold:   colabfold-alternative — GPU memory requirements, no
#   documented local CPU path (quickstart steers CPU-only users to ESMFold)
# Everything else matched by the PreToolUse matcher (run_esmfold,
# run_omegafold, run_boltz, run_proteinmpnn, run_ligandmpnn, run_esm_if1,
# run_pdbfixer, run_filtering) is CPU-capable per skills/ and only warns.
GPU_REQUIRED_TOOLS = (
    "run_rfdiffusion",
    "run_alphafold3",
    "run_chai1",
    "run_openfold3",
    "run_protenix",
    "run_colabfold",
)


def check_gpu(min_free_mb: int = 1000, gpu_required: bool = False) -> tuple[bool, str]:
    """Check GPU availability and free memory (fails open on probe errors).

    No-GPU hosts are warning-only; blocking on low free memory only applies
    when the invoked tool is GPU-required (``gpu_required=True``).
    """
    gpus = probe_gpus()
    if gpus is None:
        return True, "GPU probe failed (CPU-only machine or nvidia-smi error) — allowing"
    if not gpus:
        return True, "No NVIDIA GPU detected — warning only; CPU fallback is up to the tool"
    for gpu in gpus:
        if gpu["free_mb"] >= min_free_mb:
            return True, f"GPU {gpu['name']} has {int(gpu['free_mb'])}MB free"
    if gpu_required:
        return False, f"GPU free memory < {min_free_mb}MB (GPU-required tool)"
    return True, f"GPU free memory < {min_free_mb}MB — warning only (tool can fall back to CPU)"


def check_disk(min_free_gb: int = 1) -> tuple[bool, str]:
    """Check available disk space."""
    try:
        disk = shutil.disk_usage("/tmp")
        free_gb = disk.free / (1024**3)
        if free_gb < min_free_gb:
            return False, f"Disk space critically low: {free_gb:.1f}GB free (need {min_free_gb}GB)"
        return True, f"Disk: {free_gb:.1f}GB free"
    except Exception as exc:
        return True, f"Disk check error: {exc}"


def _is_gpu_required_invocation(data: dict[str, Any]) -> bool:
    """Detect whether the payload invokes a GPU-required runner script."""
    return get_hook_invoked_runner(data) in GPU_REQUIRED_TOOLS


def main() -> int:
    """Main entry point."""
    try:
        data = read_hook_input()
    except Exception:
        # A malformed or unstructured payload must never block execution.
        return 0
    if not isinstance(data, dict) or get_hook_invoked_runner(data) is None:
        return 0

    gpu_ok, gpu_msg = check_gpu(gpu_required=_is_gpu_required_invocation(data))
    disk_ok, disk_msg = check_disk()

    if not gpu_ok:
        print(f"GPU check failed: {gpu_msg}", file=sys.stderr)
        return 2
    if not disk_ok:
        print(f"Disk check failed: {disk_msg}", file=sys.stderr)
        return 2

    messages = []
    if "warning" in gpu_msg or "No NVIDIA GPU" in gpu_msg:
        messages.append(f"GPU check: {gpu_msg}")

    # Optional warning about low total GPU memory for AlphaFold3.
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        total_mb_str = result.stdout.strip().split("\n")[0].strip()
        if total_mb_str and float(total_mb_str) < 16000:
            messages.append(
                f"Low GPU memory detected ({int(float(total_mb_str))}MB). AlphaFold3 may be slow."
            )
    except Exception:
        pass

    output = hook_advisory_output("\n".join(messages))
    if output:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

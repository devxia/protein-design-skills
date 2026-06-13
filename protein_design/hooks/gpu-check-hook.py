#!/usr/bin/env python3
"""PreToolUse hook: GPU resource safety check before tool execution.

Blocks tool execution if GPU is unavailable or disk space is critically low.
Exit codes:
  0 = allow execution
  2 = block execution (stderr explains why)
  other = fail-open (allow execution with warning)
"""
import shutil
import subprocess
import sys


def check_gpu(min_free_mb: int = 1000) -> tuple[bool, str]:
    """Check GPU availability and free memory."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        if not lines:
            return False, "No NVIDIA GPU detected"

        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                free_mb = float(parts[1])
                if free_mb >= min_free_mb:
                    return True, f"GPU {parts[0]} has {int(free_mb)}MB free"

        return False, f"GPU free memory < {min_free_mb}MB"
    except FileNotFoundError:
        return False, "nvidia-smi not found (no NVIDIA GPU)"
    except subprocess.TimeoutExpired:
        return True, "GPU check timed out (allowing)"
    except Exception as exc:
        return True, f"GPU check error: {exc} (allowing)"


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


def main() -> int:
    """Main entry point."""
    # Tool arguments are passed as JSON via environment or stdin
    # We do generic checks regardless of specific tool

    gpu_ok, gpu_msg = check_gpu()
    disk_ok, disk_msg = check_disk()

    if not gpu_ok:
        print(f"⚠️  GPU check failed: {gpu_msg}", file=sys.stderr)
        return 2

    if not disk_ok:
        print(f"⚠️  Disk check failed: {disk_msg}", file=sys.stderr)
        return 2

    # Optional: warn about low GPU memory for AlphaFold3
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        total_mb_str = result.stdout.strip().split("\n")[0].strip()
        if not total_mb_str:
            return 0
        total_mb = float(total_mb_str)
        if total_mb < 16000:
            print(f"ℹ️  Low GPU memory detected ({int(total_mb)}MB). AlphaFold3 may be slow.", file=sys.stderr)
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

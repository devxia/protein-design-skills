"""Conda environment utilities for cross-env tool execution.

Many protein design tools (RFdiffusion, ProteinMPNN, AlphaFold3) are
installed in separate conda environments. This module provides helpers
to run commands inside those environments via `conda run`.

Design principles:
  - If conda_env is configured → wrap with `conda run -n <env>`
  - If no conda_env → run with current Python (backward compatible)
  - Never activate/ deactivate shells; `conda run` is stateless
"""

import logging
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def check_conda_env(env_name: str) -> dict[str, Any]:
    """Check whether a conda environment exists and is usable.

    Args:
        env_name: Name of the conda environment.

    Returns:
        Dict with exists, python_path, and packages info.
    """
    result: dict[str, Any] = {"exists": False, "env_name": env_name}

    # Check conda binary
    conda_bin = shutil.which("conda")
    if not conda_bin:
        result["error"] = "conda not found in PATH"
        return result

    # List envs and check
    try:
        proc = subprocess.run(
            ["conda", "env", "list", "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if proc.returncode != 0:
            result["error"] = f"conda env list failed: {proc.stderr}"
            return result

        import json
        envs_data = json.loads(proc.stdout)
        envs = envs_data.get("envs", [])

        # envs list contains full paths like /home/user/miniconda3/envs/SE3nv
        matched = None
        for env_path in envs:
            if env_path.endswith(f"/{env_name}") or env_path.endswith(f"\\{env_name}"):
                matched = env_path
                break

        if not matched:
            result["error"] = f"Environment '{env_name}' not found"
            result["available_envs"] = [p.split("/")[-1].split("\\")[-1] for p in envs]
            return result

        result["exists"] = True
        result["path"] = matched

        # Find Python inside the env
        python_candidates = [
            f"{matched}/bin/python",
            f"{matched}/Scripts/python.exe",
        ]
        for py in python_candidates:
            if shutil.which(py):
                result["python"] = py
                break

        # Check key packages
        try:
            pkg_proc = subprocess.run(
                ["conda", "run", "-n", env_name, "python", "-c",
                 "import sys; print(sys.version); import torch; print('torch:', torch.__version__)"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            if pkg_proc.returncode == 0:
                result["python_version"] = pkg_proc.stdout.strip().split("\n")[0]
                if len(pkg_proc.stdout.strip().split("\n")) > 1:
                    result["torch_version"] = pkg_proc.stdout.strip().split("\n")[1]
            else:
                result["python_version"] = "unknown (import check failed)"
        except Exception as exc:
            result["python_version"] = f"unknown ({exc})"

    except Exception as exc:
        result["error"] = str(exc)

    return result


def build_conda_cmd(cmd: list[str], conda_env: str | None = None) -> list[str]:
    """Wrap a command with `conda run` if a conda environment is specified.

    Args:
        cmd: The base command list (e.g., ["python", "script.py", "--flag"]).
        conda_env: Optional conda environment name.

    Returns:
        The wrapped command list.
    """
    if not conda_env:
        return cmd

    # Use conda run --live-stream for real-time stdout/stderr
    # --no-capture-output is alias for --live-stream in newer conda
    wrapper = ["conda", "run", "-n", conda_env, "--live-stream"]
    return wrapper + cmd


def run_in_conda(
    cmd: list[str],
    conda_env: str | None = None,
    **subprocess_kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a subprocess command inside a conda environment.

    This is a convenience wrapper around subprocess.run that automatically
    prepends `conda run -n <env>` when conda_env is given.

    Args:
        cmd: Base command list.
        conda_env: Optional conda environment name.
        **subprocess_kwargs: Passed to subprocess.run.

    Returns:
        CompletedProcess result.
    """
    wrapped = build_conda_cmd(cmd, conda_env)
    logger.info("Executing: %s", " ".join(wrapped))
    return subprocess.run(wrapped, **subprocess_kwargs)


def run_in_conda_popen(
    cmd: list[str],
    conda_env: str | None = None,
    **subprocess_kwargs: Any,
) -> subprocess.Popen:
    """Run a subprocess command with Popen inside a conda environment.

    Args:
        cmd: Base command list.
        conda_env: Optional conda environment name.
        **subprocess_kwargs: Passed to subprocess.Popen.

    Returns:
        Popen process handle.
    """
    wrapped = build_conda_cmd(cmd, conda_env)
    logger.info("Executing (Popen): %s", " ".join(wrapped))
    return subprocess.Popen(wrapped, **subprocess_kwargs)

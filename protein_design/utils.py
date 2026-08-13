"""Shared helpers for protein-design scripts and hooks.

This module centralises small, reusable utilities so they do not have to be
duplicated across ``scripts/`` and ``protein_design/hooks/``.  It intentionally
contains no heavy ML dependencies (torch, fair-esm, boltz, etc.).
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Configuration and execution history
# ---------------------------------------------------------------------------

def get_config(tool_name: str | None = None) -> dict[str, Any]:
    """Read protein-design config from YAML or return defaults.

    Looks for ``~/.protein-design/config.yaml`` first, then falls back to the
    legacy ``~/.kimi-protein-design/config.yaml``.

    Resolution priority (highest first):

    1. **Environment variables** — explicitly set env vars always win, even if
       the config file sets the same key.
    2. **Config file** — keys in the YAML file override the built-in defaults
       for env vars that were *not* explicitly set.
    3. **Built-in defaults** — used when neither env nor file provides a value.

    Args:
        tool_name: Optional tool identifier (e.g. ``"alphafold3"``). When
            provided, the corresponding ``<TOOL>_PATH`` environment variable is
            included in the resolution.

    Returns:
        A dictionary with at least ``output_dir`` and any tool-specific paths.
    """
    config_paths = [
        Path.home() / ".protein-design" / "config.yaml",
        Path.home() / ".kimi-protein-design" / "config.yaml",
    ]

    # Env vars that were explicitly set — these win over the config file.
    env_overrides: dict[str, Any] = {}
    if "PROTEIN_DESIGN_OUTPUT_DIR" in os.environ:
        env_overrides["output_dir"] = os.environ["PROTEIN_DESIGN_OUTPUT_DIR"]

    # Built-in defaults (env value when set, otherwise the fallback).
    config: dict[str, Any] = {
        "output_dir": os.environ.get("PROTEIN_DESIGN_OUTPUT_DIR", "/tmp/protein-design"),
    }

    if tool_name:
        tool_key = tool_name.lower().replace("-", "_")
        tool_upper = tool_name.upper().replace("-", "_")
        path_env = f"{tool_upper}_PATH"
        config[f"{tool_key}_path"] = os.environ.get(path_env, "")
        if path_env in os.environ:
            env_overrides[f"{tool_key}_path"] = os.environ[path_env]

        # Database directory is relevant for structure-prediction validators.
        if tool_key in ("alphafold3", "alphafold", "openfold3"):
            for db_env in (f"{tool_upper}_DB_DIR", "ALPHAFOLD_DB_DIR", "ALPHAFOLD3_DB_DIR"):
                if db_env in os.environ:
                    val = os.environ[db_env]
                    config["db_dir"] = val
                    env_overrides["db_dir"] = val
                    break
            if "db_dir" not in config:
                config["db_dir"] = ""

    for path in config_paths:
        if path.exists():
            try:
                import yaml

                with open(path, "r", encoding="utf-8") as f:
                    file_config = yaml.safe_load(f) or {}
                if isinstance(file_config, dict):
                    config.update(file_config)
            except ImportError:
                pass
            except Exception:
                # A malformed config file should not crash the calling script.
                traceback.print_exc()
            break

    # Explicitly set environment variables take precedence over the file.
    config.update(env_overrides)

    return config


def log_history(
    tool_name: str,
    params: dict[str, Any],
    runtime: float,
    success: bool,
    output_dir: str | None = None,
) -> None:
    """Append an execution record to ``~/.protein-design/history.jsonl``.

    Args:
        tool_name: Name of the tool that ran.
        params: Dictionary of parameters / inputs.
        runtime: Elapsed runtime in seconds.
        success: Whether the run succeeded.
        output_dir: Optional output directory to record.
    """
    history_file = Path.home() / ".protein-design" / "history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    record: dict[str, Any] = {
        "tool": tool_name,
        "params": params,
        "runtime": runtime,
        "success": success,
        "timestamp": datetime.now().isoformat(),
    }
    if output_dir is not None:
        record["output_dir"] = output_dir

    with open(history_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# FASTA / format helpers
# ---------------------------------------------------------------------------

def read_fasta(filepath: str | Path) -> list[tuple[str, str]]:
    """Read a FASTA file and return a list of ``(seq_id, sequence)`` tuples."""
    sequences: list[tuple[str, str]] = []
    current_id: str | None = None
    current_seq: list[str] = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_id is not None:
                    sequences.append((current_id, "".join(current_seq)))
                current_id = line[1:].split()[0]
                current_seq = []
            else:
                current_seq.append(line)

    if current_id is not None:
        sequences.append((current_id, "".join(current_seq)))

    return sequences


def write_fasta(sequences: list[tuple[str, str]], filepath: str | Path) -> None:
    """Write ``(seq_id, sequence)`` tuples to a FASTA file (60-char wrapping)."""
    with open(filepath, "w", encoding="utf-8") as f:
        for seq_id, seq in sequences:
            f.write(f">{seq_id}\n")
            for i in range(0, len(seq), 60):
                f.write(seq[i : i + 60] + "\n")


def fasta_to_alphafold3_json(
    sequences: list[tuple[str, str]],
    job_name: str = "design",
    verbose: bool = False,
) -> dict[str, Any]:
    """Convert FASTA sequences to an AlphaFold3-style JSON input dict."""
    af3_input: dict[str, Any] = {
        "name": job_name,
        "sequences": [],
        "modelSeeds": [1],
    }

    for i, (seq_id, seq) in enumerate(sequences):
        chain_id = chr(65 + i) if i < 26 else f"X{i}"
        af3_input["sequences"].append(
            {
                "protein": {
                    "id": chain_id,
                    "sequence": seq,
                }
            }
        )

    if verbose:
        print(f"Converted {len(sequences)} sequence(s) to AlphaFold3 JSON (job: {job_name})")

    return af3_input


# ---------------------------------------------------------------------------
# Confidence JSON parsing
# ---------------------------------------------------------------------------

def parse_confidence_json(json_path: str | Path) -> dict[str, Any]:
    """Parse a ``confidence.json`` file from AlphaFold3, Boltz-1, Chai-1, etc.

    Understands several schema variants:

    * ``confidence.plddt``, ``confidence.iptm``, ``confidence.ptm``
    * Top-level ``plddt``, ``iptm``, ``ptm``, ``pae``
    * ``mean_plddt`` (Protenix style)
    * Per-residue ``plddt`` lists (averaged)
    * ``ranking_score``, ``confidence_score``, ``has_clash``

    Args:
        json_path: Path to the confidence JSON file.

    Returns:
        Dictionary of extracted metrics. Missing metrics are omitted.
    """
    path = Path(json_path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return {}

    metrics: dict[str, Any] = {}

    # 1. Nested ``confidence`` block (AlphaFold3 / OpenFold3).
    conf = data.get("confidence")
    if isinstance(conf, dict):
        for key in (
            "plddt",
            "iptm",
            "ptm",
            "pae",
            "mean_plddt",
            "ranking_score",
            "confidence_score",
            "has_clash",
        ):
            value = conf.get(key)
            if value is not None:
                _store_metric(metrics, key, value)

    # 2. Flat keys (Boltz-1 / Chai-1 / ESMFold / OmegaFold).
    for key in (
        "plddt",
        "iptm",
        "ptm",
        "pae",
        "mean_plddt",
        "ranking_score",
        "confidence_score",
        "has_clash",
    ):
        if key in metrics:
            continue
        value = data.get(key)
        if value is not None:
            _store_metric(metrics, key, value)

    # 3. Per-residue pLDDT list -> mean pLDDT.
    for source in (data, conf if isinstance(conf, dict) else {}):
        if "plddt" in source and isinstance(source["plddt"], list):
            vals = [float(x) for x in source["plddt"] if isinstance(x, (int, float))]
            if vals and metrics.get("plddt") is None:
                metrics["plddt"] = sum(vals) / len(vals)
                break

    return metrics


def _store_metric(metrics: dict[str, Any], key: str, value: Any) -> None:
    """Store a scalar confidence metric, coercing numbers to float.

    ``mean_plddt`` is aliased to ``plddt`` when a direct pLDDT value is absent.
    """
    if isinstance(value, bool):
        metrics[key] = value
        return
    if isinstance(value, (int, float)):
        coerced = float(value)
        metrics[key] = coerced
        if key == "mean_plddt" and "plddt" not in metrics:
            metrics["plddt"] = coerced
        return
    # Lists / non-scalars are intentionally ignored here; list-aware logic
    # (e.g. per-residue pLDDT) is handled separately.


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def _escape_applescript(s: str) -> str:
    """Escape for AppleScript double-quoted string interpolation.

    AppleScript string literals cannot span lines, so CR/LF are flattened
    to spaces; backslash and double-quote are backslash-escaped.
    """
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r\n", " ")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _escape_powershell(s: str) -> str:
    """Escape for PowerShell double-quoted string interpolation.

    The backtick is PowerShell's escape character and must be doubled
    first; ``$`` (subexpression/variable expansion), double-quote, and
    newlines are each escaped with a backtick. Without this, notification
    text containing ``$(...)`` would execute inside ``powershell -Command``.
    """
    return (
        s.replace("`", "``")
        .replace('"', '`"')
        .replace("$", "`$")
        .replace("\r\n", "`n")
        .replace("\r", "`n")
        .replace("\n", "`n")
    )


def send_notification(title: str, message: str) -> None:
    """Send a cross-platform desktop notification.

    Supports macOS (``osascript``), Linux (``notify-send``) and Windows
    (PowerShell).  Notifications are best-effort: failures — including the
    timeout expiring — are silently ignored so a hung notifier can never block
    the caller.
    """
    system = platform.system()

    if system == "Darwin":
        safe_title = _escape_applescript(title)
        safe_message = _escape_applescript(message)
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        _run_notifier(["osascript", "-e", script])
    elif system == "Linux":
        _run_notifier(["notify-send", title, message])
    elif system == "Windows":
        safe_title = _escape_powershell(title)
        safe_message = _escape_powershell(message)
        ps_script = (
            'Add-Type -AssemblyName System.Windows.Forms; '
            f'[System.Windows.Forms.MessageBox]::Show("{safe_message}", "{safe_title}")'
        )
        _run_notifier(["powershell", "-Command", ps_script])


def _run_notifier(argv: list[str]) -> None:
    """Run a notifier subprocess, swallowing timeout and other failures.

    A 10-second timeout prevents hanging on an unresponsive notifier; both
    ``TimeoutExpired`` and any other exception are silently ignored to honour
    the best-effort contract of :func:`send_notification`.
    """
    try:
        subprocess.run(argv, capture_output=True, text=True, check=False, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass


def probe_gpus(timeout: float = 5.0) -> list[dict[str, Any]] | None:
    """Probe NVIDIA GPUs via ``nvidia-smi``.

    Returns:
        A list of ``{"name": str, "free_mb": float}`` dicts — empty when the
        probe works but no GPU is present — or ``None`` when ``nvidia-smi``
        is unavailable or errors. The distinction matters for fail-open
        policy: a probe failure (e.g. CPU-only host) must not be treated as
        "no usable GPU".
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        return None

    gpus: list[dict[str, Any]] = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            try:
                gpus.append({"name": parts[0], "free_mb": float(parts[1])})
            except ValueError:
                continue
    return gpus


# ---------------------------------------------------------------------------
# Hook input helper
# ---------------------------------------------------------------------------

def extract_content_text(result: Any) -> str:
    """Best-effort extraction of the text payload from a tool-result object.

    Hook payloads arrive from external tools and are not always well-formed:
    ``content`` may be missing, not a list, or hold non-dict entries. This
    helper never raises; it returns ``""`` whenever the text cannot be found.
    """
    if not isinstance(result, dict):
        return ""
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return ""
    first = content[0]
    if not isinstance(first, dict):
        return ""
    text = first.get("text", "")
    return text if isinstance(text, str) else ""


def read_hook_input() -> dict[str, Any]:
    """Read JSON hook payload from stdin.

    Returns an empty dict for empty stdin.  Raises ``json.JSONDecodeError`` for
    invalid JSON so callers can decide whether to stay silent or report it.
    """
    text = sys.stdin.read()
    if not text.strip():
        return {}
    return json.loads(text)

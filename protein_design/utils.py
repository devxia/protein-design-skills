"""Shared helpers for protein-design scripts and hooks.

This module centralises small, reusable utilities so they do not have to be
duplicated across ``scripts/`` and ``protein_design/hooks/``.  It intentionally
contains no heavy ML dependencies (torch, fair-esm, boltz, etc.).
"""

from __future__ import annotations

import json
import math
import os
import platform
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union


# ---------------------------------------------------------------------------
# Configuration and execution history
# ---------------------------------------------------------------------------

def get_config(tool_name: Optional[str] = None) -> dict[str, Any]:
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
            included in the resolution. For ``"alphafold3"`` the legacy
            ``ALPHAFOLD_PATH`` variable is honoured as a fallback when
            ``ALPHAFOLD3_PATH`` is not set (the latter wins when both are set).

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
        # Legacy alias: the docs historically documented ALPHAFOLD_PATH for the
        # alphafold3 tool; the derived ALPHAFOLD3_PATH still takes priority.
        if tool_key == "alphafold3" and path_env not in os.environ:
            path_env = "ALPHAFOLD_PATH"
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
    output_dir: Optional[str] = None,
) -> None:
    """Append an execution record to ``~/.protein-design/history.jsonl``.

    This is a side-channel log: any failure (unwritable ``HOME``, full disk,
    non-JSON-serialisable ``params``, ...) is reported as a short warning on
    stderr but never propagated, so a logging failure can never crash an
    otherwise successful pipeline stage.

    Args:
        tool_name: Name of the tool that ran.
        params: Dictionary of parameters / inputs.
        runtime: Elapsed runtime in seconds.
        success: Whether the run succeeded.
        output_dir: Optional output directory to record.
    """
    try:
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
    except Exception as exc:
        print(f"Warning: failed to log run history: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# FASTA / format helpers
# ---------------------------------------------------------------------------

def read_fasta(filepath: Union[str, Path]) -> list[tuple[str, str]]:
    """Read a FASTA file and return a list of ``(seq_id, sequence)`` tuples.

    Records with an empty header (a bare ``>`` line) are skipped, as is any
    sequence text that appears before the first header.
    """
    sequences: list[tuple[str, str]] = []
    current_id: Optional[str] = None
    current_seq: list[str] = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                header = line[1:].split()
                if not header:
                    # Skip records with an empty header (a bare ">");
                    # flush any pending record first.
                    if current_id is not None:
                        sequences.append((current_id, "".join(current_seq)))
                    current_id = None
                    current_seq = []
                    continue
                if current_id is not None:
                    sequences.append((current_id, "".join(current_seq)))
                current_id = header[0]
                current_seq = []
            else:
                current_seq.append(line)

    if current_id is not None:
        sequences.append((current_id, "".join(current_seq)))

    return sequences


def write_fasta(sequences: list[tuple[str, str]], filepath: Union[str, Path]) -> None:
    """Write ``(seq_id, sequence)`` tuples to a FASTA file (60-char wrapping)."""
    with open(filepath, "w", encoding="utf-8") as f:
        for seq_id, seq in sequences:
            f.write(f">{seq_id}\n")
            for i in range(0, len(seq), 60):
                f.write(seq[i : i + 60] + "\n")


def _alphafold3_chain_id(index: int) -> str:
    """Return a stable, uppercase-only AlphaFold3 chain ID for ``index``.

    IDs use bijective base-26 notation: ``A`` through ``Z``, then ``AA``
    through ``ZZ``, followed by ``AAA``.  Unlike a numeric fallback, this
    remains valid for AlphaFold3 inputs with hundreds of chains.
    """
    if index < 0:
        raise ValueError("chain index must be non-negative")

    letters: list[str] = []
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def fasta_to_alphafold3_json(
    sequences: list[tuple[str, str]],
    job_name: str = "design",
    verbose: bool = False,
) -> dict[str, Any]:
    """Convert FASTA sequences to an official AlphaFold3 JSON input dict."""
    af3_input: dict[str, Any] = {
        "dialect": "alphafold3",
        "version": 1,
        "name": job_name,
        "modelSeeds": [1],
        "sequences": [],
    }

    for i, (_seq_id, seq) in enumerate(sequences):
        af3_input["sequences"].append(
            {
                "protein": {
                    "id": _alphafold3_chain_id(i),
                    "sequence": seq,
                }
            }
        )

    if verbose:
        print(f"Converted {len(sequences)} sequence(s) to AlphaFold3 JSON (job: {job_name})")

    return af3_input


# ---------------------------------------------------------------------------
# Confidence JSON parsing and discovery
# ---------------------------------------------------------------------------

# Confidence-metric keys probed in both nested and flat confidence JSON layouts.
_CONFIDENCE_METRIC_KEYS = (
    "plddt",
    "iptm",
    "ptm",
    "pae",
    "mean_plddt",
    "ranking_score",
    "confidence_score",
    "has_clash",
)


def _confidence_file_info(path: Path) -> tuple[tuple[str, str], int]:
    """Return a deduplication key and preference for a confidence file.

    AlphaFold3 writes a detailed ``*_confidences.json`` file next to a
    ``*_summary_confidences.json`` file.  They describe one prediction, so the
    detailed file is preferred when both exist.  Boltz commonly writes
    ``confidence_<name>_model_<n>.json`` files; those remain distinct models.
    """
    name = path.name.lower()
    parent = str(path.parent.resolve())
    if name == "confidence.json":
        return (parent, "confidence.json"), 0

    if name.endswith("_summary_confidences.json"):
        stem = name[: -len("_summary_confidences.json")]
        return (parent, stem), 1
    if name.endswith("_confidences.json"):
        stem = name[: -len("_confidences.json")]
        return (parent, stem), 0
    if name.endswith("_summary_confidence.json"):
        stem = name[: -len("_summary_confidence.json")]
        return (parent, stem), 1
    if name.endswith("_confidence.json"):
        stem = name[: -len("_confidence.json")]
        return (parent, stem), 0

    # Boltz uses the ``confidence_<input>_model_<n>.json`` convention.  Keep
    # the filename in the key because separate model/sample files are useful
    # independent validation results.
    return (parent, name), 0


def discover_confidence_files(root: Union[str, Path]) -> list[Path]:
    """Find supported confidence JSON files without counting one result twice.

    Supported names include AlphaFold3's ``confidence.json``,
    ``*_confidences.json`` and ``*_summary_confidences.json`` files, plus the
    ``confidence_*.json`` / ``*_confidence.json`` forms emitted by Boltz and
    similar validators.  When detailed and summary AlphaFold3 files are both
    present, only the detailed file is returned.  Results are deterministic
    and an absent or unreadable root yields an empty list.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        return []

    candidates: list[Path] = []
    try:
        for path in root_path.rglob("*.json"):
            name = path.name.lower()
            if (
                name == "confidence.json"
                or name.endswith("_confidences.json")
                or name.endswith("_summary_confidences.json")
                or name.endswith("_confidence.json")
                or name.endswith("_summary_confidence.json")
                or name.startswith("confidence_")
            ):
                candidates.append(path)
    except OSError:
        return []

    selected: dict[tuple[str, str], tuple[int, Path]] = {}
    for path in sorted(candidates, key=lambda item: str(item.resolve())):
        key, priority = _confidence_file_info(path)
        current = selected.get(key)
        if current is None or (priority, str(path)) < (current[0], str(current[1])):
            selected[key] = (priority, path)

    return [item[1] for item in sorted(selected.values(), key=lambda item: str(item[1].resolve()))]


def _iter_json_objects(value: Any):
    """Yield nested JSON objects in stable traversal order."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_json_objects(child)


def _coerce_number(value: Any) -> Optional[float]:
    """Convert finite JSON numbers and numeric strings to floats."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _mean_numeric(value: Any) -> Optional[float]:
    """Average finite numbers from a scalar or arbitrarily nested JSON array."""
    values = _flatten_numbers(value)
    return sum(values) / len(values) if values else None


def _flatten_numbers(value: Any) -> list[float]:
    """Flatten numeric values from a JSON array, ignoring malformed entries."""
    scalar = _coerce_number(value)
    if scalar is not None:
        return [scalar]
    if isinstance(value, (list, tuple)):
        values: list[float] = []
        for child in value:
            values.extend(_flatten_numbers(child))
        return values
    return []


def _find_metric_entry(objects: list[dict[str, Any]], keys: tuple[str, ...]):
    """Find the first normalized key/value pair in nested JSON objects."""
    wanted = set(keys)
    for obj in objects:
        for key, value in obj.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in wanted and value is not None:
                return normalized, value
    return None


def _find_metric_value(objects: list[dict[str, Any]], keys: tuple[str, ...]) -> Any:
    """Find the first value for any case-insensitive normalized key."""
    entry = _find_metric_entry(objects, keys)
    return entry[1] if entry is not None else None


def _paired_confidence_path(path: Path) -> Optional[Path]:
    """Return the sibling detailed/summary confidence file, if present."""
    name = path.name
    lower_name = name.lower()
    if lower_name.endswith("_summary_confidences.json"):
        candidate = path.with_name(
            name[: -len("_summary_confidences.json")] + "_confidences.json"
        )
    elif lower_name.endswith("_confidences.json"):
        candidate = path.with_name(
            name[: -len("_confidences.json")] + "_summary_confidences.json"
        )
    else:
        return None
    return candidate if candidate.is_file() else None


def _confidence_documents(path: Path) -> list[dict[str, Any]]:
    """Load a confidence file and its optional AlphaFold3 sibling.

    The detailed file is placed first so its atom-level pLDDT/PAE values take
    precedence over any overlapping summary values.  A malformed optional
    sibling is ignored, while an error in the requested file is propagated.
    """
    paired = _paired_confidence_path(path)
    paths = [path]
    if paired is not None:
        if path.name.lower().endswith("_summary_confidences.json"):
            paths = [paired, path]
        else:
            paths.append(paired)

    documents: list[dict[str, Any]] = []
    for document_path in paths:
        try:
            with open(document_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            if document_path == path:
                raise
            continue
        if isinstance(data, dict):
            documents.append(data)
    return documents


def _parse_confidence_document(data: dict[str, Any]) -> dict[str, Any]:
    """Extract canonical confidence metrics from one JSON document."""
    # Prefer explicit confidence/summary/metrics blocks, then inspect the
    # complete document for flat layouts used by Boltz and other tools.
    objects: list[dict[str, Any]] = []
    seen_objects: set[int] = set()
    preferred = [data.get(key) for key in ("confidence", "summary", "metrics")]
    preferred.extend([data])
    for value in preferred:
        for obj in _iter_json_objects(value):
            if id(obj) not in seen_objects:
                seen_objects.add(id(obj))
                objects.append(obj)

    metrics: dict[str, Any] = {}

    # Detailed AlphaFold3 files contain atom_plddts, while summary files
    # commonly contain complex_plddt.  Keep this order so an atom-level value
    # is not replaced by a less specific summary value in the same document.
    plddt_entry = _find_metric_entry(objects, ("plddt",))
    if plddt_entry is None:
        plddt_entry = _find_metric_entry(objects, ("mean_plddt",))
    if plddt_entry is None:
        plddt_entry = _find_metric_entry(objects, ("atom_plddts",))
    if plddt_entry is None:
        plddt_entry = _find_metric_entry(objects, ("complex_plddt",))

    plddt = _mean_numeric(plddt_entry[1]) if plddt_entry is not None else None
    if plddt is not None and plddt_entry[0] == "complex_plddt" and 0 <= plddt <= 1:
        # AlphaFold3 reports complex pLDDT on a 0–1 scale, whereas atom-level
        # pLDDTs and this project's filtering thresholds use 0–100.
        plddt *= 100.0
    if plddt is not None:
        metrics["plddt"] = plddt

    iptm_entry = _find_metric_entry(
        objects, ("iptm", "complex_iptm", "interface_iptm")
    )
    iptm = _coerce_number(iptm_entry[1]) if iptm_entry is not None else None
    if iptm is not None:
        metrics["iptm"] = iptm

    ptm_entry = _find_metric_entry(objects, ("ptm", "complex_ptm"))
    ptm = _coerce_number(ptm_entry[1]) if ptm_entry is not None else None
    if ptm is not None:
        metrics["ptm"] = ptm

    pae_entry = _find_metric_entry(
        objects, ("pae", "predicted_aligned_error", "mean_pae")
    )
    pae = _mean_numeric(pae_entry[1]) if pae_entry is not None else None
    if pae is not None:
        metrics["pae"] = pae

    for key in ("ranking_score", "confidence_score"):
        value = _coerce_number(_find_metric_value(objects, (key,)))
        if value is not None:
            metrics[key] = value

    has_clash = _find_metric_value(objects, ("has_clash",))
    if isinstance(has_clash, bool):
        metrics["has_clash"] = has_clash
    elif isinstance(has_clash, str) and has_clash.strip().lower() in {"true", "false"}:
        metrics["has_clash"] = has_clash.strip().lower() == "true"

    return metrics


def parse_confidence_json(json_path: Union[str, Path]) -> dict[str, Any]:
    """Parse confidence metrics from AlphaFold3, Boltz, Chai-1, or Protenix.

    The returned mapping uses canonical keys: ``plddt`` (including the mean of
    ``atom_plddts``), ``iptm``, ``ptm``, and ``pae``.  It also understands
    AlphaFold3's detailed/summary file pair, ``complex_*`` aliases, numeric
    strings, nested result blocks, and PAE matrices.  Missing metrics are
    omitted.
    """
    path = Path(json_path)
    documents = _confidence_documents(path)
    metrics: dict[str, Any] = {}
    for document in documents:
        # Detailed files are ordered before summary files by
        # _confidence_documents().  Summary data fills gaps but never
        # overwrites a metric already extracted from the detailed document.
        for key, value in _parse_confidence_document(document).items():
            metrics.setdefault(key, value)
    return metrics


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
    """Run a notifier subprocess, swallowing launch and timeout failures.

    A 10-second timeout prevents hanging on an unresponsive notifier. Only
    ``subprocess.TimeoutExpired`` and ``OSError`` subclasses (such as
    ``FileNotFoundError`` when the notifier binary is missing) are silently
    ignored; any other exception type still propagates to the caller.
    """
    try:
        subprocess.run(argv, capture_output=True, text=True, check=False, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass


def probe_gpus(timeout: float = 5.0) -> Optional[list[dict[str, Any]]]:
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
# Protein-keyword matching (canonical pattern for hook logic and host matchers)
# ---------------------------------------------------------------------------

PROTEIN_DESIGN_KEYWORDS: tuple[str, ...] = (
    "protein", "pdb", "binder", "alphafold", "rfdiffusion", "proteinmpnn",
    "design", "structure", "sequence", "residue", "loop", "scaffold",
    "motif", "oligomer", "diffusion", "backbone", "monomer", "complex",
    "interface", "epitope", "target", "fold", "prediction",
    "plddt", "ptm", "iptm", "msa", "validation", "ranking", "filter", "chain",
)

PROTEIN_DESIGN_PATTERN: str = r"\b(" + "|".join(PROTEIN_DESIGN_KEYWORDS) + r")\b"
"""Canonical protein-design keyword regex (without flags; add re.IGNORECASE).

Host-specific UserPromptSubmit matchers may use this keyword set; tests guard
supported matchers against drift.
"""


def protein_keyword_pattern(extra_keywords: tuple[str, ...] = ()) -> str:
    """Canonical protein-design keyword regex, optionally extended.

    Hooks with intent-specific triggers (e.g. cost keywords for the cost
    estimator) extend the canonical set rather than forking it, so adding a
    canonical keyword still propagates to every re-matching hook.
    """
    keywords = PROTEIN_DESIGN_KEYWORDS + tuple(extra_keywords)
    return r"\b(" + "|".join(keywords) + r")\b"


# ---------------------------------------------------------------------------
# Hook input helper
# ---------------------------------------------------------------------------

_MISSING = object()


def _top_level_value(data: Any, *keys: str) -> Any:
    """Return the first explicitly present top-level hook field."""
    if not isinstance(data, dict):
        return _MISSING
    for key in keys:
        if key in data:
            return data[key]
    return _MISSING


def get_hook_tool_name(data: Any) -> str:
    """Return a normalized tool name from a standard or legacy hook payload.

    Current hosts send top-level ``tool_name``.  Older payloads used
    top-level ``tool`` or nested values in ``tool_input``/``params``; those
    forms remain accepted for compatibility.
    """
    value = _top_level_value(data, "tool_name", "tool")
    if value is _MISSING and isinstance(data, dict):
        for field in ("tool_input", "params"):
            nested = data.get(field)
            if isinstance(nested, dict):
                value = _top_level_value(nested, "tool_name", "tool")
                if value is not _MISSING:
                    break
    return str(value).strip() if value is not _MISSING and value is not None else ""


def get_hook_tool_input(data: Any) -> Any:
    """Return ``tool_input`` with fallback to the legacy ``params`` field."""
    value = _top_level_value(data, "tool_input")
    if value is not _MISSING:
        return value
    value = _top_level_value(data, "params")
    return None if value is _MISSING else value


def get_hook_tool_response(data: Any) -> Any:
    """Return ``tool_response`` with fallback to the legacy ``result`` field."""
    value = _top_level_value(data, "tool_response")
    if value is not _MISSING:
        return value
    value = _top_level_value(data, "result")
    return None if value is _MISSING else value


def get_hook_error(data: Any) -> Any:
    """Return the host-provided top-level tool error, if present."""
    value = _top_level_value(data, "error")
    return None if value is _MISSING else value


def get_hook_prompt(data: Any) -> str:
    """Return the submitted prompt from a UserPromptSubmit payload."""
    value = _top_level_value(data, "prompt")
    return str(value) if value is not _MISSING and value is not None else ""


def extract_content_text(value: Any) -> str:
    """Best-effort extraction of text from strings and nested tool responses.

    Hosts have used a direct string, ``{"content": [...]}``, and nested
    ``tool_response``/``result`` objects.  Content lists may contain strings,
    text blocks, or further nested objects.  Invalid shapes are ignored and
    the function never raises.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            return ""
    if isinstance(value, list):
        # A host content array contains structured text blocks, not bare
        # strings.  Keep direct strings valid for whole responses while
        # ignoring malformed scalar entries inside a content array.
        parts = [
            extract_content_text(item)
            for item in value
            if isinstance(item, (dict, list, bytes, bytearray))
        ]
        return "\n".join(part for part in parts if part)
    if not isinstance(value, dict):
        return ""

    text = value.get("text")
    if isinstance(text, str):
        return text

    # Probe the standard response containers first.  Content is expected to be
    # a list of text blocks; a scalar content string is a malformed shape and
    # must not be mistaken for a valid response.  Generic traversal below
    # covers vendor-specific wrappers without making callers know their shape.
    for key in ("content", "tool_response", "result", "response", "output", "error"):
        if key not in value:
            continue
        if key == "content" and not isinstance(value[key], (list, dict)):
            continue
        extracted = extract_content_text(value[key])
        if extracted:
            return extracted

    for key, child in value.items():
        if key == "content" and not isinstance(child, (list, dict)):
            continue
        extracted = extract_content_text(child)
        if extracted:
            return extracted
    return ""


# The runner inventory is intentionally explicit: hook decisions must never be
# enabled by arbitrary shell text or a similarly named third-party script.
HOOK_RUNNERS: frozenset[str] = frozenset(
    {
        "batch_runner", "convert_format", "job_manager", "project_dashboard",
        "run_alphafold3", "run_boltz", "run_chai1", "run_colabfold",
        "run_esm_if1", "run_esmfold", "run_filtering", "run_ligandmpnn",
        "run_omegafold", "run_openfold3", "run_pdbfixer", "run_proteinmpnn",
        "run_protenix", "run_rfdiffusion", "summarize_outputs",
    }
)
_SHELL_TOOL_NAMES = frozenset(
    {"bash", "powershell", "shell", "exec_command", "run_shell_command"}
)
# Direct tool payloads have historically used the short tool name, whereas
# shell payloads invoke the public ``scripts/run_*.py`` runner. Keep this
# mapping explicit rather than trusting prefix or substring matches.
HOOK_RUNNER_ALIASES = {
    runner.removeprefix("run_"): runner
    for runner in HOOK_RUNNERS
    if runner.startswith("run_")
}


def _is_windows_shell_tool(tool_name: str) -> bool:
    """Return whether a hook payload's structured shell uses Windows syntax."""
    return tool_name.strip().casefold() == "powershell"


def _split_hook_command(command: str, windows: bool) -> list[str]:
    """Safely split one simple structured shell command without evaluating it."""
    if not isinstance(command, str) or not command.strip():
        return []
    # Compound syntax is excluded so a runner decision cannot be influenced by
    # a second command, substitution, redirection, or interpreter code mode.
    if any(char in command for char in ("\n", "\r", ";", "|", "&", "`", "$", "<", ">")):
        return []
    try:
        import shlex

        tokens = shlex.split(command, posix=not windows)
    except ValueError:
        return []
    if windows:
        tokens = [
            token[1:-1]
            if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'"
            else token
            for token in tokens
        ]
    return tokens


def _hook_command_runner_tokens(data: Any) -> list[str]:
    """Return parsed runner invocation tokens from a structured shell payload."""
    tool_name = get_hook_tool_name(data).casefold()
    if tool_name not in _SHELL_TOOL_NAMES:
        return []
    tool_input = get_hook_tool_input(data)
    if not isinstance(tool_input, dict):
        return []
    command = tool_input.get("command")
    tokens = _split_hook_command(command, _is_windows_shell_tool(tool_name))
    if not tokens:
        return []
    interpreter = Path(tokens[0].replace("\\", "/")).name.casefold()
    if interpreter not in {"python", "python3", "python.exe", "python3.exe", "py", "py.exe"}:
        return []
    if len(tokens) < 2 or tokens[1] in {"-c", "-m"} or tokens[1].startswith("-"):
        return []
    script = tokens[1].replace("\\", "/")
    if not script.casefold().endswith(".py"):
        return []
    runner = Path(script).stem.casefold()
    if runner not in HOOK_RUNNERS:
        return []
    parts = [part for part in script.split("/") if part not in {"", "."}]
    if ".." in parts or "scripts" not in parts:
        return []
    return tokens


def get_hook_invoked_runner(data: Any) -> Optional[str]:
    """Return the allowlisted project runner invoked by a hook payload.

    Direct tool invocations may report an allowlisted runner in ``tool_name``.
    Bash and PowerShell invocations are resolved exclusively from their
    structured ``tool_input.command`` field and only after conservative token
    validation. Arbitrary text, compound shell syntax, and unrecognized scripts
    return ``None``.
    """
    tool_name = get_hook_tool_name(data).strip().casefold()
    if tool_name in HOOK_RUNNERS:
        return tool_name
    if tool_name in HOOK_RUNNER_ALIASES:
        return HOOK_RUNNER_ALIASES[tool_name]
    tokens = _hook_command_runner_tokens(data)
    if not tokens:
        return None
    return Path(tokens[1].replace("\\", "/")).stem.casefold()


def get_hook_invoked_runner_arguments(data: Any) -> list[str]:
    """Return safe runner CLI arguments, or an empty list when unresolved."""
    tokens = _hook_command_runner_tokens(data)
    return tokens[2:] if tokens else []


def hook_advisory_output(additional_context: str) -> str:
    """Serialize the portable advisory hook response schema."""
    if not isinstance(additional_context, str) or not additional_context.strip():
        return ""
    return json.dumps(
        {"hookSpecificOutput": {"additionalContext": additional_context}},
        ensure_ascii=False,
    )


def read_hook_input() -> dict[str, Any]:
    """Read JSON hook payload from stdin.

    Returns an empty dict for empty stdin.  Raises ``json.JSONDecodeError`` for
    invalid JSON so callers can decide whether to stay silent or report it.
    """
    text = sys.stdin.read()
    if not text.strip():
        return {}
    return json.loads(text)

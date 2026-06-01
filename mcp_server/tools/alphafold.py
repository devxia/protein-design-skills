"""AlphaFold3 tool implementation for structure prediction and validation.

Supports local Python execution or Docker. Parses confidence metrics
(pLDDT, pTM, ipTM) from output JSON files.
"""

import glob
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp_server.utils.config import CONFIG

logger = logging.getLogger(__name__)


def _find_alphafold_script() -> str:
    """Locate the AlphaFold3 run script.

    Returns:
        Absolute path to run_alphafold.py.

    Raises:
        FileNotFoundError: If script cannot be found.
    """
    if CONFIG.alphafold_path:
        candidate = os.path.join(CONFIG.alphafold_path, "run_alphafold.py")
        if os.path.exists(candidate):
            return candidate

    candidates = [
        "./alphafold3/run_alphafold.py",
        "../alphafold3/run_alphafold.py",
        "~/alphafold3/run_alphafold.py",
        "/opt/alphafold3/run_alphafold.py",
        "./alphafold/run_alphafold.py",
    ]
    for candidate in candidates:
        expanded = os.path.expanduser(candidate)
        if os.path.exists(expanded):
            return os.path.abspath(expanded)

    raise FileNotFoundError(
        "AlphaFold3 run_alphafold.py not found. "
        "Set ALPHAFOLD_PATH env var or install AlphaFold3."
    )


def _find_db_dir() -> str | None:
    """Locate the AlphaFold3 genetic databases directory.

    Checks (in order):
        1. params["db_dir"] from the current call
        2. CONFIG.db_dir from config file / env var
        3. Common default locations

    Returns:
        Absolute path to the databases directory, or None if not found.
    """
    # 1. Config / env var
    if CONFIG.db_dir and os.path.isdir(CONFIG.db_dir):
        return os.path.abspath(CONFIG.db_dir)

    # 2. Common default locations
    candidates = [
        "~/public_databases",
        "~/databases",
        "/opt/public_databases",
        "/opt/databases",
        "./public_databases",
        "../public_databases",
    ]
    for candidate in candidates:
        expanded = os.path.expanduser(candidate)
        if os.path.isdir(expanded):
            # Sanity check: look for a known sub-directory or file pattern
            # that indicates this is actually the AF3 databases
            if _looks_like_af3_databases(expanded):
                return os.path.abspath(expanded)

    return None


def _looks_like_af3_databases(path: str) -> bool:
    """Heuristic: does this directory look like AlphaFold3 databases?

    We look for at least one known database subdirectory.
    Users may have downloaded only a subset, so we accept partial matches.

    Args:
        path: Candidate database directory.

    Returns:
        True if it looks like AF3 databases.
    """
    known_subdirs = [
        "bfd",
        "mgy_clusters",
        "pdb_seqres",
        "rnacentral",
        "uniprot",
        "uniref90",
        "nt",
    ]
    try:
        entries = os.listdir(path)
        return any(d in entries for d in known_subdirs)
    except Exception:
        return False


def check_af3_database_status(db_dir: str | None = None) -> dict[str, Any]:
    """Check AlphaFold3 genetic database installation status.

    Args:
        db_dir: Explicit database directory to check. If None, uses auto-detection.

    Returns:
        Dict with detected, path, size_estimate_gb, and missing_databases.
    """
    resolved = db_dir or _find_db_dir()

    if not resolved:
        return {
            "detected": False,
            "path": None,
            "reason": "Database directory not found. Expected: ~/public_databases or set db_dir config.",
            "missing_databases": list(_get_expected_databases().keys()),
        }

    expected = _get_expected_databases()
    present = {}
    missing = {}

    for name, min_size_mb in expected.items():
        db_path = os.path.join(resolved, name)
        if os.path.isdir(db_path):
            size_mb = _dir_size_mb(db_path)
            present[name] = {"path": db_path, "size_mb": round(size_mb, 1)}
        else:
            missing[name] = {"expected_path": db_path}

    total_size_gb = round(sum(d.get("size_mb", 0) for d in present.values()) / 1024, 2)

    return {
        "detected": True,
        "path": resolved,
        "total_size_gb": total_size_gb,
        "present_databases": list(present.keys()),
        "missing_databases": list(missing.keys()),
        "database_details": present,
        "complete": len(missing) == 0,
    }


def _get_expected_databases() -> dict[str, int]:
    """Return expected AF3 database names with minimum expected sizes (MB).

    These are rough minimums for a functional installation.
    """
    return {
        "bfd": 1700000,          # ~1.7 TB
        "mgy_clusters": 35000,   # ~35 GB
        "pdb_seqres": 2000,      # ~2 GB
        "rnacentral": 15000,     # ~15 GB
        "uniprot": 25000,        # ~25 GB
        "uniref90": 70000,       # ~70 GB
        "nt": 300000,            # ~300 GB
    }


def _dir_size_mb(path: str) -> float:
    """Calculate total size of a directory in MB."""
    total = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
    except Exception:
        pass
    return total / (1024 * 1024)


def _parse_confidence_metrics(output_dir: str, job_name: str) -> dict[str, Any]:
    """Parse AlphaFold3 confidence metrics from output files.

    Args:
        output_dir: AlphaFold3 output directory.
        job_name: Job name used for output files.

    Returns:
        Dict with pLDDT, pTM, ipTM, ranking_score, has_clash, etc.
    """
    metrics: dict[str, Any] = {}

    # Try summary confidences first
    summary_path = os.path.join(output_dir, f"{job_name}_summary_confidences.json")
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r") as f:
                summary = json.load(f)
            metrics["ptm"] = summary.get("ptm")
            metrics["iptm"] = summary.get("iptm")
            metrics["ranking_score"] = summary.get("ranking_score")
            metrics["has_clash"] = summary.get("has_clash", False)
            metrics["fraction_disordered"] = summary.get("fraction_disordered")
            metrics["chain_ptm"] = summary.get("chain_ptm")
            metrics["chain_iptm"] = summary.get("chain_iptm")
        except Exception as exc:
            logger.warning("Failed to parse summary confidences: %s", exc)

    # Try full confidences for pLDDT
    full_conf_path = os.path.join(output_dir, f"{job_name}_confidences.json")
    if os.path.exists(full_conf_path):
        try:
            with open(full_conf_path, "r") as f:
                full_conf = json.load(f)
            # pLDDT is typically in atom_plddts or chain_plddt
            if "atom_plddts" in full_conf:
                plddts = full_conf["atom_plddts"]
                metrics["mean_plddt"] = round(sum(plddts) / len(plddts), 2) if plddts else None
            if "chain_plddt" in full_conf:
                metrics["chain_plddt"] = full_conf["chain_plddt"]
        except Exception as exc:
            logger.warning("Failed to parse full confidences: %s", exc)

    # Fallback: parse ranking_scores.csv
    ranking_path = os.path.join(output_dir, f"{job_name}_ranking_scores.csv")
    if os.path.exists(ranking_path) and not metrics.get("ranking_score"):
        try:
            with open(ranking_path, "r") as f:
                lines = f.readlines()
            if len(lines) > 1:
                parts = lines[1].strip().split(",")
                if len(parts) >= 2:
                    metrics["ranking_score"] = float(parts[1])
        except Exception as exc:
            logger.warning("Failed to parse ranking scores: %s", exc)

    return metrics


def run_alphafold3(params: dict[str, Any], progress_callback: callable) -> dict[str, Any]:
    """Execute AlphaFold3 structure prediction.

    Args:
        params: Dict with AlphaFold3 parameters.
        progress_callback: Function(progress: int) to report progress.

    Returns:
        Result dict with output directory, structures, and confidence metrics.
    """
    progress_callback(5)

    json_path = params["json_path"]
    output_dir = params["output_dir"]
    job_name = params.get("job_name", "af3_design")

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Input JSON not found: {json_path}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        script = _find_alphafold_script()
    except FileNotFoundError:
        from mcp_server.tools.tool_installer import get_missing_tool_prompt
        return get_missing_tool_prompt("alphafold3")

    cmd = [
        "python",
        script,
        f"--json_path={json_path}",
        f"--output_dir={output_dir}",
        f"--num_seeds={params.get('num_seeds', 1)}",
        f"--num_samples={params.get('num_samples', 5)}",
    ]

    if params.get("model_dir"):
        cmd.append(f"--model_dir={params['model_dir']}")

    # Resolve db_dir: explicit param > config > auto-detect
    db_dir = params.get("db_dir") or CONFIG.db_dir or _find_db_dir()
    if db_dir:
        cmd.append(f"--db_dir={db_dir}")
    elif params.get("run_data_pipeline", True):
        # Data pipeline requires databases; warn but don't block
        logger.warning("AlphaFold3 db_dir not configured. MSA search may fail.")

    if not params.get("run_data_pipeline", True):
        cmd.append("--run_data_pipeline=false")

    if params.get("save_embeddings"):
        cmd.append("--save_embeddings=true")

    if params.get("save_distogram"):
        cmd.append("--save_distogram=true")

    if params.get("force_output_dir"):
        cmd.append("--force_output_dir=true")

    logger.info("Running AlphaFold3: %s", " ".join(cmd))
    progress_callback(10)

    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=CONFIG.timeout,
            cwd=os.path.dirname(script),
        )
        progress_callback(90)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"AlphaFold3 failed: {exc.stderr}") from exc
    except subprocess.TimeoutExpired:
        raise RuntimeError("AlphaFold3 timed out")

    # Collect outputs
    cif_files = sorted(glob.glob(os.path.join(output_dir, "*.cif")))

    # Parse confidence metrics
    metrics = _parse_confidence_metrics(output_dir, job_name)

    progress_callback(100)

    return {
        "status": "completed",
        "output_dir": output_dir,
        "structures": cif_files,
        "metrics": metrics,
        "metadata": {
            "job_name": job_name,
            "command": " ".join(cmd),
            "stdout_preview": process.stdout[:500] if process.stdout else "",
        },
    }

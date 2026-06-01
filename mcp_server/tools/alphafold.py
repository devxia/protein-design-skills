"""AlphaFold3 tool implementation for structure prediction and validation.

Supports local Python execution or Docker. Parses confidence metrics
(pLDDT, pTM, ipTM) from output JSON files.

Key improvements:
  - Wrapper script support for custom environment setup
  - Smart MSA pipeline: default ON, auto-skip only if DBs missing AND not forced
  - GPU architecture auto-detection with XLA_FLAGS injection
  - Reliable log capture via file redirection
  - Result aggregation across all seed/sample subdirectories
"""

from __future__ import annotations

import glob
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp_server.utils.config import CONFIG
from mcp_server.utils.conda_utils import run_in_conda, run_in_conda_with_logs
from mcp_server.utils.progress_tracker import track_progress, save_runtime_log
from mcp_server.utils.gpu_utils import get_gpu_info

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
        1. CONFIG.db_dir from config file / env var
        2. Common default locations

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
            if _looks_like_af3_databases(expanded):
                return os.path.abspath(expanded)

    return None


def _looks_like_af3_databases(path: str) -> bool:
    """Heuristic: does this directory look like AlphaFold3 databases?

    We look for at least one known database subdirectory OR known database
    files (for flat-file / direct-download layouts).
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
    known_files = [
        "bfd_metaclust_clu_complete_id30_c90_final_seq.sorted_opt.tar.gz",
        "mgy_clusters.fa",
        "pdb_seqres.txt",
        "rnacentral.fasta",
        "uniprot_all.fasta",
        "uniref90.fasta",
    ]
    try:
        entries = os.listdir(path)
        has_subdir = any(d in entries for d in known_subdirs)
        has_file = any(f in entries for f in known_files)
        return has_subdir or has_file
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
    """Return expected AF3 database names with minimum expected sizes (MB)."""
    return {
        "bfd": 1700000,
        "mgy_clusters": 35000,
        "pdb_seqres": 2000,
        "rnacentral": 15000,
        "uniprot": 25000,
        "uniref90": 70000,
        "nt": 300000,
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


def _get_gpu_arch_flags() -> dict[str, str]:
    """Detect GPU architecture and return recommended XLA / CUDA flags.

    Returns:
        Dict of environment variable name -> value.
    """
    flags: dict[str, str] = {}
    try:
        gpus = get_gpu_info()
        if not gpus.get("available", False):
            return flags

        for gpu in gpus.get("gpus", []):
            arch = gpu.get("compute_capability", "")
            name = gpu.get("name", "").lower()

            # V100 and older (compute < 8.0) need specific XLA flags
            if arch.startswith(("7.", "6.", "5.")) or "v100" in name:
                flags["XLA_FLAGS"] = "--xla_gpu_cuda_data_dir=/usr/local/cuda"
                flags["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
                logger.info("Detected older GPU (%s, compute %s). Setting XLA_FLAGS.", name, arch)
                break

            # A100/H100 and newer
            if arch.startswith(("8.", "9.")):
                flags["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
                break
    except Exception as exc:
        logger.warning("GPU arch detection failed: %s", exc)

    return flags


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


def _collect_all_results(output_dir: str) -> dict[str, Any]:
    """Collect all AlphaFold3 results across seed/sample subdirectories.

    AlphaFold3 may create subdirs like seed-1234_sample-0/ for each run.
    We gather all CIF files and metrics from all subdirectories.

    Args:
        output_dir: Root output directory.

    Returns:
        Dict with all structures, per-seed metrics, and best result.
    """
    result: dict[str, Any] = {
        "all_structures": [],
        "all_metrics": [],
        "best_structure": None,
        "best_metrics": None,
    }

    # Find all CIF files recursively
    cif_files = sorted(glob.glob(os.path.join(output_dir, "**", "*.cif"), recursive=True))
    result["all_structures"] = cif_files

    # Also look for top-level CIFs
    top_cif_files = sorted(glob.glob(os.path.join(output_dir, "*.cif")))
    for f in top_cif_files:
        if f not in cif_files:
            cif_files.append(f)
    result["all_structures"] = sorted(cif_files)

    # Parse metrics from summary JSONs in subdirectories
    summary_files = sorted(glob.glob(os.path.join(output_dir, "**", "*summary_confidences.json"), recursive=True))
    best_score = -1.0
    for summary_path in summary_files:
        try:
            with open(summary_path, "r") as f:
                summary = json.load(f)
            metrics = {
                "ptm": summary.get("ptm"),
                "iptm": summary.get("iptm"),
                "ranking_score": summary.get("ranking_score"),
                "has_clash": summary.get("has_clash", False),
                "mean_plddt": None,
                "source_dir": os.path.dirname(summary_path),
            }
            # Try to get pLDDT from corresponding confidences.json
            conf_path = summary_path.replace("_summary_confidences.json", "_confidences.json")
            if os.path.exists(conf_path):
                with open(conf_path, "r") as f:
                    conf = json.load(f)
                if "atom_plddts" in conf:
                    plddts = conf["atom_plddts"]
                    metrics["mean_plddt"] = round(sum(plddts) / len(plddts), 2) if plddts else None

            result["all_metrics"].append(metrics)

            score = metrics.get("ranking_score", 0) or 0
            if score > best_score:
                best_score = score
                result["best_metrics"] = metrics
                # Find corresponding CIF
                job_name = os.path.basename(summary_path).replace("_summary_confidences.json", "")
                cif_candidates = glob.glob(os.path.join(os.path.dirname(summary_path), f"{job_name}*.cif"))
                if cif_candidates:
                    result["best_structure"] = sorted(cif_candidates)[0]
        except Exception as exc:
            logger.warning("Failed to parse summary %s: %s", summary_path, exc)

    return result


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

    # Determine conda environment: param > config > none
    conda_env = params.get("conda_env") or CONFIG.alphafold_conda_env
    if conda_env:
        logger.info("Using conda environment '%s' for AlphaFold3", conda_env)

    # Support wrapper scripts that set up the environment (env vars, paths, etc.)
    wrapper_script = params.get("wrapper_script")
    if wrapper_script:
        if not os.path.exists(wrapper_script):
            raise FileNotFoundError(f"Wrapper script not found: {wrapper_script}")
        # Wrapper receives the full python command as arguments
        cmd = ["bash", wrapper_script, "python", script]
    else:
        cmd = ["python", script]

    cmd.extend([
        f"--json_path={json_path}",
        f"--output_dir={output_dir}",
        f"--num_seeds={params.get('num_seeds', 1)}",
        f"--num_samples={params.get('num_samples', 5)}",
    ])

    if params.get("model_dir"):
        cmd.append(f"--model_dir={params['model_dir']}")

    # Resolve db_dir: explicit param > config > auto-detect
    db_dir = params.get("db_dir") or CONFIG.db_dir or _find_db_dir()
    db_status = check_af3_database_status(db_dir) if db_dir else {"detected": False}

    # Smart MSA pipeline decision:
    #   - Default: run data pipeline (full MSA search)
    #   - Skip ONLY if user explicitly sets run_data_pipeline=false OR databases are missing
    user_wants_msa = params.get("run_data_pipeline", True)
    if user_wants_msa and not db_status.get("detected"):
        logger.warning(
            "Databases not detected but run_data_pipeline=true. "
            "MSA search may fail. Set run_data_pipeline=false to skip MSA, "
            "or configure db_dir to the correct database path."
        )

    if db_dir:
        cmd.append(f"--db_dir={db_dir}")

    if not user_wants_msa:
        cmd.append("--run_data_pipeline=false")
        logger.info("Skipping MSA data pipeline (run_data_pipeline=false)")

    if params.get("save_embeddings"):
        cmd.append("--save_embeddings=true")

    if params.get("save_distogram"):
        cmd.append("--save_distogram=true")

    if params.get("force_output_dir"):
        cmd.append("--force_output_dir=true")

    logger.info("Running AlphaFold3: %s", " ".join(cmd))
    progress_callback(5)

    num_seeds = params.get("num_seeds", 1)
    num_samples = params.get("num_samples", 5)
    num_expected = num_seeds * num_samples

    start_time = time.time()
    tracker = None
    stdout_log = os.path.join(output_dir, "alphafold3_stdout.log")
    stderr_log = os.path.join(output_dir, "alphafold3_stderr.log")

    # Auto-inject GPU arch environment variables
    env = os.environ.copy()
    gpu_flags = _get_gpu_arch_flags()
    env.update(gpu_flags)
    if gpu_flags:
        logger.info("Injected GPU environment variables: %s", gpu_flags)

    try:
        tracker = track_progress(
            tool_name="alphafold3",
            num_expected=num_expected,
            progress_callback=progress_callback,
            output_dir=output_dir,
            file_pattern="*/*_model.cif",
            with_msa=user_wants_msa,
        )

        if wrapper_script:
            # Wrapper script handles its own env; just run it with file logs
            process = run_in_conda_with_logs(
                cmd,
                conda_env=conda_env,
                stdout_log=stdout_log,
                stderr_log=stderr_log,
                cwd=os.path.dirname(script) if script else ".",
                timeout=CONFIG.timeout,
            )
        else:
            process = run_in_conda_with_logs(
                cmd,
                conda_env=conda_env,
                stdout_log=stdout_log,
                stderr_log=stderr_log,
                cwd=os.path.dirname(script) if script else ".",
                timeout=CONFIG.timeout,
            )

        tracker.stop()

        if process.returncode != 0:
            stderr_preview = ""
            try:
                with open(stderr_log, "r", encoding="utf-8") as f:
                    stderr_preview = f.read()[-1000:]
            except Exception:
                pass
            raise RuntimeError(
                f"AlphaFold3 failed (exit {process.returncode}). "
                f"See {stderr_log} for details. Last lines: {stderr_preview}"
            )

        duration = time.time() - start_time
        save_runtime_log(
            tool_name="alphafold3",
            num_items=num_expected,
            duration_seconds=duration,
            metadata={
                "num_seeds": num_seeds,
                "num_samples": num_samples,
                "with_msa": user_wants_msa,
            },
        )

    except subprocess.TimeoutExpired:
        if tracker:
            tracker.stop()
        raise RuntimeError("AlphaFold3 timed out")

    # Collect all results across subdirectories
    collected = _collect_all_results(output_dir)

    # Parse top-level metrics for backward compatibility
    top_metrics = _parse_confidence_metrics(output_dir, job_name)

    progress_callback(100)

    return {
        "status": "completed",
        "output_dir": output_dir,
        "structures": collected["all_structures"],
        "metrics": top_metrics,
        "metadata": {
            "job_name": job_name,
            "command": " ".join(cmd),
            "duration_seconds": round(duration, 1),
            "stdout_log": stdout_log,
            "stderr_log": stderr_log,
            "num_structures": len(collected["all_structures"]),
            "best_structure": collected["best_structure"],
            "best_metrics": collected["best_metrics"],
            "all_metrics": collected["all_metrics"],
            "gpu_flags": gpu_flags,
            "run_data_pipeline": user_wants_msa,
        },
    }

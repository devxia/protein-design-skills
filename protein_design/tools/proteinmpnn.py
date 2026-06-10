"""ProteinMPNN tool implementation for amino acid sequence design.

Takes backbone PDB structures (from RFdiffusion or user-provided) and
generates amino acid sequences using the ProteinMPNN model.

Supports: direct PDB input, JSONL batch workflow, fixed positions, tied positions
(symmetry), AA bias, PSSM bias, scoring mode, and CA-only models.
"""

import glob
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from protein_design.utils.config import CONFIG
from protein_design.utils.conda_utils import run_in_conda_with_logs
from protein_design.utils.progress_tracker import track_progress, save_runtime_log

logger = logging.getLogger(__name__)


def _find_proteinmpnn_script() -> str:
    """Locate the ProteinMPNN run script.

    Returns:
        Absolute path to protein_mpnn_run.py.

    Raises:
        FileNotFoundError: If script cannot be found.
    """
    if CONFIG.proteinmpnn_path:
        candidate = os.path.join(CONFIG.proteinmpnn_path, "protein_mpnn_run.py")
        if os.path.exists(candidate):
            return candidate

    candidates = [
        "./ProteinMPNN/protein_mpnn_run.py",
        "../ProteinMPNN/protein_mpnn_run.py",
        "~/ProteinMPNN/protein_mpnn_run.py",
        "/opt/ProteinMPNN/protein_mpnn_run.py",
    ]
    for candidate in candidates:
        expanded = os.path.expanduser(candidate)
        if os.path.exists(expanded):
            return os.path.abspath(expanded)

    raise FileNotFoundError(
        "ProteinMPNN protein_mpnn_run.py not found. "
        "Set PROTEINMPNN_PATH env var or install ProteinMPNN."
    )


def run_proteinmpnn(params: dict[str, Any], progress_callback: Callable[[int], None]) -> dict[str, Any]:
    """Execute ProteinMPNN sequence design.

    Args:
        params: Dict with ProteinMPNN parameters.
        progress_callback: Function(progress: int) to report progress.

    Returns:
        Result dict with output directory, FASTA files, and metadata.
    """
    progress_callback(5)

    output_folder = params["output_folder"]
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    # Determine input mode: pdb_path (single) or jsonl_path (batch/multi-chain)
    pdb_path = params.get("pdb_path")
    jsonl_path = params.get("jsonl_path")

    if pdb_path and not os.path.exists(pdb_path):
        raise FileNotFoundError(f"Input PDB not found: {pdb_path}")
    if jsonl_path and not os.path.exists(jsonl_path):
        raise FileNotFoundError(f"Input JSONL not found: {jsonl_path}")

    try:
        script = _find_proteinmpnn_script()
    except FileNotFoundError:
        from protein_design.tools.tool_installer import get_missing_tool_prompt
        return get_missing_tool_prompt("proteinmpnn")

    # Support wrapper scripts that set up the environment
    wrapper_script = params.get("wrapper_script")
    if wrapper_script:
        if not os.path.exists(wrapper_script):
            raise FileNotFoundError(f"Wrapper script not found: {wrapper_script}")
        cmd = ["bash", wrapper_script, "python", script]
    else:
        cmd = ["python", script]

    # Input mode
    if jsonl_path:
        cmd.extend(["--jsonl_path", jsonl_path])
    elif pdb_path:
        cmd.extend(["--pdb_path", pdb_path])

    cmd.extend([
        "--out_folder", output_folder,
        "--num_seq_per_target", str(params.get("num_seq_per_target", 8)),
        "--sampling_temp", str(params.get("sampling_temp", "0.1")),
        "--model_name", params.get("model_name", "v_48_020"),
        "--seed", str(params.get("seed", 37)),
    ])

    # Chain assignments (for jsonl mode)
    if params.get("chain_id_jsonl"):
        cmd.extend(["--chain_id_jsonl", params["chain_id_jsonl"]])

    if params.get("pdb_path_chains"):
        cmd.extend(["--pdb_path_chains", params["pdb_path_chains"]])

    if params.get("fixed_positions_jsonl"):
        cmd.extend(["--fixed_positions_jsonl", params["fixed_positions_jsonl"]])

    if params.get("tied_positions_jsonl"):
        cmd.extend(["--tied_positions_jsonl", params["tied_positions_jsonl"]])

    if params.get("bias_AA_jsonl"):
        cmd.extend(["--bias_AA_jsonl", params["bias_AA_jsonl"]])

    if params.get("bias_by_res_jsonl"):
        cmd.extend(["--bias_by_res_jsonl", params["bias_by_res_jsonl"]])

    if params.get("pssm_jsonl"):
        cmd.extend(["--pssm_jsonl", params["pssm_jsonl"]])

    if "pssm_multi" in params and params["pssm_multi"] is not None:
        cmd.extend(["--pssm_multi", str(params["pssm_multi"])])

    if params.get("use_soluble_model"):
        cmd.append("--use_soluble_model")

    if params.get("backbone_noise"):
        cmd.extend(["--backbone_noise", str(params["backbone_noise"])])

    if params.get("omit_AAs"):
        cmd.extend(["--omit_AAs", params["omit_AAs"]])

    if params.get("save_score"):
        cmd.extend(["--save_score", str(int(params["save_score"]))])

    if params.get("save_probs"):
        cmd.extend(["--save_probs", str(int(params["save_probs"]))])

    if params.get("score_only"):
        cmd.extend(["--score_only", str(int(params["score_only"]))])

    if params.get("path_to_fasta"):
        cmd.extend(["--path_to_fasta", params["path_to_fasta"]])

    if params.get("ca_only"):
        cmd.append("--ca_only")

    if "batch_size" in params and params["batch_size"] is not None:
        cmd.extend(["--batch_size", str(params["batch_size"])])

    if params.get("path_to_model_weights"):
        cmd.extend(["--path_to_model_weights", params["path_to_model_weights"]])

    # Determine conda environment: param > config > none
    conda_env = params.get("conda_env") or CONFIG.proteinmpnn_conda_env
    if conda_env:
        logger.info("Using conda environment '%s' for ProteinMPNN", conda_env)

    logger.info("Running ProteinMPNN: %s", " ".join(cmd))
    progress_callback(5)

    start_time = time.time()
    tracker = None
    stdout_log = os.path.join(output_folder, "proteinmpnn_stdout.log")
    stderr_log = os.path.join(output_folder, "proteinmpnn_stderr.log")
    try:
        tracker = track_progress(
            tool_name="proteinmpnn",
            num_expected=params.get("num_seq_per_target", 8),
            progress_callback=progress_callback,
            output_dir=os.path.join(output_folder, "seqs"),
            file_pattern="*.fa",
        )

        process = run_in_conda_with_logs(
            cmd,
            conda_env=conda_env,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            cwd=os.path.dirname(script),
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
                f"ProteinMPNN failed (exit {process.returncode}). "
                f"See {stderr_log} for details. Last lines: {stderr_preview}"
            )

        duration = time.time() - start_time
        save_runtime_log(
            tool_name="proteinmpnn",
            num_items=params.get("num_seq_per_target", 8),
            duration_seconds=duration,
            metadata={
                "model_name": params.get("model_name", "v_48_020"),
                "mode": "jsonl" if jsonl_path else "pdb",
                "score_only": params.get("score_only", False),
            },
        )

    except subprocess.TimeoutExpired:
        if tracker:
            tracker.stop()
        raise RuntimeError("ProteinMPNN timed out")

    # Collect outputs
    fasta_files = sorted(glob.glob(os.path.join(output_folder, "seqs", "*.fa")))
    if not fasta_files:
        fasta_files = sorted(glob.glob(os.path.join(output_folder, "seqs", "*.fasta")))

    npz_files = []
    if os.path.exists(os.path.join(output_folder, "scores")):
        npz_files = sorted(glob.glob(os.path.join(output_folder, "scores", "*.npz")))

    progress_callback(100)

    return {
        "status": "completed",
        "output_dir": output_folder,
        "sequences": fasta_files,
        "metadata": {
            "num_fasta": len(fasta_files),
            "score_files": npz_files,
            "command": " ".join(cmd),
            "stdout_log": stdout_log,
            "stderr_log": stderr_log,
            "duration_seconds": round(duration, 1),
        },
    }

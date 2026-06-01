"""RFdiffusion tool implementation for protein backbone generation.

Supports: unconditional monomers, motif scaffolding, binder design,
partial diffusion, and symmetric oligomers.

Input PDBs are automatically preprocessed with PDBFixer unless
skip_preprocessing=True.
"""

import glob
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp_server.tools.pdbfixer_tool import preprocess_for_design
from mcp_server.utils.config import CONFIG
from mcp_server.utils.conda_utils import run_in_conda_popen
from mcp_server.utils.progress_tracker import track_progress, save_runtime_log

logger = logging.getLogger(__name__)


def _find_rfdiffusion_script() -> str:
    """Locate the RFdiffusion run_inference.py script.

    Returns:
        Absolute path to scripts/run_inference.py.

    Raises:
        FileNotFoundError: If script cannot be found.
    """
    if CONFIG.rfdiffusion_path:
        candidate = os.path.join(CONFIG.rfdiffusion_path, "scripts", "run_inference.py")
        if os.path.exists(candidate):
            return candidate

    # Common install locations
    candidates = [
        "./RFdiffusion/scripts/run_inference.py",
        "../RFdiffusion/scripts/run_inference.py",
        "~/RFdiffusion/scripts/run_inference.py",
        "/opt/RFdiffusion/scripts/run_inference.py",
    ]
    for candidate in candidates:
        expanded = os.path.expanduser(candidate)
        if os.path.exists(expanded):
            return os.path.abspath(expanded)

    raise FileNotFoundError(
        "RFdiffusion run_inference.py not found. "
        "Set RFDIFFUSION_PATH env var or install RFdiffusion."
    )


def run_rfdiffusion(params: dict[str, Any], progress_callback: callable) -> dict[str, Any]:
    """Execute RFdiffusion backbone generation.

    Args:
        params: Dict with RFdiffusion parameters.
        progress_callback: Function(progress: int) to report progress.

    Returns:
        Result dict with output directory, generated PDBs, and metadata.
    """
    progress_callback(5)

    output_prefix = params["output_prefix"]
    contig = params["contig"]
    num_designs = int(params.get("num_designs", 10))
    input_pdb = params.get("input_pdb")

    # Ensure output directory exists
    output_dir = os.path.dirname(output_prefix)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Auto-preprocess input PDB unless explicitly skipped
    if input_pdb and not params.get("skip_preprocessing", False):
        original_pdb = input_pdb
        fixed_pdb = os.path.join(output_dir, "input_fixed.pdb")
        keep_chains = params.get("keep_chains")
        if isinstance(keep_chains, str):
            keep_chains = [c.strip() for c in keep_chains.split(",")]

        logger.info("Preprocessing input PDB with PDBFixer: %s", original_pdb)
        preprocess_for_design(original_pdb, fixed_pdb, keep_chains=keep_chains)
        input_pdb = fixed_pdb
        progress_callback(15)

    # Build Hydra config overrides
    overrides = [
        f"inference.output_prefix={output_prefix}",
        f"inference.num_designs={num_designs}",
        f"'contigmap.contigs=[{contig}]'",
    ]

    if input_pdb:
        overrides.append(f"inference.input_pdb={input_pdb}")

    if "hotspot_res" in params and params["hotspot_res"]:
        hotspots = params["hotspot_res"]
        if isinstance(hotspots, list):
            hotspots = ",".join(hotspots)
        overrides.append(f"'ppi.hotspot_res=[{hotspots}]'")

    if params.get("symmetry"):
        overrides.append(f"inference.symmetry={params['symmetry']}")

    if "diffuser_T" in params:
        overrides.append(f"diffuser.T={params['diffuser_T']}")

    if params.get("ckpt_override_path"):
        overrides.append(f"inference.ckpt_override_path={params['ckpt_override_path']}")

    try:
        script = _find_rfdiffusion_script()
    except FileNotFoundError:
        from mcp_server.tools.tool_installer import get_missing_tool_prompt
        return get_missing_tool_prompt("rfdiffusion")

    cmd = ["python", script] + overrides

    # Determine conda environment: param > config > none
    conda_env = params.get("conda_env") or CONFIG.rfdiffusion_conda_env
    if conda_env:
        logger.info("Using conda environment '%s' for RFdiffusion", conda_env)

    logger.info("Running RFdiffusion: %s", " ".join(cmd))
    progress_callback(5)

    start_time = time.time()
    tracker = None
    try:
        process = run_in_conda_popen(
            cmd,
            conda_env=conda_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(script),
        )

        # Start file-system + ETA progress tracker
        tracker = track_progress(
            tool_name="rfdiffusion",
            num_expected=num_designs,
            progress_callback=progress_callback,
            output_dir=output_dir,
            file_pattern="design_*.pdb",
        )

        stdout, stderr = process.communicate(timeout=CONFIG.timeout)

        tracker.stop()

        if process.returncode != 0:
            raise RuntimeError(f"RFdiffusion failed (exit {process.returncode}): {stderr}")

        # Record actual runtime for future ETA estimates
        duration = time.time() - start_time
        save_runtime_log(
            tool_name="rfdiffusion",
            num_items=num_designs,
            duration_seconds=duration,
            metadata={"contig": contig, "diffuser_T": params.get("diffuser_T", 50)},
        )

    except subprocess.TimeoutExpired:
        if tracker:
            tracker.stop()
        process.kill()
        raise RuntimeError("RFdiffusion timed out")

    # Collect output PDBs
    pdb_files = sorted(glob.glob(os.path.join(output_dir, "design_*.pdb")))
    trb_files = sorted(glob.glob(os.path.join(output_dir, "design_*.trb")))

    progress_callback(100)

    return {
        "status": "completed",
        "output_dir": output_dir,
        "structures": pdb_files,
        "metadata": {
            "num_designs": len(pdb_files),
            "trb_files": trb_files,
            "contig": contig,
            "command": " ".join(cmd),
            "duration_seconds": round(duration, 1),
        },
    }

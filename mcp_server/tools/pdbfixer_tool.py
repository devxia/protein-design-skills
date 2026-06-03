"""PDB structure preprocessing tool using PDBFixer Python API.

This is Stage 0 of the protein design pipeline — a mandatory preprocessing
step before any design tool (RFdiffusion, ProteinMPNN, AlphaFold3).

Handles: non-standard residue conversion, heterogen removal, missing heavy
atom reconstruction. Does NOT add hydrogens (design tools don't need them).

Supports both in-process execution and cross-conda-environment execution
via the ``conda_env`` parameter.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Self-contained PDBFixer script template for execution in external conda envs.
# Must NOT import anything from mcp_server — only pdbfixer + stdlib.
_PDBFIXER_SCRIPT_TEMPLATE = r'''import json
import os
import sys
from pathlib import Path

input_pdb = sys.argv[1]
output_pdb = sys.argv[2]
keep_chains_raw = sys.argv[3]  # comma-separated or "__none__"
seed = int(sys.argv[4])

keep_chains = None
if keep_chains_raw != "__none__":
    keep_chains = [c.strip() for c in keep_chains_raw.split(",") if c.strip()]

from pdbfixer import PDBFixer
from openmm.app import PDBFile

fixer = PDBFixer(filename=input_pdb)
log = {"input": input_pdb, "fixes": []}

# 1. Keep only specified chains
if keep_chains:
    all_chains = list(fixer.topology.chains())
    to_remove = [i for i, chain in enumerate(all_chains) if chain.id not in keep_chains]
    if to_remove:
        fixer.removeChains(chainIndices=to_remove)
        removed_ids = [all_chains[i].id for i in to_remove]
        log["fixes"].append(f"removed_chains: {removed_ids}")

# 2. Non-standard residues
fixer.findNonstandardResidues()
if fixer.nonstandardResidues:
    replacements = [f"{residue.name}->{standard}" for residue, standard in fixer.nonstandardResidues]
    log["fixes"].append(f"nonstandard_residues: {replacements}")
    fixer.replaceNonstandardResidues()
else:
    log["fixes"].append("no_nonstandard_residues")

# 3. Remove heterogens
removed = fixer.removeHeterogens(keepWater=False)
if removed:
    het_names = sorted(set(r.name for r in removed))
    log["fixes"].append(f"removed_heterogens: {het_names}")
else:
    log["fixes"].append("no_heterogens")

# 4. Missing residues (warn but do NOT add)
fixer.findMissingResidues()
if fixer.missingResidues:
    missing_info = [f"chain_{chain_id}_pos_{residue_idx}: {residue_names}"
                    for (chain_id, residue_idx), residue_names in fixer.missingResidues.items()]
    log["fixes"].append(f"missing_residues_skipped: {missing_info}")
    log["warnings"] = ["Missing residues detected but NOT added (automatic loop building is unreliable)."]
    fixer.missingResidues = {}
else:
    log["fixes"].append("no_missing_residues")

# 5. Missing heavy atoms
fixer.findMissingAtoms()
if fixer.missingAtoms:
    missing_count = len(fixer.missingAtoms)
    log["fixes"].append(f"added_missing_atoms: {missing_count}_residues")
    fixer.addMissingAtoms(seed=seed)
else:
    log["fixes"].append("no_missing_atoms")

# 6. Write output
Path(output_pdb).parent.mkdir(parents=True, exist_ok=True)
with open(output_pdb, "w", encoding="utf-8") as f:
    PDBFile.writeFile(fixer.topology, fixer.positions, f)
log["output"] = output_pdb

# Emit JSON result on stdout
print(json.dumps(log))
'''


def _import_pdbfixer() -> tuple[Any, Any]:
    """Lazy-import PDBFixer to provide friendly error on missing dependency."""
    try:
        from pdbfixer import PDBFixer
        from openmm.app import PDBFile
        return PDBFixer, PDBFile
    except ImportError:
        from mcp_server.tools.tool_installer import get_missing_tool_prompt
        raise RuntimeError(get_missing_tool_prompt("pdbfixer"))


def _run_pdbfixer_in_conda(
    input_pdb: str,
    output_pdb: str,
    keep_chains: Optional[list[str]],
    seed: int,
    conda_env: str,
) -> dict[str, Any]:
    """Run PDBFixer preprocessing in an external conda environment.

    Generates a self-contained temporary Python script and executes it
    inside the specified conda environment via ``conda run``.

    Args:
        input_pdb: Path to input PDB file.
        output_pdb: Path for the preprocessed output PDB file.
        keep_chains: Optional list of chain IDs to retain.
        seed: Random seed for missing atom reconstruction.
        conda_env: Name of the target conda environment.

    Returns:
        Processing log dict.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_pdbfixer.py", delete=False
    ) as f:
        f.write(_PDBFIXER_SCRIPT_TEMPLATE)
        script_path = f.name

    keep_str = ",".join(keep_chains) if keep_chains else "__none__"

    try:
        from mcp_server.utils.conda_utils import run_in_conda_with_logs

        stdout_log = os.path.join(
            os.path.dirname(output_pdb), "pdbfixer_stdout.log"
        )
        stderr_log = os.path.join(
            os.path.dirname(output_pdb), "pdbfixer_stderr.log"
        )

        run_in_conda_with_logs(
            ["python", script_path, input_pdb, output_pdb, keep_str, str(seed)],
            conda_env=conda_env,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
        )

        # Parse JSON result from stdout log
        with open(stdout_log, "r", encoding="utf-8") as f:
            # The last non-empty line should be the JSON output
            lines = [ln.strip() for ln in f.readlines() if ln.strip()]
            if not lines:
                raise RuntimeError("PDBFixer produced no output")

            # Try the last line first (most likely the JSON result)
            for line in reversed(lines):
                try:
                    result = json.loads(line)
                    if "fixes" in result:
                        return result
                except json.JSONDecodeError:
                    continue

            # Fallback: try to parse any JSON object in the output
            for line in lines:
                try:
                    result = json.loads(line)
                    if isinstance(result, dict) and "fixes" in result:
                        return result
                except json.JSONDecodeError:
                    continue

            raise RuntimeError(
                f"Could not parse PDBFixer output. See {stdout_log} and {stderr_log}"
            )

    finally:
        # Clean up temporary script
        try:
            os.unlink(script_path)
        except OSError:
            pass


def preprocess_for_design(
    input_pdb: str,
    output_pdb: str,
    keep_chains: Optional[list[str]] = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Preprocess a PDB file for protein design workflows.

    This is a mandatory step before RFdiffusion/ProteinMPNN. It repairs
    structural issues that would cause downstream tools to fail.

    Processing steps (in order):
        1. Optional: retain only specified chains
        2. Convert non-standard residues to standard (e.g., MSE → MET)
        3. Remove all heterogens (ligands, ions, water)
        4. Detect missing residues (warn, do NOT add — quality unreliable)
        5. Find and add missing heavy atoms (N, CA, C, O)
        6. Do NOT add hydrogens (not needed for design)

    Args:
        input_pdb: Path to input PDB file (also supports .cif, .pdbx).
        output_pdb: Path for the preprocessed output PDB file.
        keep_chains: Optional list of chain IDs to retain (e.g., ["A", "B"]).
                     If None, all chains are kept.
        seed: Random seed for missing atom reconstruction.

    Returns:
        Dict with processing log and output path.

    Raises:
        FileNotFoundError: If input_pdb does not exist.
        ValueError: If the structure contains no atoms.
    """
    input_path = Path(input_pdb)
    if not input_path.exists():
        raise FileNotFoundError(f"Input PDB not found: {input_pdb}")

    PDBFixer, PDBFile = _import_pdbfixer()

    fixer = PDBFixer(filename=str(input_pdb))
    log: dict[str, Any] = {"input": str(input_pdb), "fixes": []}

    # 1. Optional: keep only specified chains
    if keep_chains:
        all_chains = list(fixer.topology.chains())
        to_remove = [
            i for i, chain in enumerate(all_chains)
            if chain.id not in keep_chains
        ]
        if to_remove:
            fixer.removeChains(chainIndices=to_remove)
            removed_ids = [all_chains[i].id for i in to_remove]
            log["fixes"].append(f"removed_chains: {removed_ids}")
            logger.info("Removed chains: %s", removed_ids)

    # 2. Find and replace non-standard residues (e.g., MSE → MET)
    fixer.findNonstandardResidues()
    if fixer.nonstandardResidues:
        replacements = [
            f"{residue.name}→{standard}"
            for residue, standard in fixer.nonstandardResidues
        ]
        log["fixes"].append(f"nonstandard_residues: {replacements}")
        logger.info("Replacing non-standard residues: %s", replacements)
        fixer.replaceNonstandardResidues()
    else:
        log["fixes"].append("no_nonstandard_residues")

    # 3. Remove all heterogens (keepWater=False deletes everything)
    removed = fixer.removeHeterogens(keepWater=False)
    if removed:
        het_names = sorted(set(r.name for r in removed))
        log["fixes"].append(f"removed_heterogens: {het_names}")
        logger.info("Removed heterogens: %s", het_names)
    else:
        log["fixes"].append("no_heterogens")

    # 4. Check missing residues — warn but DO NOT add (quality unreliable)
    fixer.findMissingResidues()
    if fixer.missingResidues:
        missing_info = [
            f"chain_{chain_id}_pos_{residue_idx}: {residue_names}"
            for (chain_id, residue_idx), residue_names in fixer.missingResidues.items()
        ]
        log["fixes"].append(f"missing_residues_skipped: {missing_info}")
        log["warnings"] = [
            "Missing residues detected but NOT added (automatic loop building is unreliable). "
            "Consider providing a more complete structure or using experimental data."
        ]
        logger.warning("Missing residues detected, skipping automatic addition: %s", missing_info)
        # Clear missing residues so addMissingAtoms won't try to add them
        fixer.missingResidues = {}
    else:
        log["fixes"].append("no_missing_residues")

    # 5. Find and add missing heavy atoms (critical for downstream tools)
    fixer.findMissingAtoms()
    if fixer.missingAtoms:
        missing_count = len(fixer.missingAtoms)
        log["fixes"].append(f"added_missing_atoms: {missing_count}_residues")
        logger.info("Adding missing heavy atoms for %d residues", missing_count)
        fixer.addMissingAtoms(seed=seed)
    else:
        log["fixes"].append("no_missing_atoms")

    # 6. Do NOT add hydrogens — RFdiffusion/ProteinMPNN only need backbone atoms
    # (Intentionally skipped)

    # 7. Ensure output directory exists
    Path(output_pdb).parent.mkdir(parents=True, exist_ok=True)

    # 8. Write preprocessed structure
    with open(output_pdb, "w", encoding="utf-8") as f:
        PDBFile.writeFile(fixer.topology, fixer.positions, f)
    log["output"] = output_pdb

    logger.info("Preprocessing complete: %s → %s", input_pdb, output_pdb)
    return log


def run_pdbfixer(params: dict[str, Any], progress_callback: callable) -> dict[str, Any]:
    """Execute PDBFixer preprocessing as an MCP tool.

    Supports both in-process execution (default) and cross-conda-environment
    execution via the ``conda_env`` parameter.

    Args:
        params: Dict with input_pdb, output_pdb, keep_chains, seed, conda_env.
        progress_callback: Function(progress: int) to update progress.

    Returns:
        Result dict with status, output_path, and log.
    """
    conda_env = params.get("conda_env")

    # Early dependency check (only when running in-process)
    if not conda_env:
        try:
            _import_pdbfixer()
        except RuntimeError as exc:
            return exc.args[0] if exc.args else {"error": "PDBFixer not installed"}

    progress_callback(10)

    input_pdb = params["input_pdb"]
    output_pdb = params.get("output_pdb")

    if not output_pdb:
        # Auto-generate output path
        base = os.path.splitext(os.path.basename(input_pdb))[0]
        output_dir = params.get("output_dir", "/tmp/protein-design")
        output_pdb = os.path.join(output_dir, f"{base}_fixed.pdb")

    keep_chains = params.get("keep_chains")
    if isinstance(keep_chains, str):
        keep_chains = [c.strip() for c in keep_chains.split(",")]

    seed = int(params.get("seed", 42))

    progress_callback(30)

    if conda_env:
        log = _run_pdbfixer_in_conda(
            input_pdb, output_pdb, keep_chains, seed, conda_env
        )
    else:
        log = preprocess_for_design(
            input_pdb, output_pdb, keep_chains=keep_chains, seed=seed
        )

    progress_callback(100)

    result = {
        "status": "completed",
        "output_path": output_pdb,
        "output_dir": os.path.dirname(output_pdb),
        "log": log,
    }
    if conda_env:
        result["conda_env"] = conda_env
    return result

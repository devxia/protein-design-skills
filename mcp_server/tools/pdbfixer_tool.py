"""PDB structure preprocessing tool using PDBFixer Python API.

This is Stage 0 of the protein design pipeline — a mandatory preprocessing
step before any design tool (RFdiffusion, ProteinMPNN, AlphaFold3).

Handles: non-standard residue conversion, heterogen removal, missing heavy
atom reconstruction. Does NOT add hydrogens (design tools don't need them).
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _import_pdbfixer() -> tuple[Any, Any]:
    """Lazy-import PDBFixer to provide friendly error on missing dependency."""
    try:
        from pdbfixer import PDBFixer
        from openmm.app import PDBFile
        return PDBFixer, PDBFile
    except ImportError:
        from mcp_server.tools.tool_installer import get_missing_tool_prompt
        raise RuntimeError(get_missing_tool_prompt("pdbfixer"))


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
    PDBFile.writeFile(fixer.topology, fixer.positions, open(output_pdb, "w"))
    log["output"] = output_pdb

    logger.info("Preprocessing complete: %s → %s", input_pdb, output_pdb)
    return log


def run_pdbfixer(params: dict[str, Any], progress_callback: callable) -> dict[str, Any]:
    """Execute PDBFixer preprocessing as an MCP tool.

    Args:
        params: Dict with input_pdb, output_pdb, keep_chains, seed.
        progress_callback: Function(progress: int) to update progress.

    Returns:
        Result dict with status, output_path, and log.
    """
    # Early dependency check
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
    log = preprocess_for_design(input_pdb, output_pdb, keep_chains=keep_chains, seed=seed)
    progress_callback(100)

    return {
        "status": "completed",
        "output_path": output_pdb,
        "output_dir": os.path.dirname(output_pdb),
        "log": log,
    }

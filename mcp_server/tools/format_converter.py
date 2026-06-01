"""Format conversion utilities for protein design pipeline.

Converts between file formats used by different tools:
- ProteinMPNN FASTA → AlphaFold3 JSON
- PDB validation and standardization
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from Bio import SeqIO

logger = logging.getLogger(__name__)


def fasta_to_alphafold3_json(
    fasta_path: str,
    job_name: str,
    seed: int = 1,
    output_path: str | None = None,
) -> str:
    """Convert ProteinMPNN output FASTA to AlphaFold3 input JSON.

    ProteinMPNN FASTA format:
    - First record is the native/reference sequence
    - Subsequent records start with "T=" (generated sequences at temperature T)
    - Multi-chain sequences are separated by "/"
    - Chains are ordered alphabetically

    Args:
        fasta_path: Path to ProteinMPNN output FASTA.
        job_name: Job name for AlphaFold3.
        seed: Random seed for AlphaFold3.
        output_path: Optional explicit output JSON path.

    Returns:
        Path to the generated JSON file.
    """
    records = list(SeqIO.parse(fasta_path, "fasta"))
    if not records:
        raise ValueError(f"No sequences found in FASTA: {fasta_path}")

    # Find first generated sequence (skip native/reference)
    design_seq = None
    for record in records:
        if record.id.startswith("T="):
            design_seq = str(record.seq)
            break

    # Fallback to first record if no generated sequences found
    if not design_seq:
        design_seq = str(records[0].seq)
        logger.warning("No generated sequences (T=) found, using first record")

    # Split by "/" for multi-chain
    chains = design_seq.split("/")

    # Build AlphaFold3 JSON
    sequences = []
    for i, chain_seq in enumerate(chains):
        chain_id = chr(ord("A") + i)  # A, B, C, ...
        sequences.append({
            "protein": {
                "id": chain_id,
                "sequence": chain_seq.upper(),
                "modifications": [],
            }
        })

    af3_input = {
        "name": job_name,
        "modelSeeds": [seed],
        "sequences": sequences,
        "dialect": "alphafold3",
        "version": 4,
    }

    if not output_path:
        output_dir = os.path.dirname(fasta_path) or "."
        output_path = os.path.join(output_dir, f"{job_name}_af3_input.json")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(af3_input, f, indent=2)

    logger.info("Converted FASTA to AlphaFold3 JSON: %s", output_path)
    return output_path


def validate_pdb(pdb_path: str) -> dict[str, Any]:
    """Validate a PDB file and return standardized info.

    Args:
        pdb_path: Path to PDB file.

    Returns:
        Dict with validation status, chain info, residue counts, etc.
    """
    from Bio.PDB import PDBParser

    result: dict[str, Any] = {"valid": False, "path": pdb_path}

    try:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("structure", pdb_path)

        chains = []
        total_residues = 0
        total_atoms = 0

        for model in structure:
            for chain in model:
                chain_id = chain.id
                residues = list(chain.get_residues())
                residue_count = len(residues)
                atom_count = sum(len(list(r.get_atoms())) for r in residues)

                chains.append({
                    "id": chain_id,
                    "residue_count": residue_count,
                    "atom_count": atom_count,
                    "residue_range": f"{residues[0].id[1]}-{residues[-1].id[1]}" if residues else "none",
                })
                total_residues += residue_count
                total_atoms += atom_count

        result.update({
            "valid": True,
            "num_chains": len(chains),
            "chains": chains,
            "total_residues": total_residues,
            "total_atoms": total_atoms,
        })

    except Exception as exc:
        result["error"] = str(exc)

    return result


def convert_format(params: dict[str, Any]) -> dict[str, Any]:
    """Execute format conversion based on parameters.

    Args:
        params: Dict with from_format, to_format, input_path, etc.

    Returns:
        Result dict with output path and conversion info.
    """
    from_format = params["from_format"]
    to_format = params["to_format"]
    input_path = params["input_path"]
    output_path = params.get("output_path")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if from_format == "fasta" and to_format == "alphafold3_json":
        job_name = params.get("job_name", "design")
        seed = int(params.get("seed", 1))
        json_path = fasta_to_alphafold3_json(input_path, job_name, seed, output_path)
        return {
            "status": "completed",
            "input_path": input_path,
            "output_path": json_path,
            "from_format": from_format,
            "to_format": to_format,
        }

    if from_format == "pdb" and to_format == "validated_pdb":
        validation = validate_pdb(input_path)
        return {
            "status": "completed",
            "input_path": input_path,
            "validation": validation,
            "from_format": from_format,
            "to_format": to_format,
        }

    raise ValueError(f"Unsupported conversion: {from_format} -> {to_format}")

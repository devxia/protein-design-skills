"""Format conversion utilities for protein design pipeline.

Converts between file formats used by different tools:
- ProteinMPNN FASTA → AlphaFold3 JSON
- PDB validation and standardization
- Raw sequence string → AlphaFold3 JSON

AlphaFold3 JSON schema support:
  - "protein" key (older AF3 server/local versions)
  - "proteinChain" key (newer AF3 versions)
  Auto-detects based on user preference or defaults to "protein".
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from Bio import SeqIO

logger = logging.getLogger(__name__)

# Standard amino acid residues
STANDARD_AAS = set("ACDEFGHIKLMNPQRSTVWY")


def _validate_sequence(seq: str) -> tuple[bool, list[str]]:
    """Validate that a sequence contains only standard amino acids.

    Args:
        seq: Protein sequence string.

    Returns:
        Tuple of (is_valid, list_of_invalid_chars).
    """
    invalid = [c for c in seq.upper() if c not in STANDARD_AAS]
    return len(invalid) == 0, invalid


def _build_af3_sequence(
    chain_seq: str,
    chain_id: str,
    schema: str = "protein",
) -> dict[str, Any]:
    """Build a single AlphaFold3 sequence entry.

    Args:
        chain_seq: Amino acid sequence.
        chain_id: Chain identifier (e.g., "A", "B").
        schema: Either "protein" or "proteinChain".

    Returns:
        AF3 sequence dict.
    """
    chain_seq = chain_seq.upper().strip()
    is_valid, invalid = _validate_sequence(chain_seq)
    if not is_valid:
        logger.warning(
            "Chain %s contains non-standard residues: %s", chain_id, invalid
        )

    if schema == "proteinChain":
        return {
            "proteinChain": {
                "id": chain_id,
                "sequence": chain_seq,
                "unpairedMsa": None,
                "pairedMsa": None,
                "templates": None,
            }
        }
    else:
        return {
            "protein": {
                "id": chain_id,
                "sequence": chain_seq,
                "modifications": [],
                "unpairedMsa": None,
                "pairedMsa": None,
                "templates": None,
            }
        }


def fasta_to_alphafold3_json(
    fasta_path: str,
    job_name: str,
    seed: int = 1,
    output_path: str | None = None,
    schema: str = "protein",
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
        schema: AF3 JSON schema variant — "protein" or "proteinChain".

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

    return sequence_to_alphafold3_json(
        sequence=design_seq,
        job_name=job_name,
        seed=seed,
        output_path=output_path,
        schema=schema,
        source_fasta=fasta_path,
    )


def sequence_to_alphafold3_json(
    sequence: str,
    job_name: str,
    seed: int = 1,
    output_path: str | None = None,
    schema: str = "protein",
    source_fasta: str | None = None,
) -> str:
    """Convert a raw protein sequence (possibly multi-chain) to AlphaFold3 JSON.

    Args:
        sequence: Protein sequence string. Multi-chain sequences use "/" separator.
        job_name: Job name for AlphaFold3.
        seed: Random seed.
        output_path: Optional explicit output JSON path.
        schema: AF3 JSON schema variant — "protein" or "proteinChain".
        source_fasta: Optional source FASTA path for metadata.

    Returns:
        Path to the generated JSON file.
    """
    # Split by "/" for multi-chain
    chains = [c.strip() for c in sequence.split("/") if c.strip()]
    if not chains:
        raise ValueError(f"No valid sequences after splitting: {sequence}")

    # Build AlphaFold3 JSON
    sequences = []
    for i, chain_seq in enumerate(chains):
        chain_id = chr(ord("A") + i)  # A, B, C, ...
        sequences.append(_build_af3_sequence(chain_seq, chain_id, schema=schema))

    af3_input: dict[str, Any] = {
        "name": job_name,
        "modelSeeds": [seed],
        "sequences": sequences,
        "dialect": "alphafold3",
        "version": 4,
    }

    if not output_path:
        output_dir = os.path.dirname(source_fasta or ".") or "."
        output_path = os.path.join(output_dir, f"{job_name}_af3_input.json")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(af3_input, f, indent=2)

    logger.info("Converted sequence to AlphaFold3 JSON (%s schema): %s", schema, output_path)
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
    schema = params.get("schema", "protein")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if from_format == "fasta" and to_format == "alphafold3_json":
        job_name = params.get("job_name", "design")
        seed = int(params.get("seed", 1))
        json_path = fasta_to_alphafold3_json(
            input_path, job_name, seed, output_path, schema=schema
        )
        return {
            "status": "completed",
            "input_path": input_path,
            "output_path": json_path,
            "from_format": from_format,
            "to_format": to_format,
            "schema": schema,
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

#!/usr/bin/env python3
"""UserPromptSubmit hook: auto-generate optimized parameters for protein design tasks.

Analyzes user design goals and outputs tailored parameter sets for each pipeline
stage, reducing trial-and-error in parameter selection.
"""

import json
import re
import sys
from typing import Any


def _parse_design_goal(text: str) -> dict[str, Any]:
    """Extract design parameters from user text."""
    text_lower = text.lower()
    result: dict[str, Any] = {
        "design_type": "unknown",
        "length": None,
        "num_designs": None,
        "target_pdb": None,
        "has_ligand": False,
    }

    # Detect design type
    if any(kw in text_lower for kw in ["binder", "bind to", "binding"]):
        result["design_type"] = "binder"
    elif any(kw in text_lower for kw in ["scaffold", "motif", "preserve", "around"]):
        result["design_type"] = "motif_scaffolding"
    elif any(kw in text_lower for kw in ["symmetric", "oligomer", "dimer", "trimer", "c2", "c3"]):
        result["design_type"] = "symmetric"
    elif any(kw in text_lower for kw in ["peptide", "cyclic", "macrocycle"]):
        result["design_type"] = "peptide"
    elif any(kw in text_lower for kw in ["enzyme", "cofactor", "heme", "ligand", "small molecule"]):
        result["design_type"] = "ligand"
    elif any(kw in text_lower for kw in ["de novo", "from scratch", "monomer", "generate"]):
        result["design_type"] = "unconditional"

    # Extract length
    length_match = re.search(r'(\d+)\s*(?:residue|aa|amino acid)', text_lower)
    if length_match:
        result["length"] = int(length_match.group(1))

    # Extract number of designs
    num_match = re.search(r'(\d+)\s*designs?', text_lower)
    if num_match:
        result["num_designs"] = int(num_match.group(1))

    # Extract PDB file
    pdb_match = re.search(r'(\S+\.pdb)', text, re.IGNORECASE)
    if pdb_match:
        result["target_pdb"] = pdb_match.group(1)

    # Detect ligand
    if any(kw in text_lower for kw in ["ligand", "cofactor", "heme", "small molecule", "metal"]):
        result["has_ligand"] = True

    return result


def _generate_rfdiffusion_params(goal: dict[str, Any]) -> dict[str, Any]:
    """Generate RFdiffusion parameters."""
    dt = goal["design_type"]
    length = goal.get("length", 150)
    num = goal.get("num_designs", 20)
    pdb = goal.get("target_pdb", "input.pdb")

    params: dict[str, Any] = {"num_designs": num, "diffuser_T": 50}

    if dt == "unconditional":
        params["contig"] = f"[{length}-{length}]"
        params["output_prefix"] = "outputs/unconditional/design"
    elif dt == "binder":
        binder_len = min(length, 100)
        params["contig"] = f"[B1-{binder_len}/0 {binder_len}-{binder_len}]"
        params["input_pdb"] = pdb
        params["hotspot_res"] = ["A30", "A33", "A34"]
        params["output_prefix"] = "outputs/binder/design"
    elif dt == "motif_scaffolding":
        params["contig"] = f"[10-40/A163-181/10-40]"
        params["input_pdb"] = pdb
        params["output_prefix"] = "outputs/scaffold/design"
    elif dt == "symmetric":
        params["contig"] = f"[{length}]"
        params["symmetry"] = "c2"
        params["output_prefix"] = "outputs/symmetric/design"
    elif dt == "peptide":
        params["contig"] = f"[B1-100/0 12-18]"
        params["input_pdb"] = pdb
        params["cyclic"] = True
        params["output_prefix"] = "outputs/peptide/design"
    elif dt == "ligand":
        params["contig"] = f"[150-150]"
        params["input_pdb"] = pdb
        params["output_prefix"] = "outputs/ligand/design"
        params["note"] = "Use RFdiffusionAA (rfdiffusion-all-atom skill) for ligand-aware design"

    return params


def _generate_proteinmpnn_params(goal: dict[str, Any]) -> dict[str, Any]:
    """Generate ProteinMPNN parameters."""
    dt = goal["design_type"]

    params: dict[str, Any] = {
        "num_seq_per_target": 8,
        "sampling_temp": "0.1",
        "output_folder": "outputs/sequences",
    }

    if dt == "binder":
        params["pdb_path_chains"] = "B"
        params["note"] = "Design only binder chain (B), keep target fixed"
    elif dt == "symmetric":
        params["note"] = "Consider using tied_positions for symmetry"
    elif dt == "ligand":
        params["note"] = "Use LigandMPNN instead for ligand-aware sequence design"

    return params


def _generate_validation_params(goal: dict[str, Any]) -> dict[str, Any]:
    """Generate validation stage parameters."""
    dt = goal["design_type"]
    has_ligand = goal.get("has_ligand", False)

    if has_ligand:
        return {
            "tool": "Boltz-1 or Chai-1",
            "reason": "Ligand-aware validation for complexes",
            "num_seeds": 1,
            "num_samples": 5,
        }
    elif dt == "binder":
        return {
            "tool": "AlphaFold3 or Boltz-1 or Chai-1",
            "num_seeds": 1,
            "num_samples": 5,
            "note": "ipTM > 0.8 for good binders",
        }
    elif dt == "peptide":
        return {
            "tool": "AlphaFold3",
            "num_seeds": 1,
            "num_samples": 5,
        }
    else:
        return {
            "tool": "OmegaFold or ESMFold (fast pre-screen), then AlphaFold3/Boltz/Chai-1 (top designs)",
            "num_seeds": 1,
            "num_samples": 5,
            "fast_screen": True,
        }


def _generate_filtering_params(goal: dict[str, Any]) -> dict[str, Any]:
    """Generate filtering criteria."""
    dt = goal["design_type"]

    criteria = {"allow_clashes": False}

    if dt == "binder":
        criteria["min_plddt"] = 80
        criteria["min_iptm"] = 0.8
        criteria["min_ptm"] = 0.7
    elif dt == "peptide":
        criteria["min_plddt"] = 70
        criteria["min_iptm"] = 0.6
    elif dt == "ligand":
        criteria["min_plddt"] = 75
        criteria["min_iptm"] = 0.7
    else:
        criteria["min_plddt"] = 80
        criteria["min_ptm"] = 0.7

    return criteria


def main() -> int:
    """Main entry point."""
    try:
        text = sys.stdin.read()
    except Exception:
        return 0

    if not text.strip():
        return 0

    # Only activate for protein design prompts
    if not re.search(
        r"\b(protein|design|binder|scaffold|rfdiffusion|proteinmpnn|alphafold|sequence|backbone)\b",
        text, re.IGNORECASE,
    ):
        return 0

    goal = _parse_design_goal(text)
    if goal["design_type"] == "unknown":
        return 0

    rf_params = _generate_rfdiffusion_params(goal)
    mpnn_params = _generate_proteinmpnn_params(goal)
    val_params = _generate_validation_params(goal)
    filter_params = _generate_filtering_params(goal)

    output = f"""[Auto Parameter Tuner] Design type: {goal['design_type']}

Stage 1 — Backbone Generation (RFdiffusion):
"""
    for k, v in rf_params.items():
        output += f"  {k}: {v}\n"

    output += """
Stage 2 — Sequence Design (ProteinMPNN):
"""
    for k, v in mpnn_params.items():
        output += f"  {k}: {v}\n"

    output += f"""
Stage 3 — Validation ({val_params.get('tool', 'AlphaFold3')}):
"""
    for k, v in val_params.items():
        output += f"  {k}: {v}\n"

    output += """
Stage 4 — Filtering Criteria:
"""
    for k, v in filter_params.items():
        output += f"  {k}: {v}\n"

    output += """
Tip: Adjust parameters based on specific requirements. See relevant skill for detailed options.
"""

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

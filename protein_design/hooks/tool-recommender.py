#!/usr/bin/env python3
"""UserPromptSubmit hook: recommend protein design tools based on user intent.

Analyzes the user's prompt for protein design keywords and returns structured
recommendations for which tools and parameters to use — reducing the need for
explicit MCP tool discovery calls.

This hook reduces MCP usage by embedding tool knowledge directly into the
agent's context at prompt-submit time.
"""

import json
import re
import sys
from typing import Any


def _extract_keywords(text: str) -> set[str]:
    """Extract protein design keywords from user text."""
    text_lower = text.lower()
    # Split on non-alphanumeric and filter empty
    words = set(re.findall(r"[a-z0-9_]+", text_lower))
    return words


def _detect_design_type(text: str) -> str:
    """Detect the protein design scenario from user text."""
    text_lower = text.lower()

    # Binder design patterns
    if any(kw in text_lower for kw in [
        "binder", "binding", "bind to", "target", "epitope",
        "interface", "interaction", "ppi", "protein-protein"
    ]):
        return "binder"

    # Motif scaffolding patterns
    if any(kw in text_lower for kw in [
        "scaffold", "scaffolding", "motif", "preserve", "keep",
        "around", "flank", "maintain"
    ]):
        return "motif_scaffolding"

    # Symmetric oligomer patterns
    if any(kw in text_lower for kw in [
        "symmetric", "symmetry", "oligomer", "dimer", "trimer",
        "tetramer", "hexamer", "c2", "c3", "c4", "d2"
    ]):
        return "symmetric_oligomer"

    # Partial diffusion / redesign patterns
    if any(kw in text_lower for kw in [
        "redesign", "redesign", "loop", "partial", "inpaint",
        "mutate", "variant", "remodel"
    ]):
        return "partial_diffusion"

    # Unconditional / de novo patterns
    if any(kw in text_lower for kw in [
        "generate", "design a protein", "de novo", "from scratch",
        "monomer", "new protein", "create"
    ]):
        return "unconditional"

    # Sequence design patterns
    if any(kw in text_lower for kw in [
        "sequence", "amino acid", "mpnn", "proteinmpnn",
        "assign sequence"
    ]):
        return "sequence_design"

    # Validation patterns
    if any(kw in text_lower for kw in [
        "validate", "validation", "alphafold", "af3",
        "predict structure", "confidence", "plddt"
    ]):
        return "validation"

    # Filtering patterns
    if any(kw in text_lower for kw in [
        "filter", "rank", "best", "top", "score",
        "quality", "select"
    ]):
        return "filtering"

    return "unknown"


def _build_recommendation(design_type: str) -> dict[str, Any]:
    """Build tool recommendation for the detected design type."""

    recommendations: dict[str, Any] = {
        "binder": {
            "scenario": "Binder Design",
            "description": "Design a protein that binds to a target structure.",
            "pipeline": ["pdbfixer", "rfdiffusion", "proteinmpnn", "alphafold3", "filtering"],
            "primary_tool": "run_rfdiffusion",
            "key_params": {
                "contig": "[B1-100/0 100-100]  # adjust target/binder lengths",
                "hotspot_res": ["A30", "A33", "A34"],
                "num_designs": 50,
                "diffuser_T": 50,
            },
            "tips": [
                "Provide target PDB as input_pdb",
                "Hotspot residues should be on the target surface",
                "Typical binder length: 60-150 residues",
                "Use ipTM > 0.8 as quality threshold for binders",
            ],
        },
        "motif_scaffolding": {
            "scenario": "Motif Scaffolding",
            "description": "Generate a scaffold around a conserved structural motif.",
            "pipeline": ["pdbfixer", "rfdiffusion", "proteinmpnn", "alphafold3", "filtering"],
            "primary_tool": "run_rfdiffusion",
            "key_params": {
                "contig": "[10-40/A163-181/10-40]  # adjust flanks and motif",
                "num_designs": 20,
                "diffuser_T": 50,
            },
            "tips": [
                "Motif residues must match input PDB numbering exactly",
                "Flanking regions provide structural context",
                "B-factor = 1 in output marks fixed motif regions",
            ],
        },
        "symmetric_oligomer": {
            "scenario": "Symmetric Oligomer Design",
            "description": "Design symmetric protein assemblies (dimers, trimers, etc.).",
            "pipeline": ["rfdiffusion", "proteinmpnn", "alphafold3", "filtering"],
            "primary_tool": "run_rfdiffusion",
            "key_params": {
                "contig": "[360]  # total length for symmetric unit",
                "symmetry": "c2  # or c3, c4, d2, tetrahedral",
                "num_designs": 20,
            },
            "tips": [
                "No input_pdb needed for unconditional symmetric design",
                "Total contig length = monomer length × symmetry multiplicity",
                "Use pTM > 0.7 as quality threshold",
            ],
        },
        "partial_diffusion": {
            "scenario": "Partial Diffusion / Redesign",
            "description": "Redesign a portion of an existing structure while keeping the rest fixed.",
            "pipeline": ["pdbfixer", "rfdiffusion", "proteinmpnn", "alphafold3", "filtering"],
            "primary_tool": "run_rfdiffusion",
            "key_params": {
                "contig": "[A1-50/0 10-20/A71-150]  # keep termini, redesign loop",
                "input_pdb": "structure.pdb",
                "num_designs": 10,
                "diffuser_T": 25,
            },
            "tips": [
                "Lower diffuser_T (25) for partial redesign (faster, more conservative)",
                "Fixed regions use 'A' prefix in contig (e.g., A1-50)",
                "Generated regions use range without prefix (e.g., 10-20)",
            ],
        },
        "unconditional": {
            "scenario": "De Novo Protein Design",
            "description": "Generate a protein from scratch without structural template.",
            "pipeline": ["rfdiffusion", "proteinmpnn", "alphafold3", "filtering"],
            "primary_tool": "run_rfdiffusion",
            "key_params": {
                "contig": "[150-150]  # target length range",
                "num_designs": 20,
                "diffuser_T": 50,
            },
            "tips": [
                "No input_pdb needed for unconditional design",
                "Contig format: [min-max] for length range",
                "Use pLDDT > 80 and pTM > 0.7 as quality thresholds",
            ],
        },
        "sequence_design": {
            "scenario": "Sequence Design",
            "description": "Assign amino acid sequences to existing backbones.",
            "pipeline": ["proteinmpnn"],
            "primary_tool": "run_proteinmpnn",
            "key_params": {
                "pdb_path": "backbone.pdb",
                "num_seq_per_target": 8,
                "sampling_temp": "0.1",
            },
            "tips": [
                "sampling_temp: 0.1=conservative, 0.3=diverse, 0.5=maximum diversity",
                "For binder-target complexes, use pdb_path_chains to fix target",
                "use_soluble_model=true for soluble expression targets",
            ],
        },
        "validation": {
            "scenario": "Structure Validation",
            "description": "Predict structure and compute confidence metrics.",
            "pipeline": ["convert_format", "alphafold3"],
            "primary_tool": "run_alphafold3",
            "key_params": {
                "json_path": "design_af3_input.json",
                "output_dir": "outputs/af3",
                "num_seeds": 1,
                "num_samples": 5,
            },
            "tips": [
                "Use convert_format to convert FASTA → AlphaFold3 JSON",
                "For quick screening: run_data_pipeline=false (skips MSA)",
                "For accurate predictions: keep run_data_pipeline=true (requires ~2.6TB DBs)",
                "Key metrics: pLDDT (per-atom), pTM (topology), ipTM (interface)",
            ],
        },
        "filtering": {
            "scenario": "Filtering & Ranking",
            "description": "Filter designs by quality metrics and rank the best.",
            "pipeline": ["filtering"],
            "primary_tool": "run_filtering",
            "key_params": {
                "criteria": {
                    "min_plddt": 70,
                    "min_iptm": 0.6,
                    "min_ptm": 0.5,
                    "allow_clashes": False,
                },
            },
            "tips": [
                "For binders: prioritize ipTM > 0.8",
                "For monomers: prioritize pLDDT > 80 and pTM > 0.7",
                "Always reject designs with has_clash=true",
            ],
        },
        "unknown": {
            "scenario": "Unknown",
            "description": "Could not determine design scenario from prompt.",
            "pipeline": ["check_all_tools"],
            "primary_tool": "get_tool_info",
            "key_params": {},
            "tips": [
                "Describe your design goal in more detail",
                "Available scenarios: binder, scaffold, symmetric, redesign, monomer, sequence, validate",
            ],
        },
    }

    return recommendations.get(design_type, recommendations["unknown"])


def _build_pipeline_guide(design_type: str) -> str:
    """Build a quick-start pipeline guide for the design type."""
    if design_type == "binder":
        return """
## Quick Pipeline: Binder Design

1. **Preprocess target**: run_pdbfixer(input_pdb="target.pdb")
2. **Generate binders**: run_rfdiffusion(input_pdb="target_fixed.pdb", contig="[B1-100/0 100-100]", hotspot_res=[...])
3. **Design sequences**: run_proteinmpnn(pdb_path="design_*.pdb", pdb_path_chains="B")
4. **Convert format**: convert_format(fasta → alphafold3_json)
5. **Validate**: run_alphafold3(json_path=..., output_dir=...)
6. **Filter**: run_filtering(criteria={min_iptm: 0.8, min_plddt: 80})
"""
    elif design_type == "unconditional":
        return """
## Quick Pipeline: De Novo Monomer

1. **Generate backbone**: run_rfdiffusion(contig="[150-150]", num_designs=20)
2. **Design sequences**: run_proteinmpnn(pdb_path="design_*.pdb")
3. **Convert format**: convert_format(fasta → alphafold3_json)
4. **Validate**: run_alphafold3(json_path=..., output_dir=...)
5. **Filter**: run_filtering(criteria={min_plddt: 80, min_ptm: 0.7})
"""
    elif design_type == "motif_scaffolding":
        return """
## Quick Pipeline: Motif Scaffolding

1. **Preprocess**: run_pdbfixer(input_pdb="motif.pdb")
2. **Generate scaffolds**: run_rfdiffusion(input_pdb="motif_fixed.pdb", contig="[10-40/A163-181/10-40]")
3. **Design sequences**: run_proteinmpnn(pdb_path="design_*.pdb")
4. **Validate**: run_alphafold3(json_path=..., output_dir=...)
5. **Filter**: run_filtering(criteria={min_plddt: 75})
"""
    return ""


def main() -> int:
    """Main entry point. Reads prompt from stdin, prints recommendations to stdout."""
    try:
        user_prompt = sys.stdin.read()
    except Exception:
        user_prompt = ""

    if not user_prompt.strip():
        return 0

    # Only activate for protein design keywords
    protein_keywords = re.compile(
        r"\b(protein|pdb|binder|alphafold|rfdiffusion|proteinmpnn|design|"
        r"structure|sequence|residue|loop|scaffold|motif|oligomer|diffusion|"
        r"backbone|monomer|complex|interface|epitope|target|fold|prediction|"
        r"plddt|ptm|iptm|msa|validation|ranking|filter|chain)\b",
        re.IGNORECASE,
    )

    if not protein_keywords.search(user_prompt):
        return 0

    design_type = _detect_design_type(user_prompt)
    recommendation = _build_recommendation(design_type)
    pipeline_guide = _build_pipeline_guide(design_type)

    output = f"""[蛋白质设计工具推荐] 检测到设计场景: {recommendation['scenario']}

{recommendation['description']}

推荐工具链: {' → '.join(recommendation['pipeline'])}
主要工具: {recommendation['primary_tool']}

关键参数:
"""
    for param, value in recommendation.get("key_params", {}).items():
        output += f"  {param}: {value}\n"

    output += "\n提示:\n"
    for tip in recommendation.get("tips", []):
        output += f"  • {tip}\n"

    if pipeline_guide:
        output += pipeline_guide

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

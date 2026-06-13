#!/usr/bin/env python3
"""UserPromptSubmit hook: auto-generate optimal parameters for common design scenarios.

Analyzes user prompts for design goals and returns pre-configured parameter
dicts — reducing the need for manual parameter research.
"""
import traceback
import json
import re
from typing import Any
import sys


def _detect_design_params(text: str) -> dict[str, Any]:
    """Detect design goal and return optimal parameters."""
    text_lower = text.lower()
    words = set(re.findall(r"[a-z0-9_]+", text_lower))

    # Extract length if specified
    length_match = re.search(r"(\d+)\s*(?:aa|residue|amino acid)", text_lower)
    length = int(length_match.group(1)) if length_match else 150

    # Extract num_designs if specified
    num_match = re.search(r"(\d+)\s*(?:design|structure|backbone)", text_lower)
    num_designs = int(num_match.group(1)) if num_match else 10

    # Binder design
    if any(kw in text_lower for kw in ["binder", "binding", "bind to", "target"]):
        return {
            "design_type": "binder",
            "description": f"Design a protein binder",
            "stages": {
                "stage0": {"tool": "run_pdbfixer", "params": {"input_pdb": "target.pdb"}},
                "stage1": {
                    "tool": "run_rfdiffusion",
                    "params": {
                        "input_pdb": "target_fixed.pdb",
                        "contig": "[B1-100/0 100-100]",
                        "output_prefix": "outputs/binder/design",
                        "num_designs": min(num_designs, 100),
                        "diffuser_T": 50,
                    }
                },
                "stage2": {
                    "tool": "run_proteinmpnn",
                    "params": {
                        "pdb_path_chains": "B",
                        "num_seq_per_target": 8,
                        "sampling_temp": "0.1",
                    }
                },
                "stage3": {
                    "tool": "run_alphafold3",
                    "params": {
                        "num_seeds": 1,
                        "num_samples": 5,
                    }
                },
                "stage4": {
                    "tool": "run_filtering",
                    "params": {
                        "criteria": {"min_iptm": 0.8, "min_plddt": 80}
                    }
                },
            },
            "quality_thresholds": {"ipTM": ">0.8", "pLDDT": ">80"},
            "tips": [
                "Provide target PDB as input_pdb for stage0",
                "Hotspot residues improve binding specificity",
                "ipTM is the most important metric for binders",
                "Consider 50-100 designs for binder discovery",
            ],
        }

    # Motif scaffolding
    if any(kw in text_lower for kw in ["scaffold", "motif", "preserve", "flank"]):
        return {
            "design_type": "motif_scaffolding",
            "description": f"Scaffold around a conserved motif",
            "stages": {
                "stage0": {"tool": "run_pdbfixer", "params": {"input_pdb": "motif.pdb"}},
                "stage1": {
                    "tool": "run_rfdiffusion",
                    "params": {
                        "input_pdb": "motif_fixed.pdb",
                        "contig": f"[10-40/A50-60/10-40]",
                        "output_prefix": "outputs/motif/design",
                        "num_designs": min(num_designs, 50),
                        "diffuser_T": 50,
                    }
                },
                "stage2": {
                    "tool": "run_proteinmpnn",
                    "params": {
                        "num_seq_per_target": 8,
                        "sampling_temp": "0.1",
                    }
                },
                "stage3": {
                    "tool": "run_alphafold3",
                    "params": {
                        "num_seeds": 1,
                        "num_samples": 5,
                    }
                },
                "stage4": {
                    "tool": "run_filtering",
                    "params": {
                        "criteria": {"min_plddt": 75, "min_ptm": 0.6}
                    }
                },
            },
            "quality_thresholds": {"pTM": ">0.6", "pLDDT": ">75"},
            "tips": [
                "Adjust contig to match your motif position and desired scaffold size",
                "Motif residues must match input PDB numbering exactly",
                "For small motifs (<10aa), use ActiveSite_ckpt.pt",
            ],
        }

    # Symmetric oligomer
    if any(kw in text_lower for kw in ["symmetric", "oligomer", "dimer", "trimer", "tetramer"]):
        symmetry = "c2"
        if "trimer" in text_lower or "c3" in text_lower:
            symmetry = "c3"
        elif "tetramer" in text_lower or "c4" in text_lower:
            symmetry = "c4"

        return {
            "design_type": "symmetric_oligomer",
            "description": f"Design a {symmetry} symmetric oligomer",
            "stages": {
                "stage1": {
                    "tool": "run_rfdiffusion",
                    "params": {
                        "contig": f"[{length}]",
                        "symmetry": symmetry,
                        "output_prefix": f"outputs/{symmetry}/design",
                        "num_designs": min(num_designs, 50),
                        "diffuser_T": 50,
                    }
                },
                "stage2": {
                    "tool": "run_proteinmpnn",
                    "params": {
                        "num_seq_per_target": 8,
                        "sampling_temp": "0.1",
                    }
                },
                "stage3": {
                    "tool": "run_alphafold3",
                    "params": {
                        "num_seeds": 1,
                        "num_samples": 5,
                    }
                },
                "stage4": {
                    "tool": "run_filtering",
                    "params": {
                        "criteria": {"min_ptm": 0.7, "min_plddt": 75}
                    }
                },
            },
            "quality_thresholds": {"pTM": ">0.7", "pLDDT": ">75"},
            "tips": [
                f"Contig length = monomer length (not total assembly)",
                f"For {symmetry}, total assembly = {length} × multiplicity",
                "Use tied_positions_jsonl for symmetric positions in ProteinMPNN",
            ],
        }

    # Cyclic peptide
    if any(kw in text_lower for kw in ["cyclic", "peptide", "macrocyclic"]):
        return {
            "design_type": "cyclic_peptide",
            "description": f"Design a cyclic peptide ({length}aa)",
            "stages": {
                "stage1": {
                    "tool": "run_rfdiffusion",
                    "params": {
                        "contig": f"[{min(length, 20)}-{min(length, 30)}]",
                        "cyclic": True,
                        "cyc_chains": "a",
                        "output_prefix": "outputs/cyclic/design",
                        "num_designs": min(num_designs, 200),
                        "diffuser_T": 25,
                    }
                },
                "stage2": {
                    "tool": "run_proteinmpnn",
                    "params": {
                        "num_seq_per_target": 8,
                        "sampling_temp": "0.1",
                    }
                },
                "stage3": {
                    "tool": "run_alphafold3",
                    "params": {
                        "num_seeds": 1,
                        "num_samples": 5,
                    }
                },
                "stage4": {
                    "tool": "run_filtering",
                    "params": {
                        "criteria": {"min_plddt": 70}
                    }
                },
            },
            "quality_thresholds": {"pLDDT": ">70"},
            "tips": [
                "Cyclic peptides often have lower pLDDT — adjust thresholds",
                "Use more designs (200+) due to short length",
                "Consider DiffPepBuilder for 8-30aa peptides",
            ],
        }

    # Default: unconditional monomer
    return {
        "design_type": "unconditional_monomer",
        "description": f"Design a {length}-residue de novo protein",
        "stages": {
            "stage1": {
                "tool": "run_rfdiffusion",
                "params": {
                    "contig": f"[{length}-{length}]",
                    "output_prefix": "outputs/monomer/design",
                    "num_designs": min(num_designs, 50),
                    "diffuser_T": 50,
                }
            },
            "stage2": {
                "tool": "run_proteinmpnn",
                "params": {
                    "num_seq_per_target": 8,
                    "sampling_temp": "0.1",
                }
            },
            "stage3": {
                "tool": "run_alphafold3",
                "params": {
                    "num_seeds": 1,
                    "num_samples": 5,
                }
            },
            "stage4": {
                "tool": "run_filtering",
                "params": {
                    "criteria": {"min_plddt": 80, "min_ptm": 0.7}
                }
            },
        },
        "quality_thresholds": {"pLDDT": ">80", "pTM": ">0.7"},
        "tips": [
            "No input PDB needed for unconditional design",
            "Contig format: [min-max] for length range",
            "For soluble expression: use ProteinMPNN's use_soluble_model",
        ],
    }


def main() -> int:
    """Main entry point."""
    try:
        text = sys.stdin.read()
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    if not user_prompt.strip():
        return 0

    # Only activate for protein design keywords
    protein_keywords = re.compile(
        r"\b(design|generate|create|protein|backbone|sequence|binder|"
        r"scaffold|motif|monomer|oligomer|symmetric|cyclic|peptide)\b",
        re.IGNORECASE,
    )

    if not protein_keywords.search(user_prompt):
        return 0

    params = _detect_design_params(user_prompt)

    output = f"""[参数生成器] 检测到设计类型: {params['design_type']}
{params['description']}

推荐流程:
"""
    for stage_name, stage in params.get("stages", {}).items():
        tool = stage.get("tool", "")
        tool_params = stage.get("params", {})
        output += f"\n{stage_name}: {tool}\n"
        for k, v in tool_params.items():
            output += f"  {k}: {v}\n"

    output += f"\n质量阈值:\n"
    for metric, threshold in params.get("quality_thresholds", {}).items():
        output += f"  {metric}: {threshold}\n"

    if params.get("tips"):
        output += f"\n提示:\n"
        for tip in params["tips"]:
            output += f"  • {tip}\n"

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""UserPromptSubmit hook: recommend protein design tools based on user intent.

Analyzes the user's prompt for protein design keywords and returns structured
recommendations for which scripts and parameters to use.

This hook embeds pipeline knowledge directly into the agent's context at
prompt-submit time.
"""
import traceback
import json
import re
from typing import Any
import sys


def _extract_keywords(text: str) -> set[str]:
    """Extract protein design keywords from user text."""
    text_lower = text.lower()
    words = set(re.findall(r"[a-z0-9_]+", text_lower))
    return words


def _detect_design_type(text: str) -> str:
    """Detect the protein design scenario from user text."""
    text_lower = text.lower()

    if any(kw in text_lower for kw in [
        "binder", "binding", "bind to", "target", "epitope",
        "interface", "interaction", "ppi", "protein-protein"
    ]):
        return "binder"

    if any(kw in text_lower for kw in [
        "scaffold", "scaffolding", "motif", "preserve", "keep",
        "around", "flank", "maintain"
    ]):
        return "motif_scaffolding"

    if any(kw in text_lower for kw in [
        "symmetric", "symmetry", "oligomer", "dimer", "trimer",
        "tetramer", "hexamer", "c2", "c3", "c4", "d2"
    ]):
        return "symmetric_oligomer"

    if any(kw in text_lower for kw in [
        "redesign", "loop", "partial", "inpaint",
        "mutate", "variant", "remodel"
    ]):
        return "partial_diffusion"

    if any(kw in text_lower for kw in [
        "generate", "design a protein", "de novo", "from scratch",
        "monomer", "new protein", "create"
    ]):
        return "unconditional"

    if any(kw in text_lower for kw in [
        "sequence", "amino acid", "mpnn", "proteinmpnn",
        "assign sequence"
    ]):
        return "sequence_design"

    if any(kw in text_lower for kw in [
        "validate", "validation", "alphafold", "af3",
        "predict structure", "confidence", "plddt"
    ]):
        return "validation"

    if any(kw in text_lower for kw in [
        "filter", "rank", "best", "top", "score",
        "quality", "select"
    ]):
        return "filtering"

    return "unknown"


def _build_recommendation(design_type: str) -> dict[str, Any]:
    """Build script recommendation for the detected design type."""

    recommendations: dict[str, Any] = {
        "binder": {
            "scenario": "Binder Design",
            "description": "Design a protein that binds to a target structure.",
            "pipeline": ["run_pdbfixer.py", "run_rfdiffusion.py", "run_proteinmpnn.py", "run_alphafold3.py", "run_filtering.py"],
            "primary_script": "scripts/run_rfdiffusion.py",
            "key_params": {
                "contig": '"[B1-100/0 100-100]"  # adjust target/binder lengths',
                "hotspot-res": "A30 A33 A34",
                "num-designs": "50",
                "diffuser-T": "50",
            },
            "example": """python scripts/run_pdbfixer.py --input target.pdb --output target_fixed.pdb
python scripts/run_rfdiffusion.py \\
  --input-pdb target_fixed.pdb \\
  --contig "[B1-100/0 100-100]" \\
  --hotspot-res A30 A33 A34 \\
  --output-prefix outputs/binder \\
  --num-designs 50 \\
  --diffuser-T 50
python scripts/run_proteinmpnn.py --pdb-path "outputs/binder_*.pdb" --out-folder outputs/seqs/
python scripts/convert_format.py --from fasta --to alphafold3_json --input outputs/seqs/ --output af3_input.json
python scripts/run_alphafold3.py --json af3_input.json --output-dir outputs/af3/ --num-samples 5
python scripts/run_filtering.py --results-dir outputs/af3/ --min-iptm 0.8 --min-plddt 80""",
            "tips": [
                "Provide target PDB as --input",
                "Hotspot residues should be on the target surface",
                "Typical binder length: 60-150 residues",
                "Use ipTM > 0.8 as quality threshold for binders",
            ],
        },
        "motif_scaffolding": {
            "scenario": "Motif Scaffolding",
            "description": "Generate a scaffold around a conserved structural motif.",
            "pipeline": ["run_pdbfixer.py", "run_rfdiffusion.py", "run_proteinmpnn.py", "run_alphafold3.py", "run_filtering.py"],
            "primary_script": "scripts/run_rfdiffusion.py",
            "key_params": {
                "contig": '"[10-40/A163-181/10-40]"  # adjust flanks and motif',
                "num-designs": "20",
                "diffuser-T": "50",
            },
            "example": """python scripts/run_pdbfixer.py --input motif.pdb --output motif_fixed.pdb --keep-chains A
python scripts/run_rfdiffusion.py \\
  --input-pdb motif_fixed.pdb \\
  --contig "[10-40/A163-181/10-40]" \\
  --output-prefix outputs/scaffold \\
  --num-designs 20 \\
  --diffuser-T 50
python scripts/run_proteinmpnn.py --pdb-path "outputs/scaffold_*.pdb" --out-folder outputs/seqs/
python scripts/run_alphafold3.py --json inputs/af3.json --output-dir outputs/af3/
python scripts/run_filtering.py --results-dir outputs/af3/ --min-plddt 75""",
            "tips": [
                "Motif residues must match input PDB numbering exactly",
                "Flanking regions provide structural context",
                "B-factor = 1 in output marks fixed motif regions",
            ],
        },
        "symmetric_oligomer": {
            "scenario": "Symmetric Oligomer Design",
            "description": "Design symmetric protein assemblies (dimers, trimers, etc.).",
            "pipeline": ["run_rfdiffusion.py", "run_proteinmpnn.py", "run_alphafold3.py", "run_filtering.py"],
            "primary_script": "scripts/run_rfdiffusion.py",
            "key_params": {
                "contig": '"[360]"  # total length for symmetric unit',
                "symmetry": "c2  # or c3, c4, d2, tetrahedral",
                "num-designs": "20",
            },
            "example": """python scripts/run_rfdiffusion.py \\
  --contig "[360]" \\
  --symmetry c2 \\
  --output-prefix outputs/sym \\
  --num-designs 20 \\
  --diffuser-T 50
python scripts/run_proteinmpnn.py --pdb-path "outputs/sym_*.pdb" --out-folder outputs/seqs/
python scripts/run_alphafold3.py --json inputs/af3.json --output-dir outputs/af3/
python scripts/run_filtering.py --results-dir outputs/af3/ --min-ptm 0.7""",
            "tips": [
                "No --input-pdb needed for unconditional symmetric design",
                "Total contig length = monomer length × symmetry multiplicity",
                "Use pTM > 0.7 as quality threshold",
            ],
        },
        "partial_diffusion": {
            "scenario": "Partial Diffusion / Redesign",
            "description": "Redesign a portion of an existing structure while keeping the rest fixed.",
            "pipeline": ["run_pdbfixer.py", "run_rfdiffusion.py", "run_proteinmpnn.py", "run_alphafold3.py", "run_filtering.py"],
            "primary_script": "scripts/run_rfdiffusion.py",
            "key_params": {
                "contig": '"[A1-50/0 10-20/A71-150]"  # keep termini, redesign loop',
                "partial-T": "10",
                "num-designs": "10",
                "diffuser-T": "25",
            },
            "example": """python scripts/run_pdbfixer.py --input structure.pdb --output structure_fixed.pdb
python scripts/run_rfdiffusion.py \\
  --input-pdb structure_fixed.pdb \\
  --contig "[A1-50/0 10-20/A71-150]" \\
  --partial-T 10 \\
  --output-prefix outputs/redesign \\
  --num-designs 10 \\
  --diffuser-T 25
python scripts/run_proteinmpnn.py --pdb-path "outputs/redesign_*.pdb" --out-folder outputs/seqs/
python scripts/run_alphafold3.py --json inputs/af3.json --output-dir outputs/af3/
python scripts/run_filtering.py --results-dir outputs/af3/ --min-plddt 75""",
            "tips": [
                "Lower --diffuser-T (25) for partial redesign (faster, more conservative)",
                "Fixed regions use 'A' prefix in contig (e.g., A1-50)",
                "Generated regions use range without prefix (e.g., 10-20)",
            ],
        },
        "unconditional": {
            "scenario": "De Novo Protein Design",
            "description": "Generate a protein from scratch without structural template.",
            "pipeline": ["run_rfdiffusion.py", "run_proteinmpnn.py", "run_alphafold3.py", "run_filtering.py"],
            "primary_script": "scripts/run_rfdiffusion.py",
            "key_params": {
                "contig": '"[150-150]"  # target length range',
                "num-designs": "20",
                "diffuser-T": "50",
            },
            "example": """python scripts/run_rfdiffusion.py \\
  --contig "[150-150]" \\
  --output-prefix outputs/monomer \\
  --num-designs 20 \\
  --diffuser-T 50
python scripts/run_proteinmpnn.py --pdb-path "outputs/monomer_*.pdb" --out-folder outputs/seqs/
python scripts/run_alphafold3.py --json inputs/af3.json --output-dir outputs/af3/
python scripts/run_filtering.py --results-dir outputs/af3/ --min-plddt 80 --min-ptm 0.7""",
            "tips": [
                "No --input-pdb needed for unconditional design",
                "Contig format: [min-max] for length range",
                "Use pLDDT > 80 and pTM > 0.7 as quality thresholds",
            ],
        },
        "sequence_design": {
            "scenario": "Sequence Design",
            "description": "Assign amino acid sequences to existing backbones.",
            "pipeline": ["run_proteinmpnn.py"],
            "primary_script": "scripts/run_proteinmpnn.py",
            "key_params": {
                "pdb-path": '"backbone.pdb"',
                "num-seq-per-target": "8",
                "sampling-temp": "0.1",
            },
            "example": """python scripts/run_proteinmpnn.py \\
  --pdb-path "backbone.pdb" \\
  --out-folder outputs/seqs/ \\
  --num-seq-per-target 8 \\
  --sampling-temp 0.1""",
            "tips": [
                "sampling-temp: 0.1=conservative, 0.3=diverse, 0.5=maximum diversity",
                "For binder-target complexes, use --pdb-path-chains to fix target",
                "Use --soluble for soluble expression targets",
            ],
        },
        "validation": {
            "scenario": "Structure Validation",
            "description": "Predict structure and compute confidence metrics.",
            "pipeline": ["convert_format.py", "run_alphafold3.py"],
            "primary_script": "scripts/run_alphafold3.py",
            "key_params": {
                "json": "design_af3_input.json",
                "output-dir": "outputs/af3",
                "num-seeds": "1",
                "num-samples": "5",
            },
            "example": """python scripts/convert_format.py --from fasta --to alphafold3_json --input seqs.fa --output af3_input.json
python scripts/run_alphafold3.py \\
  --json af3_input.json \\
  --output-dir outputs/af3/ \\
  --num-seeds 1 \\
  --num-samples 5""",
            "tips": [
                "Use convert_format.py to convert FASTA → AlphaFold3 JSON",
                "For quick screening: --run-data-pipeline false (skips MSA)",
                "For accurate predictions: --run-data-pipeline true (requires ~2.6TB DBs)",
                "Key metrics: pLDDT (per-atom), pTM (topology), ipTM (interface)",
            ],
        },
        "filtering": {
            "scenario": "Filtering & Ranking",
            "description": "Filter designs by quality metrics and rank the best.",
            "pipeline": ["run_filtering.py"],
            "primary_script": "scripts/run_filtering.py",
            "key_params": {
                "results-dir": "outputs/af3/",
                "min-plddt": "70",
                "min-iptm": "0.6",
                "min-ptm": "0.5",
            },
            "example": """python scripts/run_filtering.py \\
  --results-dir outputs/af3/ \\
  --min-plddt 70 \\
  --min-iptm 0.6 \\
  --min-ptm 0.5 \\
  --top-n 20""",
            "tips": [
                "For binders: prioritize ipTM > 0.8",
                "For monomers: prioritize pLDDT > 80 and pTM > 0.7",
                "Reject designs with atomic clashes",
            ],
        },
        "unknown": {
            "scenario": "Unknown",
            "description": "Could not determine design scenario from prompt.",
            "pipeline": ["pipeline-selection skill", "session-health-check hook"],
            "primary_script": "python protein_design/hooks/session-health-check.py",
            "key_params": {},
            "example": """python protein_design/hooks/session-health-check.py
# Then read skills/pipeline-selection/SKILL.md for guidance""",
            "tips": [
                "Describe your design goal in more detail",
                "Available scenarios: binder, scaffold, symmetric, redesign, monomer, sequence, validate",
            ],
        },
    }

    return recommendations.get(design_type, recommendations["unknown"])


def main() -> int:
    """Main entry point. Reads prompt from stdin, prints recommendations to stdout."""
    try:
        text = sys.stdin.read()
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    user_prompt = text

    if not user_prompt.strip():
        return 0

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
    rec = _build_recommendation(design_type)

    output = f"""[Tool Recommendation / 工具推荐] Scenario / 场景: {rec['scenario']}

{rec['description']}

Pipeline / 推荐脚本链: {' → '.join(rec['pipeline'])}
Primary script / 主要脚本: {rec['primary_script']}

Key parameters / 关键参数:
"""
    for param, value in rec.get("key_params", {}).items():
        output += f"  --{param}: {value}\n"

    output += "\nExample / 执行示例:\n```bash\n"
    output += rec.get("example", "")
    output += "\n```\n\nTips / 提示:\n"
    for tip in rec.get("tips", []):
        output += f"  • {tip}\n"

    output += """
Progress tracking / 进度追踪:
  python scripts/summarize_outputs.py --output-dir outputs/
"""
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

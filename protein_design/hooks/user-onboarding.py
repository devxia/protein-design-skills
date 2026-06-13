#!/usr/bin/env python3
"""UserPromptSubmit hook: friendly onboarding for protein design sessions.

When a user starts a conversation about protein design, this hook prints a
warm welcome, summarizes available workflows, and reminds them of progress
monitoring tools.
"""
import traceback
import json
import subprocess
import sys


TRIGGER_KEYWORDS = [
    "protein design",
    "design a protein",
    "protein binder",
    "binder design",
    "backbone generation",
    "sequence design",
    "rf diffusion",
    "rfdiffusion",
    "rfdiffusion3",
    "proteinmpnn",
    "alphafold3",
    "pdbfixer",
    "bindcraft",
    "chroma",
    "boltz",
    "chai",
    "omegafold",
    "esmfold",
    "peptide design",
    "enzyme design",
    "antibody design",
    "plddt",
    "iptm",
    "motif scaffold",
]

# Keywords that should NOT trigger onboarding (already in progress)
SUPPRESS_KEYWORDS = [
    "summarize",
    "summary",
    "progress",
    "report",
    "status",
    "how many",
    "count of",
]


def _should_welcome(prompt: str) -> bool:
    """Decide whether this prompt warrants a welcome message."""
    text_lower = prompt.lower()

    # Only trigger on genuine protein design starts
    has_trigger = any(kw in text_lower for kw in TRIGGER_KEYWORDS)
    if not has_trigger:
        return False

    # Avoid interrupting ongoing progress/status queries
    has_suppress = any(kw in text_lower for kw in SUPPRESS_KEYWORDS)
    if has_suppress:
        return False

    return True


def _check_tools() -> dict[str, bool]:
    """Quick check for installed tools."""
    tools = {}
    for name, import_test in [
        ("RFdiffusion", ["python", "-c", "import rfdiffusion"]),
        ("ProteinMPNN", ["python", "-c", "import protein_mpnn_run"]),
        ("AlphaFold3", ["python", "-c", "import run_alphafold"]),
        ("PDBFixer", ["python", "-c", "from pdbfixer import PDBFixer"]),
        ("ESMFold", ["python", "-c", "import esm"]),
        ("OmegaFold", ["python", "-c", "import omegafold"]),
        ("Boltz", ["python", "-c", "import boltz"]),
        ("Chai-1", ["python", "-c", "import chai1"]),
        ("Protenix", ["python", "-c", "import protenix"]),
        ("OpenFold", ["python", "-c", "import openfold"]),
    ]:
        try:
            subprocess.run(import_test, capture_output=True, timeout=5, check=True)
            tools[name] = True
        except Exception:
            tools[name] = False
    return tools


def _build_welcome() -> str:
    """Build a friendly onboarding message with tool status."""
    tools = _check_tools()
    installed = [k for k, v in tools.items() if v]
    missing = [k for k, v in tools.items() if not v]

    # Build tool status section
    tool_status = ""
    if installed:
        tool_status += f"✅ **Installed:** {', '.join(installed)}\n"
    if missing:
        tool_status += f"❌ **Not installed:** {', '.join(missing)}\n"
        tool_status += "\n**Quick alternatives for missing tools:**\n"
        alt_map = {
            "RFdiffusion": "Chroma (`pip install chroma-ai`) — MIT, fast",
            "ProteinMPNN": "ESM-IF1 (`pip install fair-esm`) — MIT, no GPU required",
            "AlphaFold3": "ESMFold (`pip install fair-esm`) or OmegaFold (`pip install omegafold`) — no databases needed",
            "PDBFixer": "`conda install -c conda-forge pdbfixer openmm` — 5 min install",
            "ESMFold": "`pip install fair-esm` — MIT, CPU-compatible",
            "OmegaFold": "`pip install omegafold` — MIT, fast",
            "Boltz": "`pip install boltz` — MIT, good for complexes",
            "Chai-1": "See chai-1 docs — Apache 2.0, single-seq mode",
            "Protenix": "See protenix docs — MIT, training+inference scaling",
            "OpenFold": "`pip install openfold3` — Apache 2.0, AF3 parity",
        }
        for tool in missing:
            if tool in alt_map:
                tool_status += f"  - **{tool}**: {alt_map[tool]}\n"

    return f"""🧬 Welcome to Protein Design Skills!

{tool_status}
## 🚀 Quick Start

Not sure where to begin? Ask me:
- "Which pipeline should I use for X?"
- "Design a binder to PD-L1"
- "Run the full pipeline on my target"

## 📋 Available Workflows (76+ Skills)

| Goal | Recommended Skill |
|------|-------------------|
| Pick the right pipeline | `pipeline-selection` |
| End-to-end standard design | `full-pipeline` |
| Automated binder design | `bindcraft-workflow` |
| Universal MIT binder design (protein/peptide/small molecule/antibody/nanobody) | `boltzgen-binder-design` |
| Conformational ensembles / cryptic pockets without MD | `bioemu-ensemble` |
| Blind small-molecule docking / virtual screening | `diffdock-ligand` |
| Autoregressive PLM generation + zero-shot fitness | `progen2-sequence` |
| Structure + binding affinity validation | `boltz2-validation` |
| Invert Boltz-1 / AlphaFold3 for all-atom binders | `boltzdesign1-binder` |
| HPC/cloud binder pipeline | `nf-binder-design` |
| Joint sequence + structure generation | `protein-generator` |
| Design with a ligand/cofactor | `rfdiffusion-all-atom` or `rfdiffusion3-workflow` → `ligandmpnn-design` |
| Validate with ligands/DNA/RNA/metals | `rosettafold-all-atom` |
| All-atom DNA/RNA/enzyme design | `rfdiffusion3-workflow` |
| Pocket redesign around ligand | `pocketgen-ligand` |
| Programmable generation from function | `esm3-generative` |
| Text-guided protein design | `proteindt-workflow` |
| Fast screening (no big DB) | `fast-screening` → `omegafold-validation` |
| Unconditional topology-aware backbones | `topodiff-workflow` |
| MIT-licensed SE(3) diffusion backbones | `framediff-backbone` |
| MIT-licensed all-atom seq+struct generation | `protpardelle-allatom` |
| Fast MIT inverse folding (sequence design) | `pifold-sequence-design` |
| Multi-motif scaffolding with floating anchors | `fadiff-multimotif` |
| Fitness-guided sequence optimization | `pro-ldm-workflow` |
| 3D ellipsoid layout-controlled design | `protcomposer-workflow` |
| Latent diffusion on pLM representations | `dima-workflow` |
| Peptide / macrocyclic peptide | `diffpepbuilder-design` / `rfpeptides-macrocycle` |
| Antibody / nanobody | `igdiff-antibody` |
| Progress monitoring | `periodic-summary` + `scripts/summarize_outputs.py` |
| Decide what to run next | `next-steps` skill |

## 📊 Track Your Progress

At any time, run:

```bash
# One-shot summary of a single output directory
python scripts/summarize_outputs.py --output-dir outputs/

# Live watch (refreshes every 30s)
python scripts/summarize_outputs.py --output-dir outputs/ --watch

# Project-wide dashboard across all stages
python scripts/project_dashboard.py --output-dir outputs/ \
  --expected-backbones 50 \
  --expected-sequences 400 \
  --expected-validations 50

# Live project dashboard
python scripts/project_dashboard.py --output-dir outputs/ --watch
```

The summary shows backbone count, sequence count, validation count, quality distribution, mean/best pLDDT and ipTM, and top designs by pLDDT.

## 🪝 Hooks

Install hooks for automatic context injection and stage reminders:

```bash
python protein_design/hooks/install-hooks.py
```

---
*How can I help with your design today?* 🎨
"""


def main() -> int:
    """Main entry point."""
    try:
        input_data = sys.stdin.read()
        data = json.loads(input_data) if input_data.strip() else {}
    except json.JSONDecodeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    prompt = str(data.get("user_prompt", ""))
    if not prompt or not _should_welcome(prompt):
        return 0

    print(_build_welcome())
    return 0


if __name__ == "__main__":
    sys.exit(main())

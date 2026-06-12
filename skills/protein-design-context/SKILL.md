---
name: protein-design-context
description: Session-start context injection — THE MAIN ENTRANCE for all protein design workflows. Auto-triggered when protein design is mentioned.
---

# Protein Design Plugin — Main Entrance

Welcome to the Protein Design plugin. **This is your starting point.**

> **First-time setup / 首次使用：** If you installed via Kimi Code marketplace, run `python protein_design/hooks/install-hooks.py kimi` once to enable automation hooks. Claude Code and Codex CLI marketplace installs already include hooks.

## What are you trying to do? Pick a scenario:

| I want to... | Go Here | Skill |
|--------------|---------|-------|
| **Design a protein from scratch** (monomer, binder, scaffold) | ➡️ [Standard Pipeline](#standard-pipeline) | `full-pipeline` |
| **Design an automated protein binder** (highest experimental success) | ➡️ [BindCraft Pipeline](#bindcraft-pipeline) | `bindcraft-workflow` |
| **Run binder design on HPC / cloud / cluster** | ➡️ [nf-binder-design Pipeline](#nf-binder-design-pipeline) | `nf-binder-design` |
| **Design something that binds a small molecule** (cofactor, metal, ligand) | ➡️ [Ligand-Aware Pipeline](#ligand-aware-pipeline) | `rfdiffusion-all-atom` |
| **Validate designs with ligands / DNA / RNA / metals** (AF3 doesn't support it) | ➡️ [RFAA Validation Pipeline](#rfaa-validation-pipeline) | `rosettafold-all-atom` |
| **Redesign an existing pocket around a ligand** | ➡️ [PocketGen Pipeline](#pocketgen-pipeline) | `pocketgen-ligand` |
| **Generate a protein from function / GO terms** | ➡️ [ESM3 Pipeline](#esm3-pipeline) | `esm3-generative` |
| **Joint sequence + structure generation** (diffusion in sequence space) | ➡️ [ProteinGenerator Pipeline](#proteingenerator-pipeline) | `protein-generator` |
| **Design a short peptide** (8-30 amino acids) | ➡️ [Peptide Pipeline](#peptide-pipeline) | `diffpepbuilder-design` |
| **Design a macrocyclic peptide** (12-18 aa, head-to-tail cyclic) | ➡️ [RFpeptides Pipeline](#rfpeptides-pipeline) | `rfpeptides-macrocycle` |
| **Design an antibody or nanobody** | ➡️ [Antibody Pipeline](#antibody-pipeline) | `igdiff-antibody` |
| **Redesign a loop or region** of an existing protein | ➡️ [Inpainting / Partial Diffusion](#partial-diffusion-pipeline) | `structure-generation` |
| **Screen many designs quickly** (100+) without big databases | ➡️ [Fast Screening Pipeline](#fast-screening-pipeline) | `fast-screening` |
| **Get the most robust validation** using multiple predictors | ➡️ [Cross-Validation Pipeline](#cross-validation-pipeline) | `cross-validation` |
| **Save time by pre-screening sequences** before expensive validation | ➡️ [Score-First Screening](#score-first-screening) | `score-first-screening` |
| **I have no idea which pipeline to use** | ➡️ [Pipeline Selection Guide](#pipeline-selection) | `pipeline-selection` |

---

## Quick Pipeline Overview

### Standard Pipeline
**Most common choice.** Design any protein backbone, assign sequences, validate structure.

```
PDBFixer → RFdiffusion → ProteinMPNN → AlphaFold3 → Filtering
   ↑            ↑              ↑              ↑            ↑
stage-0      stage-1       stage-2        stage-3      stage-4
```

**Start here:** Read `full-pipeline` skill, then run `scripts/batch_runner.py --config pipeline.yaml`

### BindCraft Pipeline
**Best for binder design.** Automated, end-to-end target-to-binder pipeline with the highest reported experimental success rate. Runs AlphaFold2 Multimer co-design, ProteinMPNN refinement, and AF2 monomer validation in one command.

```
Target PDB + settings JSON → BindCraft → Ranked binders
```

**Start here:** Read `bindcraft-workflow` skill, then run `python /path/to/BindCraft/bindcraft.py --settings target.json`

### Ligand-Aware Pipeline
Design proteins that bind small molecules, cofactors, or metal ions.

```
PDBFixer → RFdiffusionAA → LigandMPNN → AlphaFold3 → Filtering
```

**Start here:** Read `rfdiffusion-all-atom` skill

### RFAA Validation Pipeline
Validate designs that include ligands, DNA/RNA, metal ions, or covalent modifications that AlphaFold3 may not support natively. Uses explicit `pae_inter` interface metric.

```
PDBFixer → RFdiffusionAA / ProteinMPNN → RFAA → Filtering
```

**Start here:** Read `rosettafold-all-atom` skill

### PocketGen Pipeline
Redesign an existing protein pocket around a known small-molecule ligand. Faster and more targeted than full scaffold generation.

```
Scaffold PDB + Ligand SDF → PocketGen → AlphaFold3 / Boltz-1 → Filtering
```

**Start here:** Read `pocketgen-ligand` skill

### ESM3 Pipeline
Generate proteins programmatically from partial sequence, structure, or function prompts. Best for designing from GO terms or functional descriptions.

```
Partial prompt (seq / struct / function) → ESM3.generate() → AlphaFold3 / Boltz-1 → Filtering
```

**Start here:** Read `esm3-generative` skill

### ProteinGenerator Pipeline
Joint sequence + structure generation via RoseTTAFold sequence-space diffusion. Particularly strong for motif scaffolding with sequence constraints, multistate design, and custom potentials.

```
PDBFixer → ProteinGenerator (notebook + inference.py) → AlphaFold3 / Boltz-1 / RFAA → Filtering
```

**Start here:** Read `protein-generator` skill

### Peptide Pipeline
Design 8-30 aa peptide binders with disulfide bonds.

```
PDBFixer → DiffPepBuilder → AMBER/Rosetta relax → AlphaFold3 → Filtering
```

**Start here:** Read `diffpepbuilder-design` skill

### RFpeptides Pipeline
Design 12-18 aa macrocyclic peptides (head-to-tail cyclization) using standard RFdiffusion.

```
PDBFixer → RFdiffusion (cyclic=True) → ProteinMPNN → AlphaFold3/Boltz-1 → Filtering
```

**Start here:** Read `rfpeptides-macrocycle` skill

### Fast Screening Pipeline
Skip AlphaFold3's 2.6TB databases. Use OmegaFold or ESMFold for quick validation.

```
PDBFixer → RFdiffusion → ProteinMPNN → OmegaFold/ESMFold → Filtering
```

**Start here:** Read `fast-screening` skill

### Cross-Validation Pipeline
Run multiple validators (Boltz-1, Chai-1, OmegaFold, ESMFold) and rank by consensus.

```
PDBFixer → RFdiffusion → ProteinMPNN → [Boltz-1 + Chai-1 + OmegaFold] → Consensus Filtering
```

**Start here:** Read `cross-validation` skill

### Score-First Screening
Use ProteinMPNN's score_only mode to pre-filter sequences BEFORE running expensive validation.

```
PDBFixer → RFdiffusion → ProteinMPNN (design 32 seqs)
                                      ↓
                          ProteinMPNN score_only (filter to top 20%)
                                      ↓
                               AlphaFold3 (only top candidates)
```

**Start here:** Read `score-first-screening` skill

### Partial Diffusion / Inpainting
Redesign a specific region while keeping the rest fixed.

```
PDBFixer → RFdiffusion (partial_T=10) → ProteinMPNN → AlphaFold3 → Filtering
```

**Start here:** Read `structure-generation` skill (Advanced Parameters section)

### Antibody Pipeline
Design antibodies or nanobodies.

```
PDBFixer → IgDiff / RFdiffusion → AbMPNN / ProteinMPNN → AlphaFold3 → Filtering
```

**Start here:** Read `igdiff-antibody` skill

### nf-binder-design Pipeline
HPC/cloud-ready Nextflow pipeline that wraps multiple binder design methods (`rfd`, `rfd_partial`, `bindcraft`, `boltzgen`, `boltz_pulldown`) with built-in parallelization and scoring.

```
Target PDB → Nextflow nf-binder-design --method <method> → Ranked binders + scores
```

**Start here:** Read `nf-binder-design` skill

---

## Execution Mode: Choose How to Run

### Option A: Standalone Scripts (Recommended)

Use Python scripts directly. Fastest, simplest, works with any agent.

```bash
# Step-by-step
python scripts/run_pdbfixer.py --input target.pdb --output fixed.pdb
python scripts/run_rfdiffusion.py --contig "150-150" --num-designs 50
python scripts/run_proteinmpnn.py --pdb-path "design_*.pdb" --out-folder seqs/
python scripts/run_alphafold3.py --json af3_input.json --output-dir af3/
python scripts/run_filtering.py --results-dir af3/ --min-plddt 75

# Or all-at-once with batch runner
python scripts/batch_runner.py --config pipeline.yaml
```

---

## Stage Reference

| Stage | Purpose | Primary Skill | Script |
|-------|---------|--------------|--------|
| 0 | PDB repair | `structure-preprocessing` | `run_pdbfixer.py` |
| 1 | Backbone generation | `structure-generation` | `run_rfdiffusion.py` |
| 2 | Sequence design | `sequence-design` | `run_proteinmpnn.py` |
| 3 | Structure validation | `structure-validation` | `run_alphafold3.py` |
| 4 | Filtering / ranking | `filtering-ranking` | `run_filtering.py` |

## Alternative Validators (Replace Stage 3)

| Validator | Speed | Databases | License | Skill |
|-----------|-------|-----------|---------|-------|
| AlphaFold3 | Slow | 2.6TB | Non-commercial | `structure-validation` |
| RFAA | Medium | ~400GB | Open | `rosettafold-all-atom` |
| Boltz-1 | Medium | None | MIT | `boltz-validation` |
| Chai-1 | Medium | None | Apache 2.0 | `chai1-validation` |
| OmegaFold | Fast | None | Open | `omegafold-validation` |
| ESMFold | **Fastest** | None | MIT | `esmfold-validation` |
| Protenix | Medium | None | Apache 2.0 | `protenix-validation` |
| OpenFold3 | Medium | pip install | Apache 2.0 | `openfold-validation` |

## Quality Thresholds

| Metric | Acceptable | Good | Excellent |
|--------|-----------|------|-----------|
| pLDDT | >70 | >80 | >90 |
| ipTM | >0.6 | >0.8 | >0.9 |
| pTM | >0.5 | >0.7 | >0.9 |

## First-Time Setup

If tools are not installed, read `install-guide` skill for one-line install commands.

## Quick Check: Are Tools Ready?

```bash
python protein_design/hooks/session-health-check.py
```

Or check the hook output that should have fired automatically when you mentioned protein design.

---

**Next step:** Tell me what you want to design, and I'll guide you to the right pipeline and parameters.

---
name: bindcraft-workflow
description: Automated de novo protein binder design with BindCraft — one-shot target-to-binder pipeline using AlphaFold2 Multimer co-design and ProteinMPNN refinement
---

# BindCraft Workflow: Automated Binder Design

## When to Trigger

- User says "BindCraft", "automated binder", "one-shot binder", "de novo binder"
- User wants to **design a protein binder to a target** without manually chaining RFdiffusion + ProteinMPNN + AlphaFold3
- User asks for **binder design with experimental validation in mind**
- User mentions "target hotspots", "binder length", "i_pTM", "pAE"
- User wants an **end-to-end binder pipeline** in one command

## What is BindCraft?

[BindCraft](https://github.com/martinpacesa/BindCraft) is an open-source, automated pipeline for *de novo* protein binder design published in *Nature* (Pacesa et al., 2025). It achieves **10–100% experimental success rates** by co-designing binder backbone, sequence, and interface in a single optimization loop through fixed AlphaFold2 Multimer weights.

### Key Differences from Standard Pipeline

| Feature | Standard Pipeline (RFdiffusion + MPNN + AF3) | **BindCraft** |
|---------|----------------------------------------------|---------------|
| Stages | 4 separate stages | **Single end-to-end run** |
| Target flexibility | Fixed target backbone | **Flexible target + binder** |
| Design logic | Backbone first, then sequence, then validate | **Co-design all three** |
| Best for | General proteins, motif scaffolding | **Binder design only** |
| Experimental success | Variable | **10–100% reported** |
| Compute | GPU + 2.6TB AF3 DB | **GPU + ~5GB AF2 weights** |
| Output ranking | pLDDT / ipTM | **i_pTM + i_pAE + filters** |

## System Requirements

- **OS**: Linux only (Ubuntu recommended)
- **GPU**: NVIDIA with ≥32GB VRAM (48GB L40S recommended)
- **RAM**: 32–64 GB
- **CUDA**: 11.7+ (12.0+ recommended, must match JAX)
- **Python**: 3.9+ (3.10 recommended)
- **Package manager**: `conda` or `mamba`
- **License**: PyRosetta required for commercial users

## Installation

```bash
# Clone repository
git clone https://github.com/martinpacesa/BindCraft.git
cd BindCraft

# Install with matching CUDA version (critical for JAX compatibility)
bash install_bindcraft.sh --cuda '12.4' --pkg_manager 'conda'

# The installer downloads AlphaFold2 weights (~5.3 GB)
```

**⚠️ Installation tip**: Most failures are caused by JAX/CUDA version mismatches. Always match `--cuda` to your driver CUDA version.

## Usage

### Basic Local Run

BindCraft uses **JSON settings files** instead of many CLI flags:

```bash
conda activate BindCraft
cd /path/to/BindCraft

python -u ./bindcraft.py \
  --settings './settings_target/PDL1.json' \
  --filters './settings_filters/default_filters.json' \
  --advanced './settings_advanced/default_4stage_multimer.json'
```

### Target Settings JSON (`settings_target/PDL1.json`)

```json
{
  "design_path": "./outputs/PDL1_binders/",
  "binder_name": "PDL1_binder",
  "starting_pdb": "./inputs/PDL1.pdb",
  "chains": "A",
  "target_hotspot_residues": "A45,A67,A89,A91",
  "lengths": [70, 75, 80, 85, 90, 95, 100],
  "number_of_final_designs": 100
}
```

**Key fields:**

| Field | Description |
|-------|-------------|
| `design_path` | Output directory |
| `binder_name` | Prefix for output files |
| `starting_pdb` | Target structure (trim to smallest relevant region!) |
| `chains` | Target chain(s) to bind |
| `target_hotspot_residues` | Desired interface residues on target (PDB numbering) |
| `lengths` | List of binder lengths to sample (optimal: 60–180 aa) |
| `number_of_final_designs` | Target number of designs passing filters (recommend ≥100) |

### Hotspot Syntax

```
Single chain:   "23,25,27-30,35-45"
Multichain:     "A23,A25,A27-50,B45,B73,C24"
Chain-level:    "A23,A37,B45,C"
Auto-detect:    ""  (leave empty — AF2 will search for binding sites)
```

**Recommendation**: Pick a surface patch with aromatic/aliphatic residues (Phe, Tyr, Trp, Ile, Leu, Met) for best results.

### SLURM / Cluster Run

```bash
sbatch ./bindcraft.slurm \
  --settings './settings_target/PDL1.json' \
  --filters './settings_filters/default_filters.json' \
  --advanced './settings_advanced/default_4stage_multimer.json'
```

### Google Colab

BindCraft provides an official Colab notebook (one-click, no local GPU needed):
- Click "Open In Colab" on the GitHub repo
- Upload target PDB and settings
- Run all cells

## Pipeline Stages (Internal)

BindCraft runs three internal stages automatically:

```
Input: Target PDB + settings JSON
  ↓
Stage 1: AlphaFold2 Multimer co-design
         → Generates binder backbone + sequence + interface simultaneously
         → Gradient-based optimization through fixed AF2 weights
         → Uses all 5 AF2 models to avoid overfitting
  ↓
Stage 2: ProteinMPNN refinement (MPNNsol)
         → Re-optimizes core/surface for solubility and expression
         → Preserves the binding interface
  ↓
Stage 3: AlphaFold2 monomer validation + filtering
         → Re-predicts standalone binder structures
         → Filters by pLDDT, i_pTM, i_pAE, clashes, Rosetta scores
  ↓
Output: Ranked binder designs in Accepted/Ranked/
```

## Output Directory Structure

```
outputs/PDL1_binders/
├── Trajectory/                  # Raw co-design trajectories
│   ├── PDL1_binder_001.pdb
│   └── ...
├── MPNN/                        # MPNN-refined sequences
│   ├── PDL1_binder_001_mpnn.fasta
│   └── ...
├── Accepted/                    # Designs passing filters
│   ├── PDL1_binder_001.pdb
│   ├── PDL1_binder_001.fasta
│   └── ...
├── Accepted/Ranked/             # Final ranking by i_pTM
│   ├── PDL1_binder_001.pdb
│   └── ...
├── trajectory_stats.csv         # Per-trajectory metrics
├── mpnn_design_stats.csv        # Post-MPNN metrics
└── final_design_stats.csv       # Final accepted designs + all scores
```

## Interpreting Results

### Key Metrics

| Metric | What it means | Good value |
|--------|---------------|------------|
| **i_pTM** | Interface predicted TM-score (binary binding predictor) | **>0.6–0.8** |
| **i_pAE** | Interface predicted aligned error (lower = better interface) | **<10–15 Å** |
| **pLDDT** | Per-residue confidence | **>80–90** |
| **pTM** | Overall predicted TM-score | **>0.7** |
| **Binder_RMSD** | Consistency between designs | Depends on flexibility |

**Important**: i_pTM is a good **binary predictor of binding** (will it bind?) but **NOT a good predictor of affinity** (how tightly?).

### Recommended Filters

Default filters are usually appropriate. Common adjustments:

| Scenario | Adjustment |
|----------|------------|
| Flexible binders / peptides | Relax `Binder_RMSD` |
| Very large complexes (>600 aa) | Use `predict_bigbang` advanced setting |
| Beta-sheet binders | Use `betasheet_` advanced prefix |
| Difficult binding mode | Use `_hardtarget` settings |
| Need interface redesign | Use `_mpnn` settings |

## Comparison with Other Pipelines

| Use Case | Best Pipeline | Why |
|----------|---------------|-----|
| General de novo proteins | Standard Pipeline | More flexible beyond binders |
| Automated binder design | **BindCraft** | Purpose-built, highest reported experimental success |
| Peptide binders (8–30 aa) | Peptide Pipeline (DiffPepBuilder) | Specialized geometry and docking |
| Macrocyclic peptides | RFpeptides Pipeline | Head-to-tail cyclic support |
| Ligand/cofactor binders | Ligand-Aware Pipeline | Small-molecule-aware design |
| No local GPU | ColabDesign Pipeline | Free Colab GPU |
| Fast screening | Fast Screening Pipeline | OmegaFold, no databases |
| Maximum binder diversity | Ensemble Pipeline | RFdiffusion + MPNN + ESM-IF1 |

## Tips for Best Results

1. **Trim the target PDB** to the smallest relevant region — dramatically speeds up design and reduces GPU memory
2. **Run at least 100 accepted designs** — easy targets may need ~100 trajectories; difficult targets may need 1,000–10,000+
3. **Order top 5–20 for experimental validation** — don't just pick #1
4. **Define hotspots** when you have structural information; leave empty only if you want AF2 to explore
5. **Binder lengths**: 60–180 aa optimal; 8–25 aa for peptides; max reliable ~250 aa
6. **Monitor i_pTM and i_pAE** as the primary quality metrics
7. **Expect deformations** — trajectories that produce physically implausible shapes are discarded automatically

## Integration with This Plugin

BindCraft is a **self-contained pipeline** and does not use the 5-stage plugin structure directly. However, you can integrate it:

```bash
# Option A: Run BindCraft standalone
python /path/to/BindCraft/bindcraft.py --settings target.json --filters default.json

# Option B: Preprocess target with the plugin's PDBFixer first
python scripts/run_pdbfixer.py --input target.pdb --output target_fixed.pdb
# Then use target_fixed.pdb in BindCraft settings JSON

# Option C: Post-process BindCraft outputs with plugin validators
python scripts/run_alphafold3.py \
  --json bindcraft_accepted.json \
  --output-dir outputs/bindcraft_af3_validation/
```

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| "Mismatched number of atoms during alignment" | Partial residues/orphan atoms in target PDB. Re-run PDBFixer and trim target. |
| Binder misses hotspots | Expected — try trimming target, mutating off-target residues to Lys, or use `_hardtarget` settings |
| Very few accepted designs | Difficult target — increase trajectories, adjust hotspots, or relax filters |
| Out of memory | Trim target; reduce `lengths` range; use smaller `number_of_final_designs` per batch |
| Deformed/squashed trajectories | Normal — these are auto-discarded. Increase sampling if too frequent. |
| Installation fails at JAX | CUDA/JAX version mismatch. Match `--cuda` to your system's CUDA version. |

## References

- [BindCraft GitHub](https://github.com/martinpacesa/BindCraft)
- [BindCraft Wiki — De novo binder design](https://github.com/martinpacesa/BindCraft/wiki/De-novo-binder-design-with-BindCraft)
- [BindCraft Paper (Nature)](https://doi.org/10.1038/s41586-025-08721-4)
- [bioRxiv preprint](https://doi.org/10.1101/2024.09.30.615802)
- [Australian Protein Design Initiative — nf-binder-design](https://github.com/Australian-Protein-Design-Initiative/nf-binder-design) — Nextflow wrapper for HPC

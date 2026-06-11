---
name: pocketgen-ligand
description: Pocket-aware protein-ligand co-design with PocketGen — generate full-atom ligand-binding pockets conditioned on a small-molecule ligand and protein scaffold
---

# PocketGen Workflow: Ligand-Binding Pocket Design

## When to Trigger

- User says "PocketGen", "pocket design", "ligand-binding pocket", "design around a ligand"
- User wants to **redesign a protein pocket** to bind a specific small molecule
- User has a **known ligand** and a **protein scaffold** and wants to co-design the binding site
- User mentions "small molecule binder design" but with **pocket-focused** generation
- User needs **enzyme active site redesign** for a new substrate/cofactor

## What is PocketGen?

[PocketGen](https://github.com/zaixizhang/PocketGen) is a deep generative model published in *Nature Machine Intelligence* (Zhang et al., 2024) that designs **full-atom ligand-binding protein pockets**. Unlike RFdiffusionAA or LigandMPNN, which generate an entire protein around a ligand, PocketGen specifically redesigns the pocket region of an existing scaffold while preserving the rest of the protein.

### Key Differences from Other Ligand-Aware Tools

| Feature | RFdiffusionAA | LigandMPNN | **PocketGen** |
|---------|---------------|------------|---------------|
| Scope | Full protein + ligand | Sequence on fixed backbone | **Pocket region only** |
| Input | Ligand + optional motif | Backbone + ligand | **Scaffold + ligand** |
| Output | Full protein backbone | Sequence assignment | **Pocket sequence + structure** |
| Best for | *De novo* ligand binders | Sequence design on known pocket | **Pocket redesign / optimization** |
| Speed | Slow | Fast | **~10× faster than physics methods** |

## System Requirements

- **OS**: Linux (tested)
- **GPU**: NVIDIA GPU with CUDA 11.6+ support
- **Python**: 3.8
- **Storage**: ~5GB for model checkpoint + data
- **License**: MIT

## Installation

```bash
# Clone repository
git clone https://github.com/zaixizhang/PocketGen.git
cd PocketGen

# Option 1: Use provided conda environment
conda env create -f pocketgen.yaml
conda activate pocketgen

# Option 2: Manual install
conda create -n pocketgen python=3.8
conda activate pocketgen
conda install pytorch pytorch-cuda=11.6 -c pytorch -c nvidia
pip install torch-geometric rdkit openbabel tensorboard pyyaml EasyDict lmdb
pip install openmm pdbfixer flask
pip install meeko==0.1.dev3 wandb scipy pdb2pqr vina==1.2.2
# Also install AutoDockTools_py3 from git
```

**Important**: The environment includes `vina==1.2.2` for scoring generated pockets. Make sure CUDA version matches your driver.

## Data and Checkpoints

### Pretrained Checkpoint

Download the pretrained PocketGen checkpoint (usually via Google Drive link in the repo) and place it under:

```
PocketGen/checkpoints/
└── checkpoint.pt
```

Update the config YAML (`configs/train_model.yml`) to point to the checkpoint:

```yaml
model:
  checkpoint: ./checkpoints/checkpoint.pt
```

### ESM-2 Model

PocketGen uses ESM-2 (`esm2_t33_650M_UR50D`) for the sequence refinement module. It will be downloaded automatically on first use via `fair-esm`.

## Input Format

For each target, create a directory under `./generate/<pdbid>/` containing:

```
generate/
└── 2p16/
    ├── 2p16.pdb          # Full protein scaffold (pocket region will be masked/redesigned)
    └── 2p16_ligand.sdf   # Bound small-molecule ligand
```

**Notes:**
- `<name>_pocket.pdb` will be created automatically if absent
- PocketGen extracts a 10Å pocket and identifies 3.5Å binding residues automatically
- The pocket region in the input scaffold should be present but will be redesigned

## Usage

### Basic Generation

Edit `generate_new.py` to include your target names (the repo uses a hardcoded list):

```python
names = ['2p16']  # Add your PDB IDs here
```

Then run:

```bash
conda activate pocketgen
cd /path/to/PocketGen

python generate_new.py \
  --config ./configs/train_model.yml \
  --device cuda:0 \
  --target ./generate \
  --logdir ./logs
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--config` | `./configs/train_model.yml` | Model and dataset config |
| `--device` | `cuda:0` | PyTorch device |
| `--target` | `./generate` | Directory containing target subdirectories |
| `--logdir` | `./logs` | Logging directory |

### Processing Multiple Targets

```bash
# Create one subdirectory per target
mkdir -p generate/target1 generate/target2
cp target1.pdb generate/target1/target1.pdb
cp target1_ligand.sdf generate/target1/target1_ligand.sdf
cp target2.pdb generate/target2/target2.pdb
cp target2_ligand.sdf generate/target2/target2_ligand.sdf

# Edit generate_new.py names list to include 'target1', 'target2'
python generate_new.py --target ./generate --device cuda:0
```

## Pipeline Integration

### Option 1: Standalone Pocket Redesign
```
Input: Protein scaffold PDB + Ligand SDF
    ↓
PocketGen (redesign pocket region)
    ↓
Output: Pocket sequence + structure
    ↓
Rosetta / OpenMM relax
    ↓
Experimental validation
```

### Option 2: Combined with RFdiffusionAA
```
RFdiffusionAA (generate overall protein topology around ligand)
    ↓
PocketGen (refine pocket sequence + side chains)
    ↓
LigandMPNN (re-sequence full protein)
    ↓
AlphaFold3 / Boltz-1 (validate)
    ↓
Filtering
```

### Option 3: Enzyme Engineering
```
Input: Wild-type enzyme + new substrate/cofactor
    ↓
PocketGen (redesign active site pocket)
    ↓
Molecular dynamics (validate substrate binding)
    ↓
Activity assay
```

## Output Files

For each target in `./generate/<name>/`:

```
generate/
└── 2p16/
    ├── 2p16.pdb                 # Original scaffold
    ├── 2p16_ligand.sdf          # Input ligand
    ├── 2p16_pocket.pdb          # Extracted pocket (auto-generated)
    ├── 2p16_generated.pdb       # Generated pocket structure
    ├── 2p16_docked.pdbqt        # Vina docked pose
    ├── 2p16_docked.sdf          # Docked ligand pose
    └── attention.pkl            # Attention logits
```

## Interpreting Results

### Key Metrics

| Metric | Meaning | Good Value |
|--------|---------|------------|
| **AAR** | Amino Acid Recovery vs natural homologs | Higher is better (~63–64% typical) |
| **Designability** | Structural self-consistency | Higher is better (~0.77–0.80 typical) |
| **Vina Score** | Predicted binding affinity (kcal/mol) | Lower is better (more negative) |
| **scRMSD** | Self-consistency RMSD | Lower is better |
| **scTM** | Self-consistency TM-score | Higher is better |
| **pLDDT** | Predicted local distance difference test | Higher is better |

**Benchmark results:**
- CrossDocked: AAR 63.40±1.64%, Designability 0.77±0.02, Vina −7.135±0.08
- Binding MOAD: AAR 64.43±2.35%, Designability 0.80±0.04, Vina −8.112±0.14

### Success Criterion

PocketGen reports a **95% success rate** of generated pockets having **higher binding affinity** than the reference pocket (as measured by Vina score).

## Comparison with Other Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| *De novo* ligand binder (full protein) | RFdiffusionAA | Designed for full scaffold generation |
| Sequence design on known pocket | LigandMPNN | Fast, proven experimental success |
| Pocket redesign / optimization | **PocketGen** | Purpose-built for pocket co-design |
| Enzyme active site engineering | **PocketGen** | Preserves overall fold, redesigns active site |
| Docking + pose refinement | Vina / GNINA | Complementary physics-based scoring |
| Full-atom validation | AlphaFold3 / Boltz-1 | Validate final designs |

## Tips for Best Results

1. **Prepare a clean scaffold** — Remove waters, ions, and alternative conformations
2. **Use a realistic ligand pose** — The input SDF ligand geometry strongly influences the designed pocket
3. **Trim the scaffold** — PocketGen only redesigns the pocket; keeping the scaffold compact speeds up generation
4. **Compare Vina scores** — Generated pocket is successful if Vina score improves over reference
5. **Run multiple seeds** — Like all generative models, diversity improves with more samples
6. **Validate with MD** — PocketGen optimizes for predicted affinity; molecular dynamics checks stability
7. **Use PLIP** for interaction analysis — Compare non-bonded interactions between designed and reference pockets

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `tmp` directory error | Create a `tmp/` directory in the working folder before running |
| ESM-2 download fails | Check internet connection or pre-download `esm2_t33_650M_UR50D` |
| Vina scoring fails | Verify `vina==1.2.2` is installed and the ligand SDF is valid |
| CUDA out of memory | Reduce batch size in config or use a smaller scaffold |
| Pocket not detected | Ensure the ligand is close (<10Å) to the pocket residues in the input PDB |

## References

- [PocketGen GitHub](https://github.com/zaixizhang/PocketGen)
- [PocketGen Project Page](https://zitniklab.hms.harvard.edu/projects/PocketGen/)
- [Paper: Efficient generation of protein pockets with PocketGen](https://www.nature.com/articles/s42256-024-00920-9) — *Nature Machine Intelligence*, 2024
- Citation: Zhang, Zaixi, Shen, Wan Xiang, Liu, Qi, & Zitnik, Marinka. "Efficient generation of protein pockets with PocketGen." *Nature Machine Intelligence* (2024).

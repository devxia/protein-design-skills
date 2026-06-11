---
name: la-proteina-backbone
description: Joint sequence-structure generation with La-Proteina — NVIDIA's partially latent flow matching model for simultaneous amino acid sequence and full atomistic structure design (up to 800 residues)
---

# Alternative Stage 1+2: La-Proteina Joint Sequence-Structure Generation

## Quick Entry

**Use this skill when you want to generate BOTH sequence AND full atomistic structure in a single step.** Replaces Stage 1 (backbone generation) + Stage 2 (sequence design) with one model.

**Typical flow:** PDBFixer (optional) → **La-Proteina** (joint seq+structure) → `structure-validation` (Stage 3) → `filtering-ranking` (Stage 4)

## When to Trigger

- User says "La-Proteina", "NVIDIA proteina", "latent flow matching"
- User wants to generate **both sequence and full atomistic structure** in one step
- User needs **backbone + sidechains** co-designed natively
- User says "joint sequence structure", "full atomistic generation"
- User wants a **single NVIDIA-backed model** replacing Stage 1 + Stage 2
- User needs designs up to **800 residues** (most baselines collapse at this scale)

## La-Proteina Overview

[La-Proteina](https://github.com/NVIDIA-BioNeMo/la-proteina) is **NVIDIA's partially latent flow matching model** for **joint generation of amino acid sequence and full atomistic protein structure** (backbone + sidechains). Unlike the standard pipeline that separates backbone generation (Stage 1) and sequence design (Stage 2), La-Proteina generates both simultaneously in a single forward pass through a latent space.

### Key Differences from Standard Pipeline

| Feature | Standard Pipeline (RFdiffusion + ProteinMPNN) | La-Proteina |
|---------|-----------------------------------------------|-------------|
| Approach | Sequential (structure → sequence) | **Joint (simultaneous)** |
| Method | Diffusion + GNN | **Partially latent flow matching** |
| Output | Backbone only | **Full atomistic (backbone + sidechains)** |
| Latent space | None | **Partially latent representation** |
| Speed | Slower (two stages) | **Faster (single model)** |
| Max length | ~500 typical | **Up to 800 residues** |
| Engineering | Community-driven | **NVIDIA-backed, production-grade** |

## Installation

```bash
# Recommended: use mamba or micromamba
mamba env create -f environment.yaml
mamba activate laproteina_env

# Install PyTorch with CUDA
pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu118

# Install graph dependencies
pip install graphein==1.7.7 --no-deps
pip install torch_geometric torch_scatter torch_sparse torch_cluster \
    -f https://data.pyg.org/whl/torch-2.7.0+cu118.html
```

**Download checkpoints** into `./checkpoints_laproteina/`:

| Checkpoint | Model | Use Case | Max Length |
|-----------|-------|----------|------------|
| LD1_ucond_notri_512.ckpt | Unconditional, no triangular updates | General generation | 500 |
| LD2_ucond_tri_512.ckpt | Unconditional, triangular updates | General generation | 500 |
| LD3_ucond_notri_800.ckpt | Unconditional, no triangular updates | Long proteins | 800 |
| LD4_motif_idx_aa.ckpt | Indexed all-atom motif scaffolding | Motif + all atoms | 256 |
| LD5_motif_idx_tip.ckpt | Indexed tip-atom motif scaffolding | Motif + tip atoms | 256 |
| LD6_motif_uidx_aa.ckpt | Unindexed all-atom motif scaffolding | Motif + all atoms | 256 |
| LD7_motif_uidx_tip.ckpt | Unindexed tip-atom motif scaffolding | Motif + tip atoms | 256 |

**Autoencoder checkpoints** (pair with LD models):
| AE | Paired with | Max Length |
|----|-------------|------------|
| AE1_ucond_512.ckpt | LD1, LD2 | 500 |
| AE2_ucond_800.ckpt | LD3 | 800 |
| AE3_motif.ckpt | LD4-LD7 | 256 |

## Usage

### Unconditional Generation (CLI)

```bash
# Model LD1: unconditional, no triangular updates, up to 500 residues
python proteinfoundation/generate.py --config_name inference_ucond_notri

# Model LD2: unconditional, triangular updates, up to 500 residues
python proteinfoundation/generate.py --config_name inference_ucond_tri

# Model LD3: unconditional, long proteins (300-800 residues)
python proteinfoundation/generate.py --config_name inference_ucond_notri_long
```

**Config file locations:**
- `configs/generation/uncod_codes.yaml` — lengths [100, 200, 300, 400, 500], noise scales
- `configs/generation/uncod_codes_800.yaml` — lengths [300, 400, 500, 600, 700, 800]

### Atomistic Motif Scaffolding (CLI)

```bash
# LD4: Indexed all-atom motif scaffolding
python proteinfoundation/generate.py --config_name inference_motif_idx_aa

# LD5: Indexed tip-atom motif scaffolding
python proteinfoundation/generate.py --config_name inference_motif_idx_tip

# LD6: Unindexed all-atom motif scaffolding
python proteinfoundation/generate.py --config_name inference_motif_uidx_aa

# LD7: Unindexed tip-atom motif scaffolding
python proteinfoundation/generate.py --config_name inference_motif_uidx_tip
```

**Motif tasks** are defined in `configs/generation/motif_dict.yaml`:
- Tasks **with** `_TIP` suffix → use tip-atom models (LD5, LD7)
- Tasks **without** `_TIP` suffix → use all-atom models (LD4, LD6)
- Contig strings specify motif scaffolding geometry

### Python API

```python
import torch
from la_proteina import LaProteinaModel

# Load model
model = LaProteinaModel.from_pretrained("la-proteina-base")
model = model.cuda()

# Generate protein (sequence + full structure)
result = model.sample(
    length=150,
    num_steps=50,
    temperature=1.0,
)

# Access outputs
sequence = result.sequence
structure = result.structure  # Full atomistic coordinates

# Save
result.save_pdb("la_proteina_design.pdb")
result.save_fasta("la_proteina_design.fasta")
```

### Conditional Generation (Motif Scaffolding)

```python
# Scaffold around existing motif with full atomistic detail
motif_structure = load_structure("motif.pdb")

result = model.sample(
    motif=motif_structure,
    total_length=200,
    num_steps=50,
    preserve_motif_sidechains=True,
)
```

## Parameters

### Generation Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `length` | int | — | Protein length (residues). Max: 500 (LD1/LD2), 800 (LD3) |
| `num_steps` | int | 50 | Flow integration steps |
| `temperature` | float | 1.0 | Sampling temperature |
| `motif` | Structure | None | Fixed motif to scaffold around |
| `preserve_motif_sidechains` | bool | True | Keep motif sidechains intact |
| `noise_scale_ca` | float | 0.1 | Noise scale for alpha carbon atoms |
| `noise_scale_latent` | float | 0.1 | Noise scale for latent variables |
| `self_cond` | bool | True | Use self-conditioning during sampling |

### Model Selection Guide

| Task | LD Model | AE Model | Config |
|------|----------|----------|--------|
| General design, ≤500 res | LD1 or LD2 | AE1 | `inference_ucond_notri` / `inference_ucond_tri` |
| Long proteins, 300-800 res | LD3 | AE2 | `inference_ucond_notri_long` |
| Motif scaffolding, all-atom | LD4 | AE3 | `inference_motif_idx_aa` |
| Motif scaffolding, tip-atom | LD5 | AE3 | `inference_motif_idx_tip` |
| Motif scaffolding, unindexed all-atom | LD6 | AE3 | `inference_motif_uidx_aa` |
| Motif scaffolding, unindexed tip-atom | LD7 | AE3 | `inference_motif_uidx_tip` |

### Config File Parameters

Key parameters in inference config files (`configs/experiment_config/inference_base_release.yaml`):

| Parameter | Description |
|-----------|-------------|
| `ckpt_name` | Latent diffusion checkpoint name (auto-searched in `checkpoints_laproteina/`) |
| `autoencoder_ckpt_path` | Full path to autoencoder checkpoint |
| `self_cond` | Enable self-conditioning (recommended: True) |
| `sc_scale_noise` | Noise scale for CA atoms and latent variables |

### Speed Optimization

Enable `torch.compile` for 2-3x speedup:
1. Uncomment `torch.compile` lines in `proteinfoundation/nn/local_latents_transformer.py`
2. For training, enable `PaddingTransform` with fixed `max_size`

## Evaluation

```bash
# Download ProteinMPNN weights for evaluation
bash script_utils/download_pmpnn_weights.sh

# Run evaluation
python proteinfoundation/evaluate.py --config_name <config_name>
```

**Evaluation metrics:**
- (Co-)designability — self-consistency with ProteinMPNN
- Motif RMSD — for motif scaffolding tasks
- Motif sequence recovery

**Batch generation + evaluation:**
```bash
bash script_utils/gen_n_eval.sh
```

## Pipeline Integration

### Option 1: La-Proteina-Only Pipeline (Fastest)
```
Stage 0: PDBFixer (if needed)
    ↓
Stage 1+2: La-Proteina (joint sequence + full structure)
    ↓
Stage 3: AlphaFold3 / Boltz (validation)
    ↓
Stage 4: Filtering
```

### Option 2: La-Proteina + Refinement
```
Stage 1+2: La-Proteina (joint generation)
    ↓
Stage 2b: ProteinMPNN (refine sequence)
    ↓
Stage 3: AlphaFold3 (validation)
    ↓
Stage 4: Filtering
```

### Option 3: Hybrid
```
Stage 1: RFdiffusion (generate diverse backbones)
    ↓
Stage 2a: La-Proteina (generate full structures with sidechains)
    ↓
Stage 2b: ProteinMPNN (alternative sequences)
    ↓
Stage 3: AlphaFold3 (validate both sets)
    ↓
Stage 4: Filtering + Comparison
```

## Comparison with Other Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| Joint seq+structure | **La-Proteina** | NVIDIA-backed, full atoms, up to 800 res |
| Joint seq+structure (academic) | MultiFlow | Smaller, open-source |
| All-atom generation | Genie 3 | Specialized all-atom diffusion |
| Maximum length | **La-Proteina** | Up to 800 residues |
| Battle-tested reliability | RFdiffusion + ProteinMPNN | More field data |
| Fast prototyping | **La-Proteina** | Single model, fewer steps |
| Motif scaffolding (atomistic) | **La-Proteina** | Surpasses previous models |

## Tips

- **Checkpoints**: Download ALL required checkpoints before running. Each LD model needs its paired AE model.
- **Length limits**: LD1/LD2 → 500 res, LD3 → 800 res, LD4-LD7 → 256 res
- **Noise scales**: Default 0.1 for CA and latent. For LD3 (long proteins), use 0.15 CA + 0.05 latent.
- **Self-conditioning**: Always enable (`self_cond=True`) for best quality.
- **Motif tasks**: Check `configs/generation/motif_dict.yaml` for available tasks and contig strings.
- **torch.compile**: Enable for significant speedup if you run many designs.
- **Training**: Models are trained on AFDB subsets. IDs provided for reproducibility.

## References

- [La-Proteina GitHub](https://github.com/NVIDIA-BioNeMo/la-proteina)
- [La-Proteina Paper](https://arxiv.org/abs/2507.09466)
- [NVIDIA BioNeMo](https://developer.nvidia.com/bionemo)
- [Model Weights (NGC)](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/clara/collections/laproteina_weights_data/artifacts)
- [Flow Matching for Generative Modeling](https://arxiv.org/abs/2210.02747)

---
name: foldflow-backbone
description: Flow matching protein backbone generation with FoldFlow — faster, simpler alternative to diffusion models
---

# Alternative Stage 1: FoldFlow Backbone Generation

> **Quick Entry**: Stage 1 alternative | flow matching | fast prototyping | equilibrium conformations
>
> **Upstream**: `structure-preprocessing` (PDB repair and preparation) | **Downstream**: `sequence-design` (ProteinMPNN/LigandMPNN) → `structure-validation`

## When to Trigger

- User says "FoldFlow", "flow matching", "stochastic flow"
- User wants **faster** backbone generation than RFdiffusion
- User needs **equilibrium conformations** (molecular dynamics trajectories)
- User wants a **simpler** generative model (flow matching vs diffusion)
- User says "flow model", "continuous flow", "ODE-based generation"
- User wants competitive novelty with **fraction of compute/data**

## FoldFlow Overview

[FoldFlow](https://github.com/DreamFold/FoldFlow) is a **flow matching** model for protein backbone generation that uses **stochastic flows on SE(3)** instead of diffusion. Unlike RFdiffusion which uses iterative denoising, FoldFlow learns a direct probability flow from noise to data, enabling faster and simpler generation.

### Key Differences from RFdiffusion

| Feature | RFdiffusion (Diffusion) | FoldFlow (Flow Matching) |
|---------|------------------------|--------------------------|
| Method | Iterative denoising | Direct probability flow |
| Speed | Slower (many steps) | **Faster (fewer steps)** |
| Simplicity | Complex scheduling | **Simpler ODE solving** |
| Training | Noise prediction | **Velocity field learning** |
| Novelty | Good | **Competitive with less data** |
| Length | ~500 residues | **~300 residues** |
| Conformations | Single state | **Equilibrium ensembles** |

**Key insight**: FoldFlow trades some length capacity for **speed and simplicity**. It's ideal for quick prototyping and generating conformational ensembles.

## Variants

| Variant | Key Feature | Best For |
|---------|-------------|----------|
| **FoldFlow-Base** | Original SE(3) flow matching | General backbone generation |
| **FoldFlow-OT** | Riemannian Optimal Transport | Shorter, simpler flows |
| **FoldFlow-SFM** | Stochastic bridges | Improved novelty/diversity |
| **FoldFlow-2** | + Protein LLM encoding | Better sequence-structure coupling |

## Installation

```bash
# Clone repository
git clone https://github.com/DreamFold/FoldFlow.git
cd FoldFlow

# Install dependencies
pip install -e .

# Requires PyTorch and OpenFold dependencies
```

## Usage

### Basic Unconditional Generation

```python
import torch
from foldflow import FoldFlowModel

# Load model
model = FoldFlowModel.from_pretrained("foldflow-base")
model = model.cuda()

# Generate protein backbone
length = 150
structure = model.sample(
    length=length,
    num_steps=50,  # Fewer steps than diffusion
    temperature=1.0,
)

# Save to PDB
structure.save_pdb("foldflow_design.pdb")
```

### Equilibrium Conformation Ensemble

```python
# Generate MD-like conformational ensemble
ensemble = model.sample_ensemble(
    length=150,
    num_conformations=10,
    temperature=0.8,
)

for i, conf in enumerate(ensemble):
    conf.save_pdb(f"ensemble_conf_{i}.pdb")
```

### Conditional Generation (Scaffolding)

```python
# Scaffold around existing motif
from foldflow.conditional import ConditionalSampler

sampler = ConditionalSampler(model)
motif = load_structure("motif.pdb")

scaffold = sampler.sample(
    motif=motif,
    total_length=200,
    num_steps=50,
)
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `length` | int | — | Protein length (residues) |
| `num_steps` | int | 50 | Flow integration steps |
| `temperature` | float | 1.0 | Sampling temperature |
| `inference_scaling` | float | 5.0 | SO(3) inference scaling |

## Pipeline Integration

### Option 1: FoldFlow-Only Pipeline (Fast Prototyping)
```
Stage 1: FoldFlow (generate backbone)
    ↓
Stage 2: ProteinMPNN (design sequence)
    ↓
Stage 3: OmegaFold (fast validation)
    ↓
Stage 4: Filtering
```

**Why this works:**
- FoldFlow is faster than RFdiffusion
- OmegaFold validation is instant
- Quick iteration cycle for prototyping

### Option 2: FoldFlow + MD Ensemble
```
Stage 1: FoldFlow (generate equilibrium ensemble)
    ↓
Stage 2: ProteinMPNN (design on representative conformation)
    ↓
Stage 3: AlphaFold3 (validate)
    ↓
Stage 4: MD simulation (refine ensemble)
```

**Why this works:**
- FoldFlow generates conformational ensembles
- Useful for intrinsically flexible proteins
- Better represents protein dynamics

### Option 3: Hybrid (FoldFlow + RFdiffusion)
```
Stage 1a: FoldFlow (quick screen 100 designs)
    ↓
Select top 10 by quick metrics
    ↓
Stage 1b: RFdiffusion (refine top 10 with more steps)
    ↓
Stage 2: ProteinMPNN
    ↓
Stage 3: AlphaFold3
```

**Why this works:**
- FoldFlow for fast screening
- RFdiffusion for refinement of best candidates
- Best of both worlds

## Comparison Summary

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| Fast prototyping | **FoldFlow** | Fewer steps, simpler |
| Maximum length (>300aa) | RFdiffusion | Longer sequences |
| Conformational ensembles | **FoldFlow** | Native ensemble generation |
| Battle-tested reliability | RFdiffusion | More field data |
| Novelty with limited data | **FoldFlow** | Competitive with less compute |
| Complex conditioning | RFdiffusion | More mature contig system |
| Simple ODE solver | **FoldFlow** | No complex scheduling |

## Tips

- **Speed**: FoldFlow is ~2-3× faster than RFdiffusion for same quality
- **Steps**: Use 50 steps (vs 200+ for diffusion) for good results
- **Ensembles**: Use FoldFlow-SFM for best novelty/diversity
- **Length limit**: ~300 residues (use RFdiffusion for longer)
- **Inference scaling**: Default 5.0 for SO(3) works well empirically
- **Temperature**: Lower (0.8) for more realistic structures
- **Training**: Requires less data than diffusion models

## Related Flow Matching Tools

| Tool | Repository | Description |
|------|-----------|-------------|
| **FrameFlow** | `microsoft/protein-frame-flow` | Microsoft's SE(3) flow matching |
| **MultiFlow** | Available | Joint sequence-backbone flow |
| **SimpleFold-Turbo** | `usnistgov/simplefold-turbo` | Apple Silicon optimized |
| **Protein-SE(3)** | `BruthYU/protein-se3` | Unified benchmark |

## References

- [FoldFlow GitHub](https://github.com/DreamFold/FoldFlow)
- [FoldFlow Paper (ICLR 2024)](https://arxiv.org/abs/2310.02391)
- [FoldFlow-2 Paper](https://arxiv.org/abs/2405.20313)
- [FrameFlow (Microsoft)](https://github.com/microsoft/protein-frame-flow)

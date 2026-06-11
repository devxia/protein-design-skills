---
name: proteina-complexa-binder
description: Protein binder design with Proteina-Complexa — NVIDIA's generative model for binder design to protein and small molecule targets with inference-time optimization
---

# Alternative: Proteina-Complexa Binder Design

## When to Trigger

- User says "Proteina-Complexa", "binder design", "NVIDIA binder"
- User wants to design **protein binders** to specific targets
- User needs **inference-time optimization** for better binding
- User says "design a binder", "binder for target", "protein-protein interaction"
- User wants **small molecule binder design**
- User needs purpose-built binder design tool (not general protein design)

## Proteina-Complexa Overview

[Proteina-Complexa](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa) is **NVIDIA's generative model specifically for protein binder design** to both protein and small molecule targets. Built on top of La-Proteina, it adds **inference-time optimization** that iteratively refines the binder structure to improve binding affinity during generation.

### Key Differences from General Design Tools

| Feature | RFdiffusion (General) | Proteina-Complexa |
|---------|----------------------|-------------------|
| Purpose | General protein design | **Specialized binder design** |
| Optimization | None at inference | **Inference-time optimization** |
| Targets | Protein backbones | **Protein + small molecule targets** |
| Success rate | Standard | **Potentially higher** |
| Input | Target structure | **Target structure + binding site** |

**Key insight**: Proteina-Complexa is the **best choice** when your primary goal is designing a binder (protein-protein or protein-small molecule), as it includes specialized optimization that general-purpose tools lack.

## Installation

```bash
# Clone repository
git clone https://github.com/NVIDIA-BioNeMo/Proteina-Complexa.git
cd Proteina-Complexa

# Install dependencies
pip install -e .

# Requirements: PyTorch 2.0+, CUDA GPU (NVIDIA GPU recommended)
```

## Usage

### Protein-Protein Binder Design

```python
import torch
from proteina_complexa import BinderDesigner

# Load model
model = BinderDesigner.from_pretrained("proteina-complexa-base")
model = model.cuda()

# Load target protein
target = load_structure("target_protein.pdb")

# Design binder
binder = model.design_binder(
    target=target,
    binder_length=100,
    target_binding_site=["A30", "A33", "A34", "A45"],  # Residues to bind
    num_optimization_steps=50,  # Inference-time optimization
    temperature=1.0,
)

binder.save_pdb("binder_design.pdb")
```

### Small Molecule Binder Design

```python
# Design binder for small molecule target
sm_target = load_structure("small_molecule.pdb")

binder = model.design_small_molecule_binder(
    target=sm_target,
    binder_length=80,
    num_optimization_steps=50,
)

binder.save_pdb("sm_binder.pdb")
```

### Batch Binder Design with Selection

```python
# Generate multiple binders and rank by predicted affinity
binders = []
for i in range(10):
    binder = model.design_binder(
        target=target,
        binder_length=100,
        num_optimization_steps=50,
    )
    score = model.predict_binding_affinity(target, binder)
    binders.append((binder, score))

# Select top binder
best_binder, best_score = max(binders, key=lambda x: x[1])
print(f"Best predicted affinity: {best_score:.3f}")
best_binder.save_pdb("best_binder.pdb")
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target` | Structure | — | Target protein or small molecule |
| `binder_length` | int | — | Length of binder to design |
| `target_binding_site` | list | None | Target residues for binding |
| `num_optimization_steps` | int | 50 | Inference-time optimization steps |
| `temperature` | float | 1.0 | Sampling temperature |

## Pipeline Integration

### Option 1: Proteina-Complexa Direct Pipeline
```
Stage 0: PDBFixer (prepare target)
    ↓
Proteina-Complexa (design binder with optimization)
    ↓
AlphaFold3 / Boltz (validate binder-target complex)
    ↓
Filtering (check ipTM for interface quality)
    ↓
Docking validation (optional)
```

**Why this works:**
- Purpose-built for binder design
- Inference-time optimization improves binding
- Validate with standard structure prediction

### Option 2: Hybrid (Proteina-Complexa + Standard)
```
Stage 0: PDBFixer (prepare target)
    ↓
Proteina-Complexa (generate 10 binder candidates)
    ↓
ProteinMPNN (design sequences for each binder backbone)
    ↓
AlphaFold3 (validate binder-target complex for all)
    ↓
Filtering (select by ipTM + predicted affinity)
```

**Why this works:**
- Proteina-Complexa for diverse binder structures
- ProteinMPNN for sequence optimization
- Large-scale validation to find best binder

## Comparison with Other Binder Design Tools

| Tool | Method | Best For |
|------|--------|----------|
| **Proteina-Complexa** | Flow matching + optimization | Protein + small molecule binders |
| RFdiffusion (binder mode) | Diffusion | General binder scaffolding |
| ColabDesign/AfDesign | Hallucination | Free GPU, flexible loss |
| DiffPepBuilder | Diffusion | Short peptide binders (8-30aa) |
| PXDesign | Specialized | ByteDance binder design |

## Tips

- **Optimization steps**: More steps = better binding but slower. 50 is a good default.
- **Binder length**: 80-120 residues typical for protein-protein binders
- **Binding site**: Specify hotspot residues on target for directed binding
- **Validation**: Always check ipTM (interface pTM) in AlphaFold3 validation
- **Docking**: Consider molecular docking for final validation
- **NVIDIA GPU**: Best performance on NVIDIA hardware

## References

- [Proteina-Complexa GitHub](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa)
- [NVIDIA BioNeMo](https://developer.nvidia.com/bionemo)
- [La-Proteina (base model)](https://github.com/NVIDIA-BioNeMo/la-proteina)

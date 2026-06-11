---
name: genie3-backbone
description: All-atom protein backbone and sidechain generation with Genie 3 — SOTA SE(3)-equivariant diffusion for unconditional, motif scaffolding, and binder design
---

# Alternative Stage 1: Genie 3 All-Atom Generation

> **Quick Entry**: Stage 1 alternative | all-atom generation (backbone + sidechains) | SE(3)-equivariant | motif scaffolding with sidechains
>
> **Upstream**: `structure-preprocessing` (PDB repair and preparation) | **Downstream**: `sequence-design` (optional refinement) → `structure-validation`

## When to Trigger

- User says "Genie 3", "genie3", "all-atom diffusion"
- User wants **sidechain-aware** backbone generation (not just poly-Gly)
- User needs **state-of-the-art** unconditional protein generation
- User wants **motif scaffolding** with sidechain preservation
- User says "generate full protein" (backbone + sidechains)
- User wants SE(3)-equivariant generation with atomic detail

## Genie 3 Overview

[Genie 3](https://github.com/aqlaboratory/genie3) is a **fast, all-atom SE(3)-equivariant diffusion model** from Columbia University's AlQuraishi Lab (same group as OpenFold3). Unlike RFdiffusion which generates only backbone atoms (N/CA/C/O), Genie 3 generates **complete all-atom structures** including sidechains in a single diffusion process.

### Key Differences from RFdiffusion

| Feature | RFdiffusion | Genie 3 |
|---------|------------|---------|
| Output | Backbone only (N/CA/C/O) | **All atoms (backbone + sidechains)** |
| Method | RoseTTAFold-based | **SE(3)-equivariant transformer** |
| Speed | Medium (iterative denoising) | **Fast (optimized equivariance)** |
| Sidechains | No (requires Stage 2) | **Yes (native)** |
| Motif scaffolding | Yes (backbone) | **Yes (with sidechain preservation)** |
| Binder design | Yes | **Yes (SOTA reported)** |
| Training data | ~20k structures | **Larger, curated set** |

**Key insight**: Genie 3 eliminates the need for a separate Stage 2 (sequence design) in some cases because it generates sidechains natively. However, for optimal sequences, you may still want to run ProteinMPNN or LigandMPNN on the backbone.

## Installation

```bash
# Clone repository
git clone https://github.com/aqlaboratory/genie3.git
cd genie3

# Install dependencies
pip install -e .

# Requirements: PyTorch 2.0+, CUDA-capable GPU
```

## Usage

### Basic Unconditional Generation

```python
import torch
from genie3 import Genie3Model

# Load model
model = Genie3Model.from_pretrained("genie3-base")
model = model.cuda()

# Generate all-atom protein
result = model.sample(
    length=150,
    num_steps=50,
    temperature=1.0,
)

# Save complete structure (backbone + sidechains)
result.save_pdb("genie3_design.pdb")
```

### Motif Scaffolding with Sidechains

```python
# Scaffold around existing motif preserving sidechains
from genie3 import MotifScaffolder

scaffolder = MotifScaffolder(model)
motif = load_structure("motif.pdb")  # Must include sidechains

scaffold = scaffolder.sample(
    motif=motif,
    total_length=200,
    num_steps=50,
    preserve_sidechains=True,  # Keep motif sidechains intact
)

scaffold.save_pdb("scaffold_with_sidechains.pdb")
```

### Binder Design

```python
# Design a binder to a target protein
from genie3 import BinderDesigner

designer = BinderDesigner(model)
target = load_structure("target.pdb")

binder = designer.sample(
    target=target,
    binder_length=100,
    hotspot_residues=["A30", "A33", "A34"],
    num_steps=50,
)

binder.save_pdb("binder_all_atom.pdb")
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `length` | int | — | Protein length (residues) |
| `num_steps` | int | 50 | Diffusion denoising steps |
| `temperature` | float | 1.0 | Sampling temperature |
| `preserve_sidechains` | bool | False | Keep motif sidechains |
| `binder_length` | int | — | Length of binder to design |
| `hotspot_residues` | list | None | Target residues for binding |

## Pipeline Integration

### Option 1: Genie 3-Only Pipeline (Fastest)
```
Stage 0: PDBFixer (if needed)
    ↓
Stage 1: Genie 3 (all-atom generation)
    ↓
Stage 2: Optional — ProteinMPNN (refine sequence)
    ↓
Stage 3: AlphaFold3 / Boltz (validate)
    ↓
Stage 4: Filtering
```

**Why this works:**
- Genie 3 outputs complete structures with sidechains
- May skip Stage 2 entirely for some applications
- Faster than RFdiffusion + ProteinMPNN combined

### Option 2: Genie 3 + Sequence Refinement
```
Stage 1: Genie 3 (generate all-atom structure)
    ↓
Stage 2: ProteinMPNN (redesign sequence on Genie 3 backbone)
    ↓
Stage 3: AlphaFold3 (validate)
    ↓
Stage 4: Filtering
```

**Why this works:**
- Genie 3 provides excellent initial sidechain packing
- ProteinMPNN optimizes sequence for the backbone
- Best of both approaches

### Option 3: Hybrid (Genie 3 for Binder, RFdiffusion for Scaffold)
```
Stage 1a: Genie 3 (design binder with all-atom detail)
    ↓
Stage 1b: RFdiffusion (design scaffold separately)
    ↓
Stage 2: ProteinMPNN (sequence design)
    ↓
Stage 3: AlphaFold3 (validate complex)
    ↓
Stage 4: Filtering
```

**Why this works:**
- Genie 3 excels at binder design with sidechain detail
- RFdiffusion provides diverse scaffolds
- Combine strengths of both tools

## Comparison with Other Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| All-atom generation | **Genie 3** | Native sidechain output |
| Maximum length (>500aa) | RFdiffusion | Longer sequences |
| Fastest generation | **Genie 3** | Optimized equivariance |
| Battle-tested reliability | RFdiffusion | More field data |
| Binder design | **Genie 3** | SOTA reported performance |
| Motif scaffolding | Tie | Both excellent |
| Joint seq+structure | MultiFlow / La-Proteina | Designed for co-design |
| Open-source + training | OpenFold3 / Protenix | Training support |

## When to Use Genie 3 vs RFdiffusionAA

| Feature | RFdiffusionAA | Genie 3 |
|---------|--------------|---------|
| All-atom output | Yes | Yes |
| Ligand-aware | **Yes** | No |
| SE(3) equivariant | Partial | **Full** |
| Speed | Slow | **Fast** |
| Requires Apptainer | **Yes** | No |
| Sidechain quality | Good | **Better** |

**Choose RFdiffusionAA** when: ligands/cofactors are involved
**Choose Genie 3** when: speed and sidechain quality matter, no ligands

## Tips

- **Sidechain quality**: Genie 3 sidechains are often good enough for initial designs
- **Sequence refinement**: Still recommended to run ProteinMPNN for sequence optimization
- **Speed**: ~2-3× faster than RFdiffusion for same length
- **Steps**: 50 steps typically sufficient
- **Temperature**: Lower (0.8) for more realistic sidechain conformations
- **Motif scaffolding**: Use `preserve_sidechains=True` to keep functional residues
- **Binder design**: Reported SOTA on benchmark sets

## References

- [Genie 3 GitHub](https://github.com/aqlaboratory/genie3)
- [AlQuraishi Lab](https://www.aqlaboratory.com/)
- [OpenFold Consortium](https://omsf.io/programs/projects/openfold/)

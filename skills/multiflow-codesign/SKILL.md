---
name: multiflow-codesign
description: Joint sequence-structure co-design with MultiFlow — discrete + continuous flow matching for simultaneous protein sequence and backbone generation
---

# Alternative Stage 1+2: MultiFlow Joint Co-Design

## When to Trigger

- User says "MultiFlow", "joint design", "co-design", "sequence and structure together"
- User wants to generate **both sequence and backbone simultaneously**
- User needs **multimodal protein generation** (sequence + structure)
- User says "generate sequence and structure at the same time"
- User wants a **unified generative model** (not separate Stage 1 + Stage 2)
- User is interested in **flow matching** for joint generation

## MultiFlow Overview

[MultiFlow](https://github.com/jasonkyuyim/multiflow) is a **multimodal flow matching model** for **joint protein sequence and backbone co-design**. Unlike the standard pipeline that separates backbone generation (Stage 1) and sequence design (Stage 2), MultiFlow generates both simultaneously using discrete flow matching for sequences and continuous flow matching for structures.

### Key Differences from Standard Pipeline

| Feature | Standard Pipeline (RFdiffusion + ProteinMPNN) | MultiFlow |
|---------|-----------------------------------------------|-----------|
| Approach | Sequential (structure → sequence) | **Joint (simultaneous)** |
| Method | Diffusion + GNN | **Flow matching (unified)** |
| Parameters | ~50M + ~48M | **21.8M (single model)** |
| Coordination | Separate models | **End-to-end co-design** |
| Speed | Slower (two stages) | **Faster (one stage)** |
| Length | ~500 residues | **60-384 residues** |

**Key insight**: MultiFlow is the **best choice** when you want a single model that jointly optimizes sequence and structure, ensuring better compatibility between the two.

## Installation

```bash
# Clone repository
git clone https://github.com/jasonkyuyim/multiflow.git
cd multiflow

# Install dependencies
pip install -e .

# Requires PyTorch, PyTorch Geometric, e3nn
```

## Usage

### Basic Joint Generation

```python
import torch
from multiflow import MultiFlowModel

# Load model
model = MultiFlowModel.from_pretrained("multiflow-base")
model = model.cuda()

# Generate protein (sequence + backbone together)
result = model.sample(
    length=150,
    num_steps=50,
    temperature=1.0,
)

# Access outputs
sequence = result.sequence  # Amino acid sequence
backbone = result.backbone  # N/CA/C/O coordinates

# Save
result.save_pdb("multiflow_design.pdb")
result.save_fasta("multiflow_design.fasta")
```

### Conditional Generation (Motif Scaffolding)

```python
# Scaffold around existing motif
motif_sequence = "MKTLLIL..."
motif_structure = load_structure("motif.pdb")

result = model.sample(
    motif_sequence=motif_sequence,
    motif_structure=motif_structure,
    total_length=200,
    num_steps=50,
)
```

### Sequence-Only or Structure-Only

```python
# Generate sequence given structure
result = model.sample_sequence(
    structure=backbone_input,
    num_steps=50,
)

# Generate structure given sequence
result = model.sample_structure(
    sequence=sequence_input,
    num_steps=50,
)
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `length` | int | — | Protein length (60-384) |
| `num_steps` | int | 50 | Flow integration steps |
| `temperature` | float | 1.0 | Sampling temperature |
| `motif_sequence` | string | None | Fixed motif sequence |
| `motif_structure` | tensor | None | Fixed motif structure |

## Pipeline Integration

### Option 1: MultiFlow-Only Pipeline (Fastest)
```
Stage 0: PDBFixer (if needed)
    ↓
Stage 1+2: MultiFlow (joint sequence + backbone)
    ↓
Stage 3: AlphaFold3/OmegaFold (validation)
    ↓
Stage 4: Filtering
```

**Why this works:**
- Single model replaces Stage 1 + Stage 2
- Faster end-to-end generation
- Better sequence-structure compatibility

### Option 2: MultiFlow + Refinement
```
Stage 1+2: MultiFlow (joint generation)
    ↓
Stage 2b: ProteinMPNN (refine sequence on MultiFlow backbone)
    ↓
Stage 3: AlphaFold3 (validation)
    ↓
Stage 4: Filtering
```

**Why this works:**
- MultiFlow for initial co-design
- ProteinMPNN for sequence refinement
- Best of both approaches

### Option 3: Hybrid Pipeline
```
Stage 1: RFdiffusion (generate diverse backbones)
    ↓
Stage 2a: MultiFlow (generate sequences on RFdiffusion backbones)
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
| Joint co-design | **MultiFlow** | Native multimodal generation |
| Maximum length (>384aa) | RFdiffusion | Longer sequences |
| Battle-tested reliability | RFdiffusion + ProteinMPNN | More field data |
| Fast prototyping | **MultiFlow** | Single model, fewer steps |
| All-atom generation | Chroma | Includes side chains |
| Sequence-only design | EvoDiff | Specialized for sequences |
| Flow matching preference | **MultiFlow** or FoldFlow | Unified framework |

## Tips

- **Length limit**: 60-384 residues (use RFdiffusion for longer)
- **Steps**: 50 steps typically sufficient (vs 200+ for diffusion)
- **Temperature**: Lower (0.8) for more realistic designs
- **Motif scaffolding**: Provide both sequence and structure for best results
- **Single model**: Only 21.8M parameters — very efficient
- **Fresh codebase**: May have bugs; check GitHub issues

## References

- [MultiFlow GitHub](https://github.com/jasonkyuyim/multiflow)
- [MultiFlow Paper (ICML 2024)](https://arxiv.org/abs/2402.04997)
- [FrameFlow (base architecture)](https://github.com/microsoft/protein-frame-flow)
- [FoldFlow (related)](https://github.com/DreamFold/FoldFlow)

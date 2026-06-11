---
name: evodiff-sequence
description: Sequence-space protein generation with EvoDiff — Microsoft's discrete diffusion model for generating novel protein sequences and evolutionary alignments
---

# Alternative: EvoDiff Sequence Generation

## When to Trigger

- User says "EvoDiff", "Microsoft evodiff", "sequence generation"
- User wants to generate protein sequences **without structural templates**
- User needs to design **intrinsically disordered regions (IDRs)**
- User wants evolution-guided protein generation
- User says "generate sequences", "sequence-only design", "no structure needed"
- User wants to scaffold functional motifs in sequence space

## EvoDiff Overview

[EvoDiff](https://github.com/microsoft/evodiff) is a **general-purpose discrete diffusion framework** from **Microsoft Research** for controllable protein generation in **sequence space**. Unlike structure-based models (RFdiffusion, Chroma), EvoDiff generates proteins directly from sequence, enabling designs inaccessible to structure-based methods.

### Key Differences from Structure-Based Design

| Feature | RFdiffusion/Chroma | EvoDiff |
|---------|-------------------|---------|
| Design space | Structure-guided | **Sequence-only** |
| IDR design | Not supported | **Supported** |
| Structure required | Yes | **No** |
| Motif scaffolding | Structure-based | **Sequence-based** |
| Speed | Slow (diffusion) | **Moderate** |
| Training data | ~20k structures | **~42M sequences (UniRef50)** |
| License | Various | **MIT** |

**Key insight**: EvoDiff is unique in generating sequences for **intrinsically disordered proteins** and designing **without any structural input**. It's complementary to structure-based methods.

## Installation

```bash
# From PyPI
pip install evodiff

# From source
git clone https://github.com/microsoft/evodiff.git
cd evodiff
pip install -e .
```

## Models

| Model | Parameters | Description |
|-------|-----------|-------------|
| `OA_DM_640M` | 640M | Order-agnostic autoregressive diffusion (main) |
| `OA_DM_38M` | 38M | Smaller OADM variant |
| `D3PM_BLOSUM_640M` | 640M | Discrete denoising with BLOSUM matrix |
| `D3PM_UNIFORM_640M` | 640M | D3PM with uniform transitions |
| `MSA_*` | Various | MSA-based evolutionary models |

## Usage

### Basic Sequence Generation

```python
from evodiff.pretrained import OA_DM_640M
from evodiff.generate import generate_sequence

# Load model
model, collater, tokenizer, scheme = OA_DM_640M()
model = model.cuda()

# Generate unconditional sequence
sequence = generate_sequence(model, tokenizer, length=150)
print(f"Generated: {sequence}")

# Generate with temperature
temperature = 1.0  # Higher = more diverse
sequence = generate_sequence(model, tokenizer, length=150, temperature=temperature)
```

### Motif Scaffolding (Sequence Space)

```python
from evodiff.generate import generate_motif_scaffold

# Scaffold around a functional motif
motif = "MKTLLIL"  # Known functional sequence
scaffold = generate_motif_scaffold(
    model, tokenizer,
    motif=motif,
    total_length=150,
    motif_positions=[50, 57],  # Place motif at positions 50-57
)
```

### Evolution-Guided Generation (MSA)

```python
from evodiff.pretrained import MSA_OA_DM_640M

# Load MSA model
model, collater, tokenizer, scheme = MSA_OA_DM_640M()

# Generate new family member from MSA
new_sequence = generate_from_msa(
    model, tokenizer,
    msa_file="family_msa.a3m",
    query_sequence="MKTLLIL...",
)
```

### Inpainting

```python
from evodiff.generate import inpaint_sequence

# Redesign a specific region
sequence = "MKTLLILTGLVAGESKTVLQYF..."
masked_positions = list(range(50, 70))  # Redesign positions 50-70

new_sequence = inpaint_sequence(
    model, tokenizer,
    sequence=sequence,
    mask_positions=masked_positions,
)
```

## Pipeline Integration

### Option 1: EvoDiff + Structure Prediction
```
EvoDiff (generate sequences) → ESMFold/OmegaFold (predict structure)
                                    ↓
                            Validate with AlphaFold3/Boltz/Chai-1 (top hits)
                                    ↓
                            Filtering
```

### Option 2: EvoDiff for IDR Design
```
EvoDiff (generate IDR-containing sequences)
    ↓
ESMFold (fast validation — IDRs will have low pLDDT, which is expected)
    ↓
Experimental validation
```

### Option 3: Hybrid Pipeline
```
Stage 1: RFdiffusion (generate backbone for structured regions)
    ↓
Stage 1b: EvoDiff (generate IDR sequences)
    ↓
Stage 2: ProteinMPNN (design structured region sequences)
    ↓
Stage 3: AlphaFold3/Boltz (validate full protein)
```

## Comparison with Other Methods

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| Structured protein design | RFdiffusion/Chroma | Structure-guided is more reliable |
| IDR design | **EvoDiff** | Only tool supporting IDRs |
| No structural template | **EvoDiff** | Sequence-only generation |
| Evolution-guided design | **EvoDiff-MSA** | MSA conditioning |
| Motif scaffolding | RFdiffusion or EvoDiff | Both work; structure vs sequence |
| Fast screening | EvoDiff + ESMFold | Quick sequence→structure pipeline |
| Maximum accuracy | RFdiffusion + ProteinMPNN | More proven for structured proteins |

## Tips

- **IDRs**: Use EvoDiff when designing proteins with intrinsically disordered regions
- **Sequence-only**: When no structural template exists, EvoDiff is the best choice
- **Temperature**: Use temperature=1.0 for diversity, lower for more natural sequences
- **MSA models**: EvoDiff-MSA models are great for generating new members of known protein families
- **Validation**: Always validate EvoDiff sequences with structure prediction (ESMFold/OmegaFold)
- **Hybrid**: Combine EvoDiff (for IDRs) with RFdiffusion (for structured domains)

## References

- [EvoDiff GitHub](https://github.com/microsoft/evodiff)
- [EvoDiff Paper](https://doi.org/10.1101/2023.09.11.556673)
- [Microsoft Research Blog](https://www.microsoft.com/en-us/research/)

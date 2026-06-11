---
name: bcdesign-inverse
description: Biochemistry-aware inverse protein folding with BC-Design — incorporate amino acid properties and evolutionary constraints for more biologically plausible sequences
---

# Alternative: BC-Design Biochemistry-Aware Inverse Folding

## When to Trigger

- User says "BC-Design", "biochemistry-aware", "inverse folding"
- User wants **biologically plausible sequences** with biochemical constraints
- User needs to incorporate **amino acid properties** into sequence design
- User says "chemistry-aware design", "biophysical constraints"
- User wants sequences optimized for **stability and solubility**

## BC-Design Overview

[BC-Design](https://github.com/gersteinlab/BC-Design) from Gerstein Lab is a **biochemistry-aware framework for high-precision inverse protein folding**. Unlike ProteinMPNN which treats all amino acids as abstract tokens, BC-Design incorporates **biochemical knowledge** (amino acid properties, evolutionary constraints, physical-chemical features) to design more biologically plausible sequences.

### Key Differences from ProteinMPNN

| Feature | ProteinMPNN | BC-Design |
|---------|------------|-----------|
| Features | Structure only | **Structure + biochemistry** |
| Amino acid encoding | One-hot | **Property vectors** |
| Constraints | Geometric | **Biophysical + evolutionary** |
| Output | Generic sequences | **Biologically plausible** |

**Key insight**: BC-Design is the **best choice** when you need sequences that not only fit the backbone but also have desirable biochemical properties (charge, hydrophobicity, stability).

## Installation

```bash
# Clone repository
git clone https://github.com/gersteinlab/BC-Design.git
cd BC-Design

# Install dependencies
pip install -e .

# Requires PyTorch, PyTorch Geometric
```

## Usage

### Basic Biochemistry-Aware Design

```python
import torch
from bcdesign import BCDesignModel

# Load model
model = BCDesignModel.from_pretrained("bcdesign-base")
model = model.cuda()

# Design sequence with biochemical awareness
structure = load_structure("backbone.pdb")

sequence = model.design_sequence(
    structure=structure,
    num_candidates=10,
    temperature=1.0,
    # Biochemical constraints
    constraints={
        "hydrophobicity": "balanced",  # or "surface", "core"
        "charge": "neutral",           # or "positive", "negative"
        "size": "medium",              # or "small", "large"
    },
)

print(sequence)
```

### Stability-Optimized Design

```python
# Design for maximum thermodynamic stability
sequence = model.design_sequence(
    structure=structure,
    constraints={
        "hydrophobicity": "core",
        "charge": "neutral",
        "stability": "maximize",
    },
    num_candidates=50,
)
```

### Solubility-Optimized Design

```python
# Design for high solubility (surface-exposed charged residues)
sequence = model.design_sequence(
    structure=structure,
    constraints={
        "hydrophobicity": "surface",
        "charge": "mixed",
        "solubility": "maximize",
    },
)
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `structure` | Structure | — | Input backbone structure |
| `num_candidates` | int | 10 | Number of sequences to generate |
| `temperature` | float | 1.0 | Sampling temperature |
| `constraints` | dict | None | Biochemical constraints |

## Constraint Options

| Constraint | Options | Effect |
|-----------|---------|--------|
| `hydrophobicity` | `core`, `surface`, `balanced` | Hydrophobic residue placement |
| `charge` | `positive`, `negative`, `neutral`, `mixed` | Overall charge distribution |
| `size` | `small`, `medium`, `large` | Amino acid size preference |
| `stability` | `maximize`, `standard` | Thermodynamic stability |
| `solubility` | `maximize`, `standard` | Aqueous solubility |

## Pipeline Integration

### Option 1: BC-Design Primary Pipeline
```
Stage 1: RFdiffusion (generate backbone)
    ↓
BC-Design (design biochemically-aware sequences)
    ↓
AlphaFold3 (validate structures)
    ↓
Filtering (check pLDDT + biochemical properties)
```

### Option 2: Ensemble with ProteinMPNN
```
Stage 1: RFdiffusion (generate backbone)
    ↓
Stage 2a: ProteinMPNN (design sequences)
    ↓
Stage 2b: BC-Design (design sequences with constraints)
    ↓
Stage 3: AlphaFold3 (validate both sets)
    ↓
Stage 4: Compare and select best by biochemical score
```

### Option 3: Stability Engineering
```
Stage 1: RFdiffusion (generate backbone)
    ↓
BC-Design with stability constraints
    ↓
Molecular dynamics (check stability)
    ↓
AlphaFold3 (validate)
    ↓
Filtering
```

## Comparison with Other Sequence Designers

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| General sequence design | ProteinMPNN | Fast, well-tested |
| Biochemical constraints | **BC-Design** | Property-aware design |
| Stability optimization | **BC-Design** | Stability constraints |
| Solubility optimization | **BC-Design** | Solubility constraints |
| Ligand-aware | LigandMPNN | Ligand context |
| Evolutionary guidance | EvoDiff-MSA | MSA conditioning |

## Tips

- **Constraints**: Start with `balanced` hydrophobicity and adjust based on protein type
- **Core vs surface**: Use `core` for globular proteins, `surface` for membrane proteins
- **Charge**: `neutral` for intracellular, `mixed` for extracellular
- **Validation**: Check predicted structures for proper core packing
- **Ensemble**: Combine BC-Design with ProteinMPNN for diversity

## References

- [BC-Design GitHub](https://github.com/gersteinlab/BC-Design)
- [Gerstein Lab](http://www.gersteinlab.org/)
- [BC-Design Paper](https://www.biorxiv.org/content/10.1101/2024.10.28.620755)

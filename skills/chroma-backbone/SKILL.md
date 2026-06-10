---
name: chroma-backbone
description: Alternative backbone generation with Chroma — joint structure + sequence design
---

# Alternative Stage 1: Chroma Backbone Generation

## When to Trigger

- User says "use Chroma", "Chroma instead of RFdiffusion"
- User wants joint structure + sequence generation in one step
- User needs natural language prompting for protein design
- User wants all-atom generation (not just backbone)
- User requests composable design constraints (shape, SS, symmetry)

## Chroma Overview

[Chroma](https://github.com/generatebio/chroma) is a programmable generative model for protein design from Generate Biomedicines. Unlike RFdiffusion which generates only backbone atoms, Chroma can generate full all-atom structures including side chains.

### Key Differences from RFdiffusion

| Feature | RFdiffusion | Chroma |
|---------|-------------|--------|
| Output | Backbone only (N/CA/C/O) | All atoms (including side chains) |
| Sequence | Requires ProteinMPNN | Joint generation (optional) |
| Design control | Hydra configs | Composable "Conditioners" |
| Prompting | Contig strings | Natural language + code |
| Scaling | Linear | Sub-quadratic |
| License | Open source | Apache 2.0 (code), academic (weights) |

## Installation

```bash
# Clone repository
git clone https://github.com/generatebio/chroma.git
cd chroma

# Install (requires Python >= 3.9)
pip install -e .

# Download weights (requires API key from Generate Biomedicines)
# Academic license available for research use
```

## Design via Conditioners

Chroma uses composable **Conditioners** to specify design constraints:

### Basic Unconditional Design
```python
from chroma import Chroma, Protein, conditioners

chroma = Chroma()

# Generate 150-residue protein
protein = chroma.sample(
    chain_lengths=[150],
    conditioners=[],  # No constraints = unconditional
)

# Save to PDB
protein.to("outputs/chroma_design.pdb")
```

### Symmetry Conditioner
```python
# C3 symmetric trimer, 100 residues per chain
protein = chroma.sample(
    chain_lengths=[100],
    conditioners=[
        conditioners.SymmetryConditioner(
            symmetry="C3",
            num_chains=3,
        )
    ],
)
```

### Substructure (Motif) Conditioner
```python
# Scaffold around existing motif
from chroma import api

# Load motif structure
motif = Protein.from_PDB("motif.pdb", device="cuda")

# Generate scaffold around it
protein = chroma.sample(
    chain_lengths=[200],
    conditioners=[
        conditioners.SubstructureConditioner(
            protein=motif,
            backbone RMSD=2.0,  # Allow 2Å deviation
        )
    ],
)
```

### Secondary Structure Conditioner
```python
# Specify SS for each residue: H=helix, E=strand, L=loop
ss_string = "HHHHHHHHHLLLEEEEEEELLLHHHHHHHHH"

protein = chroma.sample(
    chain_lengths=[len(ss_string)],
    conditioners=[
        conditioners.SecondaryStructureConditioner(
            ss=ss_string,
        )
    ],
)
```

### Shape Conditioner
```python
# Design protein matching a target shape (e.g., sphere, ellipsoid)
protein = chroma.sample(
    chain_lengths=[200],
    conditioners=[
        conditioners.ShapeConditioner(
            shape="sphere",
            radius=15.0,
        )
    ],
)
```

### Sequence Constraint Conditioner
```python
# Fix certain residues, design the rest
sequence_constraint = "MKTXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # X = design

protein = chroma.sample(
    chain_lengths=[len(sequence_constraint)],
    conditioners=[
        conditioners.SequenceConditioner(
            sequence=sequence_constraint,
        )
    ],
)
```

### Natural Language Prompting
```python
# Design based on text description (experimental)
protein = chroma.sample(
    chain_lengths=[200],
    conditioners=[
        conditioners.TextConditioner(
            prompt="a compact alpha-helical bundle",
        )
    ],
)
```

## Pipeline Integration

Since Chroma generates all-atom structures with sequences, it can replace **both** Stage 1 and Stage 2:

### Chroma-Only Pipeline (2 stages)
```
Stage 1: Chroma → All-atom structure + sequence
Stage 3: AlphaFold3 → Validation
Stage 4: Filtering → Rank results
```

### Chroma + ProteinMPNN Pipeline (3 stages)
```
Stage 1: Chroma → Backbone + initial sequence
Stage 2: ProteinMPNN → Redesign sequence on Chroma backbone
Stage 3: AlphaFold3 → Validation
Stage 4: Filtering → Rank results
```

## Comparison with RFdiffusion

| Design Goal | RFdiffusion | Chroma |
|-------------|-------------|--------|
| Unconditional monomer | ✓ Good | ✓ Good |
| Motif scaffolding | ✓ Excellent | ✓ Good |
| Binder design | ✓ Good | ⚠️ Limited |
| Symmetric oligomers | ✓ Good | ✓ Excellent |
| All-atom generation | ✗ No | ✓ Yes |
| Natural language | ✗ No | ✓ Yes |
| Side chain packing | ✗ No | ✓ Yes |

## Tips

- Chroma is newer and less battle-tested than RFdiffusion
- Weights require API key (academic license available)
- GPU memory requirements may be higher due to all-atom generation
- For production designs, consider validating Chroma outputs with RFdiffusion + ProteinMPNN pipeline
- Chroma's sub-quadratic scaling makes it attractive for very long proteins (>500 residues)

## References

- [Chroma GitHub](https://github.com/generatebio/chroma)
- [Chroma Paper](https://www.nature.com/articles/s41586-024-08393-x)
- Generate Biomedicines

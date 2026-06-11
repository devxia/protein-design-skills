---
name: omegafold-validation
description: Fast structure validation with OmegaFold — lightweight AlphaFold3 alternative, no MSA/database required
---

# Alternative Stage 3: OmegaFold Structure Validation

> **Quick Entry**: Stage 3 alternative | fast | no databases needed
>
> **Upstream**: `sequence-design` (ProteinMPNN/LigandMPNN/ESM-IF1) | **Downstream**: `filtering-ranking`

## When to Trigger

- User wants a **fast** structure prediction without MSA search
- User doesn't have AlphaFold3's 2.6TB databases installed
- User wants a **lightweight** validation step for many designs
- User says "OmegaFold", "fast folding", "no MSA", "lightweight validation"
- User needs structure prediction on CPU or limited GPU
- User wants to validate designs quickly before expensive AlphaFold3 runs

## OmegaFold Overview

[OmegaFold](https://github.com/HeliXonProtein/OmegaFold) is a high-resolution de novo structure prediction model from Helixon that predicts protein 3D structures **directly from amino acid sequences** without requiring Multiple Sequence Alignment (MSA) or large genetic databases. This makes it dramatically faster and lighter than AlphaFold2/3.

### Key Differences from AlphaFold3

| Feature | AlphaFold3 | OmegaFold |
|---------|------------|-----------|
| Input | Sequence + MSA + templates | Sequence only |
| Databases | 2.6TB required | None required |
| MSA search | Required (slow, CPU) | Not needed |
| Speed | Slow (~minutes per sequence) | Fast (~seconds per sequence) |
| GPU memory | High | Moderate (subbatch adjustable) |
| Accuracy | State-of-the-art | Good (slightly below AF3) |
| Complexes | Yes (multimer) | Monomer only |
| Confidence | pLDDT, pTM, ipTM | pLDDT (in B-factors) |
| Setup | Complex | Simple (pip install) |

**Key insight**: OmegaFold trades some accuracy for **massive speed and simplicity**. It's ideal for:
- Quick screening of many designs
- Environments without database access
- CPU-only or low-memory GPU setups
- Pre-filtering before expensive AlphaFold3 validation

## Installation

```bash
# Simple pip install
pip install git+https://github.com/HeliXonProtein/OmegaFold.git

# Or clone and install
pip install omegafold

# Or from source
git clone https://github.com/HeliXonProtein/OmegaFold
cd OmegaFold
python setup.py install
```

**Dependencies**: Only PyTorch + biopython!

## Usage

### Command Line

```bash
# Basic usage
omegafold input.fasta output_directory

# With model 2 (updated version)
omegafold input.fasta output_directory --model 2

# Adjust subbatch size for memory constraints
omegafold input.fasta output_directory --subbatch_size 256

# More cycles for better accuracy
omegafold input.fasta output_directory --num_cycle 10
```

### Python API

```python
import torch
from omegafold import OmegaFold

# Load model
model = OmegaFold(
    model_size=2,  # 1 or 2
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
)

# Load weights (auto-downloaded to ~/.cache/omegafold_ckpt/)
model.load_weights()

# Predict structure from sequence
sequence = "MKTLLILTGLVAGESKTVLQYF...

with torch.no_grad():
    output = model.predict(sequence)
    structure = output['structure']
    plddt = output['plddt']  # Confidence scores

# Save to PDB
model.save_pdb(structure, plddt, "output.pdb")
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input.fasta` | string | — | Input FASTA file with sequences |
| `output_directory` | string | — | Output directory for PDB files |
| `--model` | int | 1 | Model version (1 or 2) |
| `--subbatch_size` | int | sequence_length | Memory/speed trade-off. Lower = less memory, slower |
| `--num_cycle` | int | 1 | Number of recycling cycles (more = better accuracy) |
| `--device` | string | auto | cuda, cpu, or mps (Apple Silicon) |

## Memory Tuning

OmegaFold's `subbatch_size` parameter provides excellent memory control:

| GPU Memory | subbatch_size | Max Sequence Length |
|------------|---------------|-------------------|
| 80 GB A100 | 448 (default) | 4096 residues |
| 24 GB RTX 3090 | 256 | ~2000 residues |
| 12 GB | 128 | ~1000 residues |
| 8 GB | 64 | ~800 residues |
| CPU only | 1 | Unlimited (slow) |

```bash
# For limited GPU memory
omegafold input.fasta output --subbatch_size 64

# For CPU-only
omegafold input.fasta output --subbatch_size 1 --device cpu
```

## Pipeline Integration

### Option 1: OmegaFold as Pre-Screen (Recommended)
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → OmegaFold (fast pre-screen)
                                                        ↓
                                        Select top designs by pLDDT
                                                        ↓
                                        Stage 3 (AlphaFold3) on top N
                                                        ↓
                                        Stage 4 (Filtering)
```

**Why this works:**
- Screen 100+ designs with OmegaFold in minutes
- Select top 10-20 by pLDDT
- Run AlphaFold3 only on the best candidates
- Saves hours of computation and database I/O

### Option 2: OmegaFold-Only Pipeline (Fast Mode)
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → OmegaFold (validation)
                                                        ↓
                                        Stage 4 (Filtering by pLDDT)
```

**When to use:**
- Quick prototyping
- No database access
- Large-scale screening
- CPU-only environment

### Option 3: Comparison Pipeline
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN)
                                ↓
                    ┌──────────┴──────────┐
                    ↓                     ↓
              OmegaFold             AlphaFold3
                    ↓                     ↓
              Compare structures   Compare pLDDT/ipTM
                    └──────────┬──────────┘
                               ↓
                        Agreement analysis
```

## pLDDT Interpretation

OmegaFold outputs pLDDT scores in the B-factor column of PDB files:

| pLDDT Range | Quality | Confidence |
|-------------|---------|------------|
| >90 | Very high | High confidence |
| 70-90 | High | Generally correct backbone |
| 50-70 | Low | Caution required |
| <50 | Very low | Often unstructured |

```python
# Extract pLDDT from OmegaFold output
from Bio import PDB

parser = PDB.PDBParser()
structure = parser.get_structure("design", "omegafold_output.pdb")

plddt_scores = []
for model in structure:
    for chain in model:
        for residue in chain:
            for atom in residue:
                plddt_scores.append(atom.get_bfactor())

mean_plddt = sum(plddt_scores) / len(plddt_scores)
print(f"Mean pLDDT: {mean_plddt:.1f}")
```

## Comparison Summary

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| Production accuracy | AlphaFold3 | State-of-the-art, full MSA |
| Fast screening | OmegaFold | No databases, seconds per seq |
| Large libraries | OmegaFold | Can process 100s quickly |
| Complexes/multimers | AlphaFold3 | OmegaFold is monomer-only |
| No database access | OmegaFold | Self-contained |
| CPU-only | OmegaFold | Works well with subbatch_size=1 |
| Low GPU memory | OmegaFold | Adjustable subbatch_size |
| Apple Silicon | OmegaFold | Native MPS support |
| Final validation | AlphaFold3 | Higher accuracy for top designs |

## Tips

- **Pre-screening strategy**: Run OmegaFold on all designs, keep top 20% by pLDDT, then validate with AlphaFold3
- **Subbatch tuning**: If you hit OOM, halve the subbatch_size until it works
- **Model 2**: Use `--model 2` for the updated version (better accuracy)
- **Recycling**: Increase `--num_cycle` for better accuracy at the cost of speed
- **Monomer limitation**: OmegaFold only predicts single chains. For complexes, use AlphaFold3 or ColabFold
- **B-factors**: pLDDT is stored in B-factors — use this for coloring in PyMOL

## References

- [OmegaFold GitHub](https://github.com/HeliXonProtein/OmegaFold)
- [OmegaFold Paper](https://www.biorxiv.org/content/10.1101/2022.07.21.500999v1)
- [Helixon Protein](https://www.helixon.com/)

---
name: esm-if1-design
description: Alternative sequence design with ESM-IF1 inverse folding model
---

# Alternative Stage 2: ESM-IF1 Sequence Design

> **Quick Entry**: Stage 2 alternative | inverse folding | variant scoring | partial masking
>
> **Upstream**: `structure-generation` (RFdiffusion/FoldFlow/Chroma/Genie 3) | **Downstream**: `structure-validation`

## When to Trigger

- User says "ESM-IF1", "ESM inverse folding", "use ESM for sequence design"
- User wants to score sequence variants on a fixed backbone
- User needs partial backbone design (some coordinates masked)
- User wants a complementary sequence designer to ProteinMPNN
- User requests variant effect prediction conditioned on structure

## ESM-IF1 Overview

[ESM-IF1](https://github.com/facebookresearch/esm) (ESM Inverse Folding 1) is a structure-conditioned sequence design model from Meta AI. It predicts amino acid sequences from backbone coordinates using an Invariant Geometric Vector Perceptron (GVP) encoder + transformer decoder.

### Key Differences from ProteinMPNN

| Feature | ESM-IF1 | ProteinMPNN |
|---------|---------|-------------|
| Architecture | GVP encoder + Transformer decoder | Graph Neural Network |
| Parameters | 142M | ~48M (v_48_020) |
| Recovery rate | 51% overall, 72% buried | ~52-54% overall |
| Partial masking | Native (set coords to `inf`) | Via fixed_positions_jsonl |
| Variant scoring | Yes | Limited |
| Multi-chain | Yes (`--multichain-backbone`) | Yes (JSONL batch) |
| Speed | Moderate | Fast |
| Known issues | Homopolymer repeats (EEEEEE) | Less prone to repeats |

**Key insight:** ESM-IF1 and ProteinMPNN are **complementary**. ESM-IF1 excels at partial backbone design and variant scoring. ProteinMPNN has better field-proven experimental hit rates. Running both and taking the union is a common strategy.

## Installation

```bash
# Simple install (may have CUDA compatibility issues)
pip install fair-esm

# Recommended: dedicated conda environment
conda create -n esm_if1 python=3.9
conda activate esm_if1
conda install pytorch cudatoolkit=11.3 -c pytorch
conda install pyg -c pyg -c conda-forde
pip install biotite
pip install git+https://github.com/facebookresearch/esm.git
```

> **Note:** The ESM repo is archived as of 2026. The `pip install fair-esm` package remains available.

## Sequence Design

### Basic Usage

```bash
python -m esm.inverse_folding.cli \
    --pdbfile input.pdb \
    --chain A \
    --num-samples 8 \
    --temperature 1.0 \
    --outpath outputs/esm_if1_seqs.fa
```

### Python API

```python
import torch
from esm import pretrained
from esm.inverse_folding import util

# Load model
model, alphabet = pretrained.esm_if1_gvp4_t16_142M_UR50()
model = model.eval()
if torch.cuda.is_available():
    model = model.cuda()

# Load structure
structure = util.load_structure("input.pdb", "A")
coords, native_seq = util.extract_coords_from_structure(structure)

# Design sequences
sampled_seqs = util.sample_sequences(
    model,
    coords,
    temperature=1.0,
    num_samples=8,
)

for i, seq in enumerate(sampled_seqs):
    print(f">design_{i}")
    print(seq)
```

### Partial Backbone Design (Masking)

Mask specific residues by setting their coordinates to infinity:

```python
import numpy as np

# coords shape: (L, 3, 3) for N, CA, C atoms
# Mask residues 10-20 (0-indexed)
coords_masked = coords.copy()
coords_masked[10:21] = np.inf

# Design only unmasked regions
sampled_seqs = util.sample_sequences(
    model,
    coords_masked,
    temperature=1.0,
    num_samples=8,
)
```

### Multi-Chain Complex Design

```python
# Design chain A conditioned on chains B and C
sampled_seqs = util.sample_sequences(
    model,
    coords,
    temperature=1.0,
    num_samples=8,
    multichain_backbone=True,  # Condition on all chains
)
```

### Variant Scoring

Score how well a given sequence matches the backbone structure:

```python
# Score a variant
sequence = "MKTLLILTGLVAGES..."
ll, _ = util.score_sequence(model, alphabet, coords, sequence)
print(f"Log-likelihood: {ll:.2f}")

# Score multiple variants
variants = ["MKTLLILTGL...", "MKTLLILAGL...", "MKTLLILCGL..."]
for seq in variants:
    ll, _ = util.score_sequence(model, alphabet, coords, seq)
    print(f"{seq}: {ll:.2f}")
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pdbfile` | string | — | Input PDB or mmCIF file |
| `--chain` | string | — | Chain ID to design |
| `--temperature` | float | 1.0 | Sampling temperature (1e-6 = greedy/max recovery) |
| `--num-samples` | int | 1 | Number of sequences to sample |
| `--multichain-backbone` | flag | False | Condition on all chains in the complex |
| `--outpath` | string | — | Output FASTA file path |

## Pipeline Integration

ESM-IF1 replaces or complements ProteinMPNN in Stage 2:

### Option 1: ESM-IF1 Only
```
Stage 1 (RFdiffusion) → Stage 2 (ESM-IF1) → Stage 3 (AlphaFold3) → Stage 4 (Filtering)
```

### Option 2: Ensemble (Recommended)
```
Stage 1 (RFdiffusion) → Stage 2a (ProteinMPNN) → Stage 2b (ESM-IF1)
                                              ↓
                                    Merge + deduplicate sequences
                                              ↓
                                    Stage 3 (AlphaFold3) → Stage 4 (Filtering)
```

**Why ensemble?**
- ProteinMPNN: better experimental success rates
- ESM-IF1: better at partial masking and variant scoring
- Union of both captures more diverse, high-quality designs

### Option 3: Variant Optimization
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → Score variants with ESM-IF1
                                              ↓
                                    Select top-scoring variants
                                              ↓
                                    Stage 3 (AlphaFold3) → Stage 4 (Filtering)
```

## Tips

- **Temperature**: Use `temperature=1.0` for diversity, `temperature=1e-6` for max recovery
- **Partial masking**: Set coordinates to `np.inf` for residues to redesign
- **Multi-chain**: Use `multichain_backbone=True` for binder-target complexes
- **Variant scoring**: ESM-IF1 log-likelihood correlates with experimental fitness
- **Homopolymer repeats**: If output has stretches like `EEEEEE`, increase temperature or add diversity constraints
- **GPU memory**: 142M parameters need ~2GB GPU memory

## Comparison Summary

| Use Case | Best Tool |
|----------|-----------|
| General sequence design | ProteinMPNN (faster, proven) |
| Partial backbone redesign | ESM-IF1 (native masking) |
| Variant effect scoring | ESM-IF1 (built-in scoring) |
| Multi-chain complexes | Tie (both support) |
| Maximum recovery rate | ProteinMPNN (slightly higher) |
| Buried residue design | ESM-IF1 (72% vs 54%) |
| Experimental success | ProteinMPNN (more field data) |

## References

- [ESM GitHub](https://github.com/facebookresearch/esm)
- [ESM-IF1 Paper](https://www.science.org/doi/10.1126/science.ade2574)
- [ESM Metagenomic Atlas](https://esmatlas.com/)

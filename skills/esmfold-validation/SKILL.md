---
name: esmfold-validation
description: Ultra-fast structure prediction with ESMFold — Meta's MSA-free model, 10-60x faster than AlphaFold2, ideal for large-scale screening
---

# Alternative Stage 3: ESMFold Structure Validation

> **Quick Entry**: Stage 3 alternative | fastest | ultra-fast screening
>
> **Upstream**: `sequence-design` (ProteinMPNN/LigandMPNN/ESM-IF1) | **Downstream**: `filtering-ranking`

## When to Trigger

- User says "ESMFold", "Meta ESM", "ESM-2 folding"
- User needs **ultra-fast** structure prediction (seconds per protein)
- User wants to screen **thousands** of designs quickly
- User needs structure prediction **without any databases**
- User says "fastest structure predictor", "quick folding"
- User has limited GPU memory (8GB+ works)

## ESMFold Overview

[ESMFold](https://github.com/facebookresearch/esm) is a protein structure prediction model from **Meta AI** that predicts 3D structures **directly from a single amino acid sequence** without requiring Multiple Sequence Alignment (MSA). It's **10-60× faster** than AlphaFold2 and requires no database setup.

### Key Differences from AlphaFold3

| Feature | AlphaFold3 | ESMFold |
|---------|------------|---------|
| Input | Sequence + MSA + templates | **Sequence only** |
| MSA required | Yes (2.6TB DBs) | **No** |
| Speed | ~minutes | **~seconds** |
| Speedup vs AF2 | Baseline | **10-60× faster** |
| Accuracy | State-of-the-art | Good (slightly below AF) |
| Complexes | Yes | **Monomer only** |
| GPU memory | High | **~8GB for 650 aa** |
| License | Non-commercial | **MIT** |

**Key insight**: ESMFold is the **fastest option** for structure validation. It's ideal for large-scale screening where you need to evaluate hundreds or thousands of designs quickly.

## Installation

```bash
# Simple install
pip install fair-esm

# Or from source
git clone https://github.com/facebookresearch/esm.git
cd esm
pip install -e .
```

**Dependencies**: PyTorch + biopython

## Usage

### Command Line (via Python script)

```bash
# Save as predict.py and run
python predict.py input.fasta output_dir/
```

```python
# predict.py
import sys
import torch
import esm

# Load model
model = esm.pretrained.esmfold_v1()
model = model.eval().cuda()

# Optional: reduce VRAM for long sequences
model.set_chunk_size(64)

# Read FASTA
from Bio import SeqIO
for record in SeqIO.parse(sys.argv[1], "fasta"):
    sequence = str(record.seq)

    with torch.no_grad():
        output = model.infer_pdb(sequence)

    output_path = f"{sys.argv[2]}/{record.id}.pdb"
    with open(output_path, "w") as f:
        f.write(output)

    print(f"Saved: {output_path}")
```

### Python API

```python
import torch
import esm

# Load model
model = esm.pretrained.esmfold_v1()
model = model.eval().cuda()

# Optional VRAM optimization
model.set_chunk_size(64)

# Predict from sequence
sequence = "MKTLLILTGLVAGESKTVLQYF..."

with torch.no_grad():
    output = model.infer_pdb(sequence)

# Save PDB
with open("output.pdb", "w") as f:
    f.write(output)

# Or get structured output
with torch.no_grad():
    result = model.infer(sequence, return_confidence=True)
    plddt = result["plddt"]  # Per-residue confidence
    ptm = result["ptm"]      # Global confidence

print(f"Mean pLDDT: {plddt.mean():.1f}")
print(f"pTM: {ptm:.3f}")
```

### Using Hugging Face Transformers

```python
from transformers import AutoTokenizer, EsmForProteinFolding

# Load from Hugging Face
tokenizer = AutoTokenizer.from_pretrained("facebook/esmfold_v1")
model = EsmForProteinFolding.from_pretrained("facebook/esmfold_v1")
model = model.cuda()

# Predict
tokenized = tokenizer("MKTLLIL...", return_tensors="pt")
with torch.no_grad():
    output = model(**tokenized)
```

## Memory Optimization

ESMFold provides chunking for long sequences:

```python
# For limited GPU memory
model.set_chunk_size(64)   # Default: sequence length
# Lower = less memory, slower
# Higher = more memory, faster

# Memory vs sequence length
| Chunk Size | Max Length @ 8GB | Max Length @ 24GB |
|------------|------------------|-------------------|
| 64         | ~1000 aa         | ~2000 aa          |
| 128        | ~800 aa          | ~1500 aa          |
| 256        | ~500 aa          | ~1000 aa          |
```

## Pipeline Integration

### Option 1: ESMFold for Ultra-Fast Screening
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → ESMFold (ultra-fast screen)
                                                        ↓
                                        Select top 10% by pLDDT
                                                        ↓
                                        AlphaFold3/Boltz/Chai-1 (accurate validation)
```

**Why this works:**
- Screen 1000 designs with ESMFold in ~30 minutes
- Select top 100 by pLDDT
- Validate top 100 with accurate predictor
- Saves hours vs running all through AlphaFold3

### Option 2: ESMFold-Only Pipeline
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → ESMFold (validation)
                                                        ↓
                                        Stage 4 (Filter by pLDDT > 70)
```

**When to use:**
- Very large libraries (1000+ designs)
- Quick prototyping
- No database access
- Limited GPU memory

### Option 3: Tiered Validation
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN)
                                ↓
                    ┌──────────┼──────────┐
                    ↓          ↓          ↓
                ESMFold   OmegaFold   Skip
                (fast)    (medium)    (slow)
                    ↓          ↓
                Top 20%    Top 20%
                    └────┬────┘
                         ↓
                    AlphaFold3/Boltz/Chai-1
                    (accurate, slow)
```

## Comparison with Other Stage 3 Tools

| Use Case | Best Tool | Speed | Accuracy |
|----------|-----------|-------|----------|
| Ultra-fast screening | **ESMFold** | **~2s/seq** | Good |
| Fast screening (no DB) | OmegaFold | ~10s/seq | Good |
| Commercial use | Boltz-1 / Chai-1 | ~min/seq | High |
| Best accuracy | AlphaFold3 | ~min/seq | **Highest** |
| Complexes | AlphaFold3 / Boltz-1 / Chai-1 | Slow | High |
| Monomer only | ESMFold / OmegaFold | **Fast** | Good |
| Limited GPU (8GB) | **ESMFold** | Fast | Good |

## Confidence Metrics

ESMFold outputs pLDDT in B-factors and provides pTM:

| Metric | Description | Good Threshold |
|--------|-------------|----------------|
| pLDDT | Per-atom confidence (in B-factors) | >70 |
| pTM | Global topology confidence | >0.7 |

```python
# Extract pLDDT from PDB B-factors
from Bio import PDB

parser = PDB.PDBParser()
structure = parser.get_structure("design", "esmfold_output.pdb")

plddts = [atom.get_bfactor() for atom in structure.get_atoms()]
mean_plddt = sum(plddts) / len(plddts)
print(f"Mean pLDDT: {mean_plddt:.1f}")
```

## ESM Atlas: Pre-computed Structures

Meta provides **617 million** pre-computed structures via ESM Atlas:
- Website: [esmatlas.com](https://esmatlas.com)
- Download structures without running ESMFold
- Search by UniProt ID or sequence

```python
# Download pre-computed structure
import requests

uniprot_id = "P69905"
url = f"https://api.esmatlas.com/fetchPredictedStructure/{uniprot_id}"
response = requests.get(url)
with open(f"{uniprot_id}.pdb", "w") as f:
    f.write(response.text)
```

## Tips

- **Speed champion**: ESMFold is the fastest option — use it for first-pass screening
- **Chunk size**: Adjust `set_chunk_size()` based on your GPU memory
- **Monomer only**: ESMFold only predicts single chains — use other tools for complexes
- **Pre-computed**: Check ESM Atlas before computing — may already exist
- **ESM-3 (2024)**: Meta's newer ESM-3 model extends to generative design
- **Batch processing**: Process sequences in batches for efficiency
- **Comparison**: ESMFold is slightly less accurate than AlphaFold2, but 10-60× faster

## References

- [ESM GitHub](https://github.com/facebookresearch/esm)
- [ESM Atlas](https://esmatlas.com)
- [ESMFold Paper](https://www.science.org/doi/10.1126/science.ade2574)
- [Hugging Face Model](https://huggingface.co/facebook/esmfold_v1)
- [ESM-3 (2024)](https://www.evolutionaryscale.ai/blog/esm3-release)

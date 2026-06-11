---
name: ablang-antibody
description: Antibody sequence analysis and completion with AbLang — antibody-specific language model for restoring missing residues and generating embeddings
---

# Antibody Sequence Analysis: AbLang

## When to Trigger

- User says "AbLang", "antibody language model", "complete antibody sequence"
- User has **incomplete antibody sequences** (missing N-terminus residues)
- User wants **antibody-specific embeddings** for downstream tasks
- User needs to predict **residue likelihoods** for antibody sequences
- User says "restore missing residues", "B-cell receptor sequence"
- User wants antibody-specific representations (better than general PLMs like ESM-2)

## AbLang Overview

[AbLang](https://github.com/oxpig/AbLang) is an **antibody-specific language model** from the Oxford Protein Informatics Group (Oxpig). Trained on the Observed Antibody Space (OAS) database, it's optimized for antibody sequences and outperforms general protein language models on antibody tasks.

### Key Differences from General Protein LMs (ESM-2, ProtTrans)

| Feature | ESM-2 | AbLang |
|---------|-------|--------|
| Training data | UniRef (general proteins) | **OAS (antibodies only)** |
| Speed on antibodies | Baseline | **7× faster** |
| Missing residues | Not specialized | **Optimized for restoration** |
| Heavy+light pairing | Single sequence | **Separate/paired models** |
| Germline awareness | Limited | **AbLang-2 addresses bias** |
| Embeddings | General | **Antibody-optimized** |

**Key insight**: AbLang is the **best choice** for antibody sequence analysis tasks — it's faster, more accurate, and handles antibody-specific features (germline bias, missing residues) better than general PLMs.

## Versions

| Version | Repository | Key Features |
|---------|-----------|-------------|
| **AbLang** | `oxpig/AbLang` | Original, heavy/light separate |
| **AbLang-2** | `oxpig/AbLang2` | Paired VH/VL, germline bias correction, TCR support |
| **AbLangRBD1** | `IGlab-VUMC/AbLangRBD1` | Fine-tuned for SARS-CoV-2 RBD binders |

## Installation

```bash
# AbLang v1
pip install ablang

# AbLang-2 (recommended)
pip install ablang2

# From source
git clone https://github.com/oxpig/AbLang2.git
cd AbLang2
pip install -e .
```

**Optional dependency** (for sequence alignment):
```bash
conda install -c bioconda anarci
```

## Usage

### AbLang v1: Heavy or Light Chain

```python
import ablang

# Load heavy chain model
heavy_model = ablang.pretrained("heavy")

# Restore missing residues
sequence = "EVQLVESGGGLVQPGGSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSGITWNSGHIGYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKVSYLSTASSLDYWGQGTLVTVSS"

# Get residue embeddings (768-dim per residue)
rescodings = heavy_model.rescoding([sequence])

# Get sequence embeddings (768-dim per sequence)
seqcodings = heavy_model.seqcoding([sequence])

# Get residue likelihoods
likelihoods = heavy_model.reslikelihood([sequence])

# Complete/repair missing residues
# (AbLang predicts the most likely residue at each position)
```

### AbLang-2: Paired Heavy + Light Chain

```python
import ablang2

# Load paired model (recommended for therapeutic antibodies)
ablang = ablang2.pretrained(model_to_use='ablang2-paired', device='cuda')

# Input: paired VH|VL sequences
vh_seq = "QVQLQESGPGLVKPSQSLSLTCSVTGYSITSGYSWNWIRQFPGNKLEWMGYISYSGSTTYNPSLKSRISITRDTSKNQFSLHLSSVTAADTAVYYCAR..."
vl_seq = "DIQMTQSPSSLSASVGDRVTITCRASQGISSWLAWYQQKPGKAPKLLIYDASSLESGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQFNSYP..."

# Format as paired sequence
paired_seq = f"{vh_seq}|{vl_seq}"
tokenized = ablang.tokenizer([paired_seq], pad=True, w_extra_tkns=False)

# Generate residue embeddings
with torch.no_grad():
    rescoding = ablang.AbRep(tokenized).last_hidden_states

# Generate likelihoods
with torch.no_grad():
    likelihoods = ablang.AbLang(tokenized)

print(f"Residue embeddings shape: {rescoding.shape}")
print(f"Likelihoods shape: {likelihoods.shape}")
```

### Restoring Missing N-Terminal Residues

AbLang's primary use case — >40% of OAS sequences miss the first ~15 amino acids:

```python
import ablang

# Incomplete sequence (missing N-terminus)
incomplete = "XXXXXXXXXXXXXXXXXESGGGLVQPGGSLRLSCAASGFTF..."

# AbLang can predict the most likely residues
model = ablang.pretrained("heavy")
likelihoods = model.reslikelihood([incomplete])

# Replace X with most likely amino acid
import numpy as np
from ablang.data import token_dictionary

predicted_seq = ""
for i, probs in enumerate(likelihoods[0]):
    if incomplete[i] == 'X':
        aa_idx = np.argmax(probs)
        predicted_seq += token_dictionary[aa_idx]
    else:
        predicted_seq += incomplete[i]

print(f"Restored: {predicted_seq}")
```

## Pipeline Integration

### Option 1: Sequence Completion → Structure Prediction
```
Incomplete antibody sequence (B-cell receptor data)
    ↓
AbLang (restore missing N-terminal residues)
    ↓
ABodyBuilder3 or AlphaFold3 (predict structure)
    ↓
IgDiff or RFdiffusion (redesign CDRs if needed)
    ↓
AbMPNN (design sequences on backbone)
    ↓
Validation + Filtering
```

### Option 2: Embedding-Based Analysis
```
Antibody sequences
    ↓
AbLang (generate 768-dim embeddings)
    ↓
Downstream ML task:
  - Affinity prediction
  - Developability scoring
  - Epitope prediction
  - Humanization assessment
```

### Option 3: Paired VH/VL Analysis
```
Paired heavy + light chain sequences
    ↓
AbLang-2 (paired model)
    ↓
Analyze:
  - Complementarity between chains
  - Germline divergence
  - CDR composition
  - Developability metrics
```

## Comparison with Other Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| Antibody sequence completion | **AbLang** | Trained on OAS, handles missing residues |
| General protein embeddings | ESM-2 | More diverse training data |
| Antibody embeddings | **AbLang** | 7× faster, antibody-optimized |
| Heavy+light paired analysis | **AbLang-2** | Native paired sequence support |
| Germline bias correction | **AbLang-2** | Addresses natural germline retention |
| TCR analysis | **AbLang-2** | TCRLang-Paired variant available |
| SARS-CoV-2 RBD binders | **AbLangRBD1** | Fine-tuned for specific epitope |
| Structure prediction | ESMFold/OmegaFold | Structure-focused |

## Tips

- **Missing residues**: AbLang excels at restoring missing N-terminal residues (>40% of OAS sequences)
- **Paired model**: Use AbLang-2 for therapeutic antibodies (VH+VL together)
- **Germline bias**: AbLang-2 corrects for natural germline retention — critical for therapeutic design
- **Speed**: 7× faster than ESM-1b on antibody sequences
- **Embeddings**: 768-dim embeddings work well for downstream ML tasks
- **ANARCI**: Install for automatic antibody numbering and alignment
- **BCR sequencing**: Essential tool for processing B-cell receptor sequencing data

## References

- [AbLang GitHub](https://github.com/oxpig/AbLang)
- [AbLang-2 GitHub](https://github.com/oxpig/AbLang2)
- [AbLang Paper](https://www.biorxiv.org/content/10.1101/2022.01.20.477061v1)
- [AbLang-2 Paper](https://www.biorxiv.org/content/10.1101/2024.XX.XX.XXXXXXv1)
- [OAS Database](https://opig.stats.ox.ac.uk/webapps/oas/)
- [Oxford Protein Informatics Group](https://www.stats.ox.ac.uk/research/protein-informatics/)

---
name: fast-screening
description: Fast protein design screening pipeline using lightweight tools (no MSA, single-sequence prediction)
---

# Fast Screening Pipeline

## When to Trigger

- User says "quick screen", "fast validation", "rapid screening"
- User wants to validate many designs quickly
- User says "no MSA", "skip MSA", "fast inference"
- User wants lightweight validation without full databases
- User says "ESMFold", "single-sequence prediction"

## Overview

The standard pipeline (RFdiffusion → ProteinMPNN → AlphaFold3) is accurate but slow, especially AlphaFold3 which requires ~2.6TB of genetic databases for MSA search.

The **fast screening pipeline** uses lightweight alternatives that skip MSA entirely, trading some accuracy for dramatically faster runtime:

```
Standard:  RFdiffusion → ProteinMPNN → AlphaFold3 (with MSA) → Filtering
Fast:      RFdiffusion → ProteinMPNN → ESMFold (no MSA)      → Filtering
```

| Metric | Standard Pipeline | Fast Pipeline |
|--------|------------------|---------------|
| Stage 3 tool | AlphaFold3 | ESMFold |
| MSA required | Yes (~2.6TB DBs) | No |
| Runtime per design | 5-90 min | 5-30 seconds |
| Accuracy | High | Moderate (good for screening) |
| Best for | Final validation | Initial screening |

## Stage 3 Alternative 1: ESMFold (Recommended for Speed)

[ESMFold](https://github.com/facebookresearch/esm) predicts protein structures from a single amino acid sequence using the ESM-2 language model embeddings.

### ESMFold Key Features
- **No MSA required** — predicts from single sequence
- **Very fast** — seconds per protein (vs minutes/hours for AF3)
- **Moderate accuracy** — excellent for known-like structures, lower for novel folds
- **Outputs PDB** with per-residue confidence (pLDDT-like)

### ESMFold Installation
```bash
# Install ESM and ESMFold
pip install fair-esm
pip install git+https://github.com/facebookresearch/esm.git
```

### ESMFold Usage
```python
import torch
from esm import pretrained

# Load model
model, alphabet = pretrained.esm_fold_v1()
model = model.eval().cuda()

# Predict structure
sequence = "MKTLLILTGLVAGES..."
with torch.no_grad():
    output = model.infer_pdb(sequence)

with open("output.pdb", "w") as f:
    f.write(output)
```

### ESMFold Pipeline Integration

1. **Generate backbones** (RFdiffusion) — same as standard
2. **Design sequences** (ProteinMPNN) — same as standard
3. **Validate with ESMFold** — batch predict all sequences
4. **Filter by pLDDT** — threshold >70 for screening, >80 for good

```python
# Batch screening with ESMFold
from esm import pretrained
import glob

model, alphabet = pretrained.esm_fold_v1()
model = model.eval().cuda()

for fasta_file in glob.glob("outputs/seqs/*.fa"):
    # Extract sequence from FASTA
    sequence = extract_sequence(fasta_file)
    
    with torch.no_grad():
        pdb_output = model.infer_pdb(sequence)
    
    # Save and score
    output_pdb = fasta_file.replace(".fa", "_esm.pdb")
    with open(output_pdb, "w") as f:
        f.write(pdb_output)
    
    # Extract pLDDT from B-factors
    plddt = extract_plddt_from_pdb(output_pdb)
    print(f"{fasta_file}: pLDDT = {plddt:.1f}")
```

## Stage 3 Alternative 2: ColabFold (Faster MSA)

[ColabFold](https://github.com/sokrypton/ColabFold) replaces AlphaFold2/3's slow jackhmmer/HHblits with fast MMseqs2 for MSA generation.

### ColabFold Key Features
- **Faster MSA** — MMseqs2 vs jackhmmer/HHblits
- **Smaller database footprint** — ~100GB vs ~2.6TB
- **Supports AlphaFold2, AlphaFold2-Multimer, RoseTTAFold**
- **Batch processing**

### ColabFold Installation
```bash
# Install localcolabfold
pip install "colabfold[alphafold] @ git+https://github.com/sokrypton/ColabFold.git"
```

### ColabFold Usage
```bash
# Predict from FASTA (native ColabFold CLI)
colabfold_batch input.fasta output_dir/ \
    --num-models 3 \
    --num-recycle 3 \
    --model-type alphafold2
```

### ColabFold Pipeline Integration

Same as standard pipeline, but use ColabFold instead of AlphaFold3:

```bash
python scripts/run_colabfold.py \
  --input inputs/designs.fa \
  --output-dir outputs/colabfold \
  --num-models 3 \
  --recycle 3
```

## Stage 3 Alternative 3: AlphaFold3 No-MSA Mode

If you have AlphaFold3 installed but not the full databases, you can skip the MSA data pipeline:

```bash
python scripts/run_alphafold3.py \
  --json inputs/design.json \
  --output-dir outputs/af3 \
  --no-msa \
  --num-seeds 1 \
  --num-samples 5
```

**Pros:** Still uses AlphaFold3's powerful structure prediction model
**Cons:** Less accurate without MSA context; best for proteins similar to training data

## Stage 3 Alternative 4: Boltz-2 (Structure + Affinity)

[Boltz-2](https://github.com/jwohlwend/boltz) predicts protein structures and ligand binding affinity.

### Boltz-2 Key Features
- Structure prediction (like AlphaFold)
- **Binding affinity prediction** — unique among tools
- Supports ligands, nucleic acids, modifications
- Fast inference

### Boltz-2 Usage
```bash
boltz predict input.yaml --out_dir outputs/
```

## Recommended Fast Screening Workflow

For screening 100+ designs quickly:

```
1. Generate backbones (RFdiffusion) — 50 designs
        ↓
2. Design sequences (ProteinMPNN) — 8 per backbone = 400 sequences
        ↓
3. Batch ESMFold screening — 400 sequences in ~30 min
        ↓
4. Filter: pLDDT > 75 → ~100 candidates
        ↓
5. Validate top 20 with AlphaFold3 (full MSA) — most accurate
        ↓
6. Final filtering: pLDDT > 80, ipTM > 0.8
```

This **two-stage validation** approach is much faster than validating all 400 with AlphaFold3:
- Total time: ~2 hours vs ~20+ hours
- Still captures the best designs for final validation

## Quality Thresholds for Fast Screening

| Tool | Acceptable | Good | Excellent |
|------|-----------|------|-----------|
| ESMFold pLDDT | >65 | >75 | >85 |
| ColabFold pLDDT | >70 | >80 | >90 |
| AF3 no-MSA pLDDT | >65 | >75 | >85 |

Note: Thresholds are lower than full AlphaFold3 because these tools are less accurate. Use them for **ranking and screening**, not final quality assessment.

## Tips

- ESMFold is fastest but least accurate for novel folds
- ColabFold offers the best speed/accuracy tradeoff for local deployment
- AlphaFold3 no-MSA is best if you already have AF3 installed
- Always validate top candidates with full AlphaFold3 (with MSA) before final selection
- For binders, ESMFold cannot predict ipTM (no multimer support) — use interface residue pLDDT as proxy
- Boltz-2 is excellent for ligand-binding designs due to affinity prediction

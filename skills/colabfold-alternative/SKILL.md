---
name: colabfold-alternative
description: Fast structure prediction with ColabFold as an AlphaFold3 alternative for screening
---

# Alternative Stage 3: ColabFold Fast Prediction

## When to Trigger

- User says "ColabFold", "fast prediction", "quick screen", "MMseqs2"
- User wants high-throughput screening of many designs
- User needs faster structure prediction than AlphaFold3
- User says "no MSA", "skip MSA search", "fast MSA"
- User wants batch processing for structure prediction

## ColabFold Overview

[ColabFold](https://github.com/sokrypton/ColabFold) wraps AlphaFold2 with **MMseqs2** for ultra-fast MSA generation. It simplifies setup and dramatically speeds up structure prediction for high-throughput screening.

### Why ColabFold is Faster

| Step | AlphaFold2/3 | ColabFold |
|------|-------------|-----------|
| MSA search | JackHMMER/HHBlits (~30-60 min) | MMseqs2 (~1-2 min) |
| Setup | Complex (~2TB databases) | Simple (~100GB or use server) |
| Batch processing | Manual | Native `colabfold_batch` |

**MMseqs2** uses optimized k-mer prefiltering instead of full profile HMM searches, achieving **100x faster than BLAST** at similar sensitivity.

### Key Differences from AlphaFold3

| Feature | ColabFold (AF2) | AlphaFold3 |
|---------|-----------------|------------|
| Speed | Fast (~2-5 min) | Slow (~30-90 min) |
| MSA | MMseqs2 (fast) | JackHMMER/HHBlits (slow) |
| Setup | Simple | Complex |
| Biomolecules | Proteins only | Proteins, RNA, DNA, ligands |
| Confidence | pLDDT, pTM, PAE | pLDDT, ipTM, pTM, PAE |
| Interface scoring | No ipTM | Has ipTM |
| Batch processing | Native | Limited |
| Calibration | Better correlation with quality | Less calibrated |

**Critical limitation:** ColabFold (AF2-based) does **not output ipTM**, which is essential for binder design filtering.

## Installation

```bash
# Conda install (recommended)
conda create -n colabfold -c conda-forge -c bioconda \
    python=3.13 kalign2=2.04 hhsuite=3.3.0 mmseqs2=18.8cc5c
conda activate colabfold
pip install colabfold[alphafold,openmm] jax[cuda] openmm[cuda12]
```

Or use Docker:
```bash
docker pull ghcr.io/sokrypton/colabfold:1.6.1-cuda12
```

## Usage

### Basic Batch Prediction

```bash
# Single command for batch
ccolabfold_batch input_sequences.fasta output_dir
```

### Split MSA and Prediction

```bash
# Step 1: Generate MSAs only (can be done offline)
ccolabfold_batch input.fasta out_dir --msa-only

# Step 2: Run prediction using cached MSAs
ccolabfold_batch out_dir/msas predictions
```

### Local Database Search (No Server)

```bash
# Requires ~940GB databases
ccolabfold_search --mmseqs /path/to/mmseqs input.fasta /path/to/db_folder msas
ccolabfold_batch msas predictions
```

## Output Files

| File | Description |
|------|-------------|
| `*.pdb` | Predicted structures (pLDDT in B-factor) |
| `*.json` | PAE matrices, pLDDT arrays, pTM scores |
| `*.png` | Visualization plots |
| `*.a3m` | MSA alignments |

## Pipeline Integration

### Hybrid Approach (Recommended)

Use ColabFold for initial screening, AlphaFold3 for final validation:

```
Stage 1: RFdiffusion → Generate backbones
    ↓
Stage 2: ProteinMPNN → Design sequences
    ↓
Stage 3a: ColabFold → Fast screen all designs (~2 min each)
    ↓
Filter: pLDDT > 75, pTM > 0.6 → ~50 candidates
    ↓
Stage 3b: AlphaFold3 → Validate top 20 (~30 min each)
    ↓
Stage 4: Filter by ipTM > 0.8, pLDDT > 80
```

**Time savings:** 100 designs × 30 min (AF3) = 50 hours
vs. 100 designs × 2 min (ColabFold) + 20 designs × 30 min (AF3) = ~1.5 hours

### Standalone ColabFold Pipeline

For designs where ipTM is not critical (monomers, simple validation):

```
Stage 1: RFdiffusion
    ↓
Stage 2: ProteinMPNN
    ↓
Stage 3: ColabFold (batch)
    ↓
Stage 4: Filter by pLDDT > 75, pTM > 0.6
```

## Limitations

1. **No ipTM** — Cannot assess protein-protein interface quality
2. **Proteins only** — No RNA, DNA, or ligand support
3. **AF2 architecture** — Not the latest AF3 model
4. **Confidence calibration** — pTM scores differ from AF3

## When to Use

| Scenario | Use ColabFold? | Use AlphaFold3? |
|----------|---------------|-----------------|
| Binder design | ⚠️ No ipTM | ✅ Yes |
| Monomer validation | ✅ Yes | ✅ Yes |
| High-throughput screen (>50 designs) | ✅ Yes | ⚠️ Slow |
| Final design validation | ⚠️ Less accurate | ✅ Yes |
| Complex with ligands/RNA | ❌ No | ✅ Yes |

## Tips

- Use `colabfold_batch --msa-only` to pre-compute MSAs offline
- For very large batches, use local MMseqs2 databases (avoid server limits)
- ColabFold confidence scores are better calibrated to actual quality than AF3
- GPU memory: ~16GB supports up to ~2000 residues
- For binder design, use ColabFold for initial ranking then AF3 for final ipTM

## References

- [ColabFold GitHub](https://github.com/sokrypton/ColabFold)
- [LocalColabFold](https://github.com/YoshitakaMo/localcolabfold)
- [MMseqs2](https://github.com/soedinglab/MMseqs2)

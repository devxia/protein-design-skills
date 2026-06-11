---
name: chai1-validation
description: Biomolecular structure prediction with Chai-1 — Apache 2.0 licensed AlphaFold3 alternative with single-sequence mode and experimental constraint support
---

# Alternative Stage 3: Chai-1 Structure Validation

> **Quick Entry**: Stage 3 alternative | Apache 2.0 | constraints | single-sequence
>
> **Upstream**: `sequence-design` (ProteinMPNN/LigandMPNN/ESM-IF1) | **Downstream**: `filtering-ranking`

## When to Trigger

- User says "Chai-1", "Chai Discovery", "chai-lab"
- User wants **commercially permissive** structure prediction (Apache 2.0)
- User needs **single-sequence prediction** without MSA
- User wants to incorporate **experimental constraints** (crosslinking, epitope mapping)
- User needs state-of-the-art protein-ligand complex prediction
- User says "Apache licensed structure predictor"

## Chai-1 Overview

[Chai-1](https://github.com/chaidiscovery/chai-lab) is a multi-modal foundation model for biomolecular structure prediction released by **Chai Discovery** in **September 2024**. It achieves state-of-the-art results across protein, nucleic acid, and small molecule benchmarks with a commercially friendly **Apache 2.0 license**.

### Key Differences from AlphaFold3

| Feature | AlphaFold3 | Chai-1 |
|---------|------------|--------|
| License | Non-commercial research only | **Apache 2.0 (commercial OK)** |
| Single-sequence mode | No (requires MSA) | **Yes (MSA-free)** |
| Experimental constraints | No | **Yes (crosslinking, epitope)** |
| Protein-ligand | Yes | Yes (~77% PoseBusters) |
| Protein-peptide | Yes | Yes (strong performance) |
| Installation | Complex | `pip install chai_lab` |
| Speed | Slow | Comparable |

**Key insight**: Chai-1 is the **best choice** when you need AlphaFold3-level accuracy with a permissive license AND want single-sequence mode or experimental constraint support.

## Installation

```bash
# Stable version from PyPI
pip install chai_lab==0.6.1

# Latest development version
pip install git+https://github.com/chaidiscovery/chai-lab.git
```

**Requirements:**
- Linux (primary), macOS/Windows reported
- CUDA GPU with **bfloat16** support (A100 80GB, H100 80GB recommended)
- Also works: A10, A30, RTX 4090 (for smaller complexes)

## Usage

### Command Line

```bash
# Run prediction with MSA server
chai-lab fold input.fasta output_dir/

# Single-sequence mode (no MSA)
chai-lab fold input.fasta output_dir/ --no-msa-server

# With experimental constraints
chai-lab fold input.fasta output_dir/ --constraints constraints.json
```

### Input Format

Chai-1 uses a simple FASTA-like format with entity types:

```
>protein|name=target
MKTLLILTGLVAGESKTVLQYF...

>protein|name=binder
GSHMQSITDFGT...

>ligand|name=drug
CC(C)Cc1ccc(cc1)C(C)C(=O)O
```

### Python API

```python
from chai_lab.chai1 import run_inference

# Predict structure
result = run_inference(
    fasta_file="input.fasta",
    output_dir="output/",
    use_msa_server=True,  # Set False for single-sequence mode
    num_trunk_recycles=3,
    num_diffn_timesteps=200,
)

# Access results
best_structure = result[0]  # Ranked by confidence
print(f"pLDDT: {best_structure.confidence.plddt:.1f}")
print(f"pTM: {best_structure.confidence.ptm:.3f}")
```

### Experimental Constraints

Chai-1 can incorporate experimental data to guide predictions:

```json
{
  "constraints": [
    {
      "type": "crosslink",
      "residue1": "A_15",
      "residue2": "B_42",
      "max_distance": 30.0
    },
    {
      "type": "epitope",
      "chain": "A",
      "residues": [30, 31, 32, 33, 34]
    }
  ]
}
```

## Single-Sequence Mode

Chai-1 can predict structures **without MSA** (unlike AlphaFold3):

```bash
# No MSA — faster, useful for quick screening
chai-lab fold input.fasta output_dir/ --no-msa-server
```

**Trade-offs:**
- Speed: ~2-5x faster (no MSA search)
- Accuracy: Slightly lower than with MSA, but still competitive
- Best for: Quick screening, orphan proteins, synthetic designs

## Pipeline Integration

### Option 1: Chai-1 as AlphaFold3 Replacement
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → Chai-1 (validation)
                                                        ↓
                                        Stage 4 (Filtering)
```

### Option 2: Single-Sequence Quick Screen
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → Chai-1 (no MSA, fast screen)
                                                        ↓
                                        Select top by pLDDT
                                                        ↓
                                        Run with MSA for accuracy
```

### Option 3: Constraint-Guided Design
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN)
                                    ↓
                        Chai-1 with experimental constraints
                                    ↓
                        Validate against known data
```

## Comparison with Other Stage 3 Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| Commercial use (Apache) | **Chai-1** | Apache 2.0 license |
| Commercial use (MIT) | Boltz-1 | MIT license |
| Single-sequence | **Chai-1** | Native MSA-free mode |
| With experimental data | **Chai-1** | Constraint support |
| RNA/DNA complexes | Boltz-1 or Chai-1 | Both excellent |
| Protein-ligand | Chai-1 or Boltz-1 | Both ~77% PoseBusters |
| Speed (no DB) | OmegaFold | Fastest, monomer only |
| Academic (best accuracy) | AlphaFold3 | Slightly better on some benchmarks |

## Confidence Metrics

| Metric | Description | Good Threshold |
|--------|-------------|----------------|
| pLDDT | Per-atom confidence | >70 |
| pTM | Topology confidence | >0.7 |
| ipTM | Interface confidence (complexes) | >0.8 |
| Cα-RMSD | Structural accuracy vs reference | <2Å |

## Tips

- **License**: Apache 2.0 allows commercial use — great for biotech startups
- **Single-sequence**: Use `--no-msa-server` for quick screening, then re-run top hits with MSA
- **Constraints**: Experimental constraints (crosslinking, epitope) can dramatically improve accuracy
- **GPU memory**: Large complexes need A100 80GB; smaller ones work on A10/RTX 4090
- **Protein-peptide**: Chai-1 excels at protein-peptide complexes (better than AF3 on some benchmarks)
- **Batch processing**: Process multiple designs by providing multi-sequence FASTA

## Chai-2 (2025)

Chai Discovery released **Chai-2** in 2025, specialized for **de novo antibody design**:
- Generates antibody sequences and structures
- Optimized for CDR loop design
- Commercially available (not fully open source)

## References

- [Chai-1 GitHub](https://github.com/chaidiscovery/chai-lab)
- [Chai-1 Technical Report](https://chaiassets.com/chai-1/paper/technical_report_v1.pdf)
- [Chai Discovery](https://www.chaidiscovery.com/)
- [Chai-2 Announcement](https://www.chaidiscovery.com/chai-2)

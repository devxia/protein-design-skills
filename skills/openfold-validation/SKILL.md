---
name: openfold-validation
description: Biomolecular structure prediction with OpenFold3 — fully open-source AlphaFold3 reproduction, Apache 2.0, commercially viable
---

# Alternative Stage 3: OpenFold3 Structure Validation

> **Quick Entry**: Stage 3 alternative | pip install | AF3 reimplementation
>
> **Upstream**: `sequence-design` (ProteinMPNN/LigandMPNN/ESM-IF1) | **Downstream**: `filtering-ranking`

## When to Trigger

- User says "OpenFold", "OpenFold3", "openfold-3"
- User wants **fully open-source** AlphaFold3 reproduction
- User needs **commercially viable** structure prediction (Apache 2.0)
- User wants to **train/fine-tune** their own folding model
- User needs **Apple Silicon** support (M-series chips)
- User wants the **leading open-source** biomolecular prediction platform
- User says "pip install structure predictor"

## OpenFold3 Overview

[OpenFold3](https://github.com/aqlaboratory/openfold-3) is the premier **fully open-source reproduction of AlphaFold3** from Columbia University's AlQuraishi Lab and the OpenFold Consortium. Released under **Apache 2.0**, it achieves **parity with AlphaFold3** on key benchmarks while being freely available for commercial use.

### Key Differences from AlphaFold3

| Feature | AlphaFold3 | OpenFold3 |
|---------|------------|-----------|
| License | Non-commercial research only | **Apache 2.0 (fully open)** |
| Installation | Complex manual setup | **`pip install openfold3`** |
| Training | Not available | **Full training supported** |
| Apple Silicon | No | **Yes (MLX fork)** |
| RNA monomers | Yes | **Matching AF3 performance** |
| Inference speed | Baseline | Comparable |
| Community | Google DeepMind | **24 consortium partners** |
| Maintenance | Limited | **Long-term commitment** |

**Key insight**: OpenFold3 is the **best choice** for organizations needing a commercially viable, well-maintained, fully open-source AlphaFold3 alternative with training capabilities.

## Versions

| Version | Description | Best For |
|---------|-------------|----------|
| **OpenFold3** | Main AF3 reproduction | General use, commercial |
| **OpenFold3-MLX** | Apple Silicon optimized | M1/M2/M3 Mac users |
| **OpenFold2** | Original AF2 reproduction | AF2-level needs |

## Installation

```bash
# Simple pip install
pip install openfold3

# Setup (downloads parameters)
setup_openfold

# Apple Silicon users
pip install openfold3-mlx  # Use MLX fork
```

**Requirements:**
- CUDA-compatible GPU (A100 recommended)
- PyTorch 2.0+
- CUDA 12+

## Usage

### Standalone Wrapper (`scripts/run_openfold3.py`)

```bash
# Predict from FASTA
python scripts/run_openfold3.py \
    --input sequences.fasta \
    --output-dir outputs/openfold3/ \
    --num-recycling 3 \
    --verbose

# Predict from AlphaFold3-style JSON
python scripts/run_openfold3.py \
    --input design.json \
    --output-dir outputs/openfold3/ \
    --model-dir /path/to/model/weights \
    --db-dir /path/to/databases \
    --verbose
```

### Native OpenFold3 CLI

```bash
# Run prediction
run_openfold predict --query_json=query.json

# With custom parameters
run_openfold predict \
    --query_json=query.json \
    --output_dir=outputs/ \
    --num_recycles=3 \
    --model_preset=multimer
```

### Input Format

```json
{
  "name": "my_protein",
  "sequences": [
    {
      "protein": {
        "id": "A",
        "sequence": "MKTLLILTGLVAGESKTVLQYF..."
      }
    },
    {
      "ligand": {
        "id": "L",
        "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
      }
    }
  ]
}
```

### Python API

```python
from openfold3 import OpenFold3Model

# Load model
model = OpenFold3Model.from_pretrained("openfold3")
model = model.cuda()

# Predict structure
result = model.predict(
    sequences=[
        {"protein": {"id": "A", "sequence": "MKTLLIL..."}},
        {"ligand": {"id": "L", "smiles": "CC(C)Cc1..."}},
    ],
    num_recycles=3,
)

# Save results
result.save_pdb("output.pdb")
result.save_confidence("confidence.json")
```

### Training (OpenFold3 Unique Feature)

```python
from openfold3 import OpenFold3Trainer

# Fine-tune on custom data
trainer = OpenFold3Trainer(
    model_name="openfold3",
    train_data="custom_dataset/",
    batch_size=1,
    learning_rate=1e-4,
)

trainer.train(epochs=10)
```

**Training performance:** 8 days → 10 hours with optimized clusters

## Pipeline Integration

### Option 1: OpenFold3 as AlphaFold3 Replacement
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → OpenFold3 (validation)
                                                        ↓
                                        Stage 4 (Filtering)
```

### Option 2: OpenFold3 for RNA Structures
```
Input: RNA sequence
    ↓
OpenFold3 (predict RNA structure)
    ↓
Validate with pLDDT
```

**Why**: OpenFold3 is the only open-source model matching AF3 on RNA monomers.

### Option 3: Commercial Pipeline
```
Stage 1 (RFdiffusion/Chroma) → Stage 2 (ProteinMPNN/LigandMPNN)
                                        ↓
                            OpenFold3 (Apache 2.0 validation)
                                        ↓
                            Filtering → Experimental validation
```

**Why**: Apache 2.0 license allows unrestricted commercial use.

## Comparison with Other Stage 3 Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| Commercial use | **OpenFold3** | Apache 2.0, consortium-backed |
| Training capability | **OpenFold3** or Protenix | Both support training |
| Apple Silicon | **OpenFold3-MLX** | Native M-series support |
| Best accuracy | **OpenFold3** | Matches AF3 on benchmarks |
| RNA structures | **OpenFold3** | Only open-source matching AF3 |
| Speed | ESMFold / OmegaFold | Faster but less accurate |
| Complexes | OpenFold3 / Boltz-1 / Chai-1 | All excellent |
| One-line install | **OpenFold3** | `pip install openfold3` |

## Performance Benchmarks

| Benchmark | OpenFold3 | AlphaFold3 |
|-----------|-----------|------------|
| Protein monomers (CASP16) | Competitive | Reference |
| Protein-protein complexes | Competitive | Reference |
| **RNA monomers** | **Matching** | Matching |
| Ligand docking | Good | Reference |

## Confidence Metrics

| Metric | Description | Good Threshold |
|--------|-------------|----------------|
| pLDDT | Per-atom confidence | >70 |
| pTM | Topology confidence | >0.7 |
| ipTM | Interface confidence | >0.8 |
| PAE | Predicted aligned error | <10 (good) |

## Tips

- **Easiest install**: `pip install openfold3` — simplest setup of any AF3 alternative
- **Commercial projects**: Apache 2.0 means no licensing worries
- **Training**: Use OpenFold3 for research requiring model fine-tuning
- **Apple Silicon**: Use OpenFold3-MLX fork for M1/M2/M3 Macs
- **RNA focus**: OpenFold3 uniquely matches AF3 on RNA — use for RNA structure prediction
- **Consortium**: Backed by 24 partners including major pharma — long-term support assured
- **Speed**: Training optimized to 10 hours (was 8 days)

## References

- [OpenFold3 GitHub](https://github.com/aqlaboratory/openfold-3)
- [OpenFold2 GitHub](https://github.com/aqlaboratory/openfold)
- [OpenFold3-MLX (Apple Silicon)](https://github.com/latent-spacecraft/openfold-3-mlx)
- [OpenFold Consortium](https://omsf.io/programs/projects/openfold/)
- [OpenFold2 Paper](https://www.nature.com/articles/s41592-024-02272-z)
- [AlQuraishi Lab](https://www.aqlaboratory.com/)

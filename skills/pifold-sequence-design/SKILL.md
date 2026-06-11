---
name: pifold-sequence-design
description: Guide for using PiFold, a fast MIT-licensed inverse folding model for structure-based protein sequence design
---

# PiFold Sequence Design Guide

**PiFold** is a fast **inverse folding** model for **structure-based protein sequence design**. Given a protein backbone structure, PiFold predicts the amino acid sequence most likely to fold into that conformation. Published at **ICLR 2023 (Spotlight)**.

Use PiFold when you want:
- **70× faster inference** than autoregressive alternatives like ProteinMPNN
- A **non-autoregressive, one-shot** sequence decoder
- An **MIT-licensed** sequence designer for commercial or academic use
- Strong recovery on inverse-folding benchmarks (51.66% on CATH 4.2, 58.72% on TS50, 60.42% on TS500)

---

## What Makes PiFold Different

| Feature | ProteinMPNN | ESM-IF1 | PiFold |
|---------|-------------|---------|--------|
| Decoder | Autoregressive | Iterative / masked | **One-shot** |
| Speed | Medium | Medium | **70× faster** than autoregressive baselines |
| Recovery (CATH 4.2) | ~52% | ~51% | **51.66%** |
| License | MIT | MIT | **MIT** |
| Best for | General fixed-backbone design | Partial masking / variants | **High-throughput fixed-backbone design** |

PiFold introduces a **novel residue featurizer** with learnable virtual atoms and **PiGNN layers** that model multi-scale residue interactions at node, edge, and global context levels. The one-shot decoder makes it especially attractive for large libraries.

---

## Installation (Document-Only — Do Not Install)

```bash
# Clone official repository
git clone https://github.com/A4Bio/PiFold.git
cd PiFold

# Install dependencies (PyTorch, PyTorch Geometric, etc.)
pip install -r requirements.txt   # if present; otherwise inspect main.py imports
```

### Quick test via Colab

The authors provide ready-to-run Colab notebooks:

- [PiFold inference demo](https://colab.research.google.com/drive/1HgXQCbsoK09mcVZmPgIWlCczY64l0iIX?usp=sharing)
- [Fixed-backbone design demo](https://colab.research.google.com/drive/1z6vpKA5L1iAmBLfREbmy8VNOtDYlkY4Q?usp=sharing)

These are the fastest way to evaluate PiFold without a local environment.

### Unofficial PyTorch re-implementation

An unofficial pip-installable version is also available:

```bash
pip install pifold-pytorch
```

Repository: [dohlee/pifold-pytorch](https://github.com/dohlee/pifold-pytorch)

**Sources:**
- [Official GitHub repository](https://github.com/A4Bio/PiFold)
- [ICLR 2023 paper](https://openreview.net/forum?id=oMsN9TYwJ0j)
- [arXiv preprint](https://arxiv.org/abs/2209.12643)

---

## Quickstart: Fixed-Backbone Sequence Design

### Option A: Colab (recommended for first tests)

Open the [fixed-backbone design Colab](https://colab.research.google.com/drive/1z6vpKA5L1iAmBLfREbmy8VNOtDYlkY4Q?usp=sharing), upload your PDB, and run the cells. The notebook outputs a FASTA file of designed sequences.

### Option B: Local inference via `API/`

The repository includes an `API/` directory with helper scripts for loading a trained PiFold model and running inference on a backbone:

```python
import torch
from methods import ProDesign
from utils import load_structure, design_sequence

# Load model
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = ProDesign(args, device)
model.load_state_dict(torch.load("checkpoint.pth"))

# Load backbone
coords, seq = load_structure("input.pdb")

# Design sequence
designed_seq = design_sequence(model, coords, device=device)
print(designed_seq)
```

> ⚠️ **Security note:** `torch.load()` defaults to `weights_only=False`, which unpickles arbitrary Python objects and can execute malicious code. When loading third-party checkpoints, use `torch.load(..., weights_only=True)` if the checkpoint only contains tensors and simple data structures, or set `TORCH_FORCE_WEIGHTS_ONLY_LOAD=1` in your environment.
>
> Note: The exact inference API may vary by commit. Refer to the latest `API/` directory and Colab notebooks for the current interface.

### Option C: Unofficial `pifold-pytorch`

```python
from pifold_pytorch import PiFold
import torch

model = PiFold()
coords = torch.randn(1, 100, 4, 3)  # (batch, length, atoms, 3)
seq = model(coords)
```

See [dohlee/pifold-pytorch](https://github.com/dohlee/pifold-pytorch) for full usage.

---

## Training

```bash
python main.py \
  --method ProDesign \
  --dataset CATH \
  --res_dir ./results \
  --ex_name cath_run
```

Key training parameters (from `parser.py`):

| Parameter | Typical Value | Purpose |
|-----------|---------------|---------|
| `--method` | `ProDesign` | Model class |
| `--dataset` | `CATH` | Training dataset |
| `--epochs` | 200 | Training epochs |
| `--batch_size` | 8 | Batch size |
| `--lr` | 1e-3 | Learning rate |
| `--use_gpu` | True | Use CUDA |

---

## Output Format

PiFold outputs:
- **Designed sequences** as strings or FASTA records
- **Per-residue logits** for uncertainty analysis
- **Recovery metrics** when ground-truth sequence is available

Typical inference pipeline:

1. Generate or load backbone(s) from Stage 1 (RFdiffusion, FrameDiff, TopoDiff, etc.)
2. Run PiFold on each backbone → designed sequences
3. Save as FASTA
4. Fold with ESMFold / AlphaFold3 / Boltz-1
5. Filter by confidence metrics

---

## Pipeline Integration

PiFold is a **Stage 2** sequence design tool. A complete pipeline:

| Stage | Tool | Purpose |
|-------|------|---------|
| 0 | PDBFixer | Repair input if needed |
| 1 | RFdiffusion / FrameDiff / TopoDiff | Generate backbone(s) |
| 2 | **PiFold** | Fast sequence design for each backbone |
| 3 | AlphaFold3 / Boltz-1 / ESMFold | Validate structures |
| 4 | Filtering | Rank by confidence and recovery |

### Recommended pairings
- High-throughput libraries → RFdiffusion → PiFold → ESMFold
- High-accuracy design → RFdiffusion → PiFold → AlphaFold3
- Commercial use → FrameDiff / TopoDiff → PiFold → Boltz-1 / Chai-1

---

## When to Use PiFold vs Other Sequence Design Tools

| Your Goal | Best Tool |
|-----------|-----------|
| General fixed-backbone design | ProteinMPNN |
| Ligand-aware sequences | LigandMPNN |
| Partial masking / variants | ESM-IF1 |
| Fitness-conditional optimization | PRO-LDM |
| Text-guided generation | ProteinDT |
| **High-throughput inverse folding, MIT license** | **PiFold** |
| pLM-latent diffusion | DiMA |

---

## Strengths and Limitations

**Strengths:**
- MIT license
- 70× faster inference than autoregressive methods
- One-shot non-autoregressive decoder
- Strong recovery on CATH, TS50, and TS500
- Novel virtual-atom featurizer and PiGNN layers
- Colab notebooks available for quick testing

**Limitations:**
- Fixed-backbone only (no ligand awareness; use LigandMPNN for that)
- Official repo training focus; inference API less documented than ProteinMPNN
- Recovery slightly below the very best autoregressive methods on some tasks
- Smaller community and fewer wrappers than ProteinMPNN

---

## Citation

Gao et al., "PiFold: Toward effective and efficient protein inverse folding," *ICLR*, 2023.

```bibtex
@inproceedings{gao2023pifold,
  title={PiFold: Toward effective and efficient protein inverse folding},
  author={Gao, Zhangyang and Tan, Cheng and Li, Stan Z.},
  booktitle={International Conference on Learning Representations},
  year={2023},
  url={https://openreview.net/forum?id=oMsN9TYwJ0j}
}

@article{gao2022pifold,
  title={PiFold: Toward effective and efficient protein inverse folding},
  author={Gao, Zhangyang and Tan, Cheng and Li, Stan Z.},
  journal={arXiv preprint arXiv:2209.12643},
  year={2022}
}
```

---

## See Also

- `sequence-design` — ProteinMPNN for general fixed-backbone design
- `ligandmpnn-design` — Ligand-aware sequence design
- `esm-if1-design` — Partial masking and variant scoring
- `pro-ldm-workflow` — Fitness-conditional latent diffusion
- `dima-workflow` — Latent diffusion on pLM representations
- `framediff-backbone` — Fast MIT-licensed backbone generation
- `fast-screening` — Rapid validation with ESMFold / OmegaFold
- `pipeline-selection` — Choose the right workflow

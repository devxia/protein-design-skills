---
name: dima-workflow
description: Guide for using DiMA, a latent diffusion framework on protein language model representations for conditional sequence generation
---

# DiMA Workflow Guide

**DiMA** (Diffusion on Language Model Encodings) is a **latent diffusion framework** for protein **sequence generation** that operates in the continuous embedding space of pretrained protein language models. Accepted at **ICML 2025**.

Use DiMA when you want:
- Sequence generation conditioned on protein language model representations
- An **encoder-agnostic** sequence generator that works with ESM-2, ESMc, CHEAP, or SaProt
- A lightweight 35M-parameter denoiser instead of full sequence-level diffusion
- Family-specific generation, motif scaffolding, infilling, or fold-conditioned design

---

## What Makes DiMA Different

| Feature | PRO-LDM | ProteinDT | DiMA |
|---------|---------|-----------|------|
| Latent space | Joint autoencoder latents | Text CLAP latents | **pLM embeddings (ESM, SaProt, CHEAP)** |
| Conditioning | Fitness labels | Text prompts | **pLM encoder + optional labels** |
| Architecture | LDM + JT-AE | CLAP + T5/multinomial | **Diffusion on pLM latents + decoder** |
| Parameter count | Larger | Varies | **35M denoiser** |
| Encoder support | ProtBERT | ProtBERT | **ESM-2, ESMc, CHEAP, SaProt** |
| License | MIT | MIT | **MIT** |

DiMA is unique because it treats pretrained protein language models as **latent spaces** and learns a small diffusion model on top. This makes it encoder-agnostic and computationally efficient.

---

## Installation (Document-Only — Do Not Install)

```bash
# Clone repository
git clone https://github.com/MeshchaninovViacheslav/DiMA.git
cd DiMA

# Create environment from provided spec
conda env create --file environment.yaml
conda activate dima_env
```

Dependencies are managed via `environment.yaml`. Key encoders include:
- **ESM2-3B** — sequence-only
- **CHEAP** — dual-decodable (sequence + structure)
- **SaProt-35M** — multimodal (sequence + structure tokens)

### Download datasets

DiMA provides datasets on HuggingFace Hub:

```bash
python -m src.datasets.load_hub \
  --config_path="../configs" \
  --load_from_hub \
  --group_name="bayes-group-diffusion"

python -m src.helpers.prepare_length_distribution \
  --config_path="../configs"
```

Available datasets:
- `bayes-group-diffusion/AFDB-v2`
- `bayes-group-diffusion/swissprot`

**Sources:**
- [GitHub repository](https://github.com/MeshchaninovViacheslav/DiMA)
- [ICML 2025 paper](https://openreview.net/forum?id=xB9eROwBCB)
- [Project page](https://meshchaninovviacheslav.github.io/DiMA/)
- [arXiv preprint](https://arxiv.org/abs/2403.03726)

---

## Quickstart

### Generate sequences with a pretrained model

```python
import torch
from src.diffusion.dima import DiMAModel

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = DiMAModel(config_path="../configs", device=device)
model.load_pretrained()

# Generate 10 sequences
sequences = model.generate_samples(num_texts=10)
```

### Configure the encoder

Edit `src/configs/config.yaml` or override `defaults.encoder`:

```yaml
defaults:
  encoder: esm2    # Options: esm2, cheap, saprot
```

| Encoder | Parameters | Modality | Best For |
|---------|-----------|----------|----------|
| `esm2` | 3B | Sequence only | General sequence generation |
| `cheap` | Varies | Sequence + structure | Joint sequence-structure tasks |
| `saprot` | 35M | Sequence + structure tokens | Multimodal conditioning, lightweight |

---

## Training Pipeline

DiMA training has three stages:

### Stage 1: Calculate normalization statistics

```bash
python -m src.preprocessing.calculate_statistics --config_path="../configs"
```

### Stage 2: (Optional) Train a custom decoder

```bash
python -m src.preprocessing.train_decoder --config_path="../configs"
```

Skip this if using a pretrained decoder.

### Stage 3: Train the diffusion denoiser

```bash
HYDRA_FULL_ERROR=1 torchrun \
  --nproc_per_node=8 \
  --master_port=31345 \
  train_diffusion.py
```

Training uses 8 GPUs by default. The denoiser has only **35M parameters**, making it much smaller than typical protein diffusion models.

---

## Conditional Generation Tasks

DiMA supports several conditional tasks out of the box:

| Task | How to configure |
|------|------------------|
| **Unconditional generation** | Default sampling from learned prior |
| **Family-specific generation** | Condition on family label / embedding |
| **Motif scaffolding** | Fix motif positions, diffuse remaining sequence |
| **Infilling** | Mask region of interest, inpaint with diffusion |
| **Fold-specific design** | Condition on fold embedding or predicted structure |

These are configured through the Hydra config in `src/configs/config.yaml` and the conditioning modules in `src/diffusion/`.

---

## Output Format

DiMA outputs amino acid sequences as strings or FASTA records. If using CHEAP or SaProt, you can also decode structure information. Typical workflow:

1. Generate sequences with DiMA
2. Save to FASTA
3. Fold with ESMFold, OmegaFold, or AlphaFold3
4. Filter by confidence metrics

---

## Pipeline Integration

DiMA is a **Stage 2 / Stage 1.5** tool — it generates sequences directly from pLM latents, optionally conditioned on motifs or fold information.

| Stage | Tool | Purpose |
|-------|------|---------|
| 1.5 | **DiMA** | Generate diverse sequences from pLM latents |
| 2 | *(optional)* ProteinMPNN | Re-design if a structure becomes available |
| 3 | ESMFold / OmegaFold / AlphaFold3 | Predict structures |
| 4 | Filtering | Rank by confidence |

### Recommended pairings
- Fast latent sequence generation → DiMA + SaProt → ESMFold
- High-accuracy design → DiMA + ESM-2 → AlphaFold3
- Joint sequence-structure exploration → DiMA + CHEAP → validation with RFAA
- Commercial use → DiMA + ESM-2 → Boltz-1 / Chai-1

---

## When to Use DiMA vs Other Sequence Generation Tools

| Your Goal | Best Tool |
|-----------|-----------|
| Sequence for a given backbone | ProteinMPNN |
| Ligand-aware sequences | LigandMPNN |
| Partial masking / variants | ESM-IF1 |
| Fitness-conditional optimization | PRO-LDM |
| Text-guided generation | ProteinDT |
| **pLM-latent diffusion with encoder choice** | **DiMA** |
| Motif scaffolding in latent space | **DiMA** |
| Joint sequence-structure from latents | **DiMA + CHEAP/SaProt** |

---

## Strengths and Limitations

**Strengths:**
- MIT license
- Encoder-agnostic (ESM-2, ESMc, CHEAP, SaProt)
- Very small denoiser (35M parameters)
- Works in continuous pLM latent space
- Supports sequence + structure decoders
- Strong theoretical framing from ICML 2025

**Limitations:**
- Generates **sequences**, not full structures directly (unless using CHEAP/SaProt)
- Requires pretrained pLM encoder as a dependency
- Multi-GPU training recommended
- Less battle-tested than ProteinMPNN for structure-conditioned design
- Smaller community and fewer tutorials than RFdiffusion

---

## Citation

Meshchaninov et al., "Diffusion on Language Model Encodings for Protein Sequence Generation," *ICML*, 2025.

```bibtex
@inproceedings{meshchaninov2025dima,
    title={Diffusion on Language Model Encodings for Protein Sequence Generation},
    author={Meshchaninov, Viacheslav and Strashnov, Pavel and Shevtsov, Andrey and Nikolaev, Fedor and Ivanisenko, Nikita and Kardymon, Olga and Vetrov, Dmitry},
    booktitle={International Conference on Machine Learning (ICML)},
    year={2025}
}
```

---

## See Also

- `sequence-design` — ProteinMPNN for structure-conditioned sequences
- `pro-ldm-workflow` — Fitness-conditional latent diffusion
- `proteindt-workflow` — Text-guided protein design
- `esm-if1-design` — Partial masking and variant scoring
- `protein-generator` — Joint sequence + structure diffusion
- `fast-screening` — Rapid validation with ESMFold / OmegaFold
- `pipeline-selection` — Choose the right workflow

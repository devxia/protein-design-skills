---
name: progen2-sequence
description: Guide for using Salesforce ProGen2, a BSD-3 licensed autoregressive protein language model for de novo sequence generation and fitness scoring
---

# ProGen2 Autoregressive Sequence Generation Guide

**ProGen2** is a family of **autoregressive protein language models** from Salesforce Research, released under a permissive **BSD-3-Clause license**. It models the distribution of natural protein sequences at scale (up to **6.4 billion parameters**) and can generate novel viable sequences from a short context or score arbitrary sequences for fitness — without task-specific fine-tuning.

Use ProGen2 when you want:
- **De novo protein sequence generation** from a partial motif or unconditional sampling
- **Zero-shot fitness scoring** of variants (log-likelihood per residue)
- A **permissive BSD-3 license** suitable for academic and commercial research
- A sequence-only alternative to structure-aware generators like ProteinMPNN or PiFold
- To explore large-scale protein sequence space without requiring structural templates

---

## What Makes ProGen2 Different

| Feature | EvoDiff | ProteinDT | DiMA | ProGen2 |
|---------|---------|-----------|------|---------|
| Architecture | Diffusion on sequences | Text-aligned transformer | Latent diffusion on pLM | **Autoregressive transformer** |
| Scale | ~640M | ~150M | 35M denoiser | **Up to 6.4B parameters** |
| Zero-shot fitness scoring | Limited | No | No | **Yes (log-likelihood)** |
| Conditioning | Sequence motifs | Text prompts | pLM latents | **Sequence context / taxonomy tags** |
| License | MIT | MIT | MIT | **BSD-3-Clause** |

ProGen2 is best for **sequence-first design campaigns**: generate a diverse sequence library, filter with the built-in likelihood model, then fold with ESMFold or OmegaFold for structural validation.

---

## Installation (Document-Only — Do Not Install)

```bash
git clone https://github.com/salesforce/progen.git
cd progen/progen2

# Download a checkpoint (example: progen2-large ~2.7B)
model=progen2-large
wget -P checkpoints/${model} \
  https://storage.googleapis.com/sfr-progen-research/checkpoints/${model}.tar.gz
tar -xvf checkpoints/${model}/${model}.tar.gz -C checkpoints/${model}/

# Create environment
python3.8 -m venv .venv
source .venv/bin/activate
pip3 install --upgrade pip setuptools
pip3 install -r requirements.txt
```

**Sources:**
- [GitHub repository](https://github.com/salesforce/progen)
- [Paper — arXiv 2022](https://arxiv.org/abs/2206.13517)
- [Checkpoints (Google Cloud Storage)](https://storage.googleapis.com/sfr-progen-research/checkpoints/)

---

## Quickstart: Generate Sequences

```bash
python3 sample.py \
  --model progen2-large \
  --t 0.8 \
  --p 0.9 \
  --max-length 512 \
  --num-samples 10 \
  --context "1"
```

- `--t` — sampling temperature (higher = more diverse)
- `--p` — nucleus top-p cutoff
- `--max-length` — maximum sequence length in tokens
- `--num-samples` — number of sequences to generate
- `--context` — starting tokens; the example prefix `"1"` is used in the official code as a start-of-sequence indicator

Generated sequences are printed to stdout. Save them to FASTA:

```bash
python3 sample.py --model progen2-large --t 0.8 --p 0.9 \
  --max-length 512 --num-samples 100 --context "1" > progen2_outputs.txt

# Convert to FASTA with a simple script
python scripts/convert_format.py --from raw --to fasta \
  --input progen2_outputs.txt --output outputs/progen2/sequences.fa
```

---

## Zero-Shot Fitness Scoring

Score a sequence or variant with `likelihood.py`:

```bash
python3 likelihood.py \
  --model progen2-large \
  --context "1MKTLLILTLG...2"
```

Output is the model log-likelihood (higher = more probable under the model, often correlated with fitness). Use this to:
1. Rank generated sequences before folding
2. Score mutation variants of a known parent
3. Filter out low-likelihood outliers

---

## Model Zoo

| Model | Parameters | Best For |
|-------|------------|----------|
| `progen2-small` | 151M | Fast prototyping, CPU inference |
| `progen2-medium` | 764M | Balance of speed and quality |
| `progen2-base` | 764M | General generation |
| `progen2-oas` | 764M | Antibody / immune repertoire sequences |
| `progen2-large` | 2.7B | High-quality generation |
| `progen2-BFD90` | 2.7B | BFD90-trained distribution |
| `progen2-xlarge` | 6.4B | Best quality, requires most memory |

---

## Pipeline Integration

ProGen2 is a **sequence-only Stage 2 alternative** (or Stage 1 if you treat sequence as the design object):

| Stage | Typical Tool | ProGen2 Role |
|-------|--------------|--------------|
| 1/2 | **ProGen2** | **Generate / score candidate sequences** |
| 3 | ESMFold / OmegaFold | Fold and validate generated sequences |
| 4 | Filtering | Rank by pLDDT + ProGen2 likelihood |

### Recommended pairings
- Unconditional family exploration → ProGen2 → `esmfold-validation`
- Motif-conditional generation → ProGen2 context → ESMFold structural check
- Fitness landscape sampling → ProGen2 likelihood ranking + `pro-ldm-workflow` optimization

---

## Hardware & Timing

- **GPU strongly recommended** for `large` and `xlarge` models
- `small`/`medium` can run on CPU, but generation is slow
- 2.7B-parameter `large` fits on a single A100 40 GB
- 6.4B-parameter `xlarge` benefits from multi-GPU or high-VRAM GPU

---

## Interpreting Outputs

| Output | Interpretation |
|--------|----------------|
| Generated sequence | Novel protein sequence sampled from the model distribution |
| Log-likelihood | Higher = more evolutionarily plausible; useful as a zero-shot fitness proxy |
| Per-token likelihood | Identify low-confidence regions that may need redesign |

A typical filtering workflow:

```bash
# 1. Generate 1000 sequences
# 2. Keep top 200 by ProGen2 log-likelihood
# 3. Fold top 200 with ESMFold
# 4. Keep designs with mean pLDDT ≥ 80
```

---

## Strengths and Limitations

**Strengths:**
- BSD-3-Clause license (commercial-friendly)
- Massive scale (up to 6.4B parameters)
- Zero-shot fitness scoring without labeled data
- Simple autoregressive sampling interface
- Specialized OAS checkpoint for antibodies

**Limitations:**
- Sequence-only: no explicit structure constraint during generation
- Large checkpoints (2.7B–6.4B require significant VRAM)
- Generation can be slow for long proteins
- May reproduce biases present in training data
- No built-in filtering or validation — must pair with ESMFold / OmegaFold

---

## Citation

Nijkamp et al., "ProGen2: Exploring the Boundaries of Protein Language Models," *arXiv*, 2022.

```bibtex
@article{nijkamp2022progen2,
  author = {Nijkamp, Erik and Ruffolo, Jeffrey and Weinstein, Eli N. and Naik, Nikhil and Madani, Ali},
  title = {ProGen2: Exploring the Boundaries of Protein Language Models},
  journal = {arXiv preprint arXiv:2206.13517},
  year = {2022},
  url = {https://arxiv.org/abs/2206.13517}
}
```

---

## See Also

- `evodiff-sequence` — Diffusion-based sequence-only generation
- `proteindt-workflow` — Text-guided sequence generation
- `dima-workflow` — Latent diffusion on pLM representations
- `bcdesign-inverse` — Property-constrained sequence design
- `esmfold-validation` — Fast structure validation for generated sequences
- `omegafold-validation` — Lightweight validation without databases
- `pipeline-selection` — Choose the right workflow
- `periodic-summary` — Track sequence outputs across runs

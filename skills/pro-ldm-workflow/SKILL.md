---
name: pro-ldm-workflow
description: Guide for using PRO-LDM, a conditional latent diffusion model for protein sequence design and functional optimization, as a Stage 2 alternative
---

# PRO-LDM Workflow Guide

**PRO-LDM** is a conditional latent diffusion model for **protein sequence design** and **functional optimization**, published in *Advanced Science* (Wiley, 2025). It combines a jointly trained autoencoder (JT-AE) with a conditional latent diffusion model (LDM) and an integrated fitness regressor.

Use PRO-LDM as a **Stage 2 alternative** when:
- You have a fixed backbone or structural template and want sequence diversity
- You want to optimize a sequence toward a target fitness/property label
- You need out-of-distribution (OOD) designs for functional optimization
- You prefer a latent-space diffusion approach over autoregressive (ProteinMPNN) or inpainting (ESM-IF1) methods

---

## What Makes PRO-LDM Different

| Feature | ProteinMPNN | ESM-IF1 | PRO-LDM |
|---------|-------------|---------|---------|
| Approach | Autoregressive graph neural network | Structure-conditioned inpainting | Conditional latent diffusion |
| Input | Backbone PDB | Partial sequence + structure | Fitness labels / unconditional |
| Output | Sequences for a given backbone | Sequences + variant scoring | Sequences + fitness prediction |
| Optimization | None direct | Zero-shot scoring | Classifier-free guidance toward labels |
| OOD design | Limited | Limited | Explicit outlier sampling via guidance ω |
| License | MIT | Non-commercial / Apache | **MIT** |

PRO-LDM is especially useful for **fitness-directed sequence optimization** and **conditional generation** when you have labeled training data or want to push sequences toward high-fitness regions.

---

## Installation (Document-Only — Do Not Install)

```bash
# Clone repository
git clone https://github.com/AzusaXuan/PRO-LDM.git
cd PRO-LDM

# Create environment
conda create -n proldm_env python=3.8
conda activate proldm_env

# Install dependencies
pip3 install -r requirements.txt
```

### Download pre-trained weights and data

```bash
pip install gdown
gdown --folder https://drive.google.com/drive/folders/1tX9PSrywPhW62HlExn3lWj2IGEsSzKFv
```

Pre-trained checkpoints are also available in `./train_logs/<dataset>` after cloning.

**Sources:**
- [GitHub repository](https://github.com/AzusaXuan/PRO-LDM)
- [Advanced Science paper](https://advanced.onlinelibrary.wiley.com/doi/10.1002/advs.202502723)
- [Preprint on bioRxiv](https://www.biorxiv.org/content/10.1101/2023.08.22.554145)

---

## Quickstart

### Training on a labeled dataset

```bash
# Multi-GPU training (recommended)
python main.py \
  --mode train \
  --dataset TAPE \
  --multi_gpu True \
  --device_id [0,1,2,3] \
  --n_epochs 1000

# Single-GPU training
python main.py \
  --mode train \
  --dataset TAPE \
  --multi_gpu False \
  --device_id [0] \
  --n_epochs 1000
```

### Evaluation

```bash
python main.py \
  --mode eval \
  --dataset TAPE \
  --eval_load_epoch 1000
```

### Sequence generation / sampling

```bash
# Unconditional sampling (label 0)
python main.py \
  --mode sample \
  --dataset TAPE \
  --dif_sample_label 0 \
  --dif_sample_epoch 1000

# Conditional sampling toward a fitness label (e.g., label 1)
python main.py \
  --mode sample \
  --dataset TAPE \
  --dif_sample_label 1 \
  --dif_sample_epoch 1000
```

**Key flags:**

| Flag | Meaning |
|------|---------|
| `--mode` | `train`, `eval`, or `sample` |
| `--dataset` | Dataset name (see supported datasets below) |
| `--multi_gpu` | Enable DataParallel training |
| `--device_id` | GPU IDs to use |
| `--n_epochs` | Training epochs |
| `--dif_sample_label` | `0` = unconditional; `1–n` = conditional class |
| `--dif_sample_epoch` | Checkpoint epoch to load for sampling |

---

## Supported Datasets

PRO-LDM ships with preprocessed benchmark datasets in `./data/`:

**Conditional (5 fitness labels):**
- `NESP`
- `ube4b`

**Conditional (8 fitness labels):**
- `gifford`
- `GFP`
- `TAPE`
- `pab1`
- `bgl3`
- `HIS7`
- `CAPSD`
- `B1LPA6`

**Unconditional:**
- `MSA`
- `MSA_RAW`
- `MDH`

Each dataset provides `<name>-train.csv` and `<name>-test.csv` files.

---

## Output Files

After running PRO-LDM, outputs are organized as:

```
PRO-LDM/
├── train_logs/
│   └── <dataset>/
│       └── checkpoints and logs
├── PROLDM_OUTLIER/
│   ├── test_output/
│   │   └── <dataset>/
│   └── generated_seq/
│       └── <dataset>/
└── data/
    └── <dataset>-train.csv
    └── <dataset>-test.csv
```

- **Checkpoints** — Trained JT-AE + LDM weights
- **test_output/** — Evaluation metrics and fitness predictions
- **generated_seq/** — Sampled protein sequences in FASTA/CSV format

---

## Functional Optimization with Classifier-Free Guidance

PRO-LDM supports **classifier-free guidance** to steer generation toward desired properties or away from the training distribution for novel functional variants.

**Concept:**
- Train the model with random label dropout
- At sampling time, interpolate between conditional and unconditional score estimates
- Guidance scale `ω` controls strength of conditioning / outlier tendency

```bash
# Higher ω pushes sequences toward the target label more strongly
python main.py \
  --mode sample \
  --dataset TAPE \
  --dif_sample_label 1 \
  --dif_sample_epoch 1000 \
  --guidance_scale 2.0
```

**Typical workflow:**
1. Train on your labeled variant dataset
2. Sample with `dif_sample_label` set to the desired fitness class
3. Increase guidance scale to trade naturalness for higher predicted fitness
4. Validate top sequences experimentally or with structure predictors

---

## Pipeline Integration

PRO-LDM can replace **Stage 2** (sequence design) when you have fitness labels, or complement other Stage 2 tools.

### Scenario A: Fitness-Guided Sequence Optimization

| Stage | Tool | Purpose |
|-------|------|---------|
| 0 | PDBFixer | Fix input structure |
| 1 | RFdiffusion / TopoDiff | Generate backbone scaffolds |
| 2 | **PRO-LDM** | Generate sequences conditioned on desired fitness |
| 3 | AlphaFold3 / Boltz-1 | Validate structures |
| 4 | Filtering | Rank by pLDDT + predicted fitness |

### Scenario B: Sequence-Only Library Generation

| Stage | Tool | Purpose |
|-------|------|---------|
| 1 | **PRO-LDM** (unconditional) | Generate diverse sequence library |
| 2 | ESMFold / OmegaFold | Predict structures for screening |
| 3 | Filtering | Select by confidence + diversity |

### Recommended pairings
- Backbone + sequence with fitness goal → RFdiffusion → PRO-LDM → AlphaFold3
- Sequence-only functional optimization → PRO-LDM → ESMFold
- Commercial use → PRO-LDM → Boltz-1 / Chai-1

---

## When to Use PRO-LDM vs Other Stage 2 Tools

| Your Goal | Best Tool |
|-----------|-----------|
| Sequence for a given backbone (general) | ProteinMPNN |
| Sequence for a ligand-aware backbone | LigandMPNN |
| Partial masking / variant scoring | ESM-IF1 |
| Fitness-conditional sequence generation | **PRO-LDM** |
| OOD / outlier functional optimization | **PRO-LDM** |
| Sequence + structure joint generation | ProteinGenerator / MultiFlow |
| MIT license required | **PRO-LDM** / ProteinMPNN |

---

## Strengths and Limitations

**Strengths:**
- MIT license
- Explicit conditional generation via fitness labels
- Integrated fitness prediction (no separate model needed)
- Classifier-free guidance for controllable OOD design
- Works in latent space → computationally efficient sampling

**Limitations:**
- Requires labeled training data for conditional tasks
- Does **not** take a PDB structure as direct input (sequence-only / MSA-based)
- Training from scratch can take hours even on 4×V100
- Smaller community than ProteinMPNN / ESM-IF1

---

## Citation

Zhang et al., "PRO-LDM: A Conditional Latent Diffusion Model for Protein Sequence Design and Functional Optimization," *Advanced Science*, e02723, 2025.

```bibtex
@article{zhang2025pro,
  title={PRO-LDM: A Conditional Latent Diffusion Model for Protein Sequence Design and Functional Optimization},
  author={Zhang, Sitao and Jiang, Zixuan and Huang, Rundong and Huang, Wenting and Peng, Siyuan and Mo, Shaoxun and Zhu, Letao and Li, Peiheng and Zhang, Ziyi and Pan, Emily and others},
  journal={Advanced Science},
  pages={e02723},
  year={2025},
  publisher={Wiley Online Library}
}
```

---

## See Also

- `sequence-design` — ProteinMPNN for general sequence design
- `ligandmpnn-design` — Ligand-aware sequence design
- `esm-if1-design` — Partial masking and variant scoring
- `protein-generator` — Joint sequence + structure diffusion
- `multiflow-codesign` — Joint sequence + backbone co-design
- `structure-generation` — Stage 1 backbone generation
- `pipeline-selection` — Choose the right workflow

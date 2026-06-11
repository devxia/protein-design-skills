---
name: topodiff-workflow
description: Guide for using TopoDiff to generate protein backbones with topology-aware latent encoding and unconditional or length-controlled sampling
---

# TopoDiff Workflow Guide

**TopoDiff** is a diffusion-based protein backbone generator that learns a **global-geometry-aware latent representation** to improve coverage and controllability. Published in *Nature Machine Intelligence* (June 2025), it is developed by Tsinghua University (Gong Lab) and released under the MIT license.

Use TopoDiff when you want:
- Unconditional backbone generation with strong coverage/diversity
- Length-controlled sampling (50–250 residues)
- A lightweight, MIT-licensed Stage 1 alternative to RFdiffusion
- Topology-aware latent control over generated structures

---

## What Makes TopoDiff Different

| Feature | RFdiffusion | TopoDiff |
|---------|-------------|----------|
| Input control | Contig strings + motifs | Length range + sampling mode |
| Latent space | None (direct structure diffusion) | Global-geometry-aware latent encoding |
| Sampling modes | General / binder / symmetry | `base`, `designability`, `novelty`, `all_round` |
| License | BSD (RFdiffusion v1) | **MIT** |
| Length range | Flexible | Optimized for 50–250 residues |
| Code size | Full RFdiffusion repo | Compact PyTorch implementation |

TopoDiff is especially useful for **exploring diverse backbone libraries** and **benchmarking coverage** against known protein folds.

---

## Installation (Document-Only — Do Not Install)

```bash
# Clone
git clone https://github.com/meneshail/TopoDiff.git
cd TopoDiff/TopoDiff

# Create environment
conda env create -n topodiff_env -f env.yml
conda activate topodiff_env

# Install package
pip install -e .

# Optional: OpenFold for memory-efficient attention
# (adds kernel optimizations but not required)
```

### Download model weights and data

Weights and datasets are hosted on Zenodo:

```bash
# Download from Zenodo record 13879812
# https://zenodo.org/records/13879812

# Expected directory layout
TopoDiff/
├── data/
│   ├── dataset/
│   └── weights/
├── notebook/
└── TopoDiff/
```

**Sources:**
- [GitHub repository](https://github.com/meneshail/TopoDiff)
- [Nature Machine Intelligence paper](https://www.nature.com/articles/s42256-025-01059-x)
- [Zenodo weights and data](https://zenodo.org/records/13879812)
- [Tsinghua web server](https://structpred.life.tsinghua.edu.cn/server_topodiff.html)

---

## Quickstart

### Unconditional sampling by length

```bash
python run_sampling.py \
  -o outputs/topodiff \
  -s 100 -e 120 \
  -i 10 \
  -n 10 \
  -m all_round \
  --gpu 0
```

**Arguments:**

| Flag | Meaning |
|------|---------|
| `-o` | Output directory |
| `-s` | Start length |
| `-e` | End length |
| `-i` | Length interval |
| `-n` | Samples per length |
| `-m` | Sampling mode: `base`, `designability`, `novelty`, `all_round` |
| `-v` | Version tag (default `v1_1_2`) |
| `--gpu` | GPU device index |

### Output layout

```
outputs/topodiff/
├── length_100/
│   ├── sample_0.pdb
│   ├── sample_1.pdb
│   └── ...
├── length_110/
│   ├── sample_0.pdb
│   └── ...
└── ...
```

Each `.pdb` is a backbone-only structure ready for Stage 2 sequence design.

---

## Sampling Modes Explained

| Mode | What it optimizes | Best For |
|------|-------------------|----------|
| `base` | Standard sampling | Quick prototyping |
| `designability` | Higher predicted designability | Designs more likely to host a stable sequence |
| `novelty` | Lower similarity to training set | Exploring novel folds |
| `all_round` | Balanced designability + novelty + diversity | **Recommended default** |

Use `all_round` for most campaigns unless you have a specific reason to favor designability or novelty.

---

## Preprocessing Your Own Data (Optional)

If you want to train or evaluate on custom PDBs:

```bash
topodiff-preprocess \
  --input_dir ./data/raw_pdbs/ \
  --output_dir ./data/processed_data/ \
  --n_worker 32
```

Outputs feature files and `info.json` for training or evaluation.

---

## Evaluation

TopoDiff provides evaluation notebooks in `notebook/`, including `3_metrics.ipynb` for diversity and coverage metrics.

For **designability** (sequence-design + structure-prediction check):

```bash
# Use the separate eval environment
mamba env create -n topodiff_eval -f se3.yml
mamba activate topodiff_eval
cd topodiff_eval
pip install -e .

python topodiff_eval/sc/run_sc.py \
  --gpu_list 0 \
  --sample_root outputs/topodiff \
  --sc_test_root outputs/topodiff_eval \
  --length_list 100 110 120 \
  --n_sample 10 \
  --seq_per_sample 8 \
  --run_phase_1 \
  --run_phase_2
```

This uses standard RMSD (not FrameDiff's mean L2 distance) for designability assessment.

---

## Pipeline Integration

TopoDiff can replace **Stage 1** (backbone generation) in the standard pipeline.

| Stage | Classic Pipeline | TopoDiff Pipeline |
|-------|-----------------|-------------------|
| 0 | PDBFixer | *(not required for unconditional)* |
| 1 | RFdiffusion | **TopoDiff** |
| 2 | ProteinMPNN | ProteinMPNN |
| 3 | AlphaFold3 | AlphaFold3 / Boltz-1 / OmegaFold |
| 4 | Filtering | Filtering |

**Recommended pairings:**
- General exploration → TopoDiff → ProteinMPNN → AlphaFold3
- Fast screening → TopoDiff → ProteinMPNN → OmegaFold / ESMFold
- Commercial use → TopoDiff → ProteinMPNN → Boltz-1 / Chai-1

---

## When to Use TopoDiff vs Other Stage 1 Tools

| Your Goal | Best Tool |
|-----------|-----------|
| Binder design with target structure | RFdiffusion / RFdiffusion3 / BindCraft |
| Motif scaffolding | RFdiffusion / ProteinGenerator |
| All-atom ligand/DNA/RNA design | RFdiffusion3 |
| Unconditional diverse backbones (50–250 aa) | **TopoDiff** |
| Topology-controlled exploration | **TopoDiff** |
| MIT license required | **TopoDiff** |
| Natural language prompting | Chroma |
| Very long proteins (>500 aa) | Chroma / La-Proteina |

---

## Strengths and Limitations

**Strengths:**
- MIT license
- Strong coverage and diversity benchmarks
- Global-geometry-aware latent space improves controllability
- Lightweight compared to RFdiffusion
- Web server available for quick tests

**Limitations:**
- Unconditional / length-controlled only (no target-aware binder mode)
- Optimized for 50–250 residues
- Requires GPU for sampling
- Does not generate sequences — requires Stage 2 (ProteinMPNN)

---

## Citation

Zhang et al., "Improving diffusion-based protein backbone generation with global-geometry-aware latent encoding," *Nature Machine Intelligence*, 2025.

Original preprint:
- Zhang, Ma & Gong, "TopoDiff: Improving Protein Backbone Generation with Topology-aware Latent Encoding," *bioRxiv*, 2023. DOI: [10.1101/2023.12.13.571602](https://doi.org/10.1101/2023.12.13.571602)

---

## See Also

- `structure-generation` — Classic RFdiffusion backbone generation
- `rfdiffusion3-workflow` — All-atom biomolecular interaction design
- `chroma-backbone` — Natural language programmable generation
- `foldflow-backbone` — Flow matching for fast prototyping
- `sequence-design` — Stage 2 with ProteinMPNN
- `fast-screening` — Stage 3 with OmegaFold / ESMFold
- `pipeline-selection` — Choose the right workflow

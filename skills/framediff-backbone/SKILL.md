---
name: framediff-backbone
description: Guide for using FrameDiff, an SE(3) diffusion model for unconditional protein backbone generation and motif scaffolding
---

# FrameDiff Backbone Generation Guide

**FrameDiff** is an **SE(3) diffusion model** for protein backbone generation. It parameterizes protein backbones as a collection of residue frames on the **SE(3)^N** manifold and learns a Riemannian diffusion process over rotations and translations. Published at **ICML 2023**.

Use FrameDiff when you want:
- A **pure diffusion backbone generator** that does not rely on a pretrained structure prediction network
- **Unconditional monomer generation** up to ~500 residues
- **Motif scaffolding** by conditioning on fixed substructures
- An open **MIT-licensed** alternative to RFdiffusion for academic and commercial use

---

## What Makes FrameDiff Different

| Feature | RFdiffusion | FrameDiff | TopoDiff |
|---------|-------------|-----------|----------|
| Core model | RoseTTAFold-based | SE(3) diffusion | Topology-aware VAE + diffusion |
| Needs pretrained structure predictor | Yes | **No** | No |
| License | Non-commercial / Rosetta Commons | **MIT** | MIT |
| Max length | ~600 | **~500** | ~250 |
| Best for | Binders, motifs, symmetry | **Unconditional + motif SE(3)** | Unconditional topology libraries |
| Training code | Available | **Available** | Available |

FrameDiff was one of the first models to show that direct diffusion on **rigid-body frames** (backbone N/Cα/C) could generate designable protein backbones without distilling a folding network.

---

## Installation (Document-Only — Do Not Install)

```bash
# Clone repository
git clone https://github.com/jasonkyuyim/se3_diffusion.git
cd se3_diffusion

# Create conda environment
conda env create -f se3.yml
conda activate se3

# Install as editable package
pip install -e .
```

### Third-party code bundled in repo

The repository includes adapted forks of:
- **OpenFold** (`openfold/`)
- **ProteinMPNN** (`ProteinMPNN/`)
- Several data utilities derived from **AlphaFold**

### Download weights

Two checkpoint files are referenced:
- `weights/paper_weights.pth` — ICML published results
- `weights/best_weights.pth` — improved `base.yaml` results (designability 0.34, diversity 0.61)

**Sources:**
- [GitHub repository](https://github.com/jasonkyuyim/se3_diffusion)
- [ICML 2023 paper](https://arxiv.org/abs/2302.02277)
- [Project page media](https://github.com/jasonkyuyim/se3_diffusion/blob/master/media/denoising.gif)

---

## Quickstart: Generate Backbones

```bash
python experiments/inference_se3_diffusion.py
```

Configuration is in `config/inference.yaml`:

```yaml
inference:
  weights_path: ./weights/paper_weights.pth
  output_dir: ./inference_outputs/
  gpu_id: null
  seed: 123

diffusion:
  num_t: 500
  noise_scale: 0.1
  min_t: 0.01

samples:
  samples_per_length: 10
  seq_per_sample: 8
  min_length: 100
  max_length: 500
  length_step: 5
```

### Key inference parameters

| Parameter | Meaning | Default |
|-----------|---------|---------|
| `num_t` | Number of diffusion sampling steps | 500 |
| `noise_scale` | Sampling temperature | 0.1 |
| `min_t` | Lowest diffusion time | 0.01 |
| `samples_per_length` | Backbone samples per length | 10 |
| `seq_per_sample` | ESMFold + ProteinMPNN sequences per backbone | 8 |
| `min_length` / `max_length` / `length_step` | Length grid to sample | 100–500 by 5 |

---

## Output Format

Inference produces:

```
inference_outputs/
└── 12D_02M_2023Y_20h_46m_13s/
    ├── inference_conf.yaml
    └── length_100/
        ├── sample_0/
        │   ├── bb_traj_1.pdb       # Diffusion trajectory x_{t-1}
        │   ├── sample_1.pdb        # Final backbone
        │   ├── x0_traj_1.pdb       # Model x_0 trajectory
        │   └── self_consistency/
        │       ├── esmf/           # ESMFold structures for MPNN sequences
        │       ├── seqs/sample_1.fa
        │       └── sc_results.csv
        └── sample_1/
```

Each `sample_*.pdb` contains backbone atoms only (N, Cα, C). Use the bundled ProteinMPNN path (`pmpnn_dir`) to automatically design sequences, then fold with ESMFold and summarize self-consistency metrics in `sc_results.csv`.

---

## Training (If Fine-Tuning)

```bash
python experiments/train_se3_diffusion.py
```

Training config lives in `config/base.yaml`. Defaults use 2 GPUs for lengths up to 512; adjust `num_gpus` as needed.

### Data preparation

1. Download PDB in mmCIF format (~1 TB uncompressed).
2. Preprocess:
   ```bash
   python process_pdb_dataset.py --mmcif_dir <pdb_dir>
   ```
3. (Optional) Download 30% sequence identity clusters for clustered training:
   ```bash
   wget https://cdn.rcsb.org/resources/sequence/clusters/clusters-by-entity-30.txt
   ```
   Then set `data.cluster_path` in the config.

### Batching modes

- `time_batch` — multiple timesteps of the same protein
- `length_batch` — multiple proteins of the same length
- `cluster_time_batch` — multiple timesteps from a cluster *(recommended)*
- `cluster_length_batch` — multiple clusters of the same length

---

## Pipeline Integration

FrameDiff is a **Stage 1** backbone generator. A complete pipeline:

| Stage | Tool | Purpose |
|-------|------|---------|
| 0 | PDBFixer | Repair input if motif scaffolding |
| 1 | **FrameDiff** | Generate backbone(s) |
| 2 | ProteinMPNN / LigandMPNN | Design sequences for backbones |
| 3 | AlphaFold3 / Boltz-1 / ESMFold | Validate structures |
| 4 | Filtering | Rank by confidence metrics |

### Recommended pairings
- Fast motif-free libraries → FrameDiff → ProteinMPNN → ESMFold
- High-accuracy design → FrameDiff → ProteinMPNN → AlphaFold3
- Commercial use → FrameDiff → ProteinMPNN → Boltz-1 / Chai-1

---

## When to Use FrameDiff vs Other Stage 1 Tools

| Your Goal | Best Tool |
|-----------|-----------|
| Binder design with hotspots | RFdiffusion |
| All-atom DNA/RNA/ligand design | RFdiffusion3 |
| Topology-aware unconditional libraries | TopoDiff |
| **Direct SE(3) diffusion without folding network** | **FrameDiff** |
| **MIT-licensed backbone generator** | **FrameDiff** |
| Long proteins (>500 aa) | RFdiffusion / Chroma |
| Fast flow-matching sampling | FoldFlow / TopoDiff |

---

## Strengths and Limitations

**Strengths:**
- MIT license
- Does **not** require a pretrained structure prediction network
- Well-documented SE(3) diffusion formulation
- Generates backbones up to ~500 residues
- Includes bundled ProteinMPNN for sequence design and self-consistency evaluation
- Training code available

**Limitations:**
- Backbone-only output (no side chains)
- Designability metrics are lower than RFdiffusion on standard benchmarks
- Requires PDB download (~1 TB) for training
- Multi-GPU training recommended
- Smaller user community than RFdiffusion
- Protein-ligand or symmetric oligomer design is not a primary focus

---

## Citation

Yim et al., "SE(3) diffusion model with application to protein backbone generation," *ICML*, 2023.

```bibtex
@article{yim2023se,
  title={SE(3) diffusion model with application to protein backbone generation},
  author={Yim, Jason and Trippe, Brian L and De Bortoli, Valentin and Mathieu, Emile and Doucet, Arnaud and Barzilay, Regina and Jaakkola, Tommi},
  journal={arXiv preprint arXiv:2302.02277},
  year={2023}
}
```

---

## See Also

- `structure-generation` — RFdiffusion for general backbone generation
- `topodiff-workflow` — Topology-aware unconditional backbones
- `foldflow-backbone` — Flow matching for fast backbone generation
- `rfdiffusion3-workflow` — All-atom biomolecular design
- `sequence-design` — ProteinMPNN for sequence design
- `structure-validation` — Validate with AlphaFold3
- `pipeline-selection` — Choose the right workflow

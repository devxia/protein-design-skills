---
name: fadiff-multimotif
description: Guide for using FADiff, a floating anchor diffusion model for multi-motif protein backbone scaffolding
---

# FADiff Multi-Motif Scaffolding Guide

**FADiff** (Floating Anchor Diffusion) is a protein backbone generation model specialized for **multi-motif scaffolding**. It treats each motif as a **rigid floating anchor** that can move independently during diffusion, automatically learning the relative spatial arrangement of multiple functional motifs. Published at **ICML 2024**.

Use FADiff when you want:
- To scaffold **multiple functional motifs** into a single protein structure
- To **automatically design motif positions** instead of fixing them manually
- A method that **generalizes from 2-motif training to arbitrary numbers of motifs**
- A **guarantee of motif presence** in generated backbones

---

## What Makes FADiff Different

| Feature | Standard inpainting | Conditional generation | FADiff |
|---------|---------------------|------------------------|--------|
| Motif position | Fixed by user | Learned, no guarantee | **Learned and guaranteed** |
| Number of motifs | Usually 1–2 | Struggles with >2 | **Arbitrary (generalizes from 2)** |
| Motif representation | Backbone fragment | Embedding | **Rigid floating anchor (SE3)** |
| Training base | — | — | **FrameDiff** |
| License | Varies | Varies | **BSD-2 (academic non-commercial)** |

FADiff addresses the core problem of multi-motif scaffolding: you know which functional motifs must be present, but you do not know their correct relative positions. By letting motifs float as rigid anchors during diffusion, the model learns where to place them.

---

## Installation (Document-Only — Do Not Install)

```bash
# Clone repository
git clone https://github.com/aim-uofa/FADiff.git
cd FADiff

# Create conda environment
conda env create -f FADiff.yml
conda activate fadiff

# Install as editable package
pip install -e .
```

### Training data (only if training or fine-tuning)

Like FrameDiff, training requires a local PDB mirror:

1. Download PDB in mmCIF format (~1 TB uncompressed) from [RCSB](https://www.wwpdb.org/ftp/pdb-ftp-sites#rcsbpdb).
2. Unzip all files:
   ```bash
   gzip -d **/*.gz
   ```
3. Preprocess:
   ```bash
   python process_pdb_dataset.py --mmcif_dir <pdb_dir>
   ```
4. (Optional) Download 30% sequence identity clusters for clustered training:
   ```bash
   wget https://cdn.rcsb.org/resources/sequence/clusters/clusters-by-entity-30.txt
   ```
   Then set `data.cluster_path` in the config.

### Training

```bash
bash train.sh
```

This launches distributed training on 8 GPUs. The config lives in `config/train.yaml`.

**Sources:**
- [GitHub repository](https://github.com/aim-uofa/FADiff)
- [ICML 2024 paper](https://openreview.net/forum?id=CtgJUQxmEo)
- [Project page](https://ai4mol.github.io/projects/FADiff/)

---

## Quickstart: Multi-Motif Scaffolding

FADiff follows the same Hydra-based inference pattern as FrameDiff:

```bash
python experiments/inference_se3_diffusion.py
```

The inference config is in `config/inference.yaml`. Key settings are similar to FrameDiff:

```yaml
inference:
  weights_path: ./weights/best_weights.pth
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

### Specifying multiple motifs

Motifs are provided as PDB files. During inference, FADiff treats each motif as a floating anchor. The exact config syntax for motif input is defined in `config/inference.yaml` and the inference script; refer to the repository for the latest format.

A typical multi-motif contig might look like:

```yaml
motif_contigs:
  - "A1-21;/;B1-15;/;0-100"   # motif A, motif B, generated scaffold
```

> The motif contig syntax is inherited from FrameDiff with `;/;` for chain breaks. Check the repository's example configs for the exact supported expressions.

---

## Output Format

FADiff produces the same nested output structure as FrameDiff:

```
inference_outputs/
└── 12D_02M_2023Y_20h_46m_13s/
    ├── inference_conf.yaml
    └── length_150/
        ├── sample_0/
        │   ├── sample_1.pdb        # Final scaffolded backbone
        │   ├── bb_traj_1.pdb       # Diffusion trajectory
        │   ├── x0_traj_1.pdb       # Model x_0 trajectory
        │   └── self_consistency/
        │       ├── esmf/           # ESMFold predictions for MPNN sequences
        │       ├── seqs/sample_1.fa
        │       └── sc_results.csv
        └── sample_1/
```

- `sample_*.pdb` — generated backbone with motifs placed
- `seqs/sample_*.fa` — ProteinMPNN-designed sequences
- `sc_results.csv` — self-consistency metrics summary

---

## Pipeline Integration

FADiff is a **Stage 1** backbone generator specialized for multi-motif scaffolding.

| Stage | Tool | Purpose |
|-------|------|---------|
| 0 | PDBFixer | Repair input motif structures |
| 1 | **FADiff** | Generate scaffold around multiple floating motifs |
| 2 | ProteinMPNN / PiFold | Design sequences for the scaffold |
| 3 | AlphaFold3 / Boltz-1 / ESMFold | Validate structures |
| 4 | Filtering | Rank by confidence and motif RMSD |

### Recommended pairings
- Multiple functional motifs → FADiff → ProteinMPNN → AlphaFold3
- Fast screening → FADiff → PiFold → ESMFold
- Commercial use → FADiff → ProteinMPNN → Boltz-1 / Chai-1

---

## When to Use FADiff vs Other Motif Scaffolding Tools

| Your Goal | Best Tool |
|-----------|-----------|
| Single motif with fixed position | RFdiffusion inpainting |
| 2–3 motifs with known relative positions | RFdiffusion / FrameDiff |
| **Arbitrary number of motifs with unknown positions** | **FADiff** |
| All-atom motif scaffolding with side-chain conditioning | Protpardelle-1c |
| Topology-aware unconditional backbones | TopoDiff |
| MIT-licensed general motif scaffolding | FrameDiff / RFdiffusion |

---

## Strengths and Limitations

**Strengths:**
- Guarantees motif presence in generated backbones
- Automates motif position design (no expert placement needed)
- Generalizes from 2-motif training to arbitrary motif counts
- Built on top of the well-documented FrameDiff SE(3) diffusion framework
- Strong theoretical framing from ICML 2024

**Limitations:**
- **Non-commercial BSD-2 license** — contact authors for commercial use
- Backbone-only output (no side chains)
- Requires PDB mirror (~1 TB) for training
- Multi-GPU training recommended
- Inference API less mature than RFdiffusion
- Smaller community and fewer tutorials than RFdiffusion

---

## Citation

Liu et al., "Floating Anchor Diffusion Model for Multi-motif Scaffolding," *ICML*, 2024.

```bibtex
@article{liu2024floating,
    title={Floating Anchor Diffusion Model for Multi-motif Scaffolding},
    author={Liu, Ke and Mao, Weian and Shen, Shuaike and Jiao, Xiaoran and Sun, Zheng and Chen, Hao and Shen, Chunhua},
    booktitle={Forty-first International Conference on Machine Learning},
    year={2024},
    url={https://openreview.net/forum?id=CtgJUQxmEo}
}
```

---

## See Also

- `framediff-backbone` — SE(3) diffusion backbone generation (FADiff is built on this)
- `structure-generation` — RFdiffusion for general motif scaffolding
- `protpardelle-allatom` — All-atom motif scaffolding with side-chain conditioning
- `topodiff-workflow` — Topology-aware unconditional backbones
- `sequence-design` — ProteinMPNN for sequence design
- `pifold-sequence-design` — Fast MIT-licensed inverse folding
- `pipeline-selection` — Choose the right workflow

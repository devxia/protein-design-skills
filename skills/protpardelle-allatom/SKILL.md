---
name: protpardelle-allatom
description: Guide for using Protpardelle-1c, an MIT-licensed all-atom protein generative model with motif scaffolding, binder generation, and multichain support
---

# Protpardelle-1c All-Atom Generation Guide

**Protpardelle-1c** is an **MIT-licensed all-atom protein generative model** from the Stanford Protein Design Lab. It codesigns protein **sequence and full-atom structure** (backbone + side chains) via a diffusion-based approach, and supports unconditional sampling, motif scaffolding, binder generation, and multichain complexes.

Use Protpardelle-1c when you want:
- **All-atom generation** without a separate sequence design stage
- **Motif scaffolding** with side-chain conditioning (outperforms RFdiffusion on MotifBench)
- **Binder generation** with hotspot conditioning
- **Multichain / complex generation** including homo/hetero-oligomers
- A **permissive MIT license** for both academic and commercial use

---

## What Makes Protpardelle-1c Different

| Feature | RFdiffusion3 | La-Proteina | Protpardelle-1c |
|---------|-------------|-------------|-----------------|
| Output | All-atom | All-atom (seq+struct) | **All-atom (seq+struct)** |
| Motif scaffolding | Yes | Yes | **Yes, with side-chain conditioning** |
| Multichain complexes | Yes | Yes | **Yes** |
| Binder generation | Yes | Yes | **Yes, with hotspots** |
| Parameters | Large | Large | **~22M (compact)** |
| License | Non-commercial / Rosetta Commons | Research / NVIDIA | **MIT** |

Protpardelle-1c is especially strong at **MotifBench**-style multi-motif scaffolding because it can condition on side-chain atom positions, not just backbone frames. The `cc58` backbone-only model scores 28.16 on MotifBench (vs RFdiffusion 21.27), and sampling 3,000 backbones takes ~40 minutes on an A100-80GB.

---

## Installation (Document-Only — Do Not Install)

```bash
# Clone repository
git clone https://github.com/ProteinDesignLab/protpardelle-1c.git
cd protpardelle-1c

# Create environment
conda create -n protpardelle python=3.12 --yes
conda activate protpardelle

# Install dependencies
bash setup.sh

# Download model weights and configs
bash download_model_params.sh
```

### External dependencies

- `gcc >= 12.4`
- `cuda >= 12.4`
- [Foldseek](https://github.com/steineggerlab/foldseek) (must be on `PATH` or set `FOLDSEEK_BIN`)
- ProteinMPNN and LigandMPNN weights (for sequence design)
- ESMFold weights (for validation)

### Optional per-clone environment

Create `<project_root>/.protpardelle.env` to override `PROTPARDELLE_OUTPUT_DIR` without changing shell config:

```bash
PROTPARDELLE_OUTPUT_DIR=/abs/path/to/this/clone/output_dir
```

**Sources:**
- [GitHub repository](https://github.com/ProteinDesignLab/protpardelle-1c)
- [Original Protpardelle paper (PNAS)](https://www.pnas.org/doi/10.1073/pnas.2311500121)
- [Protpardelle-1c preprint (bioRxiv)](https://www.biorxiv.org/content/10.1101/2025.08.18.670959v2)
- [MotifBench samples (Zenodo)](https://zenodo.org/records/16651614)
- [RFdiffusion/La-Proteina samples (Zenodo)](https://zenodo.org/records/16887802)
- [BindCraft samples (Zenodo)](https://zenodo.org/records/17096818)

---

## Quickstart: Sampling

All sampling is done with `python3 -m protpardelle.sample <config> --motif-dir <dir> [options]`.

### Unconditional sampling

```bash
python3 -m protpardelle.sample \
  examples/sampling/00_unconditional.yaml \
  --num-samples 8 \
  --num-mpnn-seqs 0
```

### Motif scaffolding

```bash
python3 -m protpardelle.sample \
  examples/sampling/02_motif_scaffolding.yaml \
  --motif-dir examples/motifs/nanobody \
  --num-samples 8 \
  --num-mpnn-seqs 0
```

### Binder generation

```bash
python3 -m protpardelle.sample \
  examples/sampling/04_bindcraft.yaml \
  --motif-dir examples/motifs/bindcraft/ \
  --num-samples 100 \
  --num-mpnn-seqs 2 \
  --use-wandb
```

### Multichain complex

```bash
python3 -m protpardelle.sample \
  examples/sampling/05_multichain.yaml \
  --motif-dir examples/motifs/nanobody/ \
  --num-samples 8 \
  --num-mpnn-seqs 0
```

### Partial diffusion / inpainting

```bash
python3 -m protpardelle.sample \
  examples/sampling/01_partial_diffusion.yaml \
  --motif-dir examples/motifs/nanobody \
  --num-samples 8 \
  --num-mpnn-seqs 0
```

---

## Model Selection

| Model | Monomers | Multichain | Type | Best For |
|-------|----------|------------|------|----------|
| `bb81_epoch450` | 1 | 0 | Backbone | Unconditional on AI-CATH |
| `bbmd_epoch500` | 1 | 0 | Backbone | Unconditional on MD-CATH |
| `cc58_epoch416` | 1 | 0 | Backbone | **MotifBench benchmark / motif scaffolding** |
| `cc83_epoch2616` | 0.5 | 0.5 | Backbone | Binder / multichain backbone generation |
| `cc89_epoch415` | 1 | 0 | All-atom (sequence mask) | Structure refinement with fixed sequence |
| `cc91_epoch383` | 1 | 0 | All-atom (no mask) | **All-atom single-chain conditional generation** |
| `cc94_epoch3100` | 0.5 | 0.5 | All-atom (no mask) | Multichain all-atom generation |
| `cc95_epoch3490` | 0.5 | 0.5 | Backbone | Multichain with heavier hotspot dropout |

Recommended starting points:
- **Motif scaffolding (backbone)** → `cc58`
- **All-atom conditional generation** → `cc91`
- **Binder generation** → `cc83` or `cc95`
- **Multichain complexes** → `cc94` or `cc95`

---

## Config Key Parameters

```yaml
search_space:
  models: [[cc58, epoch416, sampling_sidechain_conditional]]
  step_scales: [1.2]            # lower = more diverse; higher = more native-like
  schurns: [200]                # stochasticity; 0 = ODE sampling
  crop_cond_starts: [0.0]
  translations: [[0.0, 0.0, 0.0]]

motifs: [7eow_CDR3_atom_rot_128]
motif_contigs: ["0-100;A1-21;0-100"]
total_lengths: [[100]]
hotspots: [null]
ssadj: [null]
```

### `motif_contigs` syntax

Similar to RFdiffusion, but chain breaks are written as `;/;`:

- `0-100;A1-21;0-100` — scaffold → motif A1-21 → scaffold
- `A1-128;/;120-120` — target chain + 120-res generated binder chain
- `F1-18;/;H1-92;/;20-40;D6-82;10-30;D101-125;20-40;A1-12;10-20` — multi-motif complex scaffold

---

## Output Format

Results are saved under `PROTPARDELLE_OUTPUT_DIR` (default `<project_root>/results/`):

```
results/
└── sampling-experiment-name
    └── cc58-epoch416-...-rewindNone
        └── motif-pdb-stem
            ├── scaffold_info.csv
            ├── motif-pdb-stem_0.pdb
            ├── motif-pdb-stem_1.pdb
            └── ...
```

- `scaffold_info.csv` — summary metrics per sample (follows MotifBench spec)
- `*.pdb` — generated structures (backbone or all-atom depending on model)
- Sequence design outputs are created when `--num-mpnn-seqs > 0`

---

## Likelihood Evaluation

Compute likelihoods or extract latents for downstream analysis:

```bash
python3 -m protpardelle.likelihood \
  --model-name cc58 --epoch 416 \
  --pdb-path examples/motifs/nanobody
```

---

## Training

Protpardelle-1c training uses SLURM by default:

```bash
sbatch scripts/train.sbatch cc58 /path/to/experiments
```

For interactive debug:

```bash
source scripts/train.sbatch cc58 /path/to/experiments --debug
```

Public training datasets:
- [AI-CATH](https://zenodo.org/records/15881564) — designable subset (337,936 structures)
- [Boltz Interfaces](https://zenodo.org/records/16002744) — PDB chain pairs
- [Secondary Structure / Adjacency](https://zenodo.org/records/16988261) — pre-computed `ssadj` inputs

---

## Pipeline Integration

Protpardelle-1c is a **Stage 1 (+ Stage 2)** tool because it outputs full-atom structures with sequences.

| Stage | Tool | Purpose |
|-------|------|---------|
| 0 | PDBFixer | Repair input motif / target structures |
| 1 | **Protpardelle-1c** | Generate all-atom structure conditioned on motif/hotspot |
| 2 | *(optional)* ProteinMPNN / LigandMPNN | Redesign sequences if needed |
| 3 | AlphaFold3 / Boltz-1 / ESMFold | Validate predicted structure matches design |
| 4 | Filtering | Rank by confidence and novelty |

### Recommended pairings
- Fast all-atom motif scaffolding → Protpardelle-1c `cc91` → ESMFold validation
- High-accuracy binder design → Protpardelle-1c `cc83/cc95` → AlphaFold3 or Boltz-1
- Commercial pipeline → Protpardelle-1c (MIT) → Boltz-1 / Chai-1 validation

---

## When to Use Protpardelle-1c vs Other All-Atom Tools

| Your Goal | Best Tool |
|-----------|-----------|
| All-atom ligand/DNA/RNA/enzyme design | RFdiffusion3 |
| NVIDIA-backed joint seq+structure with natural language | La-Proteina |
| **MIT-licensed all-atom motif scaffolding** | **Protpardelle-1c** |
| **Compact model (~22M params) for fast sampling** | **Protpardelle-1c** |
| Binder generation with hotspot conditioning | **Protpardelle-1c** |
| Multichain complex generation | **Protpardelle-1c** |
| Pocket redesign | PocketGen |

---

## Strengths and Limitations

**Strengths:**
- MIT license (commercial-friendly)
- All-atom sequence+structure co-design
- Strong MotifBench performance with side-chain conditioning
- Supports binder, multichain, partial diffusion, and unconditional sampling
- Compact model (~22M parameters) with fast sampling
- Active development and extensive documentation

**Limitations:**
- Requires CUDA >= 12.4 and gcc >= 12.4
- Requires external tools (Foldseek, ProteinMPNN, LigandMPNN, ESMFold)
- Training requires SLURM or manual adaptation for non-cluster environments
- All-atom models are more memory-intensive than backbone-only models
- Newer than RFdiffusion, so fewer community tutorials

---

## Citation

Original Protpardelle:

```bibtex
@article{doi:10.1073/pnas.2311500121,
  title={An all-atom protein generative model},
  author={Chu, Alexander E. and Kim, Jinho and Cheng, Lucy and El Nesr, Gina and Xu, Minkai and Shuai, Richard W. and Huang, Po-Ssu},
  journal={Proceedings of the National Academy of Sciences},
  volume={121},
  number={27},
  pages={e2311500121},
  year={2024},
  doi={10.1073/pnas.2311500121}
}
```

Protpardelle-1c update:

```bibtex
@article{Lu2025.08.18.670959,
  title={Conditional Protein Structure Generation with Protpardelle-1C},
  author={Lu, Tianyu and Shuai, Richard and Kouba, Petr and Li, Zhaoyang and Chen, Yilin and Shirali, Akio and Kim, Jinho and Huang, Po-Ssu},
  journal={bioRxiv},
  year={2025},
  doi={10.1101/2025.08.18.670959}
}
```

---

## See Also

- `rfdiffusion3-workflow` — All-atom DNA/RNA/ligand/enzyme design
- `rfdiffusion-all-atom` — Ligand/cofactor-aware all-atom design
- `la-proteina-backbone` — NVIDIA joint sequence + structure generation
- `protein-generator` — Joint seq+struct via RoseTTAFold diffusion
- `pocketgen-ligand` — Pocket redesign around ligand
- `structure-validation` — Validate with AlphaFold3 / Boltz-1
- `pipeline-selection` — Choose the right workflow

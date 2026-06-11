---
name: diffdock-ligand
description: Guide for using DiffDock, an MIT-licensed diffusion-based method for blind small-molecule protein docking
---

# DiffDock Small-Molecule Docking Guide

**DiffDock** is an **MIT-licensed diffusion model** for **small-molecule protein docking**. Unlike traditional docking tools that require a predefined binding pocket, DiffDock performs **blind docking**: it predicts the 3D binding pose of a ligand given only a protein structure and a ligand description (SMILES or SDF).

Use DiffDock when you want:
- **Blind docking** without specifying a search box or binding site
- A **diffusion-based generative model** that ranks poses with a confidence model
- **Batch virtual screening** of many ligands against one or more proteins
- A **permissive MIT license** for both academic and commercial use
- To validate whether a designed ligand-binding protein actually accommodates your ligand

---

## What Makes DiffDock Different

| Feature | AutoDock Vina | GNINA | DiffDock |
|---------|---------------|-------|----------|
| Requires binding box | Yes | Yes | **No (blind docking)** |
| Handles protein flexibility | Limited | Limited | **Implicit via diffusion** |
| Input | Pocket-limited | Pocket-limited | **Full protein + ligand** |
| Speed (per complex) | Minutes | Minutes | **~GPU-seconds to minutes** |
| License | Apache 2.0 | GPL | **MIT** |

DiffDock is especially useful as a **downstream validation step** after ligand-aware protein design: generate a protein scaffold with `rfdiffusion-all-atom` or `rfdiffusion3-workflow`, design sequences with `ligandmpnn-design`, validate the structure with `rosettafold-all-atom` or `boltz-validation`, then dock the ligand with DiffDock to confirm the pose and confidence.

---

## Installation (Document-Only — Do Not Install)

```bash
git clone https://github.com/gcorso/DiffDock.git
cd DiffDock
conda env create --file environment.yml
conda activate diffdock
```

Docker alternative:

```bash
docker pull rbgcsail/diffdock
# Run interactively with GPU
docker run -it --gpus all --entrypoint /bin/bash rbgcsail/diffdock
# Inside container
micromamba activate diffdock
```

First run precomputes SO(2)/SO(3) lookup tables (a couple of minutes).

**Sources:**
- [GitHub repository](https://github.com/gcorso/DiffDock)
- [Paper — ICLR 2023](https://arxiv.org/abs/2210.01776)
- [DiffDock-L update](https://arxiv.org/abs/2402.18396)
- [Model weights](https://zenodo.org/record/7791794) (DiffDock-L on Hugging Face via the repo)

---

## Quickstart: Dock One Ligand

```bash
python -m inference \
  --config default_inference_args.yaml \
  --protein_path protein.pdb \
  --ligand "COc(cc1)ccc1C#N" \
  --out_dir outputs/diffdock/single
```

Inputs:
- `--protein_path` — PDB file (or use `--protein_sequence` for ESMFold folding on the fly)
- `--ligand` — SMILES string, or path to `.sdf`/`.mol2`

Outputs:
- Docked poses in `--out_dir`
- Confidence score per pose:
  - `c > 0` — high confidence
  - `-1.5 < c < 0` — moderate confidence
  - `c < -1.5` — low confidence

Visualize with:

```bash
python -m inference ... --save_visualisation
```

This writes `.sdf` files you can open in PyMOL or Chimera.

---

## Batch Virtual Screening

Prepare a CSV with columns `complex_name`, `protein_path`, `ligand_description`, and optionally `protein_sequence`:

```csv
complex_name,protein_path,ligand_description
7L10_docked,proteins/7l10.pdb,COc(cc1)ccc1C#N
6M1U_hit,proteins/6m1u.pdb,Cc1ccccc1O
```

Run:

```bash
python -m inference \
  --config default_inference_args.yaml \
  --protein_ligand_csv screen.csv \
  --out_dir outputs/diffdock/batch \
  --batch_size 10
```

---

## Pipeline Integration

DiffDock is a **Stage 4 analysis / validation add-on** for ligand-aware design campaigns:

| Stage | Typical Tool | Purpose |
|-------|--------------|---------|
| 0 | PDBFixer | Repair target and ligand structures |
| 1 | RFdiffusionAA / RFdiffusion3 | Generate ligand-aware scaffold |
| 2 | LigandMPNN | Design sequences around the ligand |
| 3 | AlphaFold3 / Boltz-1 / RFAA | Validate apo/holo structure |
| **4b** | **DiffDock** | **Dock ligand into predicted structure and score poses** |

### Recommended pairings
- De novo enzyme design → `rfdiffusion-all-atom` → `ligandmpnn-design` → `boltz-validation` → **DiffDock**
- Binder + small-molecule cofactor → `rfdiffusion3-workflow` → `ligandmpnn-design` → `rosettafold-all-atom` → **DiffDock**
- Virtual screen against an AlphaFold2 model → ESMFold target → **DiffDock** batch mode

---

## Hardware & Timing

- **GPU strongly recommended** (CPU is significantly slower)
- First run: ~2 minutes to build SO(2)/SO(3) lookup tables
- Typical inference: seconds to minutes per complex depending on protein size and number of diffusion steps

---

## Interpreting Confidence Scores

DiffDock outputs a confidence value for each sampled pose. In practice:

| Confidence | Interpretation |
|------------|----------------|
| `c > 0` | High-confidence pose — good candidate for downstream analysis |
| `-1.5 < c < 0` | Moderate confidence — inspect visually, consider ensemble docking |
| `c < -1.5` | Low confidence — pose unreliable, redesign pocket or ligand |

For virtual screening, rank compounds by top pose confidence and visually inspect the top 10–20 hits.

---

## Strengths and Limitations

**Strengths:**
- MIT license (commercial-friendly)
- Blind docking — no binding box required
- State-of-the-art pose prediction on standard benchmarks
- Supports batch virtual screening
- Can fold protein sequences on the fly with ESMFold
- Active community and follow-up work (DiffDock-L)

**Limitations:**
- GPU required for practical throughput
- Conda environment is heavy (PyTorch Geometric, RDKit, ESM)
- Confidence scores are useful but not a perfect proxy for experimental affinity
- Best for single-chain monomers; multimeric docking requires caution
- Does not predict binding affinity — only pose and confidence

---

## Citation

Corso et al., "DiffDock: Diffusion Steps, Twists, and Turns for Molecular Docking," *ICLR*, 2023.

```bibtex
@inproceedings{corso2023diffdock,
  author = {Corso, Gabriele and Stärk, Hannes and Jing, Bowen and Barzilay, Regina and Jaakkola, Tommi},
  title = {DiffDock: Diffusion Steps, Twists, and Turns for Molecular Docking},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year = {2023},
  url = {https://arxiv.org/abs/2210.01776}
}
```

---

## See Also

- `rfdiffusion-all-atom` — Ligand-aware protein backbone generation
- `rfdiffusion3-workflow` — All-atom biomolecular interaction design
- `ligandmpnn-design` — Ligand-aware sequence design
- `pocketgen-ligand` — Pocket redesign around a ligand
- `rosettafold-all-atom` — Validate protein-ligand complexes
- `boltz-validation` — MIT-licensed structure validation
- `pipeline-selection` — Choose the right workflow
- `periodic-summary` — Track docking outputs across batches

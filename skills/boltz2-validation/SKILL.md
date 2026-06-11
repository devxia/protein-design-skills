---
name: boltz2-validation
description: Guide for using Boltz-2, an MIT-licensed biomolecular interaction model that predicts both 3D structures and binding affinities
---

# Boltz-2 Structure + Affinity Validation Guide

**Boltz-2** is the next-generation open-source biomolecular interaction model from MIT Jameel Clinic and Recursion. Released under the **MIT license**, it predicts not only **3D structures** of protein complexes, protein-ligand systems, nucleic acids, and covalent modifications, but also **binding affinities** — approaching the accuracy of physics-based free-energy perturbation (FEP) methods while running **~1000× faster**.

Use Boltz-2 when you want:
- **Structure validation** with an MIT-licensed alternative to AlphaFold3
- **Binding affinity prediction** for hit discovery and ligand optimization
- **Single consumer GPU inference** (~18 seconds per protein-ligand affinity prediction)
- A unified model that handles proteins, ligands, DNA, RNA, and covalent modifications
- To replace or augment `boltz-validation` (Boltz-1) in your pipeline

---

## What Makes Boltz-2 Different

| Feature | AlphaFold3 | Boltz-1 | Boltz-2 |
|---------|------------|---------|---------|
| Structure prediction | Yes | Yes | **Yes** |
| License | Non-commercial | MIT | **MIT** |
| Binding affinity | No | No | **Yes** |
| Speed vs FEP | N/A | N/A | **~1000× faster** |
| Covalent modifications | Limited | Yes | **Yes** |
| Nucleic acids | Yes | Yes | **Yes** |

Boltz-2 is the first deep-learning model to approach FEP-level affinity accuracy, making it especially valuable for **drug-discovery campaigns** where ranking ligands by predicted affinity is as important as getting the right pose.

---

## Installation (Document-Only — Do Not Install)

```bash
# PyPI (recommended)
pip install boltz[cuda] -U

# Or install from source
git clone https://github.com/jwohlwend/boltz.git
cd boltz
pip install -e .[cuda]
```

For CPU-only machines, omit `[cuda]` (significantly slower).

First run downloads model weights to `~/.boltz/` (override with `--cache` or `BOLTZ_CACHE`).

**Sources:**
- [GitHub repository](https://github.com/jwohlwend/boltz)
- [Boltz-2 project page](https://boltz.bio/boltz2)
- [Boltz-2 preprint](https://doi.org/10.1101/2025.06.14.659707)
- [Boltz2_affinity fine-tuning repo](https://github.com/molecularinformatics/Boltz2_affinity)
- [MIT + Recursion launch announcement](https://www.biopharmatrend.com/post/1289-mit-and-recursion-launch-boltz-2-open-source-ai-foundation-model-for-structure-and-binding-affinity-prediction)

---

## Quickstart: Predict Structure

Write a YAML input file:

```yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: GSHSMRYFYTAMSRPGRGEPRFIAVGYVDDTQFVRFDSDAASPRGEPRAPWVEQEGPEYWDRETQKYKRQAQTDRVDLGTLRGYYNQSEAGSHTLQWMYGCDLGPDGRLLRGYDQSAYDGKDYIALNEDLRSWTAADTAAQISQRKLEAARAAEQLRAYLEGTCVEWLRRYLENGKETLQRA
  - ligand:
      id: B
      smiles: 'CC(C)Cc1ccc(C(C)C(=O)O)cc1'
```

Run:

```bash
boltz predict design.yaml --use_msa_server --out_dir outputs/boltz2
```

Outputs (default `mmcif`):

```
outputs/boltz2/
└── design/
    ├── design_0.cif          # Predicted structure
    ├── confidence.json       # pLDDT, pTM, ipTM, etc.
    └── ...
```

---

## Quickstart: Predict Affinity

Add an `affinity` property under `properties`:

```yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: GSHSMRYFYTAMSRPGRGEPRFIAVGYVDDTQFVRFDSDAASPRGEPRAPWVEQEGPEYWDRETQKYKRQAQTDRVDLGTLRGYYNQSEAGSHTLQWMYGCDLGPDGRLLRGYDQSAYDGKDYIALNEDLRSWTAADTAAQISQRKLEAARAAEQLRAYLEGTCVEWLRRYLENGKETLQRA
  - ligand:
      id: B
      smiles: 'CC(C)Cc1ccc(C(C)C(=O)O)cc1'
properties:
  - affinity:
      binder: B
```

Run:

```bash
boltz predict design_affinity.yaml --use_msa_server --out_dir outputs/boltz2_affinity
```

Affinity outputs:

| Field | Meaning | Use Case |
|-------|---------|----------|
| `affinity_probability_binary` | Probability 0–1 that the ligand is a binder | Hit discovery (binder vs decoy) |
| `affinity_pred_value` | log10(IC50) in μM | Compare binders / optimize small modifications |

High `affinity_probability_binary` (>0.5) plus low (more negative) `affinity_pred_value` indicates a stronger predicted binder.

---

## CLI Reference (`boltz predict`)

| Flag | Description | Default |
|------|-------------|---------|
| `--out_dir` | Output directory | `./` |
| `--cache` | Model/data cache | `~/.boltz` |
| `--devices` | Number of devices | `1` |
| `--accelerator` | `gpu`, `cpu`, or `tpu` | `gpu` |
| `--recycling_steps` | Recycling steps | `3` |
| `--sampling_steps` | Diffusion sampling steps | `200` |
| `--diffusion_samples` | Number of structures to sample | `1` |
| `--output_format` | `pdb` or `mmcif` | `mmcif` |
| `--use_msa_server` | Use ColabFold mmseqs2 server for MSAs | `False` |
| `--write_full_pae` | Save full PAE matrix | `False` |
| `--write_full_pde` | Save full PDE matrix | `False` |
| `--affinity_mw_correction` | Apply molecular-weight correction to affinity | `False` |
| `--sampling_steps_affinity` | Affinity sampling steps | `200` |
| `--diffusion_samples_affinity` | Affinity diffusion samples | `5` |

---

## YAML Input Specification

### Sequences

```yaml
sequences:
  - protein:
      id: A                      # single chain or list [A, B] for identical copies
      sequence: MKTLL...         # single-letter sequence
      msa: ./msa.a3m             # optional: .a3m, CSV, or omit with --use_msa_server
      modifications:
        - position: 5
          ccd: PTR               # post-translational modification
      cyclic: false
  - dna:
      id: C
      sequence: GATTACA
  - rna:
      id: D
      sequence: GAUUACA
  - ligand:
      id: E
      smiles: 'CCO'              # or ccd: ATP (not both)
```

### Constraints

```yaml
constraints:
  - pocket:
      binder: E
      contacts: [[A, 42]]
      max_distance: 6.0
  - contact:
      token1: [A, 42]
      token2: [E, 1]
      max_distance: 4.0
  - bond:
      atom1: [A, 1, N]
      atom2: [E, 1, C]
```

### Templates

```yaml
templates:
  - pdb: template.pdb
    chain_id: A
    template_id: A
```

### Affinity property

```yaml
properties:
  - affinity:
      binder: E                  # must be a ligand chain
```

Affinity predictions are designed for ligands up to ~56 heavy atoms; performance may degrade for significantly larger ligands.

---

## Pipeline Integration

Boltz-2 is a **Stage 3 validator** that replaces or complements Boltz-1 / AlphaFold3, especially when you also need affinity:

| Stage | Typical Tool | Boltz-2 Role |
|-------|--------------|--------------|
| 0 | PDBFixer | Prepare clean input structures |
| 1 | RFdiffusion / RFdiffusionAA | Generate scaffolds |
| 2 | ProteinMPNN / LigandMPNN | Design sequences |
| **3** | **Boltz-2** | **Predict structure + confidence + affinity** |
| 4 | Filtering | Rank by pLDDT / ipTM / affinity |

### Recommended pairings
- Binder design → Boltz-2 gives ipTM + affinity in one run
- Enzyme/ligand design → Boltz-2 replaces separate docking + FEP workflows
- Commercial pipeline → Boltz-2 (MIT) + Chai-1 (Apache 2.0) cross-check

---

## Hardware & Timing

- **GPU strongly recommended** (CPU is much slower)
- Single consumer GPU: ~18 s per protein-ligand affinity prediction
- NVIDIA cuEquivariance kernels accelerate recent GPUs
- Community fork runs on Tenstorrent hardware

---

## Interpreting Outputs

| Metric | Interpretation |
|--------|----------------|
| pLDDT ≥ 90 | Very high confidence structure |
| pLDDT 80–89 | Good confidence |
| ipTM ≥ 0.8 | Strong interface/binder prediction |
| `affinity_probability_binary` > 0.5 | Predicted binder |
| `affinity_pred_value` lower (more negative) | Stronger predicted affinity (log10 IC50 μM) |

Typical filtering workflow:

```bash
# 1. Run Boltz-2 with affinity on top designs
# 2. Keep designs with pLDDT ≥ 80, ipTM ≥ 0.7, affinity_probability_binary ≥ 0.6
# 3. Rank remaining by affinity_pred_value
```

---

## Strengths and Limitations

**Strengths:**
- MIT license (commercial-friendly)
- Joint structure + affinity prediction in one tool
- FEP-like affinity accuracy at ~1000× speed
- Handles proteins, ligands, DNA, RNA, covalent modifications
- Easy `boltz predict` CLI with YAML input
- Backward-compatible with Boltz-1 YAML format

**Limitations:**
- Affinity module optimized for ligands ≤ ~56 heavy atoms
- GPU required for practical throughput
- Affinity predictions are not a substitute for experimental assay
- Very large complexes may require high-VRAM GPU

---

## Citation

Passaro et al., "Boltz-2: Towards Accurate and Efficient Binding Affinity Prediction," *bioRxiv*, 2025. DOI: [10.1101/2025.06.14.659707](https://doi.org/10.1101/2025.06.14.659707)

```bibtex
@article{passaro2025boltz2,
  author = {Passaro, Saro and others},
  title = {Boltz-2: Towards Accurate and Efficient Binding Affinity Prediction},
  journal = {bioRxiv},
  year = {2025},
  doi = {10.1101/2025.06.14.659707}
}
```

---

## See Also

- `boltz-validation` — Boltz-1 structure-only validation
- `rfdiffusion-all-atom` — Ligand-aware backbone generation
- `rfdiffusion3-workflow` — All-atom DNA/RNA/ligand/enzyme design
- `ligandmpnn-design` — Ligand-aware sequence design
- `diffdock-ligand` — Diffusion-based small-molecule docking
- `pocketgen-ligand` — Pocket redesign around ligands
- `cross-validation` — Ensemble validation across predictors
- `pipeline-selection` — Choose the right workflow
- `periodic-summary` — Track structure + affinity outputs

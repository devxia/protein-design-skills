---
name: bioemu-ensemble
description: Guide for using Microsoft BioEmu to generate protein equilibrium conformational ensembles from sequence alone
---

# BioEmu Conformational Ensemble Generation Guide

**BioEmu** is an **MIT-licensed generative deep-learning model** from Microsoft Research AI for Science that predicts **protein equilibrium conformational ensembles** directly from an amino-acid sequence. Unlike single-structure predictors such as AlphaFold2, BioEmu captures functionally relevant motions: cryptic pocket opening, local unfolding, domain rearrangements, and allosteric transitions.

Use BioEmu when you want:
- **Ensemble-level structural insight** without running molecular dynamics
- To sample **thousands of statistically independent conformations per hour** on one GPU
- To estimate **relative free energies (~1 kcal/mol accuracy)** versus long MD or experiment
- To study **cryptic pockets**, **folding stability**, or **conformational selection** for drug-design targets
- A permissive **MIT license** for academic and commercial work

---

## What Makes BioEmu Different

| Feature | AlphaFold2 | AlphaFlow | BioEmu |
|---------|------------|-----------|--------|
| Output | Single best structure | Flow-based ensemble | **Generative equilibrium ensemble** |
| Speed | Minutes per sequence | Hours | **Thousands of samples per GPU hour** |
| Free-energy estimates | No | Limited | **~1 kcal/mol vs MD/experiment** |
| Cryptic pocket capture | No | Partial | **Designed for rare conformations** |
| License | Non-commercial inference | Open | **MIT** |

BioEmu is best viewed as a **complement to static design pipelines**: generate candidate sequences with RFdiffusion/ProteinMPNN, then use BioEmu to explore whether they populate the conformations you care about.

---

## Installation (Document-Only — Do Not Install)

```bash
# Linux only; Python >= 3.10
pip install bioemu

# With CUDA support
pip install bioemu[cuda]

# Optional: MD-based equilibration + side-chain relaxation
pip install bioemu[md]
```

First use auto-downloads AlphaFold2 weights (~3.5 GB) to `~/.cache/colabfold/`. Model checkpoints (`bioemu-v1.1` default) are pulled from Hugging Face on demand.

**Sources:**
- [GitHub repository](https://github.com/microsoft/bioemu)
- [Paper — *Science* (2025)](https://doi.org/10.1126/science.adv9817)
- [Hugging Face weights](https://huggingface.co/microsoft/bioemu)
- [Benchmark repo](https://github.com/microsoft/bioemu-benchmarks)
- [Azure AI Foundry deployment](https://ai.azure.com/catalog/models/BioEmu)

---

## Quickstart: Sample an Ensemble from Sequence

### 1. Run the sampler

```bash
python -m bioemu.sample \
  --sequence GYDPETGTWG \
  --num_samples 1000 \
  --output_dir outputs/bioemu/chignolin
```

Accepted `--sequence` values:
- Raw single-letter sequence string
- Path to a `.fasta` file
- Path to an `.a3m` MSA file

### 2. Add side chains and optional MD equilibration

```bash
# Side-chain reconstruction only
python -m bioemu.sidechain_relax \
  --pdb-path outputs/bioemu/chignolin/samples.pdb \
  --xtc-path outputs/bioemu/chignolin/samples.xtc \
  --outname chignolin_sc

# With short MD equilibration (requires bioemu[md])
python -m bioemu.sidechain_relax \
  --pdb-path outputs/bioemu/chignolin/samples.pdb \
  --xtc-path outputs/bioemu/chignolin/samples.xtc \
  --md-protocol nvt_equil \
  --outname chignolin_md
```

---

## CLI Reference

### `python -m bioemu.sample`

| Flag | Description | Default |
|------|-------------|---------|
| `--sequence` | Sequence string, FASTA, or A3M path | required |
| `--num_samples` | Number of conformations to generate | required |
| `--output_dir` | Output directory | required |
| `--model_name` | Checkpoint name (`bioemu-v1.0`, `bioemu-v1.1`, `bioemu-v1.2`) | `bioemu-v1.1` |
| `--batch_size_100` | Batch size expressed per 100 residues | `20` |
| `--filter_samples` | Remove unphysical samples | `True` |
| `--denoiser_config` | Path to YAML steering config | optional |
| `--msa_host_url` | Override ColabFold MSA server | optional |

### `python -m bioemu.sidechain_relax`

| Flag | Description |
|------|-------------|
| `--pdb-path` | Path to input PDB (reference topology) |
| `--xtc-path` | Path to sampled trajectory in XTC format |
| `--outname` | Prefix for output files |
| `--no-md-equil` | Skip MD equilibration |
| `--md-protocol` | `nvt_equil` or custom protocol |

---

## Output Files

```
outputs/bioemu/chignolin/
├── samples.pdb              # Backbone-frame ensemble (multi-model PDB)
├── samples.xtc              # Same ensemble in GROMACS XTC trajectory
├── denoiser_configs/        # Copy of any steering YAML used
└── logs/                    # Sampling metadata and timings
```

After `sidechain_relax`:

```
chignolin_sc.pdb
chignolin_sc.xtc
chignolin_md.pdb        # if MD equilibration was requested
chignolin_md.xtc
```

These files can be visualized in PyMOL, VMD, or MDAnalysis and analyzed with:

```bash
python scripts/summarize_outputs.py --output-dir outputs/bioemu/chignolin
```

---

## Steering with YAML Configs

BioEmu supports **physical steering** via YAML configuration files. The default (`SMC`) penalizes Cα–Cα chain breaks and steric clashes. An optional `FKC` config allows additional restraints.

Example custom `steer.yml`:

```yaml
steering:
  ca_ca_break_penalty: 10.0
  steric_clash_penalty: 5.0
  radius_of_gyration: null
```

Run with:

```bash
python -m bioemu.sample \
  --sequence myseq.fa \
  --num_samples 1000 \
  --output_dir outputs/bioemu/steered \
  --denoiser_config steer.yml
```

---

## Pipeline Integration

BioEmu does **not** replace backbone or sequence-design stages. Use it as a downstream ensemble-analysis step:

| Stage | Typical Tool | BioEmu Role |
|-------|--------------|-------------|
| 0 | PDBFixer | Prepare monomeric input structure |
| 1 | RFdiffusion / FrameDiff / TopoDiff | Generate backbones |
| 2 | ProteinMPNN / PiFold | Design sequences |
| 3 | AlphaFold3 / Boltz-1 / Chai-1 | Validate single best structure |
| **3b** | **BioEmu** | **Explore conformational landscape of validated hits** |
| 4 | Filtering / clustering | Select diverse, functionally relevant conformations |

### Recommended pairings
- Compare designed-state ensembles → BioEmu vs AlphaFlow
- Cryptic-pocket drug-discovery campaign → RFdiffusion binder → BioEmu target ensemble → docking to rare conformations
- Stability engineering → BioEmu ΔG/ΔΔG estimates + PRO-LDM fitness optimization

---

## Hardware & Timing Reference (A100 80 GB)

| Protein length | ~Time for 1000 samples (batch_size_100=20) |
|----------------|--------------------------------------------|
| 100 residues   | ~4 min |
| 300 residues   | ~40 min |
| 600 residues   | ~150 min |

BioEmu is currently **monomer-only**. For multimeric ensembles, prefer `alphaflow-ensemble` or sample each chain separately and assemble externally.

---

## Benchmarks

Microsoft provides `bioemu-benchmarks` (MIT) covering:

- `multiconf_ood60` — local conformational changes
- `multiconf_domainmotion` — global domain motions
- `singleconf_localunfolding` — local unfolding events
- `multiconf_crypticpocket` — cryptic pocket formation
- `md_emulation` — match to long MD distributions
- `folding_free_energies` — thermodynamic stability

Use these to sanity-check BioEmu on a protein family similar to your target before production runs.

---

## When to Use BioEmu vs Other Ensemble Tools

| Your Goal | Best Tool |
|-----------|-----------|
| MD-free equilibrium ensemble from sequence | **BioEmu** |
| Flow-based conformational diversity from an MSA | `alphaflow-ensemble` |
| Single best structure for validation | `structure-validation` (AlphaFold3) |
| Compare multiple predictors | BioEmu + AlphaFlow + MD |

---

## Strengths and Limitations

**Strengths:**
- MIT license (commercial-friendly)
- Thousands of statistically independent conformations per GPU hour
- Direct free-energy estimates
- Captures rare/cryptic conformations missed by single-structure predictors
- Well-documented benchmarks and Azure deployment option

**Limitations:**
- Linux-only pip package
- Monomer-only (no native multimer support)
- Requires ~3.5 GB AlphaFold2 weight download on first run
- Best for 50–600 residue proteins; very large proteins are slow
- Does not design sequences; must be paired with a design stage

---

## Citation

Noé et al., "Scalable emulation of protein equilibrium ensembles with generative deep learning," *Science*, 2025. DOI: [10.1126/science.adv9817](https://doi.org/10.1126/science.adv9817)

```bibtex
@article{noe2025bioemu,
  author = {Noé, Frank and others},
  title = {Scalable emulation of protein equilibrium ensembles with generative deep learning},
  journal = {Science},
  year = {2025},
  doi = {10.1126/science.adv9817}
}
```

---

## See Also

- `alphaflow-ensemble` — Flow-based conformational ensembles
- `structure-validation` — Single-structure validation with AlphaFold3
- `framediff-backbone` — MIT-licensed backbone generation to feed into BioEmu
- `pro-ldm-workflow` — Fitness-guided sequence optimization
- `pipeline-selection` — Choose the right workflow
- `periodic-summary` — Track ensemble outputs across runs

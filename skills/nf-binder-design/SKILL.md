---
name: nf-binder-design
description: HPC/cloud-ready Nextflow pipeline for automated protein binder design — wraps RFdiffusion, BindCraft, BoltzGen, and Boltz-2
---

# nf-binder-design Workflow

> **Quick Entry**: End-to-end binder design pipeline | Nextflow | HPC / cloud / local
>
> **Upstream**: Target structure (PDB) | **Downstream**: Filtered ranked binders

## When to Trigger

- User says "run binder design on HPC", "Nextflow pipeline", "cloud binder design"
- User wants to compare multiple binder design methods in one command
- User needs parallel execution across multiple GPUs or cluster nodes
- User wants a production pipeline that wraps RFdiffusion / BindCraft / BoltzGen
- User says "nf-binder-design", "Australian Protein Design Initiative", "APDI"

## What is nf-binder-design?

[nf-binder-design](https://github.com/Australian-Protein-Design-Initiative/nf-binder-design) is a **Nextflow pipeline** from the Australian Protein Design Initiative for automated protein binder design. It wraps several existing tools into reproducible, containerized, parallel workflows that run on local workstations, HPC clusters, or cloud platforms.

Unlike running stages manually with `scripts/run_*.py`, nf-binder-design chains everything and handles parallel dispatch, filtering, and scoring automatically.

### Available Methods

| Method | Workflow | Best For |
|--------|----------|----------|
| `rfd` | RFdiffusion → ProteinMPNN → AlphaFold2 initial guess → Boltz-2 refold | Standard de novo binder design |
| `rfd_partial` | RFdiffusion Partial Diffusion → Boltz-2 refold | Refining existing binder scaffolds |
| `bindcraft` | BindCraft parallel across GPUs | Highest experimental success rate |
| `boltzgen` | BoltzGen generative model | Protein/peptide/small-molecule/nanobody binders |
| `boltz_pulldown` | AlphaPulldown-like with Boltz-2 | Large-scale interaction screening |

### Key Features

- **Containerized** with Apptainer/Singularity
- **HPC-ready** with SLURM configs (`conf/platforms/`)
- **Built-in filtering** (e.g., `rg<20`, interface metrics)
- **BindCraft-derived scoring**: interface score, dG, dSASA, clash scores
- **Method-specific `--help`** for parameter discovery
- **nf-test** test suite included

## Installation

```bash
# Install Nextflow
curl -s https://get.nextflow.io | bash
mv nextflow ~/.local/bin/   # or any directory in $PATH

# Clone pipeline
git clone https://github.com/Australian-Protein-Design-Initiative/nf-binder-design.git
cd nf-binder-design

# Verify
nextflow run Australian-Protein-Design-Initiative/nf-binder-design --help
```

### Requirements

- Nextflow >= 23.04.0
- Apptainer or Singularity (for containers)
- CUDA-capable GPU(s) for most methods
- For HPC: SLURM or PBS access + a platform config in `conf/platforms/`

## Method 1: RFdiffusion Binder Design (`rfd`)

Complete standard pipeline inside Nextflow:

```bash
nextflow run Australian-Protein-Design-Initiative/nf-binder-design \
  --method rfd \
  --input_pdb target.pdb \
  --outdir results/rfd \
  --contigs "[A371-508/A753-883/0 70-100]" \
  --hotspot_res "A473,A995,A411,A421" \
  --rfd_n_designs 50 \
  --pmpnn_seqs_per_struct 8 \
  -profile local
```

**Key parameters:**
- `--input_pdb` — target structure
- `--contigs` — generated binder + fixed target segments
- `--hotspot_res` — target hotspot residues (comma-separated)
- `--rfd_n_designs` — number of RFdiffusion backbones
- `--pmpnn_seqs_per_struct` — sequences per backbone
- `--rfd_filters` — filters like `"rg<20"`
- `--rfd_extra_args` — extra RFdiffusion potentials/guidance

**Outputs:**
- `results/rfd/` — PDBs, FASTAs, AlphaFold2 initial guesses
- Boltz-2 refolded structures
- Filtered + scored summary CSV

## Method 2: Partial Diffusion Refinement (`rfd_partial`)

Take existing binder PDBs and refine them with partial diffusion:

```bash
nextflow run Australian-Protein-Design-Initiative/nf-binder-design \
  --method rfd_partial \
  --input_pdb 'my_designs/*.pdb' \
  --outdir results/partial \
  --rfd_n_partial_per_binder 10 \
  --rfd_batch_size 5 \
  --rfd_partial_T 2,5,10,20 \
  --hotspot_res "A473,A995,A411,A421" \
  -profile local
```

**Notes:**
- Binder chain is always named `A` in outputs
- Other chains are `B`, `C`, etc.
- `--rfd_partial_T` accepts multiple T values for exploration

## Method 3: BindCraft (`bindcraft`)

Run BindCraft trajectories in parallel across multiple GPUs:

```bash
nextflow run Australian-Protein-Design-Initiative/nf-binder-design \
  --method bindcraft \
  --input_pdb input/PDL1.pdb \
  --target_chains "A" \
  --hotspot_res "A56,A125" \
  --hotspot_subsample 0.5 \
  --binder_length_range "55-120" \
  --bindcraft_n_traj 20 \
  --bindcraft_batch_size 1 \
  --bindcraft_advanced_settings_preset "default_4stage_multimer" \
  --bindcraft_filters_preset "default_filters" \
  --gpu_devices 0,1 \
  -profile local
```

**Key parameters:**
- `--target_chains` — target chain IDs
- `--binder_length_range` — `"min-max"` length
- `--bindcraft_n_traj` — total trajectories (parallelized over GPUs)
- `--gpu_devices` — GPU IDs to use

**Outputs:**
- `bindcraft/final_design_stats.csv`
- `bindcraft_report.html`
- Final PDBs and FASTAs

## Method 4: BoltzGen (`boltzgen`)

Use BoltzGen for diverse binder types:

```bash
nextflow run Australian-Protein-Design-Initiative/nf-binder-design \
  --method boltzgen \
  --config_yaml config/my_design.yaml \
  --outdir results/boltzgen \
  --num_designs 100 \
  --batch_size 10 \
  --devices 0 \
  -profile local
```

**Supported design types in BoltzGen:**
- `protein-anything`
- `peptide-anything`
- `protein_small-molecule`
- `nanobody-anything`

## HPC Execution

Use platform-specific configs instead of `-profile local`:

```bash
# Example: M3 cluster
nextflow run Australian-Protein-Design-Initiative/nf-binder-design \
  --method rfd \
  --input_pdb target.pdb \
  --outdir results/rfd \
  --contigs "[A371-508/0 70-100]" \
  --hotspot_res "A473,A995" \
  --rfd_n_designs 100 \
  -c conf/platforms/m3.config
```

Set Apptainer cache environment variables for large HPC runs:

```bash
export NXF_APPTAINER_CACHEDIR=/scratch/$USER/apptainer_cache
export NXF_APPTAINER_TMPDIR=/scratch/$USER/apptainer_tmp
```

## Comparison: nf-binder-design vs Manual Scripts

| Aspect | Manual `scripts/run_*.py` | nf-binder-design |
|--------|---------------------------|------------------|
| Setup | Per-tool conda envs | One Nextflow + Apptainer |
| Parallelism | User-managed | Built-in across methods |
| HPC | Manual job arrays | SLURM configs ready |
| Filtering | Manual with `run_filtering.py` | Built-in filters per method |
| Scoring | pLDDT / ipTM / pTM | Interface score, dG, dSASA, clash |
| Flexibility | Fine-grained control | Higher-level method switching |
| Best for | Exploration / single designs | Production / batch / HPC |

## When to Use Which Method

| Goal | Method |
|------|--------|
| Standard binder design | `rfd` |
| Refine / diversify existing binders | `rfd_partial` |
| Maximum experimental success rate | `bindcraft` |
| Peptide or nanobody binder | `boltzgen` |
| Large-scale interaction screen | `boltz_pulldown` |

## Pipeline Integration

You can use nf-binder-design as the **binder design stage** in a larger workflow:

```
PDBFixer (local) → nf-binder-design (HPC) → Filtering (local)
```

Example:

```bash
# Stage 0 locally
python scripts/run_pdbfixer.py --input target.pdb --output target_fixed.pdb

# Stage 1-3 on HPC
nextflow run Australian-Protein-Design-Initiative/nf-binder-design \
  --method rfd \
  --input_pdb target_fixed.pdb \
  --outdir outputs/nf_binder \
  --contigs "[A1-200/0 70-100]" \
  --hotspot_res "A45,A88" \
  --rfd_n_designs 100 \
  -c conf/platforms/m3.config

# Stage 4 locally (if not already filtered by pipeline)
python scripts/run_filtering.py --results-dir outputs/nf_binder/ --min-iptm 0.75
```

## Progress Monitoring

Nextflow provides native progress tracking:

```bash
# Watch live execution
nextflow log

# After completion
ls outputs/nf_binder/
```

For a project-wide summary across local + Nextflow outputs:

```bash
python scripts/summarize_outputs.py --output-dir outputs/ --expected-backbones 100
```

## Tips

- Use `--method <method> --help` to see method-specific parameters
- Pass parameters via JSON: `-params-file params.json`
- Container images are large — pre-pull them before big runs
- BindCraft method requires PyRosetta (non-commercial license); ensure compliance
- For local testing, start with `--rfd_n_designs 1` and `-profile local`

## See Also

- `bindcraft-workflow` skill — stand-alone BindCraft guide
- `structure-generation` skill — RFdiffusion parameters explained
- `boltz-validation` skill — Boltz-2 standalone usage
- `batch-submission` skill — managing large batches locally without Nextflow
- `fast-screening` skill — lightweight pre-screening before expensive pipelines

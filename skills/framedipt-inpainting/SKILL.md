---
name: framedipt-inpainting
description: Protein structure inpainting with FrameDiPT — SE(3) diffusion for targeted redesign of protein regions (CDR loops, active sites, interfaces) with Hydra config system
---

# Alternative: FrameDiPT Structure Inpainting

## Quick Entry

**Use this skill when you want to redesign a SPECIFIC REGION of a protein while keeping everything else exactly the same.** This is "true inpainting" — not full redesign.

**Typical flow:** PDBFixer → **FrameDiPT** (redesign region) → `sequence-design` (Stage 2) → `structure-validation` (Stage 3) → `filtering-ranking` (Stage 4)

**Not for:** Designing a protein from scratch (use `structure-generation` or `rfdiffusion-all-atom` instead)

## When to Trigger

- User says "FrameDiPT", "inpainting", "redesign region", "redesign loop"
- User wants to **redesign a specific region** while keeping the rest intact
- User needs **CDR loop redesign** for antibodies/TCRs
- User says "redesign this region", "change these residues", "loop design"
- User wants to **optimize an interface** without redesigning the whole protein
- User needs **active site redesign** for enzyme engineering

## FrameDiPT Overview

[FrameDiPT](https://github.com/instadeepai/FrameDiPT) is an **SE(3) diffusion model for protein structure inpainting** from InstaDeep. Unlike full-structure generators (RFdiffusion, Genie 3), FrameDiPT **redesigns specific regions** of a protein while preserving the rest — enabling targeted modifications.

### Key Differences from Full Generation

| Feature | RFdiffusion / Genie 3 | FrameDiPT |
|---------|----------------------|-----------|
| Scope | Full structure | **Specific region only** |
| Input | None or motif | **Full structure + mask** |
| Preservation | Limited | **Complete (unmasked regions)** |
| Use case | De novo design | **Redesign / optimization** |
| Output | New structure | **Modified structure** |

## Installation

```bash
# Create conda environment
conda env create --name framedipt-env --file environment.yml
conda activate framedipt-env

# Install package
pip install --editable .

# Download pre-trained weights (requires git-lfs)
git lfs install
git clone https://huggingface.co/InstaDeepAI/FrameDiPTModels
# Weights stored at ./FrameDiPTModels/weights/denovo.pth and ./FrameDiPTModels/weights/inpainting.pth
```

**Note:** `foldseek`, `anarci`, and `pdbfixer` may not be available on Apple Silicon. For TCR CDR loop design, `anarci` is required — use Docker instead.

## Usage

### CLI Inference (Recommended)

FrameDiPT uses **Hydra** configs. The main inference script is `experiments/inference.py` with config at `config/inference.yaml`.

```bash
# Run inference with default config
python experiments/inference.py
```

### De Novo Protein Design

```bash
# Modify config/inference.yaml:
# inference:
#   name: denovo
#   inpainting: False
#   input_aatype: False
#   weights_path: ./FrameDiPTModels/weights/denovo.pth
#   samples:
#     samples_per_length: 10
#     seq_per_sample: 8
#     min_length: 100
#     max_length: 500
#     length_step: 100
#   diffusion:
#     num_t: 200
#     noise_scale: 1.0
#     min_t: 0.01

python experiments/inference.py
```

### TCR CDR3 Loop Inpainting (Default)

```bash
# Default config is set for TCR CDR3 loop inpainting
# Modify config/inference.yaml:
# inference:
#   name: tcr_cdr3_inpainting
#   inpainting: True
#   input_aatype: True
#   weights_path: ./FrameDiPTModels/weights/inpainting.pth
#   inpainting_samples:
#     tcr: True
#     cdr_loops: [CDR3]
#     data_path: ./database/TCR.csv
#     download_dir: /path/to/TCR_first_assemblies
#     first_assembly: True
#     samples: 5

python experiments/inference.py
```

### All CDR Loops Inpainting

```bash
# inference:
#   inpainting_samples:
#     tcr: True
#     cdr_loops: [CDR1, CDR2, CDR3]
#     shifted_region: null  # null, before, or after

python experiments/inference.py
```

### N-/C-terminal Flank Inpainting

```bash
# inference:
#   inpainting_samples:
#     tcr: True
#     cdr_loops: [CDR3]
#     shifted_region: before  # or "after"

python experiments/inference.py
```

## Parameters

### Inference Config (`config/inference.yaml`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `inference.name` | str | — | Name of inference run (used for output folder) |
| `inference.inpainting` | bool | True | True = inpainting, False = de novo design |
| `inference.input_aatype` | bool | True | Input amino acid types to model |
| `inference.weights_path` | str | — | Path to model weights (.pth file) |
| `inference.output_dir` | str | ./inference_outputs/ | Output directory |

### Sample Generation Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `inference.samples.samples_per_length` | int | — | Samples per sequence length |
| `inference.samples.seq_per_sample` | int | — | Sequences + ESMFold samples per backbone |
| `inference.samples.min_length` | int | — | Minimum sequence length |
| `inference.samples.max_length` | int | — | Maximum sequence length |
| `inference.samples.length_step` | int | — | Gap between sampled lengths |

### Diffusion Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `inference.diffusion.num_t` | int | 200 | Number of inference time steps |
| `inference.diffusion.noise_scale` | float | 1.0 | Noise level for inference (0 to 1) |
| `inference.diffusion.min_t` | float | 0.01 | Minimum timestep (slightly > 0) |

### TCR Inpainting Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `inference.inpainting_samples.tcr` | bool | True | Run TCR inpainting |
| `inference.inpainting_samples.cdr_loops` | list | [CDR3] | Which CDR loops to diffuse |
| `inference.inpainting_samples.shifted_region` | str | null | "before", "after", or null |
| `inference.inpainting_samples.data_path` | str | — | CSV with TCR samples |
| `inference.inpainting_samples.download_dir` | str | — | Directory to download PDBs |
| `inference.inpainting_samples.first_assembly` | bool | True | Use first assembly files |
| `inference.inpainting_samples.max_len` | int | null | Max length filter |
| `inference.inpainting_samples.samples` | int | 5 | Backbone samples per test case |

## Output Format

```
inference_outputs/
└── {timestamp}/                          # e.g., 12D_02M_2023Y_20h_46m_13s
    ├── inference_conf.yaml               # Config used
    └── {pdb_id}_length_{diffused_length}/
        ├── {pdb_id}_1.pdb                # Cleaned ground truth
        ├── esmf_pred.pdb                 # ESMFold prediction (if enabled)
        ├── diffusion_info.csv            # Diffusion metadata
        ├── sample_0/
        │   ├── bb_traj_0_1.pdb           # Diffusion trajectory (optional)
        │   ├── sample_0_1.pdb            # Final sample
        │   └── x0_traj_0_1.pdb           # Model prediction trajectory (optional)
        └── sample_1/
            └── ...
```

## Generate Full-Atom Models

FrameDiPT outputs **backbone-only** models. Use cg2all for full atoms:

```bash
# See cg2all/README.md for details
cd cg2all
python convert_backbone_to_fullatom.py --input sample_0_1.pdb --output fullatom.pdb
```

## Evaluation

### TCR Evaluation

```bash
# Configure config/evaluation.yaml
# inference_path: /path/to/inference/outputs
# eval_output_path: /path/to/evaluation/outputs
# sample_selection_strategy: mode  # mean, median, mode, mean_closest, median_closest
# alignment: False
# exclude_diffused_regions_in_alignment: True
# separate_alignment: True

python evaluation/evaluate_tcr.py
```

**Metrics available:**
- `bb_rmsd` — backbone RMSD
- `full_atom_rmsd` — full atom RMSD
- `angle_error` — phi, psi, omega angle errors
- `asa_abs_error` / `asa_square_error` — accessible surface area
- `rsa_abs_error` / `rsa_square_error` — relative surface area

### De Novo Design Evaluation

Requires: MaxCluster, foldseek

```bash
# Configure config/evaluation.yaml
denovo:
  pretrained_inference_path: /optional/path/to/pretrained/results
  esmfold_sample_choice: best  # best or median
  diversity_tm_score_th: 0.5
  novelty_target_db: /path/to/foldseek/db

python evaluation/eval_denovo.py
```

**Three evaluation aspects:**
1. **Designability** (scRMSD) — ProteinMPNN sequence design → ESMFold structure prediction → compare to generated backbone
2. **Diversity** — MaxCluster clustering: `num_clusters / num_samples`
3. **Novelty** (pdbTM) — foldseek search against PDB for highest TM-score

## Pipeline Integration

### Option 1: CDR Optimization Pipeline
```
Input: Parent antibody/TCR structure
    ↓
FrameDiPT (redesign CDR loops)
    ↓
ProteinMPNN (design sequences for new loops)
    ↓
AlphaFold3 / Boltz (validate full antibody)
    ↓
Filtering (check pLDDT, ipTM)
    ↓
Affinity prediction (optional)
```

### Option 2: Active Site Engineering
```
Input: Wild-type enzyme structure
    ↓
FrameDiPT (redesign active site for new substrate)
    ↓
LigandMPNN (design sequences with ligand awareness)
    ↓
AlphaFold3 (validate enzyme-ligand complex)
    ↓
Docking (verify substrate binding)
    ↓
Filtering
```

### Option 3: Interface Optimization
```
Input: Protein-protein complex
    ↓
FrameDiPT (redesign interface residues on binder)
    ↓
ProteinMPNN (design sequences)
    ↓
AlphaFold3 (validate complex — check ipTM)
    ↓
Filtering
```

## Hardware Requirements

| Mode | GPU | Notes |
|------|-----|-------|
| De novo design | Required | Needs ESMFold for structure prediction |
| Inpainting | CPU possible | Slower (several minutes per sample) |
| Recommended | 1 GPU | CUDA-capable, ≥16GB VRAM |

## Tips

- **Mask size**: Keep masked region to <30% of structure for best results
- **Context**: Include 10-15Å around mask for proper context
- **Noise scale**: 1.0 default. Lower for conservative redesigns, higher for exploration
- **num_t**: 200 default. Lower for faster sampling, higher for quality
- **TCR data**: CSV files in `database/` directory. Download PDBs to `download_dir`
- **Full atoms**: Always run cg2all after FrameDiPT for full-atom structures
- **Validation**: Check unmasked region RMSD < 1Å to confirm preservation
- **Sample selection**: Use `mode` strategy (highest Gaussian kernel density) for evaluation

## Comparison with Other Methods

| Use Case | Method | Why |
|----------|--------|-----|
| Full redesign | RFdiffusion / Genie 3 | Better for de novo |
| Targeted redesign | **FrameDiPT** | Only true inpainting |
| CDR optimization | **FrameDiPT** | Preserves framework |
| Active site | **FrameDiPT** | Preserves enzyme fold |
| Interface | **FrameDiPT** | Preserves both partners |
| Motif scaffolding | RFdiffusion | Better for large motifs |

## References

- [FrameDiPT GitHub](https://github.com/instadeepai/FrameDiPT)
- [FrameDiPT Paper](https://www.biorxiv.org/content/10.1101/2023.11.21.568057v2)
- [InstaDeep Research](https://www.instadeep.com/)
- [SE(3) Diffusion](https://arxiv.org/abs/2302.02242)
- [cg2all](https://github.com/huhlim/cg2all) — for full-atom conversion

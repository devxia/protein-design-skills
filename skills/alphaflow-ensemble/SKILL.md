---
name: alphaflow-ensemble
description: Conformational ensemble generation with AlphaFlow — flow-matching-based AlphaFold for generating diverse protein conformations and dynamics (AlphaFlow-PDB, AlphaFlow-MD, ESMFlow)
---

# Alternative: AlphaFlow Conformational Ensemble Generation

## Quick Entry

**Use this skill when you need MULTIPLE CONFORMATIONS of a protein, not just one structure.** Essential for flexible proteins, IDRs, and allosteric analysis.

**Typical flow:** `sequence-design` (Stage 2) → **AlphaFlow** (generate ensemble) → Ensemble analysis → `filtering-ranking` (Stage 4)

**Not for:** Getting a single best structure (use `structure-validation` with AlphaFold3 instead)

## When to Trigger

- User says "AlphaFlow", "conformational ensemble", "protein dynamics"
- User wants to generate **multiple conformations** of a protein
- User needs to model **intrinsically flexible regions**
- User says "protein conformations", "structural ensemble", "dynamic states"
- User wants to understand **conformational landscapes**
- User needs ensemble for **molecular dynamics** initialization

## AlphaFlow Overview

[AlphaFlow](https://github.com/bjing2016/alphaflow) is an **AlphaFold model fine-tuned with flow matching** for generating **protein conformational ensembles** rather than single static structures. Published at ICML 2024, it addresses a critical limitation of standard structure predictors: real proteins are dynamic and exist as ensembles of conformations.

### Key Differences from Standard Structure Prediction

| Feature | AlphaFold3 / ESMFold | AlphaFlow |
|---------|---------------------|-----------|
| Output | Single structure | **Conformational ensemble** |
| Method | Single forward pass | **Flow matching + sampling** |
| Dynamics | No | **Yes (multiple states)** |
| Flexible regions | Low confidence (high PAE) | **Multiple conformations** |
| Use case | Static structure | **Dynamic behavior** |
| Training | Standard AF | **AF fine-tuned on ensembles** |

## Installation

```bash
conda create -n alphaflow python=3.9
conda activate alphaflow

pip install numpy==1.21.2 pandas==1.5.3
pip install torch==1.12.1+cu113 -f https://download.pytorch.org/whl/torch_stable.html
pip install biopython==1.79 dm-tree==0.1.6 modelcif==0.7 ml-collections==0.1.0 scipy==1.7.1 absl-py einops
pip install pytorch_lightning==2.0.4 fair-esm mdtraj==1.9.9 wandb

# OpenFold installation (requires CUDA 11)
# If system CUDA is wrong version, install in conda:
conda install nvidia/label/cuda-11.8.0::cuda
conda install nvidia/label/cuda-11.8.0::cuda-cudart-dev
conda install nvidia/label/cuda-11.8.0::libcusparse-dev
conda install nvidia/label/cuda-11.8.0::libcusolver-dev
conda install nvidia/label/cuda-11.8.0::libcublas-dev
ln -s $CONDA_PREFIX/lib/libcudart_static.a $CONDA_PREFIX/lib/libcudart.a

CUDA_HOME=$CONDA_PREFIX pip install 'openfold @ git+https://github.com/aqlaboratory/openfold.git@103d037'
```

## Model Weights

### AlphaFlow Models

| Model | Version | Best For | Weights URL |
|-------|---------|----------|-------------|
| AlphaFlow-PDB | base | Experimental ensembles (X-ray, cryo-EM) | alphaflow_pdb_base_202402.pt |
| AlphaFlow-PDB | distilled | Faster PDB ensemble | alphaflow_pdb_distilled_202402.pt |
| AlphaFlow-MD | base | MD trajectories at 300K | alphaflow_md_base_202402.pt |
| AlphaFlow-MD | distilled | Faster MD ensemble | alphaflow_md_distilled_202402.pt |
| AlphaFlow-MD+Templates | base | MD + reference structure | alphaflow_md_templates_base_202402.pt |
| AlphaFlow-MD+Templates | distilled | Faster MD+Templates | alphaflow_md_templates_distilled_202402.pt |
| AlphaFlow-MD+Templates | 12l-base | **2.5x faster**, small accuracy loss | alphaflow_12l_md_templates_base_202406.pt |
| AlphaFlow-MD+Templates | 12l-distilled | Fastest | alphaflow_12l_md_templates_distilled_202406.pt |

### ESMFlow Models (No MSA Required)

| Model | Version | Best For |
|-------|---------|----------|
| ESMFlow-PDB | base / distilled | No-MSA experimental ensembles |
| ESMFlow-MD | base / distilled | No-MSA MD ensembles |
| ESMFlow-MD+Templates | base / distilled | No-MSA MD + reference |

**All weights:** [HuggingFace bjing-mit/alphaflow](https://huggingface.co/bjing-mit/alphaflow)

## Usage

### AlphaFlow Inference (Requires MSA)

```bash
# Prepare input CSV with 'name' and 'seqres' columns
# See splits/atlas_test.csv for format

# Prepare MSA directory with .a3m files:
# {alignment_dir}/{name}/a3m/{name}.a3m

# Generate MSA with ColabFold server (if you don't have MSAs)
python -m scripts.mmseqs_query --split input.csv --outdir msa_dir/

# Or with local MMseqs2 (requires UniRef30 + ColabDB)
python -m scripts.mmseqs_search_helper --split input.csv --db_dir /path/to/dbs --outdir msa_dir/

# Run AlphaFlow-PDB (recommended: add --self_cond --resample)
python predict.py \
    --mode alphafold \
    --input_csv input.csv \
    --msa_dir msa_dir/ \
    --weights alphaflow_pdb_base_202402.pt \
    --samples 100 \
    --outpdb output_dir/ \
    --self_cond --resample

# Run AlphaFlow-MD+Templates (with reference structure)
python predict.py \
    --mode alphafold \
    --input_csv input.csv \
    --msa_dir msa_dir/ \
    --weights alphaflow_md_templates_base_202402.pt \
    --samples 100 \
    --outpdb output_dir/ \
    --templates_dir templates/

# Run distilled model (faster)
python predict.py \
    --mode alphafold \
    --input_csv input.csv \
    --msa_dir msa_dir/ \
    --weights alphaflow_pdb_distilled_202402.pt \
    --samples 100 \
    --outpdb output_dir/ \
    --noisy_first --no_diffusion
```

### ESMFlow Inference (No MSA Required)

```bash
# ESMFlow does NOT need MSAs — much faster setup
python predict.py \
    --mode esmfold \
    --input_csv input.csv \
    --weights esmflow_pdb_base_202402.pt \
    --samples 100 \
    --outpdb output_dir/
```

### Speed vs Quality Trade-off

```bash
# Default: --tmax 1.0 --steps 10 (balanced)

# Higher precision, lower diversity:
python predict.py ... --tmax 0.2 --steps 2

# Lower precision, higher diversity:
python predict.py ... --tmax 1.0 --steps 20
```

## Parameters

### CLI Arguments

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--mode` | Yes | — | `alphafold` or `esmfold` |
| `--input_csv` | Yes | — | CSV with `name` and `seqres` columns |
| `--weights` | Yes | — | Path to model weights (.pt file) |
| `--samples` | Yes | — | Number of conformations to generate |
| `--outpdb` | Yes | — | Output directory for PDB files |
| `--msa_dir` | AlphaFlow only | — | MSA directory (`.a3m` files) |
| `--templates_dir` | MD+Templates only | — | Template PDB directory |
| `--pdb_id` | No | all | Select specific row(s) from CSV |
| `--self_cond` | No | False | Self-conditioning (recommended for PDB) |
| `--resample` | No | False | Resampling (recommended for PDB) |
| `--noisy_first` | No | False | Required for distilled models |
| `--no_diffusion` | No | False | Required for distilled models |
| `--tmax` | No | 1.0 | Max timestep (lower = less diverse) |
| `--steps` | No | 10 | Flow integration steps |

### Model Selection Guide

| Scenario | Recommended Model | Why |
|----------|------------------|-----|
| Experimental ensemble | AlphaFlow-PDB base | Trained on PDB structures |
| MD ensemble | AlphaFlow-MD base | Trained on MD trajectories |
| Have reference structure | AlphaFlow-MD+Templates | Uses structure as template |
| Need speed | distilled or 12l | Faster with small accuracy loss |
| No MSA available | ESMFlow-PDB | No MSA needed |
| Quick screening | ESMFlow distilled | Fastest option |

## Pipeline Integration

### Option 1: Ensemble-Aware Design Pipeline
```
Stage 1: RFdiffusion / Genie 3 (generate backbone)
    ↓
Stage 2: ProteinMPNN (design sequences)
    ↓
Stage 3a: AlphaFlow (generate conformational ensemble for top design)
    ↓
Stage 3b: Analyze ensemble (RMSD distribution, flexible regions)
    ↓
Stage 4: Select designs with stable conformations
```

### Option 2: IDR Design Pipeline
```
Stage 1: EvoDiff (generate sequence with IDR)
    ↓
Stage 2: AlphaFlow (generate ensemble — IDRs will show high diversity)
    ↓
Stage 3: Analyze ensemble to characterize IDR behavior
    ↓
Stage 4: Experimental validation
```

### Option 3: Allosteric Design Pipeline
```
Stage 1: RFdiffusion (design scaffold with allosteric site)
    ↓
Stage 2: ProteinMPNN (design sequence)
    ↓
Stage 3a: AlphaFlow (generate ensemble in apo state)
    ↓
Stage 3b: AlphaFlow (generate ensemble in holo state with ligand)
    ↓
Stage 4: Compare ensembles to verify allosteric coupling
```

## Ensemble Analysis

```python
import numpy as np
from Bio import PDB

# Load all conformations
structures = []
for i in range(num_samples):
    s = PDB.PDBParser().get_structure(f"c{i}", f"output_dir/{name}_sample_{i}.pdb")
    structures.append(s)

# Pairwise CA RMSD matrix
rmsd_matrix = np.zeros((len(structures), len(structures)))
for i in range(len(structures)):
    for j in range(i+1, len(structures)):
        rmsd = compute_ca_rmsd(structures[i], structures[j])
        rmsd_matrix[i, j] = rmsd
        rmsd_matrix[j, i] = rmsd

# Identify flexible regions
mean_rmsd_per_residue = compute_per_residue_rmsd(structures)
flexible_regions = np.where(mean_rmsd_per_residue > 3.0)[0]
print(f"Flexible regions: {flexible_regions}")

# Cluster ensemble into representative states
from sklearn.cluster import KMeans
# Flatten coordinates and cluster
labels = KMeans(n_clusters=5).fit_predict(coords)
```

### Provided Evaluation Scripts

```bash
# Download ATLAS dataset
bash scripts/download_atlas.sh

# Analyze ensembles
python -m scripts.analyze_ensembles \
    --atlas_dir /path/to/atlas \
    --pdb_dir /path/to/alphaflow/outputs \
    --num_workers 4

# Print comparison table
python -m scripts.print_analysis output1.pkl output2.pkl ...
```

## Comparison with Other Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| Single best structure | AlphaFold3 | Highest accuracy for single structure |
| Conformational ensemble | **AlphaFlow** | Only tool for ensemble generation |
| Fast single structure | ESMFold / OmegaFold | Faster than AlphaFlow |
| IDR characterization | **AlphaFlow** | Captures conformational diversity |
| Allosteric analysis | **AlphaFlow** | Compare apo/holo ensembles |
| MD initialization | **AlphaFlow** | Diverse starting conformations |
| No MSA ensemble | **ESMFlow** | Same capability, no MSA needed |

## Tips

- **Sample size**: Use 50-100 conformations for good coverage
- **PDB model**: Always add `--self_cond --resample` for better performance
- **Distilled models**: Require `--noisy_first --no_diffusion` flags
- **Speed**: 12l models are 2.5x faster with small accuracy loss
- **tmax/steps**: Default `--tmax 1.0 --steps 10`. Lower tmax = less diversity, higher precision
- **MSA generation**: Use ColabFold server for convenience, or local MMseqs2 for privacy
- **Templates**: For MD+Templates, provide single-chain PDB with no residue gaps
- **ESMFlow**: Use when you don't have MSAs — much faster setup

## Training (Advanced)

```bash
# Download pretrained weights
wget https://storage.googleapis.com/alphafold/alphafold_params_2022-12-06.tar
tar -xvf alphafold_params_2022-12-06.tar params_model_1.npz
wget https://dl.fbaipublicfiles.com/fair-esm/models/esmfold_3B_v1.pt

# Train AlphaFlow-PDB base
python train.py \
    --lr 5e-4 --noise_prob 0.8 --accumulate_grad 8 \
    --train_epoch_len 80000 --train_cutoff 2018-05-01 --filter_chains \
    --train_data_dir [DIR] --train_msa_dir [DIR] \
    --mmcif_dir [DIR] --val_msa_dir [DIR] \
    --run_name [NAME]

# Continue on ATLAS (MD)
python train.py \
    --normal_validate --sample_train_confs --sample_val_confs \
    --num_val_confs 100 --pdb_chains splits/atlas_train.csv \
    --val_csv splits/atlas_val.csv --self_cond_prob 0.0 --noise_prob 0.9 \
    --train_data_dir [DIR] --train_msa_dir [DIR] \
    --ckpt [AlphaFlow-PDB checkpoint] --run_name [NAME]

# Distillation
python train.py ... --distillation --ckpt [model_to_distill.pt]
```

## References

- [AlphaFlow GitHub](https://github.com/bjing2016/alphaflow)
- [AlphaFlow Paper (ICML 2024)](https://arxiv.org/abs/2402.04845)
- [OpenFold](https://github.com/aqlaboratory/openfold)
- [ATLAS Dataset](https://www.nature.com/articles/s41586-023-06812-9)

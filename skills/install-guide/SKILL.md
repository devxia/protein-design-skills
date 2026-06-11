---
name: install-guide
description: Step-by-step installation guide for third-party protein design tools
---

# Installation Guide for Third-Party Tools

## When to Trigger

- User says "install", "how to install", "setup", "download"
- User asks about tool requirements
- User needs help with conda environments
- User is setting up for the first time

## Overview

This plugin requires 4 third-party tools to be installed separately. Each tool is a large ML model (multi-GB) that must be downloaded and configured.

## Start Here: Minimum Viable Setup (2 tools)

**You only need 2 tools to start designing proteins right now:**

```bash
# 1. PDBFixer (structure repair) — 30 seconds
conda install -c conda-forge pdbfixer openmm

# 2. ESMFold (structure validation) — 1 minute
pip install fair-esm
```

With just these 2 tools, you can:
- Repair PDB files (Stage 0)
- Validate protein structures (Stage 3)

**Then add more tools as needed:**

| When you need... | Install this | Time |
|------------------|-------------|------|
| Backbone generation | RFdiffusion | 30 min |
| Sequence design | ProteinMPNN | 10 min |
| Better validation | AlphaFold3 (needs 2.6TB DB) | 2+ hours |

## Full Install Checklist

```
□ 1. Install Conda (miniconda or anaconda)
□ 2. Install PDBFixer + OpenMM
□ 3. Install RFdiffusion
□ 4. Install ProteinMPNN
□ 5. Install AlphaFold3 (or ESMFold/OmegaFold for no-database setup)
□ 6. Configure plugin paths
□ 7. Verify with session-health-check hook
```

## Step 1: Install Conda

```bash
# Download Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# Initialize
conda init bash
source ~/.bashrc
```

## Step 2: Install PDBFixer + OpenMM

```bash
conda create -n protein-design python=3.10
conda activate protein-design

conda install -c conda-forge pdbfixer openmm

# Verify
python -c "from pdbfixer import PDBFixer; print('PDBFixer OK')"
python -c "from openmm.app import PDBFile; print('OpenMM OK')"
```

## Step 3: Install RFdiffusion

```bash
# Clone repository
git clone https://github.com/RosettaCommons/RFdiffusion.git
cd RFdiffusion

# Create environment
conda env create -f env/SE3nv.yml
conda activate SE3nv

# Install RFdiffusion
pip install -e .
pip install -e env/SE3-transformer

# Download model weights (~2GB)
mkdir models
# Download from: http://files.ipd.uw.edu/pub/RFdiffusion/
# Or use the provided scripts

# Verify
python -c "import rfdiffusion; print('RFdiffusion OK')"
```

**Required model checkpoints:**
- `Base_ckpt.pt` — Default for unconditional/motif
- `Complex_base_ckpt.pt` — Binder design
- `InpaintSeq_ckpt.pt` — Inpainting

## Step 4: Install ProteinMPNN

```bash
# Clone repository
git clone https://github.com/dauparas/ProteinMPNN.git
cd ProteinMPNN

# Create environment
conda create -n proteinmpnn python=3.9
conda activate proteinmpnn

# Install dependencies
pip install torch torchvision
pip install biopython

# Download model weights (~200MB)
# Weights are included in the repository

# Verify
python protein_mpnn_run.py --help
```

## Step 5: Install AlphaFold3

```bash
# Clone repository
git clone https://github.com/google-deepmind/alphafold3.git
cd alphafold3

# Create environment
conda create -n alphafold python=3.11
conda activate alphafold

# Install dependencies
pip install -e .
pip install jax[cuda12]  # For CUDA 12

# Download model parameters (~7GB)
# Request access at: https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md
# After approval, download to ./models/

# Download genetic databases (~2.6TB)
# Or configure to skip MSA: run_data_pipeline=false

# Verify
python run_alphafold.py --help
```

**Alternative: No-Database Validators**

If you don't have 2.6TB for databases, use these instead:

| Tool | Install | GPU Required | Databases |
|------|---------|-------------|-----------|
| ESMFold | `pip install fair-esm` | Optional | None |
| OmegaFold | `pip install omegafold` | Yes | None |
| Boltz-1 | `pip install boltz` | Yes | None |
| Chai-1 | See chai-1 docs | Yes | None |

### Database Setup (Optional but Recommended)

```bash
# Download databases (~2.6TB total)
# Or use a smaller subset for testing

# Configure database directory in the config file
mkdir -p ~/.protein-design
cat > ~/.protein-design/config.yaml <<'EOF'
database_dir: ~/public_databases
EOF
```

## Step 6: Configure Plugin

```bash
# After installing all tools, configure the plugin
cd /path/to/protein-design-skills

# Option 1: Via environment variables
export RFDIFFUSION_PATH=~/software/RFdiffusion
export PROTEINMPNN_PATH=~/software/ProteinMPNN
export ALPHAFOLD_PATH=~/software/alphafold3

# Option 2: Via config file
mkdir -p ~/.protein-design
cat > ~/.protein-design/config.yaml <<'EOF'
paths:
  rfdiffusion: ~/software/RFdiffusion
  proteinmpnn: ~/software/ProteinMPNN
  alphafold: ~/software/alphafold3
EOF

# Option 3: Via conversation
# Tell the agent: "RFdiffusion is at ~/software/RFdiffusion"
```

## Step 7: Verify Installation

```bash
# Run verification
python protein_design/hooks/session-health-check.py
```

Expected output:
```
RFdiffusion: ✓
ProteinMPNN: ✓
AlphaFold3: ✓
PDBFixer: ✓
```

## Troubleshooting Installation

### Conda environment conflicts
```bash
# If environments conflict, use wrapper_script
wrapper_script = """
#!/bin/bash
conda activate SE3nv
python "$@"
"""
```

### CUDA version mismatch
```bash
# Check CUDA version
nvidia-smi

# Install matching PyTorch
# For CUDA 11.8: pip install torch --index-url https://download.pytorch.org/whl/cu118
# For CUDA 12.1: pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### Out of disk space
```bash
# Databases need ~2.6TB
# Use external drive or network storage
# Or skip MSA: run_data_pipeline=false
```

### Model weights not found
```bash
# Download from official sources
# RFdiffusion: http://files.ipd.uw.edu/pub/RFdiffusion/
# AlphaFold3: Follow Google DeepMind instructions
```

## Minimal Setup (No Databases)

For quick testing without full databases:

```bash
# 1. Install only PDBFixer + RFdiffusion + ProteinMPNN
# 2. Use ESMFold or OmegaFold for Stage 3 (no databases needed)
pip install fair-esm  # ESMFold
# or
pip install omegafold  # OmegaFold

# 3. Run the pipeline with alternative validator
python scripts/run_esmfold.py --input seqs.fa --output-dir outputs/validation/
# or
python scripts/run_omegafold.py --input seqs.fa --output-dir outputs/validation/
```

**Recommended minimal stack for beginners:**
```
PDBFixer + RFdiffusion + ProteinMPNN + ESMFold
```
This gives you a complete pipeline with no database downloads and reasonable GPU requirements (8GB+ VRAM).

### Quick Start with 3 Tools (Complete Pipeline)

```bash
# Install all 3 tools at once
conda create -n protein-design python=3.10
conda activate protein-design
conda install -c conda-forge pdbfixer openmm
pip install fair-esm  # ESMFold — no databases needed

# Clone and install RFdiffusion
git clone https://github.com/RosettaCommons/RFdiffusion.git
cd RFdiffusion && conda env create -f env/SE3nv.yml && conda activate SE3nv && pip install -e .

# Clone and install ProteinMPNN
cd .. && git clone https://github.com/dauparas/ProteinMPNN.git
cd ProteinMPNN && conda create -n proteinmpnn python=3.9 && conda activate proteinmpnn && pip install torch biopython

# Verify all tools
python protein_design/hooks/session-health-check.py
```

**What you can do with this setup:**
- ✅ Repair PDB files (PDBFixer)
- ✅ Generate protein backbones (RFdiffusion)
- ✅ Design sequences (ProteinMPNN)
- ✅ Validate structures (ESMFold — fast, no databases)
- ✅ Filter and rank designs (built-in script)

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA with 8GB VRAM | NVIDIA A100/V100 with 16GB+ |
| CPU | 8 cores | 16+ cores |
| RAM | 32GB | 64GB+ |
| Disk | 100GB | 3TB (with databases) |
| OS | Linux | Linux (Ubuntu 20.04+) |

## Tool Not Installed?

If a required tool is not installed, you have options:

| Missing Tool | Quick Alternative | Install Time |
|--------------|-------------------|-------------|
| RFdiffusion | Use Chroma (`pip install chroma`) or FoldFlow | 15-30 min |
| ProteinMPNN | Use ESM-IF1 (`pip install fair-esm`) | 5 min |
| AlphaFold3 | Use ESMFold (`pip install fair-esm`) or OmegaFold (`pip install omegafold`) | 5-10 min |
| PDBFixer | Use `conda install -c conda-forge pdbfixer openmm` | 5 min |

**No GPU?** Use ESMFold (CPU-compatible) or run on Google Colab.

**No conda?** Use pip-only alternatives: ESMFold, OmegaFold, Boltz-1.

## Tips

- Install tools in separate conda environments to avoid conflicts
- Use `wrapper_script` for complex environment setups
- Keep model weights on fast storage (SSD/NVMe)
- For shared systems, install tools in a shared location
- Always verify with `python protein_design/hooks/session-health-check.py` after installation

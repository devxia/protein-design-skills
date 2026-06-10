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

## Quick Install Checklist

```
□ 1. Install Conda (miniconda or anaconda)
□ 2. Install PDBFixer + OpenMM
□ 3. Install RFdiffusion
□ 4. Install ProteinMPNN
□ 5. Install AlphaFold3
□ 6. Configure plugin paths
□ 7. Verify with check_all_tools
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
mkdir models
# Follow AlphaFold3 docs for download links

# Download genetic databases (~2.6TB)
# Or configure to skip MSA: run_data_pipeline=false

# Verify
python run_alphafold.py --help
```

### Database Setup (Optional but Recommended)

```bash
# Download databases (~2.6TB total)
# Or use a smaller subset for testing

# Configure in plugin
configure_db_dir(path="~/public_databases")
```

## Step 6: Configure Plugin

```bash
# After installing all tools, configure the plugin
cd /path/to/protein-design-skills

# Option 1: Via environment variables
export RFDIFFUSION_PATH=~/software/RFdiffusion
export PROTEINMPNN_PATH=~/software/ProteinMPNN
export ALPHAFOLD_PATH=~/software/alphafold3

# Option 2: Via MCP tools
python -m protein_design.server
# Then: configure_tool_path(tool_name="rfdiffusion", path="~/software/RFdiffusion")

# Option 3: Via conversation
# Tell the agent: "RFdiffusion is at ~/software/RFdiffusion"
```

## Step 7: Verify Installation

```bash
# Run verification
python -m protein_design.server
# Then call: check_all_tools()
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
# Skip database download
# Use run_data_pipeline=false for AlphaFold3
# Use ESMFold for fast screening
```

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA with 8GB VRAM | NVIDIA A100/V100 with 16GB+ |
| CPU | 8 cores | 16+ cores |
| RAM | 32GB | 64GB+ |
| Disk | 100GB | 3TB (with databases) |
| OS | Linux | Linux (Ubuntu 20.04+) |

## Tips

- Install tools in separate conda environments to avoid conflicts
- Use `wrapper_script` for complex environment setups
- Keep model weights on fast storage (SSD/NVMe)
- For shared systems, install tools in a shared location
- Always verify with `check_all_tools` after installation

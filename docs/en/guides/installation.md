---
title: Installation Guide
source: README.md
---

# Installation Guide

> **Important**: This plugin does **NOT** install RFdiffusion, ProteinMPNN, AlphaFold3, or PDBFixer. These are large machine-learning models (multi-GB) that must be installed separately. The plugin provides the **orchestration layer** — skills, hooks, and standalone scripts — that guides agents through the design pipeline.

## Architecture Overview

This plugin uses a **skills + hooks + scripts** architecture:

- **Skills** (`skills/`) — 79 Markdown workflow guides that tell the agent how to use each tool
- **Hooks** (`protein_design/hooks/`) — 24 automation scripts for context injection, GPU checks, progress tracking, and notifications
- **Standalone Scripts** (`scripts/`) — 16 direct CLI scripts for tool execution

The plugin works with any coding agent that reads skills and runs Python scripts.

## Choose your agent

| Agent | Setup |
|-------|-------|
| **Claude Code** | `claude plugin marketplace add devxia/protein-design-skills` then `claude plugin install protein-design-skills@protein-design-skills` |
| **Codex CLI** | `codex plugin marketplace add devxia/protein-design-skills` then `codex plugin install protein-design-skills` |
| **Kimi Code** | `/plugins install https://github.com/devxia/protein-design-skills` |

For manual installation, install hooks per agent:

```bash
# Claude Code
python protein_design/hooks/install-hooks.py claude

# Codex CLI
python protein_design/hooks/install-hooks.py codex

# All agents
python protein_design/hooks/install-hooks.py
```

You can also install project-local hooks for Claude Code and Codex CLI:

```bash
python protein_design/hooks/install-hooks.py --local claude codex
```

## Install the plugin

```bash
git clone https://github.com/devxia/protein-design-skills.git
cd protein-design-skills
pip install -r requirements.txt
```

### Install hooks (recommended)

Hooks provide automatic context injection, GPU safety checks, and desktop notifications:

```bash
# For Claude Code
python protein_design/hooks/install-hooks.py claude

# For Codex CLI
python protein_design/hooks/install-hooks.py codex

# For all agents
python protein_design/hooks/install-hooks.py
```

Hooks are installed per-agent and can be customized. See `protein_design/hooks/install-hooks.py --help` for options.

### Kimi Code

From GitHub:
```
/plugins install https://github.com/devxia/protein-design-skills
```

From local directory:
```
/plugins install /path/to/protein-design-skills
```

Start a **new session** after installation:
```
/new
```

> Plugin changes only apply to new sessions.

## System requirements

- Python >= 3.9
- CUDA-capable GPU with >= 16GB VRAM (recommended)
- Conda (miniconda or anaconda)
- Separately installed: RFdiffusion, ProteinMPNN, AlphaFold3, PDBFixer + OpenMM

## Install external tools

> **Already have these tools?** Just tell the Agent where each tool is located and which conda environment it uses. The plugin auto-detects common install locations.

### Step 1: Create a Conda environment

```bash
conda create -n protein-design python=3.10
conda activate protein-design
```

### Step 2: Install PDBFixer + OpenMM

```bash
conda install -c conda-forge pdbfixer openmm>=8.2
```

Verify: `python -c "from pdbfixer import PDBFixer; print('PDBFixer OK')"`

### Step 3: Install RFdiffusion

```bash
cd ~/software
git clone https://github.com/RosettaCommons/RFdiffusion.git
cd RFdiffusion
conda env create -f env/SE3nv.yml
conda activate SE3nv
pip install -e .
```

Download model weights (~2GB) per official instructions.

### Step 4: Install ProteinMPNN

```bash
cd ~/software
git clone https://github.com/dauparas/ProteinMPNN.git
```

No pip install needed — run directly as a script.

### Step 5: Install AlphaFold3

**Option A: Docker (Recommended)**

```bash
git clone https://github.com/google-deepmind/alphafold3.git
cd alphafold3
docker build -t alphafold3 -f docker/Dockerfile .
```

**Option B: Local Installation**

```bash
git clone https://github.com/google-deepmind/alphafold3.git
cd alphafold3
pip install -r requirements.txt
```

Download model parameters (~1.6GB): Request access at https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md

Download genetic databases (~2.6TB): See AlphaFold3 documentation for database setup.

**Option C: No-Database Validators (Easiest)**

If you don't have 2.6TB for databases, use these alternatives:

| Tool | Install | GPU | Databases | Speed |
|------|---------|-----|-----------|-------|
| ESMFold | `pip install fair-esm` | Optional | None | ~2s/seq |
| OmegaFold | `pip install omegafold` | Yes | None | ~5s/seq |
| Boltz-1 | `pip install boltz` | Yes | None | ~10s/seq |
| Chai-1 | See chai-1 docs | Yes | None | ~10s/seq |

### Optional: Install additional validation tools

| Tool | License | Best For |
|------|---------|----------|
| Boltz-1 | MIT | Complexes, covalent modifications |
| Chai-1 | Apache 2.0 | Constraints, licensing flexibility |
| OmegaFold | MIT | Fast, no databases |
| ESMFold | MIT | Ultra-fast screening, CPU-compatible |

## Configure tool paths

**Method A: Environment Variables**

```bash
export RFDIFFUSION_PATH="$HOME/software/RFdiffusion"
export PROTEINMPNN_PATH="$HOME/software/ProteinMPNN"
export ALPHAFOLD_PATH="$HOME/software/alphafold3"
export PROTEIN_DESIGN_OUTPUT_DIR="/tmp/protein-design"
```

**Method B: Config File (Recommended)**

```yaml
# ~/.protein-design/config.yaml
output_dir: /tmp/protein-design
max_jobs: 4
timeout: 3600
rfdiffusion_path: /Users/YOURNAME/software/RFdiffusion
proteinmpnn_path: /Users/YOURNAME/software/ProteinMPNN
alphafold_path: /Users/YOURNAME/software/alphafold3
rfdiffusion_conda_env: SE3nv
proteinmpnn_conda_env: null
alphafold_conda_env: null
```

> **Legacy path**: `~/.kimi-protein-design/config.yaml` is also supported for backward compatibility.

**Method C: Symlinks**

```bash
ln -s ~/software/RFdiffusion ./RFdiffusion
ln -s ~/software/ProteinMPNN ./ProteinMPNN
ln -s ~/software/alphafold3 ./alphafold3
```

## Verify installation

After installing hooks and external tools, verify everything works:

```bash
# Check skill discovery
ls skills/

# Test standalone script execution
python scripts/run_pdbfixer.py --help

# Check tool detection
python protein_design/hooks/session-health-check.py
```

The `session-health-check` hook reports which tools are installed, their detected paths, and provides installation instructions for any missing tools.

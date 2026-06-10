---
title: Installation Guide
source: README.md
---

# Installation Guide

> ⚠️ **Important**: This plugin does **NOT** install RFdiffusion, ProteinMPNN, AlphaFold3, or PDBFixer. These are large machine-learning models (multi-GB) that must be installed separately. The plugin provides the **orchestration layer** that calls these tools via subprocess.

## Choose your agent

This plugin works with any MCP-compatible coding agent:

| Agent | Setup |
|-------|-------|
| **Claude Code** | Use `.mcp.json` (included) or `~/.claude/settings.json` |
| **Codex CLI** | Add MCP server config to `~/.codex/settings.json` |
| **Kimi Code** | Use `kimi.plugin.json` (included) — `/plugins install` |

## Install the plugin

### Claude Code / Codex CLI

```bash
git clone https://github.com/devxia/protein-design-mcp.git
cd protein-design-mcp
pip install -r requirements.txt
```

The included `.mcp.json` configures the MCP server automatically when the agent starts in this directory.

For global availability, add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "protein-design-mcp": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/protein-design-mcp",
      "env": {
        "PYTHONPATH": "/path/to/protein-design-mcp",
        "PROTEIN_DESIGN_OUTPUT_DIR": "/tmp/protein-design",
        "PROTEIN_DESIGN_MAX_JOBS": "4"
      }
    }
  }
}
```

### Kimi Code

From GitHub:
```
/plugins install https://github.com/devxia/protein-design-mcp
```

From local directory:
```
/plugins install /path/to/protein-design-mcp
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

> 💡 **Already have these tools?** Just tell the Agent where each tool is located and which conda environment it uses. The plugin auto-detects common install locations.

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

Download model parameters (~1.6GB) and genetic databases (~2.6TB).

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

Check that the MCP server is connected (method varies by agent), then test:

```
Call get_tool_info
Call health_check
```

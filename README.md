# 🧬 Kimi Protein Design

> **English** | [中文](./README.zh.md)

A [Kimi Code](https://github.com/MoonshotAI/Kimi-Code) plugin for end-to-end protein design workflows. Generate protein backbones, design sequences, validate structures, and rank results — all through natural language conversation.

## Features

- **Stage 0 — Structure Preprocessing**: Automatic PDB repair with PDBFixer (non-standard residues, heterogens, missing atoms)
- **Stage 1 — Backbone Generation**: RFdiffusion for monomers, binders, motif scaffolding, and symmetric oligomers
- **Stage 2 — Sequence Design**: ProteinMPNN for amino acid sequence assignment
- **Stage 3 — Structure Validation**: AlphaFold3 for confidence scoring (pLDDT, ipTM, pTM)
- **Stage 4 — Filtering & Ranking**: Automated quality filtering and composite scoring
- **Async Job Management**: Submit long-running jobs and poll for results
- **Batch Validation**: CronCreate support for large-scale AlphaFold3 screening
- **Hooks (0.6.0+)**: Context injection, GPU safety checks, and desktop notifications

## ⚠️ Important: Plugin ≠ Tools

This plugin **does not bundle** RFdiffusion, ProteinMPNN, AlphaFold3, or PDBFixer. These are large machine-learning models (multi-GB) that must be installed separately. The plugin provides the **orchestration layer** (MCP Server + Skills) that calls these tools via subprocess.

## Requirements

- Kimi Code >= 0.6.0
- Python >= 3.9
- CUDA-capable GPU with >= 16GB VRAM (recommended)
- Conda (miniconda or anaconda)
- Separately installed: RFdiffusion, ProteinMPNN, AlphaFold3, PDBFixer + OpenMM

## Prerequisites Installation

### Step 1: Create a Conda Environment

```bash
conda create -n protein-design python=3.10
conda activate protein-design
```

### Step 2: Install PDBFixer + OpenMM (Stage 0)

PDBFixer is the only Python-API dependency; the rest are subprocess calls.

```bash
conda install -c conda-forge pdbfixer openmm>=8.2
```

Verify:
```bash
python -c "from pdbfixer import PDBFixer; print('PDBFixer OK')"
```

### Step 3: Install RFdiffusion (Stage 1)

```bash
# Clone repository
cd ~/software  # or your preferred directory
git clone https://github.com/RosettaCommons/RFdiffusion.git
cd RFdiffusion

# Create its own conda environment (recommended)
conda env create -f env/SE3nv.yml
conda activate SE3nv

# Install RFdiffusion package
pip install -e .

# Download model weights (~2GB)
mkdir -p models
# Follow official instructions: https://github.com/RosettaCommons/RFdiffusion
# Typically involves downloading from Zenodo or HuggingFace
```

The plugin looks for `RFdiffusion/scripts/run_inference.py` at these locations (in order):
1. `$RFDIFFUSION_PATH/scripts/run_inference.py` (environment variable)
2. `./RFdiffusion/scripts/run_inference.py`
3. `~/RFdiffusion/scripts/run_inference.py`
4. `/opt/RFdiffusion/scripts/run_inference.py`

### Step 4: Install ProteinMPNN (Stage 2)

```bash
cd ~/software
git clone https://github.com/dauparas/ProteinMPNN.git
```

No additional pip install is needed — it's run directly as a script.

The plugin looks for `ProteinMPNN/protein_mpnn_run.py` at:
1. `$PROTEINMPNN_PATH/protein_mpnn_run.py` (environment variable)
2. `./ProteinMPNN/protein_mpnn_run.py`
3. `~/ProteinMPNN/protein_mpnn_run.py`
4. `/opt/ProteinMPNN/protein_mpnn_run.py`

### Step 5: Install AlphaFold3 (Stage 3)

AlphaFold3 is the most complex dependency. Two installation modes:

#### Option A: Docker (Recommended, Easiest)

```bash
cd ~/software
git clone https://github.com/google-deepmind/alphafold3.git
cd alphafold3

# Build Docker image
docker build -t alphafold3 -f docker/Dockerfile .

# Download model parameters (~1.6GB) and databases (~2.6TB total)
# Follow: https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md
```

> **Note:** The current plugin code uses local Python execution (`python run_alphafold.py`). For Docker mode, you would need to modify `mcp_server/tools/alphafold.py` to wrap commands in `docker run`. See the comments in that file for guidance.

#### Option B: Local Installation

```bash
cd ~/software
git clone https://github.com/google-deepmind/alphafold3.git
cd alphafold3

# Install dependencies
pip install -r requirements.txt

# Download model parameters to ~/models
# Download genetic databases to ~/public_databases
# See: https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md
```

The plugin looks for `alphafold3/run_alphafold.py` at:
1. `$ALPHAFOLD_PATH/run_alphafold.py` (environment variable)
2. `./alphafold3/run_alphafold.py`
3. `~/alphafold3/run_alphafold.py`
4. `/opt/alphafold3/run_alphafold.py`

### Step 6: Tell the Plugin Where Your Tools Are

After installing the tools, you must inform the plugin of their locations.

**Method A: Environment Variables** (temporary, current shell only)

```bash
export RFDIFFUSION_PATH="$HOME/software/RFdiffusion"
export PROTEINMPNN_PATH="$HOME/software/ProteinMPNN"
export ALPHAFOLD_PATH="$HOME/software/alphafold3"
export PROTEIN_DESIGN_OUTPUT_DIR="/tmp/protein-design"
```

Add to `~/.bashrc` or `~/.zshrc` to make permanent.

**Method B: Config File** (persistent, recommended)

```bash
mkdir -p ~/.kimi-protein-design
cat > ~/.kimi-protein-design/config.yaml << 'EOF'
output_dir: /tmp/protein-design
max_jobs: 4
timeout: 3600
rfdiffusion_path: /Users/YOURNAME/software/RFdiffusion
proteinmpnn_path: /Users/YOURNAME/software/ProteinMPNN
alphafold_path: /Users/YOURNAME/software/alphafold3
EOF
```

Replace `/Users/YOURNAME` with your actual home directory path.

**Method C: Symlinks** (simplest if you don't want config files)

```bash
ln -s ~/software/RFdiffusion ./RFdiffusion
ln -s ~/software/ProteinMPNN ./ProteinMPNN
ln -s ~/software/alphafold3 ./alphafold3
```

Place these symlinks in the same directory where Kimi Code launches the MCP server (i.e., the plugin root directory).

### Step 7: Verify Installation

After installing the plugin (`/plugins install ...` + `/new`), run:

```
/mcp
```

You should see `protein` server connected. Then test:

```
Call get_tool_info
Call health_check
```

`health_check` will report whether RFdiffusion, ProteinMPNN, and AlphaFold3 are detectable.

## Installation

### From GitHub (Recommended)

```
/plugins install https://github.com/<owner>/kimi-protein-design
```

### From Local Directory

```
/plugins install /path/to/kimi-protein-design
```

### Activate Plugin

After installation, start a **new session** for the plugin to take effect:

```
/new
```

> ⚠️ **Important**: Plugin changes only apply to new sessions. Existing sessions keep their initial plugin snapshot.

## Uninstallation

### What `/plugins install` Actually Installs

When you run `/plugins install`, Kimi Code downloads the plugin repository to its internal plugin directory (`~/.kimi-code/plugins/...`) and registers:

| Component | What it is | Location |
|-----------|-----------|----------|
| **Manifest** | `kimi.plugin.json` | Inside plugin directory |
| **Skills** | 7 Markdown files under `skills/` | Inside plugin directory |
| **MCP Server** | Python source under `mcp_server/` | Inside plugin directory |
| **MCP Registration** | Stdio server config | Kimi Code internal state |
| **Session Start** | Auto-load skill binding | Kimi Code internal state |

**Important**: The plugin does **NOT** install RFdiffusion, ProteinMPNN, AlphaFold3, or PDBFixer. Those are external tools you install separately.

### Plugin-Level Uninstall

```
/plugins remove kimi-protein-design
```

This removes:
- ✅ Plugin source code (`~/.kimi-code/plugins/.../kimi-protein-design/`)
- ✅ MCP server registration (protein server no longer starts)
- ✅ Skills index and session-start binding

This does **NOT** remove:
- ❌ `~/.kimi-protein-design/config.yaml` (your path configurations)
- ❌ Hooks in `~/.kimi-code/hooks/` (if you ran `install-hooks.py`)
- ❌ Hooks entries in `~/.kimi-code/config.toml`
- ❌ Output files in `/tmp/protein-design/`
- ❌ External tools (RFdiffusion, ProteinMPNN, AlphaFold3, databases)

### Complete Cleanup (Remove Everything)

To completely erase all traces:

```bash
# 1. Uninstall plugin (in Kimi Code)
# /plugins remove kimi-protein-design

# 2. Delete plugin configuration
rm -rf ~/.kimi-protein-design/

# 3. Delete hooks (if installed)
rm -f ~/.kimi-code/hooks/protein-context-inject.py
rm -f ~/.kimi-code/hooks/gpu-check-hook.py
rm -f ~/.kimi-code/hooks/design-complete-notify.py
rm -f ~/.kimi-code/hooks/background-notify.py

# 4. Edit ~/.kimi-code/config.toml and remove [[hooks]] sections for this plugin

# 5. Delete history outputs (optional)
rm -rf /tmp/protein-design/

# 6. External tools (optional, very large)
rm -rf ~/software/RFdiffusion
rm -rf ~/software/ProteinMPNN
rm -rf ~/software/alphafold3
rm -rf ~/public_databases
```

### Cleanup Checklist

| Component | `remove` command | Manual cleanup needed? |
|-----------|-----------------|----------------------|
| Plugin source | ✅ Auto | No |
| MCP registration | ✅ Auto | No |
| `~/.kimi-protein-design/config.yaml` | ❌ No | `rm -rf ~/.kimi-protein-design/` |
| Hooks scripts | ❌ No | `rm ~/.kimi-code/hooks/*.py` |
| Hooks config.toml entries | ❌ No | Edit `~/.kimi-code/config.toml` |
| Output files | ❌ No | `rm -rf /tmp/protein-design/` |
| External tools | ❌ No | `rm -rf ~/software/...` |

## Quick Start

### Example 1: Design a 150-aa monomer

```
User: Generate a 150 amino acid protein backbone
→ Plugin auto-runs RFdiffusion with contig [150-150]
```

### Example 2: Design a binder for PD-L1

```
User: Design a binder targeting PD-L1
→ Stage 0: PDBFixer preprocesses target.pdb
→ Stage 1: RFdiffusion generates binder backbones
→ Stage 2: ProteinMPNN designs binder sequences
→ Stage 3: AlphaFold3 validates structures
→ Stage 4: Filter by ipTM > 0.8 and pLDDT > 80
```

## Architecture

```
kimi-protein-design/
├── kimi.plugin.json              # Plugin manifest
├── skills/                       # Workflow guidance
│   ├── protein-design-context/   # Session-start context
│   ├── structure-preprocessing/  # Stage 0: PDBFixer
│   ├── structure-generation/     # Stage 1: RFdiffusion
│   ├── sequence-design/          # Stage 2: ProteinMPNN
│   ├── structure-validation/     # Stage 3: AlphaFold3
│   ├── filtering-ranking/        # Stage 4: Filtering
│   └── full-pipeline/            # End-to-end orchestration
├── mcp_server/                   # MCP Server (stdio JSON-RPC)
│   ├── server.py                 # Main entry
│   ├── tools/                    # Tool implementations
│   │   ├── job_manager.py        # Async task management
│   │   ├── pdbfixer_tool.py      # PDB preprocessing
│   │   ├── rfdiffusion.py        # Backbone generation
│   │   ├── proteinmpnn.py        # Sequence design
│   │   ├── alphafold.py          # Structure validation
│   │   ├── format_converter.py   # FASTA ↔ JSON conversion
│   │   ├── filtering.py          # Quality filtering
│   │   └── system_info.py        # Environment checks
│   ├── utils/                    # Utilities
│   │   ├── config.py             # Configuration
│   │   └── gpu_utils.py          # GPU detection
│   └── hooks/                    # Recommended hooks
│       ├── install-hooks.py      # One-click installer
│       ├── protein-context-inject.py
│       ├── gpu-check-hook.py
│       ├── design-complete-notify.py
│       └── background-notify.py
└── README.md
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `get_tool_info` | List all tools and their parameters |
| `health_check` | Check GPU, CUDA, conda, disk space |
| `submit_job` | Submit async computation job |
| `query_job` | Poll job status by task_id |
| `cancel_job` | Cancel a running job |
| `run_pdbfixer` | Preprocess PDB/CIF (mandatory Stage 0) |
| `run_rfdiffusion` | Generate protein backbones |
| `run_proteinmpnn` | Design amino acid sequences |
| `run_alphafold3` | Predict and validate structures |
| `convert_format` | Convert FASTA → AlphaFold3 JSON |
| `run_filtering` | Filter and rank by metrics |
| `check_batch_progress` | Check multiple jobs at once |

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROTEIN_DESIGN_OUTPUT_DIR` | `/tmp/protein-design` | Output directory |
| `PROTEIN_DESIGN_MAX_JOBS` | `4` | Max concurrent jobs |
| `PROTEIN_DESIGN_TIMEOUT` | `3600` | Job timeout (seconds) |
| `RFDIFFUSION_PATH` | auto-detect | RFdiffusion install path |
| `PROTEINMPNN_PATH` | auto-detect | ProteinMPNN install path |
| `ALPHAFOLD_PATH` | auto-detect | AlphaFold3 install path |

Config file: `~/.kimi-protein-design/config.yaml`

```yaml
output_dir: /tmp/protein-design
max_jobs: 4
timeout: 3600
rfdiffusion_path: /opt/RFdiffusion
proteinmpnn_path: /opt/ProteinMPNN
alphafold_path: /opt/alphafold3
```

## Hooks (Strongly Recommended)

Kimi Code 0.6.0+ supports hooks for enhanced protein design workflows.

### Install Hooks

```bash
python mcp_server/hooks/install-hooks.py
```

This installs:
- **UserPromptSubmit** — Auto-inject GPU/tool status into model context
- **PreToolUse** — Block submit_job if GPU/disk is insufficient
- **PostToolUse** — Desktop notification when jobs complete
- **Notification** — Alert on background task completion/failure

Then restart Kimi Code: `/new`

### Manual Hook Configuration

Add to `~/.kimi-code/config.toml`:

```toml
[[hooks]]
event = "UserPromptSubmit"
matcher = "(?i)(protein|pdb|binder|alphafold|rfdiffusion|proteinmpnn|design|structure|sequence|residue|loop|scaffold)"
command = "python ~/.kimi-code/hooks/protein-context-inject.py"
timeout = 3

[[hooks]]
event = "PreToolUse"
matcher = "mcp__.*__submit_job"
command = "python ~/.kimi-code/hooks/gpu-check-hook.py"
timeout = 5

[[hooks]]
event = "PostToolUse"
matcher = "mcp__.*__query_job"
command = "python ~/.kimi-code/hooks/design-complete-notify.py"
timeout = 5

[[hooks]]
event = "Notification"
matcher = "task\\.completed|task\\.failed|task\\.killed"
command = "python ~/.kimi-code/hooks/background-notify.py"
timeout = 5
```

## Batch Validation with CronCreate

For large-scale screening (>10 designs), use CronCreate instead of blocking polling:

1. Submit all AlphaFold3 validation jobs (async)
2. Create periodic check:
   ```
   CronCreate(cron="*/10 * * * *", prompt="Check AF3 batch progress for task_ids [X,Y,Z]. Report completed count and pLDDT>80 pass rate.")
   ```
3. Session is freed for other work
4. When done, cancel timer:
   ```
   CronDelete(id="<id>")
   ```

## Quality Thresholds

| Metric | Acceptable | Good | Excellent |
|--------|-----------|------|-----------|
| pLDDT | >70 | >80 | >90 |
| ipTM | >0.6 | >0.8 | >0.9 |
| pTM | >0.5 | >0.7 | >0.9 |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Plugin not loading | Run `/new` after installation |
| `run_pdbfixer` not found | `conda install -c conda-forge pdbfixer openmm` |
| RFdiffusion not found | Set `RFDIFFUSION_PATH` env var |
| GPU out of memory | Reduce `num_designs` or `diffuser_T` |
| AlphaFold3 MSA timeout | Set `run_data_pipeline=false` if re-running |
| Hooks not working | Verify `~/.kimi-code/config.toml` syntax, then `/new` |

## License

MIT

## Acknowledgments

- RFdiffusion — [Watson et al., 2023](https://www.nature.com/articles/s41586-023-06415-8)
- ProteinMPNN — [Dauparas et al., 2022](https://www.science.org/doi/10.1126/science.add2187)
- AlphaFold3 — [Abramson et al., 2024](https://www.nature.com/articles/s41586-024-07487-w)
- PDBFixer — OpenMM project

---
name: config-management
description: Manage plugin configuration through natural language
---

# Configuration Management

## When to Trigger

- User says "configure", "set path", "where is", "install location"
- User wants to change output directory
- User asks about tool paths or conda environments
- User wants to check current configuration
- User says "my databases are at", "my tools are in"

## Current Configuration

The plugin reads configuration from (in priority order):
1. **Environment variables** (highest priority)
2. **Config file** (`~/.protein-design/config.yaml`)
3. **Auto-detection** (lowest priority)

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `RFDIFFUSION_PATH` | RFdiffusion installation directory | `~/software/RFdiffusion` |
| `PROTEINMPNN_PATH` | ProteinMPNN installation directory | `~/software/ProteinMPNN` |
| `ALPHAFOLD_PATH` | AlphaFold3 installation directory | `~/software/alphafold3` |
| `PROTEIN_DESIGN_OUTPUT_DIR` | Default output directory | `/tmp/protein-design` |
| `PROTEIN_DESIGN_MAX_JOBS` | Max concurrent jobs | `4` |

### Config File (`~/.protein-design/config.yaml`)

```yaml
rfdiffusion_path: /home/user/software/RFdiffusion
proteinmpnn_path: /home/user/software/ProteinMPNN
alphafold_path: /home/user/software/alphafold3
db_dir: /home/user/public_databases
output_dir: /tmp/protein-design
max_jobs: 4
rfdiffusion_conda_env: SE3nv
proteinmpnn_conda_env: proteinmpnn
alphafold_conda_env: alphafold
```

## Natural Language Configuration

Users can tell the agent:

### Setting Tool Paths

```
User: My RFdiffusion is at ~/software/RFdiffusion
→ Plugin auto-configures RFDIFFUSION_PATH

User: ProteinMPNN uses conda env "mpnn"
→ Plugin saves proteinmpnn_conda_env to config

User: I have all tools in /opt/protein-tools
→ Plugin detects and configures all tools
```

### Setting Database Path

```
User: My AlphaFold databases are at /data/databases
→ Plugin auto-detects valid database subdirectories
→ Saves to config if valid

User: Check database status
→ Plugin shows detected databases, sizes, and completeness
```

### Checking Configuration

```
User: What's my current config?
→ Plugin shows all configured paths, detected tools, and environment

User: Are my tools properly configured?
→ Plugin runs `python protein_design/hooks/session-health-check.py` and reports status
```

### Setting Output Directory

```
User: Save outputs to ~/protein-design-results
→ Plugin sets PROTEIN_DESIGN_OUTPUT_DIR

User: Use /tmp for outputs
→ Plugin sets output_dir to /tmp
```

## Auto-Detection

The plugin automatically searches common locations:

### RFdiffusion
- `./RFdiffusion`
- `~/RFdiffusion`
- `/opt/RFdiffusion`
- Conda environments with `rfdiffusion` package

### ProteinMPNN
- `./ProteinMPNN`
- `~/ProteinMPNN`
- `/opt/ProteinMPNN`

### AlphaFold3
- `./alphafold3`
- `~/alphafold3`
- `/opt/alphafold3`

### Databases
- `~/public_databases`
- `~/databases`
- `/opt/public_databases`

## Configuration Commands

### Direct YAML Editing (Recommended)

Create or edit `~/.protein-design/config.yaml`:

```yaml
# Tool paths
tool_paths:
  rfdiffusion: ~/software/RFdiffusion
  proteinmpnn: ~/software/ProteinMPNN
  alphafold3: ~/software/alphafold3
  boltz: ~/software/boltz
  chai1: ~/software/chai-1
  omegafold: ~/software/OmegaFold
  esmfold: ~/software/esmfold
  protenix: ~/software/protenix
  openfold3: ~/software/openfold3
  pdbfixer: ~/software/pdbfixer

# Conda environments for each tool
conda_envs:
  rfdiffusion: SE3nv
  proteinmpnn: mpnn
  alphafold3: af3

# AlphaFold3 genetic databases directory (~2.6 TB)
db_dir: ~/public_databases

# Job management
max_jobs: 4
output_dir: /tmp/protein-design

# Timeouts (seconds)
timeout: 3600
```

You can also use environment variables (highest priority):

```bash
export RFDIFFUSION_PATH=~/software/RFdiffusion
export PROTEINMPNN_PATH=~/software/ProteinMPNN
export ALPHAFOLD_PATH=~/software/alphafold3
export PROTEIN_DESIGN_OUTPUT_DIR=/tmp/protein-design
export PROTEIN_DESIGN_MAX_JOBS=4
```

### Via Conversation

The agent interprets natural language and writes the config for you:

```
User: "RFdiffusion is in ~/software/RFdiffusion, SE3nv env"
→ Agent updates ~/.protein-design/config.yaml

User: "Databases at /data/public_databases"
→ Agent sets db_dir in config.yaml

User: "max 8 jobs"
→ Agent sets max_jobs: 8 in config.yaml
```

## Tips

- Configuration persists across sessions (saved to `~/.protein-design/config.yaml`)
- Environment variables override config file settings
- Auto-detection runs on every session start
- Use `python protein_design/hooks/install-hooks.py` for automation
- Legacy `~/.kimi-protein-design/` config is also supported for migration

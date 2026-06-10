# 🧬 Protein Design MCP

> **English** | [中文](./README.zh.md)

An agent-agnostic protein design plugin for coding agents (Claude Code, Codex CLI, Kimi Code, etc.). Orchestrates RFdiffusion, ProteinMPNN, AlphaFold3, and PDBFixer for end-to-end protein design workflows. Generate protein backbones, design sequences, validate structures, and rank results — all through natural language conversation.

## Features

- **Stage 0 — Structure Preprocessing**: Automatic PDB repair with PDBFixer
- **Stage 1 — Backbone Generation**: RFdiffusion for monomers, binders, motif scaffolding, and symmetric oligomers
- **Stage 2 — Sequence Design**: ProteinMPNN for amino acid sequence assignment
- **Stage 3 — Structure Validation**: AlphaFold3 for confidence scoring (pLDDT, ipTM, pTM)
- **Stage 4 — Filtering & Ranking**: Automated quality filtering and composite scoring
- **Async Job Management**: Submit long-running jobs and poll for results
- **Batch Validation**: Scheduling support for large-scale AlphaFold3 screening
- **Hooks (0.6.0+)**: Context injection, GPU safety checks, and desktop notifications


> **Note:** This plugin does not bundle RFdiffusion, ProteinMPNN, AlphaFold3, or PDBFixer. These are large machine-learning models (multi-GB) that must be installed separately. The plugin provides the orchestration layer (MCP Server + Skills) that calls these tools via subprocess.


## Installation

### Prerequisites

This plugin works with any MCP-compatible coding agent (Claude Code, Codex CLI, Kimi Code, etc.).

### Option 1: Claude Code

```bash
# Clone the plugin
git clone https://github.com/devxia/protein-design-mcp.git
cd protein-design-mcp

# Install dependencies
pip install -r requirements.txt

# The .mcp.json at the project root configures the MCP server automatically.
# Or add to ~/.claude/settings.json manually.
```

### Option 2: Kimi Code

```
/plugins install https://github.com/devxia/protein-design-mcp
/new
```

### Option 3: Other MCP agents

Add to your agent's MCP configuration (format varies by agent):

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

### System requirements

- Python >= 3.9
- CUDA-capable GPU with >= 16GB VRAM (recommended)
- Conda (miniconda or anaconda)
- Separately installed: RFdiffusion, ProteinMPNN, AlphaFold3, PDBFixer + OpenMM

> 📚 **Detailed installation steps for each tool**: [docs/en/guides/installation.md](./docs/en/guides/installation.md)


## Setup via conversation

The easiest way to configure the plugin is to **talk to the Agent**.

**Already have the tools installed?** Just tell the Agent:
- Where each tool is located (e.g., "RFdiffusion is at `~/software/RFdiffusion`")
- Which conda environment it runs in (e.g., "RFdiffusion uses conda env `SE3nv`")

The plugin auto-detects common install locations and asks you to confirm. You can also run `check_all_tools` at any time to see what's detected.

**Prefer manual configuration?** You can set paths via:
- Environment variables (`RFDIFFUSION_PATH`, `PROTEINMPNN_PATH`, `ALPHAFOLD_PATH`)
- Config file (`~/.protein-design/config.yaml`)
- Symlinks in the plugin root directory

> 📚 See [docs/en/guides/installation.md](./docs/en/guides/installation.md) for detailed configuration options.


## Quick start

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

Pipeline defaults: 10 backbones → 8 sequences each → 5 predictions each. Adjust through natural language (e.g., "Generate 50 backbones", "Validate with 3 seeds").


## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](./docs/en/guides/installation.md) | Step-by-step tool installation and configuration |
| [Quick Start](./docs/en/guides/quickstart.md) | Pipeline defaults and example workflows |
| [Pipeline Architecture](./docs/en/guides/pipeline.md) | 5-stage design flow and project structure |
| [API Reference](./docs/en/api-reference/tools.md) | All MCP tools and their parameters |
| [Troubleshooting](./docs/en/guides/troubleshooting.md) | Common issues and solutions |
| [Changelog](./docs/en/release-notes/changelog.md) | Release notes |


## Quality thresholds

| Metric | Acceptable | Good | Excellent |
|--------|-----------|------|-----------|
| pLDDT | >70 | >80 | >90 |
| ipTM | >0.6 | >0.8 | >0.9 |
| pTM | >0.5 | >0.7 | >0.9 |


## License

MIT


## Acknowledgments

- RFdiffusion — [Watson et al., 2023](https://www.nature.com/articles/s41586-023-06415-8)
- ProteinMPNN — [Dauparas et al., 2022](https://www.science.org/doi/10.1126/science.add2187)
- AlphaFold3 — [Abramson et al., 2024](https://www.nature.com/articles/s41586-024-07487-w)
- PDBFixer — OpenMM project

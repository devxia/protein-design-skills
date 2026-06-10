# 🧬 Protein Design MCP

> **English** | [中文](./README.zh.md)

An agent-agnostic protein design plugin for coding agents (Claude Code, Codex CLI, Kimi Code, etc.). Orchestrates RFdiffusion, ProteinMPNN, AlphaFold3, and PDBFixer for end-to-end protein design workflows. Generate protein backbones, design sequences, validate structures, and rank results — all through natural language conversation.

## Features

- **Stage 0 — Structure Preprocessing**: Automatic PDB repair with PDBFixer
- **Stage 1 — Backbone Generation**: RFdiffusion for monomers, binders, motif scaffolding, symmetric oligomers, partial diffusion, inpainting, cyclic peptides, and more
- **Stage 2 — Sequence Design**: ProteinMPNN for amino acid sequence assignment (with advanced features: fixed positions, symmetry, bias, scoring)
- **Stage 3 — Structure Validation**: AlphaFold3 for confidence scoring (pLDDT, ipTM, pTM)
- **Stage 4 — Filtering & Ranking**: Automated quality filtering and composite scoring
- **Async Job Management**: Submit long-running jobs and poll for results
- **Batch Validation**: Scheduling support for large-scale AlphaFold3 screening
- **Alternative Pipelines**: ESMFold fast screening, Chroma joint generation, LigandMPNN ligand-aware design, DiffPepBuilder peptide design, ESM-IF1 inverse folding
- **Design Patterns**: 10 ready-to-use templates for common scenarios
- **Hooks (0.6.0+)**: Context injection, tool recommendation, pipeline orchestration, error recovery, GPU safety checks, progress reporting, and desktop notifications
- **Skills (16+)**: Workflow guidance for every pipeline stage, troubleshooting, protein analysis, and batch management


> **Note:** This plugin does not bundle RFdiffusion, ProteinMPNN, AlphaFold3, or PDBFixer. These are large machine-learning models (multi-GB) that must be installed separately. The plugin provides the orchestration layer (MCP Server + Skills) that calls these tools via subprocess.


## Installation

### Prerequisites

This plugin works with any MCP-compatible coding agent (Claude Code, Codex CLI, Kimi Code, etc.).

### Option 1: Claude Code

```bash
# Clone the plugin
git clone https://github.com/devxia/protein-design-skills.git
cd protein-design-skills

# Install dependencies
pip install -r requirements.txt

# The plugin.json at the project root configures the MCP server automatically.
# Or add to ~/.claude/settings.json manually.
```

### Option 2: Kimi Code

```
/plugins install https://github.com/devxia/protein-design-skills
/new
```

### Option 3: Other MCP agents

Add to your agent's MCP configuration (format varies by agent):

```json
{
  "mcpServers": {
    "protein-design-skills": {
      "command": "python",
      "args": ["-m", "protein_design.server"],
      "cwd": "/path/to/protein-design-skills",
      "env": {
        "PYTHONPATH": "/path/to/protein-design-skills",
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


## Alternative Pipelines

The plugin supports multiple design workflows:

| Pipeline | Stage 1 | Stage 2 | Stage 3 | Best For |
|----------|---------|---------|---------|----------|
| **Standard** | RFdiffusion | ProteinMPNN | AlphaFold3 (full MSA) | Best accuracy |
| **Fast Screening** | RFdiffusion | ProteinMPNN | ESMFold (no MSA) | Speed > accuracy |
| **Balanced** | RFdiffusion | ProteinMPNN | AlphaFold3 (no-MSA) | Medium speed |
| **Chroma** | Chroma (joint) | — | AlphaFold3 | All-atom generation |
| **Ligand** | RFdiffusion | LigandMPNN | AlphaFold3 | Ligand-aware design |
| **Peptide** | DiffPepBuilder | — | AlphaFold3 | Short peptide binders (8-30aa) |
| **Ensemble** | RFdiffusion | ProteinMPNN + ESM-IF1 | AlphaFold3 | Maximum diversity |

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](./docs/en/guides/installation.md) | Step-by-step tool installation and configuration |
| [Quick Start](./docs/en/guides/quickstart.md) | Pipeline defaults and example workflows |
| [Pipeline Architecture](./docs/en/guides/pipeline.md) | 5-stage design flow and project structure |
| [API Reference](./docs/en/api-reference/tools.md) | All MCP tools and their parameters |
| [Troubleshooting](./docs/en/guides/troubleshooting.md) | Common issues and solutions |
| [Changelog](./docs/en/release-notes/changelog.md) | Release notes |
| [Skills](./skills/) | 16+ workflow skills for all pipeline stages |


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
- Chroma — [Generate Biomedicines](https://github.com/generatebio/chroma)
- LigandMPNN — [Dauparas et al.](https://github.com/dauparas/LigandMPNN)
- ESM-IF1 — [Meta AI](https://github.com/facebookresearch/esm)
- DiffPepBuilder — [Wang et al.](https://github.com/YuzheWangPKU/DiffPepBuilder)

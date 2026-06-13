# 🧬 Protein Design Skills

> **English** | [中文](./README.zh.md)

An **agent-agnostic** protein design plugin for coding agents (Claude Code, Codex CLI, Kimi Code, and any agent that reads skills). Orchestrates RFdiffusion, ProteinMPNN, AlphaFold3, Boltz-1, Chai-1, and 15+ other tools for end-to-end protein design workflows.

## Architecture

This plugin uses **three layers** — no server needed:

| Layer | What | Count | Location |
|-------|------|-------|----------|
| **Skills** | Markdown knowledge for the LLM | 79 | `skills/` |
| **Hooks** | Automation scripts | 22 | `protein_design/hooks/` |
| **Scripts** | Standalone execution | 19 | `scripts/` |

**How it works:** Skills teach the agent → Hooks fire automatically → Scripts run tools directly.

## Features

- **Stage 0 — Preprocessing**: PDBFixer repair
- **Stage 1 — Backbone**: RFdiffusion, Chroma, FoldFlow, DiffPepBuilder, RFpeptides, and more
- **Stage 2 — Sequence**: ProteinMPNN, LigandMPNN, ESM-IF1, EvoDiff
- **Stage 3 — Validation**: AlphaFold3, Boltz-1, Chai-1, OmegaFold, ESMFold, Protenix, OpenFold3
- **Stage 4 — Filtering**: Quality metrics, cross-validation consensus, score-first screening
- **79 Skills**: Covering 30+ design pipelines from fast screening to full validation
- **22 Hooks**: Auto-context injection, GPU checks, tool recommendation, pipeline orchestration, error recovery
- **19 Scripts**: Direct command-line execution for all pipeline stages

## 15+ Design Pipelines Available

| Pipeline | Stage 1 | Stage 2 | Stage 3 | Best For |
|----------|---------|---------|---------|----------|
| **Standard** | RFdiffusion | ProteinMPNN | AlphaFold3 | General purpose |
| **Fast Screening** | RFdiffusion | ProteinMPNN | ESMFold/OmegaFold | No databases needed |
| **Ligand-Aware** | RFdiffusionAA | LigandMPNN | AlphaFold3 | Small molecules, cofactors |
| **Peptide** | DiffPepBuilder | Built-in | AlphaFold3 | 8-30aa peptides |
| **Macrocyclic** | RFpeptides | ProteinMPNN | AlphaFold3/Boltz-1 | 12-18aa cyclic peptides |
| **Cross-Validation** | RFdiffusion | ProteinMPNN | Boltz-1 + Chai-1 + OmegaFold | Most robust ranking |
| **Score-First** | RFdiffusion | ProteinMPNN (score_only) | AlphaFold3 | Pre-screen to save compute |
| **Chroma** | Chroma (joint) | — | AlphaFold3 | All-atom, natural language |
| **ColabDesign** | AfDesign | AfDesign | AlphaFold3 | No local GPU |
| **Ensemble** | RFdiffusion | ProteinMPNN + ESM-IF1 | AlphaFold3 | Maximum diversity |
| **FoldFlow** | FoldFlow | ProteinMPNN | AlphaFold3 | Fast flow matching |
| **OpenFold3** | RFdiffusion | ProteinMPNN | OpenFold3 | pip install, AF3 parity |
| **Protenix** | RFdiffusion | ProteinMPNN | Protenix | Training + inference scaling |
| **Antibody** | IgDiff/RFdiffusion | AbMPNN/ProteinMPNN | AlphaFold3 | Antibodies, nanobodies |
| **Enzyme** | RFdiffusionAA | LigandMPNN | AlphaFold3 | Active sites, catalysis |

## Quick Start

### Plugin Marketplace (Recommended)

**Claude Code:**
```bash
claude plugin marketplace add devxia/protein-design-skills
claude plugin install protein-design-skills@protein-design-skills
```

**Codex CLI:**
```bash
codex plugin marketplace add devxia/protein-design-skills
codex plugin install protein-design-skills
```

**Kimi Code:**
```bash
/plugins install https://github.com/devxia/protein-design-skills
/new
```

### Manual Install

```bash
git clone https://github.com/devxia/protein-design-skills.git
cd protein-design-skills
pip install -r requirements.txt
```

### Install Hooks for Your Agent

The plugin auto-detects your agent. Or install for a specific one:

```bash
# Auto-detect all installed agents
python protein_design/hooks/install-hooks.py

# Or specify your agent explicitly
python protein_design/hooks/install-hooks.py claude    # Claude Code
python protein_design/hooks/install-hooks.py codex     # Codex CLI
python protein_design/hooks/install-hooks.py kimi      # Kimi Code

# Install for multiple agents at once
python protein_design/hooks/install-hooks.py claude codex

# Validate plugin manifests
python protein_design/hooks/install-hooks.py --validate
```

**What gets installed:**
- **Claude Code**: Hooks registered in `~/.claude/settings.json` (or `.claude/settings.json` with `--local`)
- **Codex CLI**: Hooks written to `~/.codex/hooks.json` (or `.codex/hooks.json` with `--local`)
- **Kimi Code**: Hooks registered in `~/.kimi-code/config.toml`

**Project-local installation (no global config):**
```bash
python protein_design/hooks/install-hooks.py --local claude codex
```

### Verify Installation

```bash
# Check hooks are registered (Claude Code example)
cat ~/.claude/settings.json | grep -A 5 "protein"

# You should see hook entries like:
# "UserPromptSubmit": [..., "session-health-check.py", ...]
```

### Start Designing

```bash
# Read the entry skill
cat skills/protein-design-context/SKILL.md

# Or just start — hooks will auto-activate on protein-related prompts
python scripts/run_rfdiffusion.py --contig "150-150" --num-designs 50
```

### Batch Pipeline

Run the full 5-stage pipeline from a YAML config:

```bash
# Create pipeline config
cat > pipeline.yaml << 'EOF'
stages:
  - name: "Stage 0: PDBFixer"
    command: [python, scripts/run_pdbfixer.py, --input, target.pdb, --output, outputs/fixed.pdb]
  - name: "Stage 1: RFdiffusion"
    command: [python, scripts/run_rfdiffusion.py, --input-pdb, outputs/fixed.pdb, --contig, "[150-150]", --num-designs, "50"]
  - name: "Stage 2: ProteinMPNN"
    command: [python, scripts/run_proteinmpnn.py, --pdb-path, "outputs/design_*.pdb", --out-folder, outputs/seqs/, --num-seq, "8"]
  - name: "Stage 3: OmegaFold"
    command: [python, scripts/run_omegafold.py, --input, outputs/seqs/seqs.fa, --output-dir, outputs/validation/]
  - name: "Stage 4: Filtering"
    command: [python, scripts/run_filtering.py, --results-dir, outputs/validation/, --min-plddt, "75", --top-n, "10"]
EOF

# Run the whole pipeline
python scripts/batch_runner.py --config pipeline.yaml
```

### Verify Everything Works

```bash
# Test hook execution (should print onboarding message)
echo "design a protein" | python protein_design/hooks/user-onboarding.py

# Test tool detection (should list installed/missing tools)
echo "protein design" | python protein_design/hooks/session-health-check.py

# Test script execution (should show help)
python scripts/run_rfdiffusion.py --help
```

## What Hooks Do (After Installation)

Once hooks are installed, your agent automatically gets:

| Hook | Trigger | What It Does |
|------|---------|--------------|
| **user-onboarding** | First protein prompt | Welcome message + tool status + quick start guide |
| **session-health-check** | Protein prompts | Checks installed tools, suggests alternatives for missing ones |
| **tool-recommender** | Design requests | Recommends scripts and parameters for your scenario |
| **error-recovery** | Tool failures | Suggests fixes, alternative tools, and install commands |
| **progress-reporter** | Long jobs | ETA estimation, file counting, progress updates |
| **pipeline-orchestrator** | Stage completion | Auto-detects next step, suggests what to run |
| **quality-gate** | Validation results | Pass/fail decisions with thresholds |
| **design-report** | Filtering complete | Auto-generates summary with rankings |
| **gpu-check-hook** | Before GPU jobs | Checks VRAM, warns if insufficient |

No manual setup needed — hooks fire automatically when you talk about protein design.

## Supported Agents

| Agent | Config Location | Hook Format | Status |
|-------|----------------|-------------|--------|
| **Claude Code** | `~/.claude/settings.json` (or `.claude/settings.json` with `--local`) | JSON | ✅ Fully supported |
| **Codex CLI** | `~/.codex/hooks.json` (or `.codex/hooks.json` with `--local`) | JSON | ✅ Fully supported |
| **Kimi Code** | `~/.kimi-code/config.toml` | TOML | ✅ Fully supported |

All agents get the same 22 hooks and 79 skills (76 workflow skills + 3 project-level doc-maintenance skills). The plugin auto-detects which agents are installed.

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA 8GB VRAM | NVIDIA A100/V100 16GB+ |
| CPU | 8 cores | 16+ cores |
| RAM | 32GB | 64GB+ |
| Disk | 100GB | 3TB (with databases) |
| OS | Linux | Linux (Ubuntu 20.04+) |
| Python | 3.9 | 3.10+ |

> **Note:** This plugin does not bundle ML models. It provides the orchestration layer (skills + hooks + scripts) that calls your installed tools.

## Configuration

```bash
# Set tool paths
export RFDIFFUSION_PATH="~/RFdiffusion"
export PROTEINMPNN_PATH="~/ProteinMPNN"
export ALPHAFOLD_PATH="~/alphafold3"

# Or use config file
cat ~/.protein-design/config.yaml
```

## Progress Tracking

Monitor a running campaign without blocking the session:

```bash
# One-shot summary
python scripts/summarize_outputs.py --output-dir outputs/

# Live dashboard (refreshes every 30 seconds)
python scripts/summarize_outputs.py --output-dir outputs/ --watch

# Project-wide dashboard with expected counts
python scripts/project_dashboard.py --output-dir outputs/ \
  --expected-backbones 50 \
  --expected-sequences 400 \
  --expected-validations 50
```

## Documentation

| Document | Description |
|----------|-------------|
| [Skills Index](./skills/SKILL_INDEX.md) | All 79 skills with navigation |
| [Installation Guide](./docs/en/guides/installation.md) | Tool installation |
| [Quick Start](./docs/en/guides/quickstart.md) | Example workflows |
| [Pipeline Architecture](./docs/en/guides/pipeline.md) | 5-stage design flow |
| [Troubleshooting](./docs/en/guides/troubleshooting.md) | Common issues |
| [Changelog](./docs/en/release-notes/changelog.md) | Release notes |

## Quality Thresholds

| Metric | Acceptable | Good | Excellent |
|--------|-----------|------|-----------|
| pLDDT | >70 | >80 | >90 |
| ipTM | >0.6 | >0.8 | >0.9 |
| pTM | >0.5 | >0.7 | >0.9 |

## Troubleshooting Installation

### Hooks not firing?

```bash
# Check if hooks are registered
cat ~/.claude/settings.json | grep protein  # Claude Code
cat ~/.codex/hooks.json | grep protein   # Codex CLI

# Re-install hooks (force overwrite)
python protein_design/hooks/install-hooks.py claude --force

# List all installed hooks
python protein_design/hooks/install-hooks.py --list
```

### "Module not found" errors?

```bash
# Ensure you're in the plugin directory
cd protein-design-skills

# Install dependencies
pip install -r requirements.txt
```

### Agent not detected?

```bash
# Install manually for your agent
python protein_design/hooks/install-hooks.py claude
python protein_design/hooks/install-hooks.py codex
python protein_design/hooks/install-hooks.py kimi
```

### Check hook installation status

```bash
# List all installed hooks per agent
python protein_design/hooks/install-hooks.py --list

# Or check manually
ls -la ~/.claude/hooks/     # Claude Code
ls -la ~/.codex/hooks/      # Codex CLI
ls -la ~/.kimi-code/hooks/  # Kimi Code
```

## Plugin Structure

This project supports multiple coding agents with agent-specific manifest files:

| File | Purpose | Used By |
|------|---------|---------|
| `.claude-plugin/plugin.json` | Claude Code plugin manifest | Claude Code |
| `.claude-plugin/marketplace.json` | Plugin marketplace registration | `claude plugin marketplace add` |
| `plugin.json` | Root-level metadata | npm, GitHub, general tooling |
| `kimi.plugin.json` | Kimi Code plugin manifest | Kimi Code |
| `hooks/hooks.json` | Standard hook configuration | Claude Code plugin loader |

The `.claude-plugin/plugin.json` follows the [Claude Code plugin-structure spec](https://docs.anthropic.com/en/docs/claude-code/plugins). Hooks are also installable via `protein_design/hooks/install-hooks.py` for agents that don't use the standard hook loader.

## License

MIT

## Acknowledgments

- RFdiffusion — [Watson et al., 2023](https://www.nature.com/articles/s41586-023-06415-8)
- ProteinMPNN — [Dauparas et al., 2022](https://www.science.org/doi/10.1126/science.add2187)
- AlphaFold3 — [Abramson et al., 2024](https://www.nature.com/articles/s41586-024-07487-w)
- Boltz-1 — [Wöhlke et al.](https://github.com/jwohlwend/boltz)
- Chai-1 — [Chai Discovery](https://github.com/chaidiscovery/chai1)
- Protenix — [ByteDance](https://github.com/bytedance/Protenix)
- PDBFixer — OpenMM project

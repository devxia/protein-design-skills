# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Protein Design Skills is an agent-agnostic plugin for end-to-end protein design. It orchestrates external ML tools (RFdiffusion, ProteinMPNN, AlphaFold3, PDBFixer, Boltz-1, Chai-1, etc.) via **Skills + Hooks + Standalone Scripts** through a 5-stage pipeline.

| Stage | Primary Tool | Alternatives | Purpose |
|-------|-------------|--------------|---------|
| 0 | PDBFixer | — | Mandatory PDB repair before any design tool |
| 1 | RFdiffusion | Chroma, FoldFlow, Genie 3, DiffPepBuilder, RFpeptides | Backbone generation |
| 2 | ProteinMPNN | LigandMPNN, ESM-IF1 | Sequence design |
| 3 | AlphaFold3 | Boltz-1, Chai-1, OmegaFold, ESMFold, Protenix, OpenFold3 | Structure validation |
| 4 | Filtering | Cross-validation, Score-first screening | Quality ranking |

The plugin does **not** bundle the ML tools — they must be installed separately. The plugin provides the **Skills + Hooks + Scripts** orchestration layer.

**Supported coding agents:** Claude Code, Codex CLI, Kimi Code, and any agent that reads skills.

## Commands

```bash
# Install hooks for automation (auto-detect agents)
python protein_design/hooks/install-hooks.py

# Install hooks for a specific agent only
python protein_design/hooks/install-hooks.py claude
python protein_design/hooks/install-hooks.py codex
python protein_design/hooks/install-hooks.py kimi

# Install for multiple agents at once
python protein_design/hooks/install-hooks.py claude codex

# List installed hooks per agent
python protein_design/hooks/install-hooks.py --list

# Force reinstall hooks (overwrite existing)
python protein_design/hooks/install-hooks.py claude --force

# Run standalone scripts
python scripts/run_pdbfixer.py --input structure.pdb --output fixed.pdb
python scripts/run_rfdiffusion.py --contig "150-150" --num-designs 50
python scripts/run_proteinmpnn.py --pdb-path design.pdb --out-folder outputs/seqs/
python scripts/run_alphafold3.py --json input.json --output-dir outputs/af3/
python scripts/run_filtering.py --results-dir outputs/af3/ --min-plddt 75
python scripts/convert_format.py --from fasta --to alphafold3_json --input seqs.fa --output af3.json

# Batch pipeline (chains all stages)
python scripts/batch_runner.py --config pipeline.yaml

# Job management
python scripts/job_manager.py submit --name rfdiff -- python scripts/run_rfdiffusion.py --contig "150-150"
python scripts/job_manager.py list
python scripts/job_manager.py status <job_id>

# Progress monitoring
python scripts/summarize_outputs.py --output-dir outputs/
python scripts/project_dashboard.py --output-dir outputs/ --watch

# Run tests
python -m pytest tests/
```

There is no build step. Dependencies: `biopython>=1.81`, `pyyaml>=6.0`.

## Agent configuration

### Claude Code

Install via marketplace (recommended):

```bash
claude plugin marketplace add devxia/protein-design-skills
claude plugin install protein-design-skills@protein-design-skills
```

Or install hooks manually for automation:

```bash
python protein_design/hooks/install-hooks.py claude
```

Hooks are registered in `~/.claude/settings.json` and fire automatically on protein-related prompts.

### Kimi Code

Install via marketplace (recommended):

```bash
/plugins install https://github.com/devxia/protein-design-skills
/new
```

Uses `kimi.plugin.json` at the project root for skills. Hooks are registered in `~/.kimi-code/config.toml` via the installer:

```bash
python protein_design/hooks/install-hooks.py kimi
```

### Codex CLI

Install via marketplace (recommended):

```bash
codex plugin marketplace add devxia/protein-design-skills
codex plugin install protein-design-skills
```

Or install hooks manually for context injection and automation:

```bash
python protein_design/hooks/install-hooks.py codex
```

Hooks are written to `~/.codex/hooks.json` (global) or `.codex/hooks.json` (with `--local`) and fire automatically on protein-related prompts.

### Verify installation

```bash
# List installed hooks per agent
python protein_design/hooks/install-hooks.py --list

# Force reinstall if hooks aren't working
python protein_design/hooks/install-hooks.py claude --force
```

## Architecture

### Two-layer plugin structure

1. **Skills** (`skills/`) — Markdown files providing workflow guidance to the LLM. 76 skills covering all pipeline stages, design patterns, tool alternatives, and troubleshooting.
2. **Hooks** (`protein_design/hooks/`) — 22 agent hook scripts (plus `install-hooks.py`) for context injection, tool recommendations, progress tracking, error recovery, and desktop notifications. `install-hooks.py` supports multiple agents.
3. **Scripts** (`scripts/`) — 19 standalone Python scripts for direct tool execution, format conversion, job management, and progress monitoring.

### What hooks do

Hooks fire automatically when you talk about protein design:

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

### Tool execution pattern

Standalone scripts in `scripts/` follow this pattern:
1. Locate the external script (configured path → env vars → common locations → editable-install detection via conda)
2. Build CLI arguments (Hydra config overrides for RFdiffusion, script flags for ProteinMPNN/AlphaFold3)
3. Optionally wrap with `conda run -n <env>` via `conda_utils.py`
4. Execute via `subprocess.run()` with proper timeouts
5. Collect output files, save runtime to `~/.protein-design/history.jsonl` for future ETA
6. Return exit codes (0 = success, 1+ = error)

### Configuration priority

Environment variables > config file (`~/.protein-design/config.yaml`) > defaults:
- `PROTEIN_DESIGN_OUTPUT_DIR` (default `/tmp/protein-design`)
- `PROTEIN_DESIGN_MAX_JOBS` (default 4)
- `RFDIFFUSION_PATH`, `PROTEINMPNN_PATH`, `ALPHAFOLD_PATH`

### Progress tracking

Hooks and scripts provide progress tracking:
- **`scripts/summarize_outputs.py`** — One-shot summary of output directories (backbone count, sequence count, validation count, quality distribution)
- **`scripts/project_dashboard.py`** — Real-time dashboard with `--watch` mode
- **`scripts/job_manager.py`** — Background job tracking
- **`progress-reporter` hook** — Log file parsing + file counting for ETA estimation
- **`pipeline-orchestrator` hook** — Auto-detects stage completions and suggests next steps

### Docs maintenance

`docs/` is bilingual (en/zh). Source-of-truth rules defined in `docs/AGENTS.md`:
- API reference (`docs/{en,zh}/api-reference/scripts.md`) documents all standalone scripts
- Changelog is English-first, managed by the `sync-changelog` skill
- All other docs are mirrored pairs — changes in either locale must sync to the other
- Development-only helper skills: `gen-docs`, `sync-changelog`, `translate-docs` (in `.agents/skills/`) — used to maintain docs, not counted as plugin skills

## Key design decisions

- **Cross-conda execution**: Tools often live in separate conda environments. `conda_utils.py` wraps commands with `conda run -n <env>` rather than activating/deactivating shells. The `wrapper_script` parameter provides an escape hatch for complex environment setup.
- **PDBFixer is mandatory**: `run_rfdiffusion` auto-preprocesses input PDBs via `preprocess_for_design()` unless `skip_preprocessing=true`.
- **No bundled ML models**: This plugin provides orchestration, not models. Missing-tool errors return structured messages with download URLs and install guides.
- **Agent-agnostic**: Works with any agent that reads skills and runs hooks.
- **Timeout is global**: All subprocess calls use `CONFIG.timeout` (default 3600s). Cancellation terminates the subprocess and cleans up partial files.
- **Tool-not-installed fallback**: Every core skill includes alternative tools. If RFdiffusion is missing, use Chroma. If ProteinMPNN is missing, use ESM-IF1. If AlphaFold3 is missing, use ESMFold or OmegaFold (no databases needed).

## Current coverage

- **76 skills** — core pipeline stages, tool-specific guides, design patterns, and specialized workflows
- **22 hooks** — 9 UserPromptSubmit + 3 PreToolUse + 8 PostToolUse + 2 Notification
- **19 scripts** — 10 core tool runners + 1 format converter + 1 job manager + 1 batch runner + 1 summarizer + 1 dashboard + 4 validation utilities

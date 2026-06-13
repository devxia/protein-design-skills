# Agent Guide — Protein Design Skills

This file contains project-specific guidance for AI coding agents working on the `protein-design-skills` repository. The reader is assumed to know nothing about the project.

## Project overview

**Protein Design Skills** is an agent-agnostic plugin for coding agents (Claude Code, Codex CLI, Kimi Code, and any agent that reads skills). It orchestrates external ML tools for end-to-end protein design workflows.

- **Version**: `0.2.0` (declared in `protein_design/__init__.py`, `plugin.json`, `kimi.plugin.json`, and `.claude-plugin/plugin.json`).
- **License**: MIT.
- **Repository**: `https://github.com/devxia/protein-design-skills`.
- **Core philosophy**: The plugin provides **orchestration only** — it does **not** bundle ML models or tools. It teaches the agent via Markdown skills, fires automation hooks, and runs standalone Python scripts that call the user's installed tools.

The plugin uses a three-layer architecture with no server:

| Layer | Purpose | Count | Location |
|-------|---------|-------|----------|
| **Skills** | Markdown knowledge consumed by the LLM | 76 | `skills/` |
| **Hooks** | Automation scripts that fire on agent events | 22 | `protein_design/hooks/` |
| **Scripts** | Standalone command-line execution | 19 | `scripts/` |

The canonical five-stage design pipeline is:

| Stage | Purpose | Primary script | Primary skill |
|-------|---------|----------------|---------------|
| 0 | Structure preprocessing / PDB repair | `scripts/run_pdbfixer.py` | `structure-preprocessing` |
| 1 | Backbone generation | `scripts/run_rfdiffusion.py` | `structure-generation` |
| 2 | Sequence design | `scripts/run_proteinmpnn.py` | `sequence-design` |
| 3 | Structure validation | `scripts/run_alphafold3.py` | `structure-validation` |
| 4 | Filtering / ranking | `scripts/run_filtering.py` | `filtering-ranking` |

Each stage has alternatives documented in `skills/SKILL_INDEX.md` and `skills/protein-design-context/SKILL.md`.

## Technology stack

- **Language**: Python 3.9+ (CI tests against 3.10, 3.11, 3.12).
- **Core dependencies** (see `requirements.txt`):
  - `biopython>=1.81`
  - `numpy>=1.23.0`
  - `pyyaml>=6.0`
  - `pytest>=7.0.0`
- **No compiled build system**: There is no `pyproject.toml`, `setup.py`, `package.json`, `Cargo.toml`, or `Makefile` in the project root. Installation is `pip install -r requirements.txt`.
- **External tools** (not bundled; user installs separately): RFdiffusion, ProteinMPNN, AlphaFold3, PDBFixer, Boltz-1, Chai-1, ESMFold, OmegaFold, Protenix, OpenFold3, LigandMPNN, ESM-IF1, ColabFold, etc.
- **CI/CD**: GitHub Actions (`.github/workflows/ci.yml`) runs `py_compile` and `pytest` on pushes/PRs to `main`/`master`.

## Code organization

```
protein-design-skills/
├── protein_design/              # Python package
│   ├── __init__.py              # Version string
│   ├── utils.py                 # Shared helpers (FASTA, config, notifications, confidence parsing)
│   └── hooks/                   # Hook scripts (22 automation hooks + install-hooks.py)
├── scripts/                     # 19 standalone CLI scripts
├── skills/                      # 76 skill directories, each containing SKILL.md
├── skills/SKILL_INDEX.md        # Index of all skills
├── tests/                       # Pytest test suite
├── docs/                        # Bilingual documentation (en/zh)
├── docs/AGENTS.md               # Rules for maintaining docs/
├── examples/                    # Example pipeline YAML configs
├── hooks/hooks.json             # Canonical hook definitions consumed by install-hooks.py
├── plugin.json                  # Root-level metadata
├── kimi.plugin.json             # Kimi Code manifest
├── .claude-plugin/plugin.json   # Claude Code manifest
├── .claude-plugin/marketplace.json # Marketplace registration
├── .codex-plugin/plugin.json    # Codex CLI manifest
├── .agents/plugins/marketplace.json # Marketplace index
├── requirements.txt             # Python dependencies
└── README.md / README.zh.md     # Human-facing documentation
```

### `protein_design/hooks/`

Hook scripts fire automatically after installation. They are grouped by agent event in `hooks/hooks.json`:

- **UserPromptSubmit**: onboarding, health checks, context injection, tool recommendations, parameter tuning, batch orchestration, progress query helper, cost estimation, parameter generation.
- **PreToolUse**: alternative-tool recommender, execution adapter, GPU check.
- **PostToolUse**: design-complete notify, design comparator, design report, error recovery, format converter, job monitor, pipeline orchestrator, quality gate.
- **Notification**: progress reporter, background notify.

`install-hooks.py` is the cross-agent installer. It reads `hooks/hooks.json` and registers hooks for Claude Code, Codex CLI, and/or Kimi Code.

### `scripts/`

Standalone CLI runners for each tool and utility. They share `protein_design.utils.get_config()` and `protein_design.utils.log_history()`. Scripts include:

- Tool runners: `run_pdbfixer.py`, `run_rfdiffusion.py`, `run_proteinmpnn.py`, `run_alphafold3.py`, `run_boltz.py`, `run_chai1.py`, `run_esmfold.py`, `run_omegafold.py`, `run_openfold3.py`, `run_protenix.py`, `run_colabfold.py`, `run_esm_if1.py`, `run_ligandmpnn.py`
- Utilities: `run_filtering.py`, `convert_format.py`, `batch_runner.py`, `job_manager.py`, `summarize_outputs.py`, `project_dashboard.py`

### `skills/`

Each skill is a directory containing a `SKILL.md` file. The main entry skill is `protein-design-context`. Skill metadata is in YAML front matter (e.g., `name`, `description`). See `skills/SKILL_INDEX.md` for navigation.

### `tests/`

- `test_argparse_smoke.py`: Runs `--help` on every script in `scripts/`.
- `test_hooks_smoke.py`: Runs `--help` on every hook; if `--help` is unsupported, imports the module to verify it loads.
- `test_utils.py`: Unit tests for `protein_design.utils` helpers.

## Build and test commands

There is no build step. Use the following commands during development:

```bash
# Install core dependencies
pip install -r requirements.txt

# Run the full test suite
python -m pytest tests/

# Compile-check all scripts and hooks
python -m py_compile scripts/*.py protein_design/hooks/*.py

# Install hooks locally for development/testing
python protein_design/hooks/install-hooks.py

# Validate plugin manifests and hooks configuration
python protein_design/hooks/install-hooks.py --validate

# List hooks registered per agent
python protein_design/hooks/install-hooks.py --list
```

### CI pipeline

`.github/workflows/ci.yml` runs on every push/PR to `main` or `master`:

1. Checks out the repository.
2. Sets up Python (matrix: 3.10, 3.11, 3.12).
3. Installs `requirements.txt`.
4. Runs `python -m py_compile scripts/*.py protein_design/hooks/*.py`.
5. Runs `python -m pytest tests/`.

## Code style guidelines

- **Python version**: Target Python 3.9+ syntax; type hints use `from __future__ import annotations` so modern annotations are accepted.
- **Docstrings**: Module-level docstrings describe purpose, usage, and exit codes. Function docstrings describe args/returns/raises.
- **CLI**: Scripts use `argparse.ArgumentParser` with `RawDescriptionHelpFormatter` and an `epilog` containing examples.
- **Exit codes**: Scripts use explicit non-zero exit codes documented in their module docstrings (e.g., `1 = Config file not found`, `2 = Tool not found`, `3 = Execution error`).
- **Subprocess**: Tools are invoked via `subprocess.run()` with `capture_output=True`, `text=True`, and explicit `timeout` values. Avoid shell=True.
- **Path handling**: Use `pathlib.Path`; resolve paths relative to the script location when needed.
- **Shared utilities**: Reuse `protein_design.utils` for config, FASTA I/O, confidence JSON parsing, notifications, and hook input reading. Do not add heavy ML dependencies (torch, fair-esm, boltz, etc.) to this module.
- **No shell metacharacters in hook paths**: `install-hooks.py` validates that hook script paths stay inside `protein_design/hooks/` and reject shell metacharacters.
- **Logging**: Use `log_history()` from `protein_design.utils` to append run records to `~/.protein-design/history.jsonl`.
- **Bilingual docs**: `docs/` is mirrored English/Chinese. See `docs/AGENTS.md` for source-of-truth and terminology rules. Non-changelog pages must stay in sync across locales.

## Testing instructions

- Add unit tests to `tests/` following the existing pytest style.
- If you add a new script, `test_argparse_smoke.py` will automatically pick it up and verify `--help` works.
- If you add a new hook, `test_hooks_smoke.py` will automatically pick it up and verify it either supports `--help` or imports cleanly.
- If you modify `protein_design.utils`, add or update tests in `test_utils.py`.
- Run the CI commands locally before committing:

```bash
python -m py_compile scripts/*.py protein_design/hooks/*.py
python -m pytest tests/
```

## Configuration and runtime architecture

### Configuration priority

1. Environment variables (highest priority).
2. `~/.protein-design/config.yaml` (preferred) or legacy `~/.kimi-protein-design/config.yaml`.
3. Defaults in `protein_design.utils.get_config()`.

Common environment variables:

- `PROTEIN_DESIGN_OUTPUT_DIR` — default output directory (`/tmp/protein-design`).
- `RFDIFFUSION_PATH`, `PROTEINMPNN_PATH`, `ALPHAFOLD_PATH` — tool installation paths.
- `ALPHAFOLD_DB_DIR` / `ALPHAFOLD3_DB_DIR` — database directories for structure predictors.

### How scripts locate external tools

Scripts follow a consistent discovery order (see `scripts/run_rfdiffusion.py` as the canonical example):

1. Configured path from `get_config(tool_name)`.
2. Common filesystem locations (`~/ToolName/`, `/opt/ToolName/`, etc.).
3. Conda environments via `conda run -n <env>`.
4. If not found, print a structured error with install URL and exit with the tool-not-found code.

### Batch pipeline

`scripts/batch_runner.py` chains stages from a YAML/JSON config or from CLI arguments. Example configs live in `examples/pipeline.yaml`.

### Job and progress tracking

- `scripts/job_manager.py` — background job submit/list/status.
- `scripts/summarize_outputs.py` — one-shot output summary.
- `scripts/project_dashboard.py` — live dashboard with `--watch` mode.
- `~/.protein-design/history.jsonl` — execution history for ETA estimation.

## Deployment / distribution

The plugin is distributed in two ways:

1. **Plugin marketplace** (recommended):
   - Claude Code: `claude plugin marketplace add devxia/protein-design-skills && claude plugin install protein-design-skills@protein-design-skills`
   - Codex CLI: `codex plugin marketplace add devxia/protein-design-skills && codex plugin install protein-design-skills`
   - Kimi Code: `/plugins install https://github.com/devxia/protein-design-skills` then `/new`
2. **Manual install**: `git clone` + `pip install -r requirements.txt` + `python protein_design/hooks/install-hooks.py`.

After installation, hooks fire automatically on protein-related prompts.

## Security considerations

- **Hook path validation**: `install-hooks.py` resolves hook script paths and verifies they are inside `protein_design/hooks/`. It rejects paths containing shell metacharacters (`;|&$()` etc.).
- **No secrets in repo**: `.gitignore` excludes `.env`, `.env.*`, virtual environments, and IDE files. Do not commit credentials or API keys.
- **Subprocess safety**: Scripts avoid `shell=True` and construct command lists explicitly. Inputs that become command arguments should be validated where feasible.
- **Best-effort notifications**: `protein_design.utils.send_notification()` invokes platform-specific binaries (`osascript`, `notify-send`, PowerShell) with escaped strings; failures are silently ignored.
- **Config file robustness**: `get_config()` catches malformed YAML and prints a traceback but does not crash the caller.

## Useful references

- Entry skill: `skills/protein-design-context/SKILL.md`
- Skill index: `skills/SKILL_INDEX.md`
- Human README: `README.md` / `README.zh.md`
- Docs maintenance rules: `docs/AGENTS.md`
- Claude-specific guidance: `CLAUDE.md`
- Canonical hooks definition: `hooks/hooks.json`
- Shared utilities: `protein_design/utils.py`

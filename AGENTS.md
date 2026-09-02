# Agent Guide — Protein Design Skills

This file contains project-specific guidance for AI coding agents working on the `protein-design-skills` repository. The reader is assumed to know nothing about the project.

## Project overview

**Protein Design Skills** is an agent-agnostic plugin for coding agents (Claude Code, Codex CLI, Kimi Code, and any agent that reads skills). It orchestrates external ML tools for end-to-end protein design workflows.

- **Version**: `0.2.0` (declared in `protein_design/__init__.py`, `plugin.json`, `kimi.plugin.json`, and `.claude-plugin/plugin.json`).
- **License**: MIT.
- **Repository**: `https://github.com/devxia/protein-design-skills`.
- **Core philosophy**: The plugin provides **orchestration only** — it does **not** bundle ML models or tools. It teaches the agent via Markdown skills, fires automation hooks, and runs standalone Python scripts that call the user's installed tools.

**Supported coding agents:** Claude Code, Codex CLI, Kimi Code, and any agent that reads skills.

The plugin uses a three-layer architecture with no server:

| Layer | Purpose | Count | Location |
|-------|---------|-------|----------|
| **Skills** | Markdown knowledge consumed by the LLM | 76 | `skills/` |
| **Hooks** | Cross-host automation registrations that fire on agent events | 20 | Host manifests |
| **Scripts** | Standalone command-line execution | 19 | `scripts/` |

The canonical five-stage design pipeline is:

| Stage | Primary Tool | Alternatives | Purpose | Primary script | Primary skill |
|-------|-------------|--------------|---------|----------------|---------------|
| 0 | PDBFixer | — | Mandatory PDB repair before any design tool | `scripts/run_pdbfixer.py` | `structure-preprocessing` |
| 1 | RFdiffusion | Chroma, FoldFlow, Genie 3, DiffPepBuilder, RFpeptides | Backbone generation | `scripts/run_rfdiffusion.py` | `structure-generation` |
| 2 | ProteinMPNN | LigandMPNN, ESM-IF1 | Sequence design | `scripts/run_proteinmpnn.py` | `sequence-design` |
| 3 | AlphaFold3 | Boltz-1, Chai-1, OmegaFold, ESMFold, Protenix, OpenFold3 | Structure validation | `scripts/run_alphafold3.py` | `structure-validation` |
| 4 | Filtering | Cross-validation, Score-first screening | Quality ranking | `scripts/run_filtering.py` | `filtering-ranking` |

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
│   ├── conda_utils.py           # Cross-conda tool execution helpers (env probing, command building)
│   └── hooks/                   # Hook scripts (20 cross-host registrations + installer)
├── scripts/                     # 19 standalone CLI scripts
├── skills/                      # 76 skill directories, each containing SKILL.md
├── skills/SKILL_INDEX.md        # Index of all skills
├── tests/                       # Pytest test suite
├── docs/                        # Bilingual documentation (en/zh)
├── docs/AGENTS.md               # Rules for maintaining docs/
├── examples/                    # Example pipeline YAML configs
├── hooks/hooks.json             # Claude Code hook definitions
├── hooks/codex-hooks.json       # Codex CLI hook definitions
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

Hook scripts fire automatically after installation. Claude definitions are grouped by agent event in `hooks/hooks.json`; Codex uses the equivalent host-specific `hooks/codex-hooks.json`.

- **UserPromptSubmit**: onboarding, health checks, context injection, tool recommendations, parameter tuning, batch orchestration, progress query helper, cost estimation, parameter generation.
- **PreToolUse**: alternative-tool recommender, execution adapter, GPU check.
- **PostToolUse**: design-complete notify, design comparator, design report, error recovery, format converter, job monitor, pipeline orchestrator, quality gate.

Only these three cross-host events are registered; progress and background helper scripts remain available for direct use but are not registered as unsupported Notification hooks.

`install-hooks.py` is the cross-agent installer. It reads the host-specific sources (`hooks/hooks.json`, `hooks/codex-hooks.json`, or `kimi.plugin.json`) and registers hooks for Claude Code, Codex CLI, and/or Kimi Code.

Key hooks and what they do:

| Hook | Trigger | What It Does |
|------|---------|--------------|
| **user-onboarding** | First protein prompt | Welcome message + tool status + quick start guide |
| **session-health-check** | Protein prompts | Checks installed tools, suggests alternatives for missing ones |
| **tool-recommender** | Design requests | Recommends scripts and parameters for your scenario |
| **error-recovery** | Tool failures | Suggests fixes, alternative tools, and install commands |
| **progress-reporter** | Direct helper (not registered) | On-demand ETA estimation, file counting, and progress updates |
| **pipeline-orchestrator** | Stage completion | Auto-detects next step, suggests what to run |
| **quality-gate** | Validation results | Pass/fail decisions with thresholds |
| **design-report** | Filtering complete | Auto-generates summary with rankings |
| **gpu-check-hook** | Before GPU jobs | Checks VRAM, warns if insufficient |

### `scripts/`

Standalone CLI runners for each tool and utility. The **tool runners** (13 `run_*.py` scripts) share `protein_design.utils.get_config()` and `protein_design.utils.log_history()`; the **utility scripts** (`convert_format.py`, `batch_runner.py`, `job_manager.py`, `summarize_outputs.py`, `project_dashboard.py`, `run_filtering.py`) are self-contained and do not call these helpers. All runners that touch conda environments share `protein_design.conda_utils` for env probing and command building. Scripts include:

- Tool runners: `run_pdbfixer.py`, `run_rfdiffusion.py`, `run_proteinmpnn.py`, `run_alphafold3.py`, `run_boltz.py`, `run_chai1.py`, `run_esmfold.py`, `run_omegafold.py`, `run_openfold3.py`, `run_protenix.py`, `run_colabfold.py`, `run_esm_if1.py`, `run_ligandmpnn.py`
- Utilities: `run_filtering.py`, `convert_format.py`, `batch_runner.py`, `job_manager.py`, `summarize_outputs.py`, `project_dashboard.py`

### `skills/`

Each skill is a directory containing a `SKILL.md` file. The main entry skill is `protein-design-context`. Skill metadata is in YAML front matter (e.g., `name`, `description`). See `skills/SKILL_INDEX.md` for navigation.

### `tests/`

- `test_argparse_smoke.py`: Runs `--help` on every script in `scripts/`.
- `test_hooks_smoke.py`: Runs `--help` on every hook; if `--help` is unsupported, imports the module to verify it loads.
- `test_utils.py`: Unit tests for `protein_design.utils` helpers.
- `test_conda_utils.py`: Unit tests for `protein_design.conda_utils` helpers.
- `test_plugin_manifests.py`: Regression tests for plugin manifest consistency.

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

# Install hooks for a specific agent only
python protein_design/hooks/install-hooks.py claude
python protein_design/hooks/install-hooks.py codex
# Kimi Code hooks are declared in kimi.plugin.json and enabled automatically

# Install for multiple agents at once
python protein_design/hooks/install-hooks.py claude codex

# Validate plugin manifests and hooks configuration
python protein_design/hooks/install-hooks.py --validate

# List hooks registered per agent
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
- **Shared utilities**: Reuse `protein_design.utils` for config, FASTA I/O, confidence JSON parsing, notifications, and hook input reading. Do not add heavy ML dependencies (torch, fair-esm, boltz, etc.) to this module. Reuse `protein_design.conda_utils` for cross-conda env probing and command building.
- **No shell metacharacters in hook paths**: `install-hooks.py` validates that hook script paths stay inside `protein_design/hooks/` and reject shell metacharacters.
- **Logging**: Use `log_history()` from `protein_design.utils` to append run records to `~/.protein-design/history.jsonl`.
- **Bilingual docs**: `docs/` is mirrored English/Chinese. See `docs/AGENTS.md` for source-of-truth and terminology rules. Non-changelog pages must stay in sync across locales.

## Testing instructions

- Add unit tests to `tests/` following the existing pytest style.
- If you add a new script, `test_argparse_smoke.py` will automatically pick it up and verify `--help` works.
- If you add a new hook, `test_hooks_smoke.py` will automatically pick it up and verify it either supports `--help` or imports cleanly.
- If you modify `protein_design.utils`, add or update tests in `test_utils.py`.
- If you modify `protein_design.conda_utils`, add or update tests in `test_conda_utils.py`.
- Run the CI commands locally before committing:

```bash
python -m py_compile scripts/*.py protein_design/hooks/*.py
python -m pytest tests/
```

## Configuration and runtime architecture

### Configuration priority

1. Environment variables (highest priority — explicitly set env vars always win, even if the config file sets the same key).
2. `~/.protein-design/config.yaml` (preferred) or legacy `~/.kimi-protein-design/config.yaml`.
3. Defaults in `protein_design.utils.get_config()`.

Common environment variables:

- `PROTEIN_DESIGN_OUTPUT_DIR` — default output directory (`/tmp/protein-design`).
- `PROTEIN_DESIGN_MAX_JOBS` — controls batch parallelism (default 4, used by `batch-orchestrator`).
- `RFDIFFUSION_PATH`, `PROTEINMPNN_PATH`, `ALPHAFOLD3_PATH` — tool installation paths (`ALPHAFOLD3_PATH` is canonical for AlphaFold3; the legacy `ALPHAFOLD_PATH` is still honoured).
- `ALPHAFOLD_DB_DIR` / `ALPHAFOLD3_DB_DIR` — database directories for structure predictors.

### How scripts locate and execute external tools

Scripts probe tools through the following levels; most scripts implement all of them, a few (e.g. pip-first CLIs like `run_boltz.py`) check PATH before conda (see each script's `find_*` function):

1. Configured path from `get_config(tool_name)`.
2. Common filesystem locations (`~/ToolName/`, `/opt/ToolName/`, etc.).
3. Conda environments via `conda_utils.find_conda_env()` / `probe_conda_envs()`.
4. `which` lookup for pip-installed CLI binaries.
5. If not found, print a structured error with install URL and exit with the tool-not-found code.

Once the tool is located, the execution pattern is:

1. Build CLI arguments (Hydra config overrides for RFdiffusion, script flags for ProteinMPNN/AlphaFold3).
2. Convert the tool command string to an argv list via `conda_utils.build_tool_command()` (handles `conda run`, `conda_api:` markers, `python -m`, bare executables, and script paths).
3. Optionally wrap with a per-tool `wrapper_script` (from config) for complex environment setup.
4. Execute via `subprocess.run()` with explicit timeouts (per-script: 3600s for RFdiffusion, 600s for PDBFixer, etc.).
5. Collect output files, save runtime to `~/.protein-design/history.jsonl` for future ETA.
6. Return exit codes (0 = success, 1+ = error).

### Batch pipeline

`scripts/batch_runner.py` chains stages from a YAML/JSON config or from CLI arguments. Example configs live in `examples/pipeline.yaml`.

### Job and progress tracking

- `scripts/job_manager.py` — background job submit/list/status.
- `scripts/summarize_outputs.py` — one-shot output summary (backbone count, sequence count, validation count, quality distribution).
- `scripts/project_dashboard.py` — live dashboard with `--watch` mode.
- `~/.protein-design/history.jsonl` — execution history for ETA estimation.
- `progress-reporter` hook — log file parsing + file counting for ETA estimation.
- `pipeline-orchestrator` hook — auto-detects stage completions and suggests next steps.

## Key design decisions

- **Cross-conda execution**: Tools often live in separate conda environments. `protein_design/conda_utils.py` wraps commands with `conda run -n <env>` rather than activating/deactivating shells. The `wrapper_script` parameter provides an escape hatch for complex environment setup.
- **PDBFixer is mandatory**: `run_rfdiffusion` auto-preprocesses input PDBs via `preprocess_for_design()` (which calls `run_pdbfixer`) unless `--skip-preprocessing` is passed. Default behaviour repairs every user-supplied structure before it enters the design pipeline.
- **No bundled ML models**: This plugin provides orchestration, not models. Missing-tool errors return structured messages with download URLs and install guides.
- **Agent-agnostic**: Works with any agent that reads skills and runs hooks.
- **Per-script timeouts**: Each script sets an explicit `subprocess.run(timeout=...)` appropriate to the tool (e.g. 3600s for RFdiffusion, 600s for PDBFixer, 10s for conda env probes).
- **Tool-not-installed fallback**: Every core skill includes alternative tools. If RFdiffusion is missing, use Chroma. If ProteinMPNN is missing, use ESM-IF1. If AlphaFold3 is missing, use ESMFold or OmegaFold (no databases needed).

## Plugin manifests

This project supports multiple coding agents with agent-specific manifest files:

| File | Purpose | Used By |
|------|---------|---------|
| `.claude-plugin/plugin.json` | Claude Code plugin manifest. Must contain only plugin metadata plus `skills` paths. Do **not** put `category`, `source`, or the default `hooks` path here; Claude auto-discovers `hooks/hooks.json`. | Claude Code |
| `.claude-plugin/marketplace.json` | Claude marketplace registration. `category` and `source` belong here; `source` should be `"./"`. | `claude plugin marketplace add` |
| `.codex-plugin/plugin.json` | Codex CLI plugin manifest. Declares `hooks/codex-hooks.json`. | Codex CLI |
| `plugin.json` | Root-level metadata | npm, GitHub, general tooling |
| `kimi.plugin.json` | Kimi Code plugin manifest and native hook source | Kimi Code |
| `.agents/plugins/marketplace.json` | Multi-agent marketplace index | `.agents` plugin loader |
| `hooks/hooks.json` | Claude hook definitions using `${CLAUDE_PLUGIN_ROOT}`. | Claude Code auto-discovery, `install-hooks.py` |
| `hooks/codex-hooks.json` | Codex hook definitions using `${PLUGIN_ROOT}` and supported Codex event matchers. | Codex manifest, `install-hooks.py` |

## Deployment / distribution

The plugin is distributed in two ways:

1. **Plugin marketplace** (recommended):
   - Claude Code: `claude plugin marketplace add devxia/protein-design-skills && claude plugin install protein-design-skills@protein-design-skills`
   - Codex CLI: `codex plugin marketplace add devxia/protein-design-skills && codex plugin install protein-design-skills`
   - Kimi Code: `/plugins install https://github.com/devxia/protein-design-skills` then `/new`
2. **Manual install**: `git clone` + `pip install -r requirements.txt` + `python protein_design/hooks/install-hooks.py`.

After installation, hooks fire automatically on protein-related prompts.

### Per-agent hook installation

Marketplace installs already activate hooks automatically. Use the installer below only if you want hooks registered in your user/global config, or if an agent does not load plugin-bundled hooks:

```bash
# Auto-detect all installed agents
python protein_design/hooks/install-hooks.py

# Or specify your agent explicitly
python protein_design/hooks/install-hooks.py claude    # Claude Code
python protein_design/hooks/install-hooks.py codex     # Codex CLI
# Kimi Code hooks are enabled automatically via kimi.plugin.json

# Project-local installation (no global config)
python protein_design/hooks/install-hooks.py --local claude codex
```

- **Claude Code**: Registers hooks in `~/.claude/settings.json` (or `.claude/settings.json` with `--local`).
- **Codex CLI**: Writes hooks to `~/.codex/hooks.json` (or `.codex/hooks.json` with `--local`).
- **Kimi Code**: No installer needed — hooks are enabled automatically via `kimi.plugin.json`.

### Verify installation

```bash
# List installed hooks per agent
python protein_design/hooks/install-hooks.py --list

# Force reinstall if hooks aren't working
python protein_design/hooks/install-hooks.py claude --force
```

## Docs maintenance

`docs/` is bilingual (en/zh). Source-of-truth rules defined in `docs/AGENTS.md`:

- API reference (`docs/{en,zh}/api-reference/scripts.md`) documents all standalone scripts. Update parameter tables when script CLI arguments change; maintain both English and Chinese versions.
- Changelog is English-first, managed by the `sync-changelog` skill — do not edit manually.
- All other docs are mirrored pairs — changes in either locale must sync to the other.
- Development-only helper skills: `gen-docs`, `sync-changelog`, `translate-docs` (in `.agents/skills/`) — used to maintain docs, not counted as plugin skills.

## Security considerations

- **Hook path validation**: `install-hooks.py` resolves hook script paths and verifies they are inside `protein_design/hooks/`. It rejects paths containing shell metacharacters (`;|&$()` etc.).
- **No secrets in repo**: `.gitignore` excludes `.env`, `.env.*`, virtual environments, and IDE files. Do not commit credentials or API keys.
- **Subprocess safety**: Scripts avoid `shell=True` and construct command lists explicitly. Inputs that become command arguments should be validated where feasible.
- **Best-effort notifications**: `protein_design.utils.send_notification()` invokes platform-specific binaries (`osascript`, `notify-send`, PowerShell) with escaped strings and a 10-second timeout; failures (including timeout) are silently ignored.
- **Config file robustness**: `get_config()` catches malformed YAML and prints a traceback but does not crash the caller.

## Useful references

- Entry skill: `skills/protein-design-context/SKILL.md`
- Skill index: `skills/SKILL_INDEX.md`
- Human README: `README.md` / `README.zh.md`
- Docs maintenance rules: `docs/AGENTS.md`
- Canonical hooks definition: `hooks/hooks.json`
- Shared utilities: `protein_design/utils.py`, `protein_design/conda_utils.py`

## Agent skills

### Issue tracker

Issues live in GitHub Issues for this repo (uses the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical triage roles mapped 1:1 to default label strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

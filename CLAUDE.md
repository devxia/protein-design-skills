# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Protein Design Skills is an agent-agnostic plugin for end-to-end protein design. It orchestrates external ML tools (RFdiffusion, ProteinMPNN, AlphaFold3, PDBFixer) via subprocess through a 5-stage pipeline:

| Stage | Tool | Purpose |
|-------|------|---------|
| 0 | PDBFixer | Mandatory PDB repair before any design tool |
| 1 | RFdiffusion | Backbone generation (monomers, binders, motif scaffolding) |
| 2 | ProteinMPNN | Amino acid sequence design on backbones |
| 3 | AlphaFold3 | Structure prediction and confidence scoring (pLDDT, ipTM, pTM) |
| 4 | Filtering | Quality filtering and composite-score ranking |

The plugin does **not** bundle the ML tools — they must be installed separately. The plugin provides the orchestration layer (MCP Server + Skills) that calls them.

**Supported coding agents:** Claude Code, Codex CLI, Kimi Code, and any MCP-compatible agent.

## Commands

```bash
# Run the MCP server directly (stdio JSON-RPC)
python -m protein_design.server

# Install hooks (auto-detects Claude Code, Kimi Code, Codex CLI)
python protein_design/hooks/install-hooks.py

# Install hooks for a specific agent only
python protein_design/hooks/install-hooks.py claude

# Run tests
python -m pytest tests/
```

There is no build step. Dependencies: `biopython>=1.81`, `pyyaml>=6.0`.

## Agent configuration

### Claude Code

Add to `~/.claude/settings.json` or the project's `.mcp.json` (provided):

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

### Kimi Code

Uses `kimi.plugin.json` at the project root. The MCP server is launched automatically when the plugin is installed.

### Codex CLI

Add to `~/.codex/settings.json`:

```json
{
  "mcpServers": {
    "protein-design-skills": {
      "command": "python",
      "args": ["-m", "protein_design.server"],
      "cwd": "/path/to/protein-design-skills"
    }
  }
}
```

## Architecture

### Three-layer plugin structure

1. **MCP Server** (`protein_design/`) — stdio JSON-RPC 2.0 server that exposes tools for each pipeline stage. This is standard MCP — any MCP-compatible agent can launch it.
2. **Skills** (`skills/`) — Markdown files providing workflow guidance to the LLM. One skill per pipeline stage + `full-pipeline` for orchestration + `protein-design-context` for session-start injection.
3. **Hooks** (`protein_design/hooks/`) — Agent hook scripts for context injection on protein-related prompts, GPU safety checks before tool use, and desktop notifications on job completion. `install-hooks.py` supports multiple agents.

### MCP server internals

- **`server.py`** — Async stdio JSON-RPC loop. Reads lines from stdin, dispatches to `execute_tool()`, writes responses to stdout. Logging goes to stderr.
- **`tools/tool_registry.py`** — Central tool schema registry (`TOOL_SCHEMAS`) and dispatcher (`execute_tool()`). All tools are defined here with their JSON Schema parameters. Lazy-loads compute-heavy tool executors to avoid circular imports.
- **`tools/job_manager.py`** — `JobManager` singleton with `ThreadPoolExecutor` (default 4 workers). All compute tools (RFdiffusion, ProteinMPNN, AlphaFold3) are submitted via `submit_job()` and polled via `query_job()`. Jobs auto-cleanup after 1 hour. Supports cancellation with subprocess kill and partial file cleanup.
- **`tools/tool_installer.py`** — Installation detection across conda environments (editable-install probing, filesystem search, PATH search). Also handles `configure_tool_path()` and `configure_db_dir()` with YAML persistence to `~/.protein-design/config.yaml` (legacy `~/.kimi-protein-design/` also supported).

### Tool execution pattern

Each ML tool executor (e.g., `rfdiffusion.py`) follows this pattern:
1. Locate the external script (configured path → env vars → common locations → editable-install detection via conda)
2. Build CLI arguments (Hydra config overrides for RFdiffusion, script flags for ProteinMPNN/AlphaFold3)
3. Optionally wrap with `conda run -n <env>` via `conda_utils.py`
4. Start a `FileProgressTracker` that polls the output directory for completed files + uses historical ETA estimation
5. Execute via `run_in_conda_with_logs()` (stdout/stderr → log files)
6. Collect output files, save runtime to `~/.protein-design/history.jsonl` for future ETA

### Configuration priority

Environment variables > config file (`~/.protein-design/config.yaml`) > defaults:
- `PROTEIN_DESIGN_OUTPUT_DIR` (default `/tmp/protein-design`)
- `PROTEIN_DESIGN_MAX_JOBS` (default 4)
- `RFDIFFUSION_PATH`, `PROTEINMPNN_PATH`, `ALPHAFOLD_PATH`

### Progress tracking

`utils/progress_tracker.py` combines three signals to estimate progress (0-100):
- **File-based**: count completed files matching a glob pattern (e.g., `design_*.pdb`)
- **Log-based**: parse `step X/Y` patterns from stdout logs (last 8KB)
- **Time-based**: elapsed time / estimated total (from `history.jsonl` median or built-in defaults)

Takes the most optimistic signal, caps at 95% until explicitly completed.

### Docs maintenance

`docs/` is bilingual (en/zh). Source-of-truth rules defined in `docs/AGENTS.md`:
- API reference (`docs/{en,zh}/api-reference/tools.md`) must be regenerated from `TOOL_SCHEMAS` when tool_registry.py changes
- Changelog is English-first, managed by the `sync-changelog` skill
- All other docs are mirrored pairs — changes in either locale must sync to the other
- Three project-level skills: `gen-docs`, `sync-changelog`, `translate-docs` (in `.agents/skills/`)

## Key design decisions

- **Cross-conda execution**: Tools often live in separate conda environments. `conda_utils.py` wraps commands with `conda run -n <env>` rather than activating/deactivating shells. The `wrapper_script` parameter provides an escape hatch for complex environment setup.
- **PDBFixer is mandatory**: `run_rfdiffusion` auto-preprocesses input PDBs via `preprocess_for_design()` unless `skip_preprocessing=true`.
- **No bundled ML models**: This plugin provides orchestration, not models. Missing-tool errors return structured messages with download URLs and install guides.
- **Agent-agnostic MCP**: The server speaks standard stdio JSON-RPC 2.0 MCP. Any agent that supports MCP can use it. The `kimi.plugin.json` is a convenience wrapper for Kimi Code; other agents use their own config formats (`.mcp.json`, `settings.json`).
- **Timeout is global**: All subprocess calls use `CONFIG.timeout` (default 3600s). Cancellation terminates the subprocess and cleans up partial files.

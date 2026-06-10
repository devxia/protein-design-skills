# gen-docs

Generate and maintain human-facing product documentation for the `protein-design-mcp` MCP plugin.

## When To Use

- After adding, removing, or modifying tools in `mcp_server/tools/`
- After changing tool parameters (JSON Schema) in `mcp_server/tools/tool_registry.py`
- After updating `README.md` or `README.zh.md` and wanting to sync changes into structured docs
- When setting up docs for the first time on a new project

## Overview

The `docs/` directory contains human-facing product documentation:

```
docs/
├── en/                          # English docs
│   ├── README.md               # Docs landing page
│   ├── guides/                 # User guides
│   │   ├── installation.md
│   │   ├── quickstart.md
│   │   ├── pipeline.md
│   │   └── troubleshooting.md
│   ├── api-reference/
│   │   └── tools.md            # Auto-generated from tool_registry.py
│   └── release-notes/
│       └── changelog.md        # Managed by sync-changelog skill
├── zh/                          # Chinese docs (mirror structure)
│   └── ...
└── AGENTS.md                   # Rules for AI doc maintainers
```

**Core rule**: English docs are the source of truth. Chinese docs are translated from English. The AI must keep both in sync.

## Workflow

### Step 1: Generate API Reference (`docs/{lang}/api-reference/tools.md`)

Source of truth: `mcp_server/tools/tool_registry.py` → `TOOL_SCHEMAS`

For each tool schema in `TOOL_SCHEMAS`, extract:
- `name`: Tool name
- `description`: Tool description
- `inputSchema.properties`: Each parameter with type, default, description
- `inputSchema.required`: Required parameters

Generate a Markdown table + detailed section per tool.

Example output structure:

```markdown
# API Reference — Tools

## run_pdbfixer

Preprocess a PDB/CIF file with PDBFixer...

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| input_pdb | string | Yes | — | Input PDB/CIF file path |
| output_pdb | string | No | auto | Output PDB file path |
| conda_env | string | No | — | Target conda environment |
```

### Step 2: Sync Guides from README

Source of truth: `README.md` (English) and `README.zh.md` (Chinese)

Map README sections to guide files:

| README Section | Guide File |
|----------------|------------|
| Prerequisites / Installation | `guides/installation.md` |
| Quick Start / Example Workflow | `guides/quickstart.md` |
| Pipeline Stages / Full Workflow | `guides/pipeline.md` |
| Troubleshooting table | `guides/troubleshooting.md` |

Rules:
- Copy content from README, do not rewrite unless the README itself is outdated
- Preserve code blocks, tables, and formatting
- Add a front-matter header to each guide file:
  ```markdown
  ---
  title: Installation Guide
  source: README.md
  ---
  ```

### Step 3: Ensure Bi-Lingual Sync

After updating English docs, mirror the changes to Chinese docs:

- Same file structure (`docs/zh/` mirrors `docs/en/`)
- Same section order and entry counts
- Translate title and body; keep tool names, parameter names, code blocks, and file paths as-is
- Follow Chinese typography: full-width punctuation, spaces between Chinese and English

### Step 4: Write `docs/AGENTS.md`

This file tells future AI agents how to maintain docs:

```markdown
# Docs Maintenance Guide

## Directory Structure
...

## Rules
- English is source of truth
- Keep Chinese docs in sync with English
- Auto-regenerate api-reference/tools.md when tool_registry.py changes
- Do not edit docs directly without updating the source (code or README)
```

## Stop Signals

- `mcp_server/tools/tool_registry.py` does not exist or `TOOL_SCHEMAS` is empty
- `README.md` does not exist
- Generated docs would lose content compared to existing docs (ask user before overwriting)

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Hardcoding tool schemas instead of reading from tool_registry.py | Always extract from `TOOL_SCHEMAS` dynamically |
| Forgetting to update Chinese docs after English changes | Run the bi-lingual sync step every time |
| Rewriting user-facing descriptions | Copy from source; only edit if source is wrong |
| Missing required vs optional parameter indicators | Preserve from `inputSchema.required` |

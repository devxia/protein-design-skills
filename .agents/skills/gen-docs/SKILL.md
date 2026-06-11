# gen-docs

Generate and maintain human-facing product documentation for the `protein-design-skills` plugin.

## When To Use

- After adding, removing, or modifying scripts in `scripts/`
- After adding or modifying skills in `skills/`
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
│   │   └── scripts.md          # Auto-generated from scripts/
│   └── release-notes/
│       └── changelog.md        # Managed by sync-changelog skill
├── zh/                          # Chinese docs (mirror structure)
│   └── ...
└── AGENTS.md                   # Rules for AI doc maintainers
```

**Core rule**: English docs are the source of truth. Chinese docs are translated from English. The AI must keep both in sync.

## Workflow

### Step 1: Generate API Reference (`docs/{lang}/api-reference/scripts.md`)

Source of truth: `scripts/` directory — each script's `--help` output and argparse definitions.

For each script in `scripts/`, extract:
- Script name and description
- CLI arguments and options
- Usage examples
- Exit codes

Generate a Markdown table + detailed section per script.

### Step 2: Sync Guides from README

Source of truth: `README.md` (English) and `README.zh.md` (Chinese)

Map README sections to guide files:

| README Section | Guide File |
|----------------|------------|
| Prerequisites / Installation | `guides/installation.md` |
| Quick Start / Example Workflow | `guides/quickstart.md` |
| Pipeline Stages / Full Workflow | `guides/pipeline.md` |
| Troubleshooting table | `guides/troubleshooting.md` |

### Step 3: Ensure Bi-Lingual Sync

After updating English docs, mirror the changes to Chinese docs:

- Same file structure (`docs/zh/` mirrors `docs/en/`)
- Same section order and entry counts
- Translate title and body; keep tool names, parameter names, code blocks, and file paths as-is

## Stop Signals

- `README.md` does not exist
- Generated docs would lose content compared to existing docs (ask user before overwriting)

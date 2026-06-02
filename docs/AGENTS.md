# Docs Maintenance Guide

This file tells AI agents how to maintain the `docs/` directory for the `kimi-protein-design` project.

## Directory Structure

```
docs/
├── en/                          # English docs (source of truth)
│   ├── README.md               # Docs landing page
│   ├── guides/                 # User guides
│   ├── api-reference/          # Auto-generated from tool_registry.py
│   └── release-notes/          # Changelog
├── zh/                          # Chinese docs (translated from EN)
│   └── ... (mirror structure)
└── AGENTS.md                   # This file
```

## Rules

1. **English is the source of truth**. Always update English docs first, then mirror to Chinese.
2. **Keep Chinese docs in sync** with English in terms of:
   - File structure and names
   - Section order and heading hierarchy
   - Entry counts in tables and lists
3. **Auto-regenerate `api-reference/tools.md`** whenever `tool_registry.py` changes:
   - Extract `TOOL_SCHEMAS`
   - Generate parameter tables (name, type, required, default, description)
   - Do not hardcode tool schemas
4. **Do not edit docs directly** without updating the source (code or README).
   - Guides should be extracted from `README.md` / `README.zh.md`
   - API reference should be generated from `tool_registry.py`
5. **Changelog is managed by `sync-changelog` skill** — do not edit manually.

## Workflow When Code Changes

1. Run `gen-docs` skill to regenerate API reference and sync guides
2. Run `sync-changelog` skill if the change is user-facing
3. Verify both English and Chinese docs are in sync
4. Commit with message: `docs: update docs for <description>`

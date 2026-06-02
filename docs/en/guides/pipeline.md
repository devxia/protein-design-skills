---
title: Pipeline Architecture
source: README.md
---

# Pipeline Architecture

## Project structure

```
kimi-protein-design/
├── kimi.plugin.json              # Plugin manifest
├── skills/                       # Workflow guidance
│   ├── protein-design-context/   # Session-start context
│   ├── structure-preprocessing/  # Stage 0: PDBFixer
│   ├── structure-generation/     # Stage 1: RFdiffusion
│   ├── sequence-design/          # Stage 2: ProteinMPNN
│   ├── structure-validation/     # Stage 3: AlphaFold3
│   ├── filtering-ranking/        # Stage 4: Filtering
│   └── full-pipeline/            # End-to-end orchestration
├── mcp_server/                   # MCP Server (stdio JSON-RPC)
│   ├── server.py                 # Main entry
│   ├── tools/                    # Tool implementations
│   │   ├── job_manager.py        # Async task management
│   │   ├── pdbfixer_tool.py      # PDB preprocessing
│   │   ├── rfdiffusion.py        # Backbone generation
│   │   ├── proteinmpnn.py        # Sequence design
│   │   ├── alphafold.py          # Structure validation
│   │   ├── format_converter.py   # FASTA ↔ JSON conversion
│   │   ├── filtering.py          # Quality filtering
│   │   └── system_info.py        # Environment checks
│   ├── utils/                    # Utilities
│   │   ├── config.py             # Configuration
│   │   └── gpu_utils.py          # GPU detection
│   └── hooks/                    # Recommended hooks
│       ├── install-hooks.py      # One-click installer
│       ├── protein-context-inject.py
│       ├── gpu-check-hook.py
│       ├── design-complete-notify.py
│       └── background-notify.py
└── README.md
```

## Design pipeline (5 stages)

| Stage | Purpose | Tool | Default Output |
|-------|---------|------|---------------|
| 0 | Preprocessing | PDBFixer | Fixed PDB |
| 1 | Backbone generation | RFdiffusion | 10 backbones |
| 2 | Sequence design | ProteinMPNN | 8 sequences / backbone |
| 3 | Structure validation | AlphaFold3 | 5 predictions / design |
| 4 | Filtering & ranking | Filtering | Ranked by quality score |

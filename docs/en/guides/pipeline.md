---
title: Pipeline Architecture
source: README.md
---

# Pipeline Architecture

## Project structure

```
protein-design-skills/
├── kimi.plugin.json              # Plugin manifest (Kimi Code)
├── skills/                       # Workflow guidance
│   ├── protein-design-context/   # Session-start context
│   ├── structure-preprocessing/  # Stage 0: PDBFixer
│   ├── structure-generation/     # Stage 1: RFdiffusion
│   ├── sequence-design/          # Stage 2: ProteinMPNN
│   ├── structure-validation/     # Stage 3: AlphaFold3
│   ├── filtering-ranking/        # Stage 4: Filtering
│   └── full-pipeline/            # End-to-end orchestration
├── protein_design/                   # MCP Server (stdio JSON-RPC)
│   ├── server.py                 # Main entry
│   ├── tools/                    # Tool implementations
│   │   ├── tool_registry.py      # Tool schemas and dispatch
│   │   ├── job_manager.py        # Async task management
│   │   ├── pdbfixer_tool.py      # PDB preprocessing
│   │   ├── rfdiffusion.py        # Backbone generation
│   │   ├── proteinmpnn.py        # Sequence design
│   │   ├── alphafold.py          # Structure validation
│   │   ├── format_converter.py   # FASTA ↔ JSON conversion
│   │   ├── filtering.py          # Quality filtering
│   │   ├── tool_installer.py     # Tool path configuration
│   │   └── system_info.py        # Environment checks
│   ├── utils/                    # Utilities
│   │   ├── config.py             # Configuration
│   │   ├── conda_utils.py        # Cross-conda execution
│   │   ├── gpu_utils.py          # GPU detection
│   │   └── progress_tracker.py   # File-based progress + ETA
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

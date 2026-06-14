---
title: Pipeline Architecture
source: README.md
---

# Pipeline Architecture

## Project structure

```
protein-design-skills/
├── plugin.json / kimi.plugin.json / .claude-plugin/*.json / .codex-plugin/*.json  # Plugin manifests
├── skills/                       # Workflow guidance (76 skills)
│   ├── protein-design-context/   # Session-start context
│   ├── structure-preprocessing/  # Stage 0: PDBFixer
│   ├── structure-generation/     # Stage 1: RFdiffusion + alternatives
│   ├── sequence-design/          # Stage 2: ProteinMPNN + alternatives
│   ├── structure-validation/     # Stage 3: AlphaFold3 + alternatives
│   ├── filtering-ranking/        # Stage 4: Filtering
│   ├── full-pipeline/            # End-to-end orchestration
│   ├── pipeline-selection/       # Choose from 30+ design pipelines
│   └── ...                       # Additional specialized skills
├── protein_design/
│   └── hooks/                    # Automation scripts (22 hooks + install-hooks.py)
│       ├── install-hooks.py      # One-click installer
│       ├── protein-context-inject.py
│       ├── gpu-check-hook.py
│       ├── session-health-check.py
│       ├── job-monitor.py
│       ├── progress-reporter.py
│       ├── execution-adapter.py
│       ├── pipeline-orchestrator.py
│       └── ...
├── scripts/                      # Standalone execution scripts
│   ├── run_pdbfixer.py           # Stage 0
│   ├── run_rfdiffusion.py        # Stage 1
│   ├── run_proteinmpnn.py        # Stage 2
│   ├── run_alphafold3.py         # Stage 3
│   ├── run_boltz.py              # Stage 3 (alternative)
│   ├── run_chai1.py              # Stage 3 (alternative)
│   ├── run_omegafold.py          # Stage 3 (alternative)
│   ├── run_esmfold.py            # Stage 3 (alternative)
│   ├── run_filtering.py          # Stage 4
│   ├── convert_format.py         # Format conversion
│   ├── job_manager.py            # Background jobs
│   └── batch_runner.py           # Pipeline orchestration
└── README.md
```

## Design pipeline (5 stages)

| Stage | Purpose | Primary Tool | Default Output |
|-------|---------|-------------|---------------|
| 0 | Preprocessing | PDBFixer | Fixed PDB |
| 1 | Backbone generation | RFdiffusion | 10 backbones |
| 2 | Sequence design | ProteinMPNN | 8 sequences / backbone |
| 3 | Structure validation | AlphaFold3 | 5 predictions / design |
| 4 | Filtering & ranking | Filtering | Ranked by quality score |

## Execution flow

```
User Request
    |
    v
Skill Selection (protein-design-context / pipeline-selection)
    |
    v
Hook: protein-context-inject.py (auto-inject relevant skill context)
    |
    v
Hook: gpu-check-hook.py (verify GPU availability)
    |
    v
Standalone Script Execution (scripts/run_*.py)
    |
    v
Hook: progress-reporter.py (track progress, estimate ETA)
    |
    v
Hook: design-complete-notify.py (desktop notification on completion)
    |
    v
Results + Next Skill Recommendation
```

## Choosing a pipeline

Use `skills/pipeline-selection/SKILL.md` to choose from 15+ design pipelines:

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

## Hooks reference

| Hook | Trigger | Purpose |
|------|---------|---------|
| `install-hooks.py` | Manual | Install hooks for chosen agent |
| `protein-context-inject.py` | Protein-related prompt | Auto-inject relevant skill context |
| `gpu-check-hook.py` | Before GPU-intensive task | Verify GPU availability and memory |
| `session-health-check.py` | Manual / Session start | Check tool installations |
| `job-monitor.py` | After job submission | Monitor background jobs |
| `progress-reporter.py` | During long tasks | Parse logs, estimate ETA |
| `execution-adapter.py` | Script execution | Route to correct script with args |
| `pipeline-orchestrator.py` | Multi-stage request | Chain stages automatically |
| `design-complete-notify.py` | Job completion | Desktop notification |
| `background-notify.py` | Background job completion | Notification for async jobs |
| `auto-parameter-tuner.py` | Parameter tuning | Suggest optimal parameters |
| `design-comparator.py` | Result comparison | Compare multiple designs |
| `cost-estimator.py` | Before execution | Estimate GPU time and cost |
| `quality-gate.py` | After validation | Automated quality checks |
| `error-recovery.py` | On failure | Suggest recovery actions |
| `batch-orchestrator.py` | Batch jobs | Manage batch submissions |
| `format-converter.py` | Format conversion | Convert between file formats |
| `tool-recommender.py` | Tool selection | Recommend tools for task |
| `alternative-tool-recommender.py` | Tool not found | Suggest alternatives |
| `design-report.py` | After pipeline | Generate summary report |
| `user-onboarding.py` | First protein prompt | Welcome message + tool status |
| `progress-query-helper.py` | Progress questions | Help parse progress queries |
| `parameter-generator.py` | Parameter requests | Generate tool-specific parameters |

## Architecture

Execution flows: **Skills → Hooks → Standalone Scripts**.

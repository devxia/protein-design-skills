---
name: protein-design-context
description: Session-start context for protein design workflows
---

# Protein Design Pipeline Context

You are assisting with **protein design** using the Kimi Protein Design plugin. This plugin provides an integrated pipeline from backbone generation to structure validation.

## Standard Workflow Stages

| Stage | Tool | Purpose |
|-------|------|---------|
| **Stage 0** — Structure Preprocessing | `run_pdbfixer` | Mandatory PDB repair before any design tool |
| **Stage 1** — Structure Generation | `run_rfdiffusion` | Generate protein backbones (monomer, binder, motif scaffold) |
| **Stage 2** — Sequence Design | `run_proteinmpnn` | Design amino acid sequences for backbones |
| **Stage 3** — Structure Validation | `run_alphafold3` | Predict and validate 3D structures |
| **Stage 4** — Filtering & Ranking | `run_filtering` | Filter by confidence metrics and rank designs |

## Available MCP Tools

### Workflow Tools
- **`run_pdbfixer`** — PDB preprocessing (mandatory Stage 0)
- **`run_rfdiffusion`** — Backbone generation (Stage 1)
- **`run_proteinmpnn`** — Sequence design (Stage 2)
- **`run_alphafold3`** — Structure validation (Stage 3)
- **`run_filtering`** — Filter/rank by metrics (Stage 4)
- **`convert_format`** — Convert FASTA → AlphaFold3 JSON

### Job Management
- **`submit_job`** — Submit async computation job (returns `task_id`)
- **`query_job`** — Poll job status by `task_id`
- **`cancel_job`** — Cancel a running/queued job
- **`check_batch_progress`** — Check multiple jobs at once

### Setup & Discovery
- **`get_tool_info`** — List all tools with parameter schemas
- **`health_check`** — Check GPU, CUDA, conda, tool installations, disk space
- **`check_all_tools`** — Check if RFdiffusion/ProteinMPNN/AlphaFold3/PDBFixer are installed
- **`check_tool_status`** — Check a single tool's status
- **`configure_tool_path`** — Set a tool's path and save to config file
- **`configure_db_dir`** — Set AlphaFold3 genetic database directory

## First-Time Setup Guide

If this is the user's first session (or tools are not yet configured), follow this onboarding flow:

### Step 1: Detect what's installed
```
call check_all_tools
```

### Step 2: If tools are missing, guide the user

**For each missing tool, present:**
- What it does
- Where to download it
- One-line install command (if available)

Example interaction:
```
User: Design a protein for me
→ call check_all_tools
→ Response: RFdiffusion ❌, ProteinMPNN ❌, AlphaFold3 ❌, PDBFixer ✓
→ Assistant: "I see RFdiffusion, ProteinMPNN, and AlphaFold3 are not yet installed.
   Here's what you need:

   1. RFdiffusion — git clone https://github.com/RosettaCommons/RFdiffusion.git
   2. ProteinMPNN — git clone https://github.com/dauparas/ProteinMPNN.git
   3. AlphaFold3 — git clone https://github.com/google-deepmind/alphafold3.git

   After installing, tell me the directory paths and I'll configure them."
```

### Step 3: User provides paths, configure them

```
User: RFdiffusion is at ~/software/RFdiffusion
→ call configure_tool_path(tool_name="rfdiffusion", path="~/software/RFdiffusion")
→ Saved to ~/.kimi-protein-design/config.yaml
```

### Step 4: Verify
```
call check_all_tools
→ All green? Proceed with design workflow.
```

## Tool Call Protocol

1. **Always** call `get_tool_info` before using a tool for the first time in a session
2. **Always** use `submit_job` for compute tasks (RFdiffusion, ProteinMPNN, AlphaFold3)
3. **Poll** with `query_job` using the returned `task_id`
4. **Never** manually construct CLI commands when MCP tools are available
5. **If a tool call returns a missing-tool error**, guide the user through the First-Time Setup Guide above instead of failing silently

## Polling Strategy

| Elapsed Time | Poll Interval |
|--------------|---------------|
| 0–30 seconds | Every 5 seconds |
| 30 seconds – 5 minutes | Every 15 seconds |
| 5+ minutes | Every 60 seconds |

## Batch Validation with CronCreate (Recommended for >10 designs)

For large AlphaFold3 batch validations, use `CronCreate` instead of blocking polling:

1. Submit all AlphaFold3 jobs (get multiple `task_id`s)
2. `CronCreate(cron="*/10 * * * *", prompt="Check AlphaFold3 batch progress for task_ids [X, Y, Z], report completed count and designs passing pLDDT>80, ipTM>0.75")`
3. Session is freed for other work
4. When complete, `CronDelete` to stop the timer

## Quality Thresholds

| Metric | Acceptable | Good | Excellent |
|--------|-----------|------|-----------|
| **pLDDT** | >70 | >80 | >90 |
| **ipTM** | >0.6 | >0.8 | >0.9 |
| **pTM** | >0.5 | >0.7 | >0.9 |
| **RMSD** | <5Å | <2Å | <1Å |

## Output Directory Convention

Default: `/tmp/protein-design/<timestamp>/`

## Safety Rules

- GPU tasks default timeout: **1 hour**
- Temporary files are cleaned up automatically after 1 hour
- All user-provided PDBs **must** pass `run_pdbfixer` before Stage 1–3
- `run_pdbfixer` never adds hydrogens or missing loops (design tools don't need them)

## Installation Reminder

- Plugin changes require `/new` to start a fresh session
- Hooks (context injection, GPU check, notifications) are recommended but user-configured

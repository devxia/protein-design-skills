---
name: full-pipeline
description: End-to-end protein design pipeline orchestration
---

# Full Pipeline: End-to-End Protein Design

## When to Trigger

- User says "design a protein", "full pipeline", "end to end"
- User describes a design goal: "binder for PD-L1", "150-aa monomer", "scaffold around this motif"
- User provides a target and wants a complete binder design
- User requests fast screening: "quick screen", "rapid validation"
- User requests specific workflow: "use ESMFold", "skip MSA", "fast pipeline"

## Pipeline Overview

The protein design pipeline has **5 stages** that execute sequentially:

```
Stage 0 (PDBFixer) → Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN)
                                              ↓
Stage 4 (Filtering) ← Stage 3 (AlphaFold3) ←┘
```

### Alternative Pipelines

The project supports **7 distinct pipelines** covering different design needs:

| # | Pipeline | Stage 1 | Stage 2 | Stage 3 | Best For | Speed |
|---|----------|---------|---------|---------|----------|-------|
| 1 | **Standard** | RFdiffusion | ProteinMPNN | AlphaFold3 (full MSA) | General purpose | Medium |
| 2 | **Ligand-Aware** | RFdiffusionAA | LigandMPNN | AlphaFold3 | Ligands, cofactors, heme | Slow |
| 3 | **Fast Screening** | RFdiffusion | ProteinMPNN | OmegaFold (no MSA/DB) | Quick validation, no DBs | Fast |
| 4 | **Chroma** | Chroma (joint) | — | AlphaFold3 | All-atom, NL prompting | Medium |
| 5 | **ColabDesign** | AfDesign | AfDesign (built-in) | AF3/OmegaFold | No local GPU | Medium |
| 6 | **Peptide** | DiffPepBuilder | Built-in + ESM | AlphaFold3 | 8-30aa peptides | Slow |
| 7 | **Ensemble** | RFdiffusion | ProteinMPNN + ESM-IF1 | AlphaFold3 | Maximum diversity | Slow |

**Pipeline selection guide:**
- "I need the best accuracy" → Standard or Ensemble pipeline
- "I need fast results / no databases" → Fast Screening pipeline (OmegaFold)
- "I'm designing with a ligand/cofactor" → Ligand-Aware pipeline (RFdiffusionAA)
- "I don't have a local GPU" → ColabDesign pipeline (free Colab)
- "I'm designing a peptide" → Peptide pipeline (DiffPepBuilder)
- "I want all-atom generation" → Chroma pipeline
- "I have many designs to check" → Two-stage: OmegaFold screen → AlphaFold3 validate top 20

See `pipeline-selection` skill for detailed decision guidance.

## Stage Details

### Stage 0 — Structure Preprocessing (Mandatory)
**Script**: `scripts/run_pdbfixer.py`

All user-provided PDBs must be preprocessed before any design tool.
- Converts non-standard residues (MSE→MET, etc.)
- Removes heterogens (ligands, ions, water)
- Adds missing heavy atoms
- **Does NOT add hydrogens or missing loops**

### Stage 1 — Backbone Generation
**Script**: `scripts/run_rfdiffusion.py`

Generates poly-Glycine backbone structures.
- **Input**: Preprocessed PDB (for motif/binder) or none (unconditional)
- **Key parameter**: `contig` — defines what to generate/fix
- **Output**: PDB files with only N/CA/C/O atoms

### Stage 2 — Sequence Design
**Script**: `scripts/run_proteinmpnn.py`

Assigns amino acid sequences to backbones.
- **Input**: PDB from Stage 1
- **Key parameter**: `sampling_temp` — controls sequence diversity
- **Output**: FASTA files with designed sequences

### Stage 3 — Structure Validation
**Script**: `scripts/run_alphafold3.py`

Predicts structures and computes confidence metrics.
- **Input**: JSON (converted from Stage 2 FASTA via `convert_format`)
- **Key metrics**: pLDDT, ipTM, pTM
- **Output**: mmCIF structures + confidence JSON

### Stage 4 — Filtering & Ranking
**Script**: `scripts/run_filtering.py`

Selects best designs by quality thresholds.
- **Input**: Metrics from Stage 3
- **Output**: Ranked list of passing designs

## Automation Hooks / 自动化钩子

When hooks are installed, the pipeline gets automatic orchestration support:

| Hook | File | Trigger | What it does |
|------|------|---------|--------------|
| `pipeline-orchestrator` | `protein_design/hooks/pipeline-orchestrator.py` | Stage completion | Suggests the next stage and command |
| `progress-reporter` | `protein_design/hooks/progress-reporter.py` | Stage / notification | Reports artifact counts and quality distribution |
| `quality-gate` | `protein_design/hooks/quality-gate.py` | Validation results | Pass/fail decisions against thresholds |
| `design-complete-notify` | `protein_design/hooks/design-complete-notify.py` | Stage completion | Notification with summary |
| `batch-orchestrator` | `protein_design/hooks/batch-orchestrator.py` | Batch job setup | Helps coordinate multi-design batches |
| `error-recovery` | `protein_design/hooks/error-recovery.py` | Tool failure | Suggests recovery commands |

Install hooks with:
```bash
python protein_design/hooks/install-hooks.py
```

## Progress Monitoring & Output Summaries

At any point during or after the pipeline, get a live summary of artifacts and quality metrics:

```bash
# One-shot summary of output directory
python scripts/summarize_outputs.py --output-dir outputs/

# Watch live progress (refreshes every 30 seconds)
python scripts/summarize_outputs.py --output-dir outputs/ --watch

# With expected counts for progress bars
python scripts/summarize_outputs.py --output-dir outputs/ \
  --expected-backbones 50 \
  --expected-sequences 200 \
  --expected-validations 50

# JSON output for downstream scripts
python scripts/summarize_outputs.py --output-dir outputs/ --json
```

The summary reports:
- **Backbone count** — generated PDB files from Stage 1
- **Sequence count** — FASTA files from Stage 2
- **Validation count** — confidence JSON files from Stage 3
- **Quality distribution** — Excellent (pLDDT ≥90), Good (80–90), Acceptable (70–80), Poor (<70)
- **Top designs by pLDDT** — ranked table with ipTM and pTM

Hook-based progress reminders also activate after each stage when hooks are installed:

```bash
python protein_design/hooks/install-hooks.py
```

## Complete Example: PD-L1 Binder Design

### Step 0: Preprocess target structure
```bash
python scripts/run_pdbfixer.py \
  --input target.pdb \
  --output target_fixed.pdb
```

### Step 1: Generate binder backbones
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb target_fixed.pdb \
  --contig "[B1-100/0 100-100]" \
  --hotspot-res A30 A33 A34 \
  --output-prefix outputs/binder \
  --num-designs 50
```

Track progress while it runs:
```bash
python scripts/summarize_outputs.py --output-dir outputs/ --expected-backbones 50 --watch
```

### Step 2: Design sequences
```bash
python scripts/run_proteinmpnn.py \
  --pdb-path "outputs/binder_*.pdb" \
  --out-folder outputs/seqs/ \
  --chains B \
  --num-seq 8 \
  --temp 0.1
```

### Step 3a: Convert FASTA to AlphaFold3 JSON
```bash
python scripts/convert_format.py \
  --from fasta \
  --to alphafold3_json \
  --input outputs/seqs/design_0.fa \
  --output outputs/seqs/design_0_af3_input.json \
  --job-name design_0
```

### Step 3b: Validate with AlphaFold3
```bash
python scripts/run_alphafold3.py \
  --json outputs/seqs/design_0_af3_input.json \
  --output-dir outputs/af3/design_0 \
  --db-dir /path/to/public_databases
```

> **AlphaFold3 Database Setup**: AlphaFold3 requires genetic databases (~2.6TB) for MSA search. The plugin auto-detects `~/public_databases` or other common locations. If not found:
> 1. Download databases per [AlphaFold3 docs](https://github.com/google-deepmind/alphafold3)
> 2. Configure path by editing `~/.protein-design/config.yaml`:
>    ```yaml
>    db_dir: ~/public_databases
>    ```
> 3. Or skip MSA (faster, less accurate): pass `--no-msa`
> 4. Or pass `--db-dir` explicitly in each `run_alphafold3.py` call

### Step 4: Filter results
```bash
python scripts/run_filtering.py \
  --output-dir outputs/af3/ \
  --min-plddt 75 \
  --min-iptm 0.75
```

## Alternative: Fast Screening Pipeline

For screening many designs quickly (e.g., 400 sequences), use the two-stage approach:

### Stage 3a: Rapid Screen with ESMFold (No MSA)
```bash
# ESMFold predicts ~5-30 seconds per sequence
# No databases needed
```

### Stage 3b: Validate Top Candidates with AlphaFold3
After ESMFold screening, take the top 20 designs and validate with full AlphaFold3:

```bash
python scripts/run_alphafold3.py \
  --json top_design.json \
  --output-dir outputs/af3_top \
  --db-dir /path/to/public_databases \
  --num-seeds 1 \
  --num-samples 5
```

**Time savings:** 400 designs × 30 min (AF3) = 200 hours
vs. 400 designs × 10 sec (ESMFold) + 20 designs × 30 min (AF3) = ~1.5 hours

### Stage 3 Alternative: AlphaFold3 No-MSA Mode
Skip MSA for faster inference (moderate accuracy):

```bash
python scripts/run_alphafold3.py \
  --json design.json \
  --output-dir outputs/af3_fast \
  --no-msa \
  --num-seeds 1 \
  --num-samples 1
```

## Batch Validation with Progress Monitoring

When validating many designs (>10), avoid blocking the session with continuous polling:

### Option A: Watch Output Directory Automatically
```bash
# Refresh summary every 30 seconds until you Ctrl-C
python scripts/summarize_outputs.py \
  --output-dir outputs/af3/ \
  --expected-validations 50 \
  --watch \
  --interval 30
```

### Option B: Schedule Periodic Reports
Use a cron/loop inside Claude Code to get periodic summaries without blocking:

```
/loop 10m Check AlphaFold3 batch progress in outputs/af3/. Report: total validations completed, count with pLDDT>80 and ipTM>0.75, list any failures.
```

Stop the loop when the batch is complete.

## Mid-Pipeline Intervention

Users can modify parameters at any stage:
- **After Stage 1**: "Generate more backbones" → re-run RFdiffusion with higher `num_designs`
- **After Stage 2**: "Make sequences more diverse" → re-run ProteinMPNN with higher `sampling_temp`
- **After Stage 3**: "Relax the filters" → re-run filtering with lower thresholds
- **After Stage 4**: "Take the top design and validate more seeds" → run AlphaFold3 with more `num_seeds` on the winner

Single-stage failures do not affect completed stages. Results are preserved in the output directory.

## Error Handling

| Stage | Common Error | Strategy |
|-------|-------------|----------|
| 0 | Missing atoms | PDBFixer adds them automatically |
| 0 | Non-standard residues | PDBFixer converts automatically |
| 1 | Contig mismatch | Verify residue numbering in input PDB |
| 1 | GPU OOM | Reduce `num_designs` or `diffuser_T` |
| 2 | Chain ID mismatch | Verify chain IDs in PDB match params |
| 3 | JSON format error | Re-run `convert_format` |
| 3 | MSA timeout | Use `run_data_pipeline=false` if re-running |
| 4 | All designs fail | Relax criteria or regenerate |

## Installation & Session Notes

- Plugin changes require restarting the session
- Hooks (context injection, GPU check, notifications) are recommended for best experience — run `python protein_design/hooks/install-hooks.py`

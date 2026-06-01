---
name: full-pipeline
description: End-to-end protein design pipeline orchestration
---

# Full Pipeline: End-to-End Protein Design

## When to Trigger

- User says "design a protein", "full pipeline", "end to end"
- User describes a design goal: "binder for PD-L1", "150-aa monomer", "scaffold around this motif"
- User provides a target and wants a complete binder design

## Pipeline Overview

The protein design pipeline has **5 stages** that execute sequentially:

```
Stage 0 (PDBFixer) → Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN)
                                              ↓
Stage 4 (Filtering) ← Stage 3 (AlphaFold3) ←┘
```

## Stage Details

### Stage 0 — Structure Preprocessing (Mandatory)
**Tool**: `run_pdbfixer`

All user-provided PDBs must be preprocessed before any design tool.
- Converts non-standard residues (MSE→MET, etc.)
- Removes heterogens (ligands, ions, water)
- Adds missing heavy atoms
- **Does NOT add hydrogens or missing loops**

### Stage 1 — Backbone Generation
**Tool**: `run_rfdiffusion`

Generates poly-Glycine backbone structures.
- **Input**: Preprocessed PDB (for motif/binder) or none (unconditional)
- **Key parameter**: `contig` — defines what to generate/fix
- **Output**: PDB files with only N/CA/C/O atoms

### Stage 2 — Sequence Design
**Tool**: `run_proteinmpnn`

Assigns amino acid sequences to backbones.
- **Input**: PDB from Stage 1
- **Key parameter**: `sampling_temp` — controls sequence diversity
- **Output**: FASTA files with designed sequences

### Stage 3 — Structure Validation
**Tool**: `run_alphafold3`

Predicts structures and computes confidence metrics.
- **Input**: JSON (converted from Stage 2 FASTA via `convert_format`)
- **Key metrics**: pLDDT, ipTM, pTM
- **Output**: mmCIF structures + confidence JSON

### Stage 4 — Filtering & Ranking
**Tool**: `run_filtering`

Selects best designs by quality thresholds.
- **Input**: Metrics from Stage 3
- **Output**: Ranked list of passing designs

## Complete Example: PD-L1 Binder Design

### Step 0: Preprocess target structure
```json
{"tool": "run_pdbfixer", "params": {"input_pdb": "target.pdb", "output_pdb": "target_fixed.pdb"}}
```

### Step 1: Generate binder backbones
```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "target_fixed.pdb",
  "contig": "[B1-100/0 100-100]",
  "hotspot_res": ["A30", "A33", "A34"],
  "output_prefix": "outputs/binder",
  "num_designs": 50
}}
```

### Step 2: Design sequences
```json
{"tool": "run_proteinmpnn", "params": {
  "pdb_path": "outputs/binder/design_0.pdb",
  "output_folder": "outputs/seqs",
  "pdb_path_chains": "B",
  "num_seq_per_target": 8,
  "sampling_temp": "0.1"
}}
```

### Step 3a: Convert FASTA to AlphaFold3 JSON
```json
{"tool": "convert_format", "params": {
  "from_format": "fasta",
  "to_format": "alphafold3_json",
  "input_path": "outputs/seqs/design_0.fa",
  "job_name": "design_0"
}}
```

### Step 3b: Validate with AlphaFold3
```json
{"tool": "run_alphafold3", "params": {
  "json_path": "outputs/seqs/design_0_af3_input.json",
  "output_dir": "outputs/af3/design_0",
  "db_dir": "/path/to/public_databases"
}}
```

> **AlphaFold3 Database Setup**: AlphaFold3 requires genetic databases (~2.6TB) for MSA search. The plugin auto-detects `~/public_databases` or other common locations. If not found:
> 1. Download databases per [AlphaFold3 docs](https://github.com/google-deepmind/alphafold3)
> 2. Configure path: `configure_db_dir(path="~/public_databases")`
> 3. Or skip MSA (faster, less accurate): `"run_data_pipeline": false`
> 4. Or pass `db_dir` explicitly in each `run_alphafold3` call

### Step 4: Filter results
```json
{"tool": "run_filtering", "params": {
  "designs": [...],
  "criteria": {"min_plddt": 75, "min_iptm": 0.75}
}}
```

## Batch Validation with CronCreate (0.6.0+)

When validating many designs (>10), avoid blocking the session with continuous polling:

1. Submit all AlphaFold3 jobs (async, get multiple task_ids)
2. `CronCreate(cron="*/10 * * * *", prompt="Check AlphaFold3 batch progress for task_ids [X,Y,Z,...]. Report: total completed, count with pLDDT>80 and ipTM>0.75, list any failures.")`
3. Session is freed — user can do other work
4. When batch is complete, `CronDelete` to stop the timer

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

- Plugin changes require `/new` to start a fresh session
- Hooks (UserPromptSubmit context injection, PreToolUse GPU check, PostToolUse notifications) are recommended for best experience
- Install hooks via: `python mcp_server/hooks/install-hooks.py`

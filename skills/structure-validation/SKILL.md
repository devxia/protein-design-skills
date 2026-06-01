---
name: structure-validation
description: Structure prediction and validation with AlphaFold3 (Stage 3)
---

# Stage 3: Structure Validation (AlphaFold3)

## When to Trigger

- User says "validate this design", "predict structure", "run AlphaFold"
- Follow-up to ProteinMPNN: "check if the sequence folds correctly"
- User wants confidence metrics (pLDDT, pTM, ipTM) for a sequence

## AlphaFold3 Overview

AlphaFold3 predicts 3D protein structures from sequence input. In the design pipeline, it's used to validate that sequences designed by ProteinMPNN actually fold into the intended backbone structure.

## Input Format

AlphaFold3 accepts a JSON file. For protein-only designs:

```json
{
  "name": "my_design",
  "modelSeeds": [1],
  "sequences": [
    {
      "protein": {
        "id": "A",
        "sequence": "MKTLLILTGLVAGES...",
        "modifications": []
      }
    }
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

**Multi-chain example:**
```json
{
  "name": "binder_complex",
  "sequences": [
    {"protein": {"id": "A", "sequence": "TARGETSEQ...", "modifications": []}},
    {"protein": {"id": "B", "sequence": "BINDERSEQ...", "modifications": []}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

## MCP Tool

```json
{
  "tool": "run_alphafold3",
  "params": {
    "json_path": "inputs/design_af3_input.json",
    "output_dir": "outputs/af3",
    "model_dir": "/path/to/models",
    "db_dir": "/path/to/databases",
    "num_seeds": 1,
    "num_samples": 5
  }
}
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `json_path` | ✅ | — | Input JSON file path |
| `output_dir` | ✅ | — | Output directory |
| `model_dir` | ❌ | `~/models` | Model parameters directory |
| `db_dir` | ❌ | `~/public_databases` | Genetic databases directory |
| `num_seeds` | ❌ | 1 | Number of random seeds |
| `num_samples` | ❌ | 5 | Samples per seed |
| `run_data_pipeline` | ❌ | true | Run MSA search (slow, CPU-only) |

## Database Setup

AlphaFold3 requires **genetic databases** (~2.6TB) for MSA search. The plugin handles this automatically:

| Scenario | Behavior |
|----------|----------|
| `db_dir` passed explicitly | Uses the provided path |
| `db_dir` configured via `configure_db_dir` | Uses the configured path |
| `~/public_databases` exists and looks valid | Auto-detected |
| No databases found + `run_data_pipeline=true` | Logs warning, MSA may fail |
| No databases found + `run_data_pipeline=false` | Skips MSA, runs inference only |

**To configure databases in Kimi:**
```
User: My AlphaFold3 databases are at /data/public_databases
→ call configure_db_dir(path="/data/public_databases")
→ Saved to ~/.kimi-protein-design/config.yaml
```

**To check database status:**
```
call check_tool_status(tool_name="alphafold3")
→ Returns: script found + database detected/present/missing details
```

## Format Conversion (Stage 2 → Stage 3)

ProteinMPNN outputs FASTA; AlphaFold3 needs JSON. Use `convert_format`:

```json
{
  "tool": "convert_format",
  "params": {
    "from_format": "fasta",
    "to_format": "alphafold3_json",
    "input_path": "seqs/design_0.fa",
    "job_name": "design_0",
    "seed": 1
  }
}
```

## Output Format

```
my_design/
├── my_design_model.cif              # Top-ranked structure (mmCIF)
├── my_design_confidences.json       # Full confidence data
├── my_design_summary_confidences.json  # Summary metrics
├── my_design_data.json              # Input + MSA data
├── my_design_ranking_scores.csv     # All predictions ranked
└── seed-1_sample-0/                 # Individual predictions
    ├── ...
```

## Confidence Metrics & Thresholds

| Metric | Range | Acceptable | Good | Excellent |
|--------|-------|------------|------|-----------|
| **pLDDT** | 0–100 | >70 | >80 | >90 |
| **pTM** | 0–1 | >0.5 | >0.7 | >0.9 |
| **ipTM** | 0–1 | >0.6 | >0.8 | >0.9 |
| **ranking_score** | [-100, 1.5] | Higher is better | — | — |
| **has_clash** | bool | false | false | false |

## Metric Interpretations

- **pLDDT**: Per-atom confidence. High values = well-defined structure.
- **pTM**: Overall topology confidence. >0.7 indicates correct fold likely.
- **ipTM**: Interface confidence (critical for binder design). >0.8 = strong interface.
- **has_clash**: True if severe atomic clashes detected. Reject these designs.

## Typical Runtime

| Protein Size | With MSA | MSA Precomputed |
|-------------|----------|-----------------|
| <200 aa | 5–30 min | 2–10 min |
| 200–500 aa | 30–90 min | 10–30 min |
| >500 aa | 1–3 hours | 30–60 min |

## Workflow

```
Input: FASTA from Stage 2 (ProteinMPNN)
     ↓
convert_format(fasta → alphafold3_json)
     ↓
submit_job("alphafold3", params)
     ↓
query_job polling (can take minutes to hours)
     ↓
Parse metrics (pLDDT, ipTM, pTM)
     ↓
Return: mmCIF + confidence JSON → Stage 4 (filtering)
```

## Batch Validation Optimization

For >10 designs, use CronCreate instead of blocking polling:

1. Submit all AlphaFold3 jobs (get task_ids)
2. `CronCreate(cron="*/10 * * * *", prompt="Check AF3 batch progress for [task_ids], report completed and pLDDT>80 count")`
3. When all done, `CronDelete` the timer

## Tips

- Skip MSA (`run_data_pipeline=false`) if re-running with precomputed data
- For binder validation, ipTM is the most important metric
- pLDDT > 80 and ipTM > 0.8 is a good initial filter
- Always check `has_clash` — clashes indicate physically impossible structures

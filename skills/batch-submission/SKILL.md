---
name: batch-submission
description: Efficient batch job submission and management for large-scale protein design screening
---

# Batch Submission and Management

## When to Trigger

- User wants to validate 10+ designs at once
- User says "batch", "screen many", "parallel", "ensemble"
- User wants to compare multiple design variants
- User needs to manage multiple long-running jobs

## Overview

Individual script runs are fine for 1-3 designs. For large-scale screening (10-100+ designs), use batch submission patterns to avoid blocking the session.

The plugin provides `scripts/job_manager.py` for background execution and `scripts/summarize_outputs.py` for filesystem-based batch progress tracking.

## Pattern 1: Submit All, Poll Batch

### Step 1: Submit all jobs via `scripts/job_manager.py`

```bash
# Submit all AlphaFold3 jobs at once
for design_json in outputs/seqs/*_af3_input.json; do
  python scripts/job_manager.py submit \
    --name "af3_$(basename "$design_json" .json)" \
    -- python scripts/run_alphafold3.py \
      --json "$design_json" \
      --output-dir "outputs/af3/$(basename "$design_json" .json)" \
      --run-data-pipeline false
done
```

### Step 2: Poll all jobs with `scripts/job_manager.py list`

```bash
# Check all jobs in one call
python scripts/job_manager.py list

# Example output:
# job_abc123  running  af3_design_0
# job_def456  completed  af3_design_1
# job_ghi789  failed   af3_design_2
```

### Step 3: Repeat until all done

```bash
#!/bin/bash
while true; do
  python scripts/job_manager.py list
  remaining=$(python scripts/job_manager.py list | grep -c "running\|pending" || true)
  if [ "$remaining" -eq 0 ]; then
    break
  fi
  sleep 60  # Poll every minute
done
```

## Pattern 2: Scheduled Batch Monitoring (0.6.0+)

For very large batches (>20 designs), use scheduling instead of blocking poll:

### Submit all jobs

```bash
for i in $(seq 1 50); do
  python scripts/job_manager.py submit \
    --name "af3_design_${i}" \
    -- python scripts/run_alphafold3.py \
      --json "inputs/design_${i}.json" \
      --output-dir "outputs/af3/design_${i}" \
      --run-data-pipeline false
done
```

### Set up scheduled monitoring

```bash
# Schedule a summary every 10 minutes (example cron expression)
# Using Claude Code CronCreate or your system cron
*/10 * * * * cd /path/to/protein-design-skills && \
  python scripts/summarize_outputs.py --results-dir outputs/af3/ --expected 50
```

Or from inside Claude Code, use `/schedule` or `CronCreate` to run:

```
python scripts/summarize_outputs.py --results-dir outputs/af3/ --expected 50 --json
```

### When all complete, stop the schedule

Use `CronDelete <job_id>` (for Claude Code session schedules) or remove the cron entry.

**Benefits:**
- Session is freed for other work
- Progress reports arrive automatically
- No manual polling needed

## Pattern 3: Staged Submission (Screen → Validate)

For maximum efficiency with 100+ designs:

### Stage 1: Fast screen with ESMFold (all designs)

```bash
# ESMFold: ~10 seconds per design
for fasta in outputs/seqs/*.fa; do
  python scripts/job_manager.py submit \
    --name "esm_$(basename "$fasta" .fa)" \
    -- python scripts/run_esmfold.py \
      --fasta "$fasta" \
      --output-dir "outputs/esm/$(basename "$fasta" .fa)"
done
```

### Stage 2: Filter by ESMFold pLDDT

```bash
# Collect all ESMFold results
python scripts/run_filtering.py \
  --results-dir outputs/esm/ \
  --min-plddt 75 \
  --top-n 20 \
  --output outputs/esm_top20.json

# top_designs.json contains the top 20 by quality score
```

### Stage 3: Validate top 20 with AlphaFold3 (full MSA)

```bash
for design in $(cat outputs/esm_top20.json | jq -r '.filtered_designs[].name'); do
  python scripts/job_manager.py submit \
    --name "af3_${design}" \
    -- python scripts/run_alphafold3.py \
      --json "inputs/${design}.json" \
      --output-dir "outputs/af3/${design}" \
      --run-data-pipeline true  # Full accuracy
done
```

**Time savings:** 100 designs × 30 min = 50 hours
vs. 100 designs × 10s (ESMFold) + 20 designs × 30 min (AF3) = ~1.5 hours

## Pattern 4: Parallel Pipeline Stages

When designs are independent, run stages in parallel:

```
Design 1: RFdiffusion → ProteinMPNN → AlphaFold3
Design 2: RFdiffusion → ProteinMPNN → AlphaFold3
Design 3: RFdiffusion → ProteinMPNN → AlphaFold3
```

All can run simultaneously since they're independent. Use `PROTEIN_DESIGN_MAX_JOBS` to control parallelism (default 4).

```bash
export PROTEIN_DESIGN_MAX_JOBS=4
python scripts/job_manager.py submit --name design1_stage1 -- python scripts/run_rfdiffusion.py ...
python scripts/job_manager.py submit --name design2_stage1 -- python scripts/run_rfdiffusion.py ...
python scripts/job_manager.py submit --name design3_stage1 -- python scripts/run_rfdiffusion.py ...
```

## Pattern 5: Job Cancellation

If you need to stop a batch:

```bash
# Cancel a specific job
python scripts/job_manager.py cancel <job_id>

# Cancel all running jobs
for job_id in $(python scripts/job_manager.py list | grep running | awk '{print $1}'); do
  python scripts/job_manager.py cancel "$job_id"
done
```

## Best Practices

| Batch Size | Strategy |
|------------|----------|
| 1-5 | Individual `scripts/job_manager.py submit` + `status` |
| 5-20 | Batch submit + `scripts/job_manager.py list` |
| 20-100 | Scheduled monitoring via `CronCreate` or system cron |
| 100+ | Two-stage: ESMFold screen → AF3 validate top N |

### Resource Management

- Default max concurrent jobs: 4 (`PROTEIN_DESIGN_MAX_JOBS`)
- GPU memory is the bottleneck for parallel jobs
- AlphaFold3 with MSA is CPU-bound during MSA search, then GPU-bound
- RFdiffusion is always GPU-bound

### Error Handling

```bash
# Collect all results including failures
python scripts/job_manager.py list --json > outputs/job_status.json

# Inspect failures
python scripts/summarize_outputs.py --results-dir outputs/af3/ --json | \
  jq '.failures[] | {name, error}'
```

## Tips

- Always use `scripts/job_manager.py list` instead of checking individual job files
- Set `--run-data-pipeline false` for initial screening, `true` for final validation
- Use `PROTEIN_DESIGN_MAX_JOBS` env var to control parallelism
- Failed jobs don't affect other jobs in the batch
- Job outputs are preserved even if the session closes
- Use scheduled monitoring for overnight runs

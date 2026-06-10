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

Individual `submit_job` + `query_job` polling is fine for 1-3 designs. For large-scale screening (10-100+ designs), use batch submission patterns to minimize MCP overhead and avoid blocking the session.

## Pattern 1: Submit All, Poll Batch

### Step 1: Submit all jobs (get task_ids)

```python
# Submit all AlphaFold3 jobs at once
task_ids = []
for design_json in glob("outputs/seqs/*_af3_input.json"):
    result = submit_job(
        tool="alphafold3",
        params={
            "json_path": design_json,
            "output_dir": f"outputs/af3/{os.path.basename(design_json)}",
            "run_data_pipeline": False,  # Fast screening
        }
    )
    task_ids.append(result["task_id"])

print(f"Submitted {len(task_ids)} jobs")
```

### Step 2: Poll all at once with `check_batch_progress`

```python
# Check all jobs in one call
batch = check_batch_progress(task_ids=task_ids)

completed = sum(1 for r in batch["batch_results"] if r["status"] == "completed")
failed = sum(1 for r in batch["batch_results"] if r["status"] == "failed")
running = sum(1 for r in batch["batch_results"] if r["status"] == "running")

print(f"Completed: {completed}, Failed: {failed}, Running: {running}")
```

### Step 3: Repeat until all done

```python
import time

while True:
    batch = check_batch_progress(task_ids=task_ids)
    statuses = [r["status"] for r in batch["batch_results"]]
    
    if all(s in ("completed", "failed") for s in statuses):
        break
    
    time.sleep(60)  # Poll every minute
```

## Pattern 2: Scheduled Batch Monitoring (0.6.0+)

For very large batches (>20 designs), use scheduling instead of blocking poll:

### Submit all jobs

```python
task_ids = []
for i, design in enumerate(designs):
    result = submit_job(tool="alphafold3", params={...})
    task_ids.append(result["task_id"])
```

### Set up scheduled monitoring

```
scheduling (CronCreate or equivalent)(
    cron="*/10 * * * *",
    prompt="Check AlphaFold3 batch progress for task_ids [X, Y, Z, ...]. Report: total completed, count with pLDDT>80 and ipTM>0.75, list any failures."
)
```

### When all complete, stop the schedule

```
stop the scheduled check  # Stop the timer
```

**Benefits:**
- Session is freed for other work
- Progress reports arrive automatically
- No manual polling needed

## Pattern 3: Staged Submission (Screen → Validate)

For maximum efficiency with 100+ designs:

### Stage 1: Fast screen with ESMFold (all designs)

```python
# ESMFold: ~10 seconds per design
screen_task_ids = []
for fasta in glob("outputs/seqs/*.fa"):
    result = submit_job(
        tool="esmfold",  # If available
        params={"fasta_path": fasta, "output_dir": f"outputs/esm/{basename}"}
    )
    screen_task_ids.append(result["task_id"])
```

### Stage 2: Filter by ESMFold pLDDT

```python
# Wait for all ESMFold jobs
# Select top 20 by pLDDT
top_designs = sorted(results, key=lambda x: x["plddt"], reverse=True)[:20]
```

### Stage 3: Validate top 20 with AlphaFold3 (full MSA)

```python
af3_task_ids = []
for design in top_designs:
    result = submit_job(
        tool="alphafold3",
        params={
            "json_path": design["json"],
            "output_dir": f"outputs/af3/{design['name']}",
            "run_data_pipeline": True,  # Full accuracy
        }
    )
    af3_task_ids.append(result["task_id"])
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

## Pattern 5: Job Cancellation

If you need to stop a batch:

```python
# Cancel all jobs in a batch
for task_id in task_ids:
    cancel_job(task_id=task_id)
```

Or cancel specific failed/stuck jobs:

```python
batch = check_batch_progress(task_ids=task_ids)
for result in batch["batch_results"]:
    if result["status"] == "failed" or result["progress"] == 0:
        cancel_job(task_id=result["task_id"])
```

## Best Practices

| Batch Size | Strategy |
|------------|----------|
| 1-5 | Individual submit + poll |
| 5-20 | Batch submit + `check_batch_progress` |
| 20-100 | Scheduled monitoring (CronCreate) |
| 100+ | Two-stage: ESMFold screen → AF3 validate top N |

### Resource Management

- Default max concurrent jobs: 4 (`PROTEIN_DESIGN_MAX_JOBS`)
- GPU memory is the bottleneck for parallel jobs
- AlphaFold3 with MSA is CPU-bound during MSA search, then GPU-bound
- RFdiffusion is always GPU-bound

### Error Handling

```python
# Collect all results including failures
batch = check_batch_progress(task_ids=task_ids)

successes = []
failures = []
for result in batch["batch_results"]:
    if result["status"] == "completed":
        successes.append(result)
    else:
        failures.append(result)

print(f"Successes: {len(successes)}, Failures: {len(failures)}")
if failures:
    print("Failed tasks:")
    for f in failures:
        print(f"  {f['task_id']}: {f.get('error', 'Unknown error')}")
```

## Tips

- Always use `check_batch_progress` instead of individual `query_job` calls
- Set `run_data_pipeline=false` for initial screening, `true` for final validation
- Use `PROTEIN_DESIGN_MAX_JOBS` env var to control parallelism
- Failed jobs don't affect other jobs in the batch
- Job outputs are preserved even if the session closes
- Use scheduled monitoring for overnight runs

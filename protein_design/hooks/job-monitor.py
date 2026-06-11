#!/usr/bin/env python3
"""PostToolUse hook: provide direct monitoring commands for job status.

When users check job status, this hook provides direct shell commands
for monitoring background jobs.

Priority:
1. job_manager.py (standalone script)
2. Direct log/process monitoring (fallback)
"""

import json
import sys
from pathlib import Path


def _find_job_manager() -> str:
    """Find job_manager.py script."""
    script = Path(__file__).parent.parent.parent / "scripts" / "job_manager.py"
    if script.exists():
        return str(script)
    return ""


def main() -> int:
    """Main entry point."""
    try:
        text = sys.stdin.read()
        data = json.loads(text) if text.strip() else {}
    except Exception:
        return 0

    # Only intercept query_job calls
    if data.get("tool") != "query_job":
        return 0

    job_manager = _find_job_manager()

    output_parts = ["""[Job Monitor] query_job detected
"""]

    # Option 1: Use standalone job manager (preferred)
    if job_manager:
        output_parts.append(f"""
## ✅ Option 1: Standalone Job Manager (Recommended)

The `job_manager.py` script replaces query_job/submit_job/cancel_job:

```bash
# Submit a background job
JOB_ID=$(python {job_manager} submit --name rfdiff -- \\
  python scripts/run_rfdiffusion.py --contig "150-150" --num-designs 50)

# Check status
python {job_manager} status $JOB_ID

# Tail log
python {job_manager} tail $JOB_ID --lines 50

# List all jobs
python {job_manager} list

# Cancel
python {job_manager} cancel $JOB_ID

# Wait for completion
python {job_manager} wait $JOB_ID --timeout 3600
```
""")

    # Option 2: Direct monitoring (fallback)
    output_parts.append("""
## Option 2: Direct Log Monitoring

```bash
# Tail the latest log
tail -f logs/rfdiffusion_*.log

# Or grep for completion
grep -E "(Finished|Error|Complete|step [0-9]+/[0-9]+)" logs/*.log
```

## Option 3: Process Monitoring

```bash
# List running protein design processes
ps aux | grep -E "(rfdiffusion|protein_mpnn|alphafold|boltz|chai|omegafold)"

# Check GPU usage
watch -n 5 nvidia-smi

# Check specific process
pgrep -f "run_inference.py" && echo "RFdiffusion running" || echo "Not running"
```

## Option 4: File-Based Progress

```bash
# Count completed designs
ls outputs/design_*.pdb 2>/dev/null | wc -l

# Watch for new files
watch -n 10 'ls outputs/*.pdb 2>/dev/null | wc -l'

# Check latest modification
ls -lt outputs/*.pdb | head -5
```

## Option 5: Python Progress Tracker

```python
import glob
import time
from pathlib import Path

def monitor_progress(output_dir, expected_count):
    while True:
        current = len(list(Path(output_dir).glob("*.pdb")))
        pct = current / expected_count * 100
        print(f"Progress: {current}/{expected_count} ({pct:.0f}%)")
        if current >= expected_count:
            print("Complete!")
            break
        time.sleep(30)

monitor_progress("outputs/", expected_count=50)
```
""")

    # Option 6: Screen/Tmux for long jobs
    output_parts.append("""
## Option 6: Screen/Tmux for Long Jobs

For long-running jobs, use `screen` or `tmux` to keep sessions alive:
```bash
screen -S rfdiffusion
conda run -n SE3nv python scripts/run_inference.py ...
# Ctrl+A, D to detach
screen -r rfdiffusion  # to reattach
```
""")

    print("\n".join(output_parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())

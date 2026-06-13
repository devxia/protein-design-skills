#!/usr/bin/env python3
"""PreToolUse hook: auto-batch protein design jobs for efficiency.

When multiple designs need validation, this hook suggests batching strategies
and provides ready-to-use batch submission patterns.
"""
import traceback
import json
from typing import Any
import sys


def _detect_batch_needs(context: str) -> dict[str, Any]:
    """Detect if user needs batch processing."""
    text_lower = context.lower()

    batch_signals = [
        "batch", "many designs", "multiple", "library", "screen",
        "100", "200", "500", "1000", "dozens", "hundreds",
        "all designs", "every design", "each design",
    ]

    has_batch = any(s in text_lower for s in batch_signals)

    # Detect validation tool preference
    tool = "alphafold3"  # default
    if "omega" in text_lower or "omegafold" in text_lower:
        tool = "omegafold"
    elif "esm" in text_lower and "fold" in text_lower:
        tool = "esmfold"
    elif "boltz" in text_lower:
        tool = "boltz"
    elif "chai" in text_lower:
        tool = "chai"
    elif "protenix" in text_lower:
        tool = "protenix"

    # Estimate count
    count = 10  # default
    import re
    m = re.search(r'(\d+)\s*designs?', text_lower)
    if m:
        count = int(m.group(1))

    return {
        "has_batch": has_batch,
        "tool": tool,
        "count": count,
    }


def _build_batch_strategy(info: dict[str, Any]) -> str:
    """Build batch submission strategy."""
    tool = info["tool"]
    count = info["count"]

    if not info["has_batch"] and count < 10:
        return ""

    output = f"""[Batch Orchestrator] Detected {count} designs. Here are efficient batch strategies:

## Strategy 1: Two-Tier Validation (Recommended for {count}+ designs)

```
Tier 1 — Fast Pre-screen (all {count} designs):
  Tool: ESMFold or OmegaFold (no DB, ~seconds/seq)
  Action: submit_job x {count}

Tier 2 — Accurate Validation (top 10-20%):
  Tool: AlphaFold3 / Boltz-1 / Chai-1 / Protenix
  Action: submit_job x {max(5, count // 10)}
```

**Why**: Screen {count} in ~{count * 2 // 60} minutes with ESMFold, then validate top {max(5, count // 10)} accurately.

## Strategy 2: Parallel Submission

```python
# Submit all jobs in parallel
task_ids = []
for i in range({count}):
    result = submit_job(tool="{tool}", params=design_params[i])
    task_ids.append(result["task_id"])

# Check batch progress
check_batch_progress(task_ids=task_ids)
```

## Strategy 3: Cron-Based Monitoring (for long jobs)

```
# Submit all jobs
# Set up cron to check progress every 10 minutes
# Auto-report when all complete
```

## Estimated Timelines

| Stage | Tool | {count} Designs | Time |
|-------|------|----------------|------|
| Pre-screen | ESMFold | {count} | ~{count * 2} sec |
| Pre-screen | OmegaFold | {count} | ~{count * 10} sec |
| Accurate | AlphaFold3 | {count} | ~{count * 5} min |
| Accurate | Boltz-1 | {count} | ~{count * 5} min |
| Accurate | Protenix (5 samples) | {count} | ~{count * 10} min |

## Resource Estimates

| Tool | GPU Memory | Disk per Design | Total Disk |
|------|-----------|----------------|------------|
| ESMFold | 8GB | 1MB | {count}MB |
| OmegaFold | 12GB | 1MB | {count}MB |
| AlphaFold3 | 40GB | 500MB | {count * 500}MB |
| Boltz-1 | 40GB | 500MB | {count * 500}MB |
| Protenix | 40GB | 500MB | {count * 500}MB |

## Tips

- Use **check_batch_progress** instead of individual query_job calls
- For >50 designs, always use two-tier (fast → accurate)
- Set PROTEIN_DESIGN_MAX_JOBS to control parallelism
- Use background-notify hook for completion alerts
"""

    return output


def main() -> int:
    """Main entry point."""
    try:
        text = sys.stdin.read()
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    if not text.strip():
        return 0

    info = _detect_batch_needs(text)
    if not info["has_batch"] and info["count"] < 10:
        return 0

    strategy = _build_batch_strategy(info)
    if strategy:
        print(strategy)
    return 0


if __name__ == "__main__":
    sys.exit(main())

---
name: filtering-ranking
description: Filter and rank protein designs by AlphaFold3 metrics (Stage 4)
---

# Stage 4: Filtering & Ranking

## When to Trigger

- User says "filter designs", "rank by quality", "find the best designs"
- After AlphaFold3 validation: "show me the top 10"
- User wants to apply quality thresholds: "only keep pLDDT > 80"

## Filtering Overview

The filtering stage evaluates AlphaFold3 confidence metrics and ranks designs by a composite quality score. Designs failing thresholds are excluded; survivors are sorted by quality.

## MCP Tool

```json
{
  "tool": "run_filtering",
  "params": {
    "designs": [
      {
        "name": "design_0",
        "metrics": {
          "mean_plddt": 85.2,
          "iptm": 0.82,
          "ptm": 0.91,
          "has_clash": false
        }
      },
      {
        "name": "design_1",
        "metrics": {
          "mean_plddt": 68.5,
          "iptm": 0.45,
          "ptm": 0.62,
          "has_clash": true
        }
      }
    ],
    "criteria": {
      "min_plddt": 70,
      "min_iptm": 0.6,
      "min_ptm": 0.5,
      "allow_clashes": false
    }
  }
}
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `designs` | ✅ | — | List of design dicts, each with `name` and `metrics` |
| `criteria.min_plddt` | ❌ | 70 | Minimum mean pLDDT (0–100) |
| `criteria.min_iptm` | ❌ | 0.6 | Minimum ipTM (0–1) |
| `criteria.min_ptm` | ❌ | 0.5 | Minimum pTM (0–1) |
| `criteria.allow_clashes` | ❌ | false | Allow designs with atomic clashes |

## Design Dict Format

```json
{
  "name": "design_0",
  "metrics": {
    "mean_plddt": 85.2,
    "iptm": 0.82,
    "ptm": 0.91,
    "has_clash": false,
    "ranking_score": 0.85
  },
  "paths": {
    "pdb": "designs/design_0.pdb",
    "fasta": "seqs/design_0.fa",
    "cif": "af3/design_0.cif"
  }
}
```

## Composite Quality Score

The ranking uses a weighted combination:

```
score = 0.40 × (pLDDT / 100) + 0.35 × ipTM + 0.25 × pTM
```

Higher score = better design. Designs are sorted descending by this score.

## Output Format

```json
{
  "status": "completed",
  "filtered_designs": [
    {
      "name": "design_0",
      "metrics": {...},
      "quality_score": 0.8734,
      "rank": 1,
      "filter_status": "pass",
      "filter_reasons": []
    }
  ],
  "failed_designs": [
    {
      "name": "design_1",
      "metrics": {...},
      "filter_status": "fail",
      "filter_reasons": ["pLDDT 68.5 < 70", "ipTM 0.45 < 0.6", "has_clash=true"]
    }
  ],
  "summary": {
    "total": 50,
    "passed": 23,
    "failed": 27,
    "criteria": {...}
  }
}
```

## Quality Thresholds Reference

| Application | min_plddt | min_iptm | min_ptm | allow_clashes |
|------------|-----------|----------|---------|---------------|
| Strict (publication) | 80 | 0.8 | 0.7 | false |
| Standard (default) | 70 | 0.6 | 0.5 | false |
| Lenient (exploration) | 60 | 0.5 | 0.4 | false |
| Binder design | 75 | 0.75 | 0.6 | false |

## Presentation to User

Present results as a Markdown table:

```markdown
| Rank | Design | pLDDT | ipTM | pTM | Quality Score | Status |
|------|--------|-------|------|-----|--------------|--------|
| 1 | design_0 | 85.2 | 0.82 | 0.91 | 0.873 | ✅ Pass |
| 2 | design_3 | 81.5 | 0.78 | 0.88 | 0.834 | ✅ Pass |
| — | design_1 | 68.5 | 0.45 | 0.62 | — | ❌ Fail (pLDDT, ipTM, clash) |
```

## Workflow

```
Input: AlphaFold3 results from Stage 3
     ↓
Collect metrics from each design's confidence JSON
     ↓
Build designs list
     ↓
submit_job("filtering", {designs, criteria})
     ↓
Return ranked list → User review / iteration
```

## Iteration Support

If no designs pass filtering:
1. Suggest relaxing criteria (e.g., pLDDT > 60)
2. Suggest generating more backbones (Stage 1) with different contigs
3. Suggest adjusting ProteinMPNN temperature for more diversity

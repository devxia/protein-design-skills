---
name: filtering-ranking
description: Filter and rank protein designs by AlphaFold3 metrics (Stage 4)
---

# Stage 4: Filtering & Ranking

> **Quick Entry**: Stage 4 | pLDDT/ipTM/pTM filtering | ranking | clash detection
>
> **Upstream**: `structure-validation` (AlphaFold3/Boltz-1/Chai-1/OmegaFold/ESMFold/Protenix/OpenFold3) | **Downstream**: (none — final stage)

**This skill is the FINAL stage of the pipeline.**

**Quick entry:** If you have validation results (AlphaFold3, Boltz-1, etc.) and need to find the best designs, you are in the right place.

**Typical flow:** `structure-generation` (Stage 1) → `sequence-design` (Stage 2) → `structure-validation` (Stage 3) → **THIS SKILL** (Stage 4)

## When to Use This Skill

- You have validation results and want to rank designs by quality
- You need to apply thresholds (pLDDT, ipTM, pTM) to filter designs
- You want to find the top N candidates for experimental validation
- You need to compare designs across multiple validators

**Cross-validator filtering?** Read `cross-validation` skill for multi-validator consensus ranking.

## Filtering Overview

The filtering stage evaluates validation confidence metrics and ranks designs by a composite quality score. Designs failing thresholds are excluded; survivors are sorted by quality.

## Standalone Script

`run_filtering.py` scans a validation output directory, parses all `confidence.json` files, applies thresholds, and ranks passing designs by a composite score.

```bash
python scripts/run_filtering.py \
  --results-dir outputs/validation/ \
  --min-plddt 70 \
  --min-iptm 0.6 \
  --min-ptm 0.7 \
  --max-pae 10.0 \
  --top-n 20
```

## Parameters

| Parameter | CLI Flag | Required | Default | Description |
|-----------|----------|----------|---------|-------------|
| `results_dir` | `--results-dir` / `-d` | ✅ | — | Directory containing validation outputs |
| `min_plddt` | `--min-plddt` | ❌ | 70 | Minimum mean pLDDT (0–100) |
| `min_iptm` | `--min-iptm` | ❌ | 0.6 | Minimum ipTM (0–1) |
| `min_ptm` | `--min-ptm` | ❌ | 0.7 | Minimum pTM (0–1) |
| `max_pae` | `--max-pae` | ❌ | 10.0 | Maximum PAE threshold |
| `top_n` | `--top-n` | ❌ | all | Only show top N designs |
| `verbose` | `--verbose` / `-v` | ❌ | false | Verbose output with statistics |

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

| Application | min_plddt | min_iptm | min_ptm | max_pae |
|------------|-----------|----------|---------|---------|
| Strict (publication) | 80 | 0.8 | 0.7 | 10.0 |
| Standard (default) | 70 | 0.6 | 0.7 | 10.0 |
| Lenient (exploration) | 60 | 0.5 | 0.5 | 15.0 |
| Binder design | 75 | 0.75 | 0.7 | 10.0 |

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
python scripts/run_filtering.py --results-dir outputs/validation/ [thresholds]
     ↓
Ranked list printed / saved → User review / iteration
```

## Iteration Support

If no designs pass filtering:
1. Suggest relaxing criteria (e.g., pLDDT > 60)
2. Suggest generating more backbones (Stage 1) with different contigs
3. Suggest adjusting ProteinMPNN temperature for more diversity

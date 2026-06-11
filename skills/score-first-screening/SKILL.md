---
name: score-first-screening
description: ProteinMPNN score-only pre-screening pipeline — score existing sequences before expensive validation
---

# Score-First Screening Pipeline: Pre-Filter with ProteinMPNN

## When to Trigger

- User says "score sequences", "evaluate sequences", "rank by confidence"
- User has existing sequences and wants to know which are worth validating
- User wants to avoid expensive validation on poor designs
- User needs to evaluate sequence-backbone compatibility
- User wants to use ProteinMPNN as a discriminator

## Overview

**Score-First Screening** uses ProteinMPNN's `score_only` mode to evaluate how well existing sequences match given backbone structures BEFORE running expensive structure predictors (AlphaFold3, Boltz-1, etc.). This saves significant compute by filtering out incompatible sequence-backbone pairs early.

**Workflow:**
```
Backbone + Candidate Sequences
    ↓
ProteinMPNN score_only (fast, ~seconds per sequence)
    ↓
Filter by score threshold
    ↓
Only top-scoring sequences → Validation (AlphaFold3/Boltz-1)
```

## ProteinMPNN Score-Only Mode

ProteinMPNN can score sequence-backbone pairs without generating new sequences:

```bash
conda run -n proteinmpnn python protein_mpnn_run.py \
    --pdb_path design.pdb \
    --path_to_fasta candidates.fasta \
    --out_folder outputs/scores/ \
    --score_only 1
```

**Output metrics:**
- `score`: Average negative log probability of designed residues (lower = better)
- `global_score`: Average over ALL residues including fixed (lower = better)
- `seq_recovery`: Sequence identity to input (if applicable)

### Interpreting Scores

| Score Range | Interpretation | Action |
|-------------|---------------|--------|
| < 0.5 | Excellent | Proceed to validation |
| 0.5 - 1.0 | Good | Likely worth validating |
| 1.0 - 1.5 | Moderate | Consider with caution |
| 1.5 - 2.0 | Poor | Probably discard |
| > 2.0 | Very poor | Discard |

**Note:** Scores are relative to the model and dataset. Compare within the same run, not across different models.

## Score-First Pipeline

### Step 1: Generate Candidate Sequences

Generate diverse sequences for each backbone using ProteinMPNN:

```bash
# Standard sequence design
conda run -n proteinmpnn python protein_mpnn_run.py \
    --pdb_path 'designs/*.pdb' \
    --out_folder outputs/candidates/ \
    --num_seq_per_target 32 \
    --sampling_temp '0.1 0.2 0.3'
```

### Step 2: Score All Candidates

```bash
# Score each candidate against its backbone
for pdb in designs/*.pdb; do
    base=$(basename $pdb .pdb)
    conda run -n proteinmpnn python protein_mpnn_run.py \
        --pdb_path $pdb \
        --path_to_fasta outputs/candidates/${base}.fa \
        --out_folder outputs/scores/${base}/ \
        --score_only 1
done
```

### Step 3: Parse Scores and Rank

```python
import json
from pathlib import Path

def parse_proteinmpnn_scores(score_dir):
    """Parse score-only outputs and rank sequences."""
    results = []
    for score_file in Path(score_dir).rglob('*.jsonl'):
        with open(score_file) as f:
            for line in f:
                data = json.loads(line)
                results.append({
                    'name': data.get('name', ''),
                    'score': data.get('score', 999),
                    'global_score': data.get('global_score', 999),
                    'seq': data.get('seq', ''),
                })
    
    # Sort by score (lower is better)
    results.sort(key=lambda x: x['score'])
    return results

# Keep top 20% for validation
def filter_top_percent(results, percent=20):
    cutoff = int(len(results) * percent / 100)
    return results[:max(cutoff, 10)]

# Example usage
all_scores = parse_proteinmpnn_scores('outputs/scores/')
top_candidates = filter_top_percent(all_scores, percent=20)
print(f"Selected {len(top_candidates)}/{len(all_scores)} candidates for validation")
```

### Step 4: Validate Top Candidates Only

```bash
# Write top candidates to FASTA
python -c "
import json
with open('outputs/top_candidates.json') as f:
    candidates = json.load(f)
with open('outputs/to_validate.fa', 'w') as f:
    for c in candidates:
        f.write(f'>{c[\"name\"]}|score={c[\"score\"]:.3f}\n{c[\"seq\"]}\n')
"

# Run validation only on top candidates
python scripts/run_boltz.py --input outputs/to_validate.fa --out-dir outputs/validation/
```

## Advanced: Conditional Probabilities

ProteinMPNN can output per-position probabilities (useful for identifying problematic regions):

```bash
# Get conditional probabilities p(s_i | backbone)
conda run -n proteinmpnn python protein_mpnn_run.py \
    --pdb_path design.pdb \
    --out_folder outputs/probs/ \
    --conditional_probs_only_backbone 1 \
    --save_probs 1
```

**Use case:** Identify positions with low confidence (high entropy) — these may be problematic in validation.

## Advanced: Unconditional Probabilities (PSSM-like)

Generate position-specific scoring matrix from backbone:

```bash
# Get unconditional probabilities p(s_i | backbone)
conda run -n proteinmpnn python protein_mpnn_run.py \
    --pdb_path design.pdb \
    --out_folder outputs/pssm/ \
    --unconditional_probs_only 1 \
    --save_probs 1
```

**Use case:** Compare with designed sequences to find deviations from the "ideal" distribution.

## Score-First vs Direct Validation Cost

| Step | Direct Validation | Score-First |
|------|------------------|-------------|
| Sequences per backbone | 32 | 32 |
| Validation tool | AlphaFold3 (all 32) | ProteinMPNN score (all 32) |
| Time per sequence | ~5 min (AF3) | ~0.5 sec (MPNN score) |
| Total validation time | 32 × 5 min = 160 min | 32 × 0.5 sec + 6 × 5 min = 30.3 min |
| **Savings** | — | **~81% faster** |

Assuming we keep top 20% (6 sequences) for full validation.

## Integration with Other Pipelines

### Score-First + Standard Pipeline
```
RFdiffusion → ProteinMPNN (design 32 seqs) → ProteinMPNN score_only → Top 6 → AlphaFold3
```

### Score-First + Cross-Validation
```
RFdiffusion → ProteinMPNN (design 32 seqs) → ProteinMPNN score_only → Top 10 → Boltz-1 + Chai-1
```

### Score-First + Fast Screening
```
RFdiffusion → ProteinMPNN (design 64 seqs) → ProteinMPNN score_only → Top 20 → ESMFold → Top 5 → AlphaFold3
```

## Tips

1. **Score is relative**: Compare scores within the same backbone, not across different backbones
2. **Use global_score for overall quality**: It includes fixed residues
3. **seq_recovery is not always good**: High recovery = similar to native, but you may want diversity
4. **Combine with sequence diversity**: Keep a mix of low-score AND diverse sequences
5. **score_only works on any FASTA**: You can score sequences from EvoDiff, ESM-IF1, etc.
6. **Batch scoring**: Use `jsonl_path` mode for batch scoring multiple backbones

## References

- [ProteinMPNN GitHub](https://github.com/dauparas/ProteinMPNN)
- See `sequence-design` skill for ProteinMPNN design mode
- See `quickstart-guide` skill for getting started

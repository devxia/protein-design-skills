---
name: cross-validation
description: Multi-validator cross-validation pipeline — use Boltz-1, Chai-1, OmegaFold, and ESMFold together for robust design ranking
---

# Cross-Validation Pipeline: Multi-Validator Design Ranking

## When to Trigger

- User says "cross-validate", "ensemble validation", "multiple predictors"
- User wants the most robust design ranking possible
- User needs to avoid AlphaFold3 database requirements
- User wants commercial-friendly validation (no AF3 restrictions)
- User needs quick + accurate hybrid validation
- User says "validate with multiple tools" or "compare predictions"

## Overview

Instead of relying on a single structure predictor (e.g., AlphaFold3 alone), the **Cross-Validation Pipeline** runs multiple validators in parallel or sequence and aggregates their confidence metrics for more robust design ranking. This approach:

- **Reduces false positives**: A design that scores well on only one predictor may be an artifact
- **Increases confidence**: Designs scoring well across multiple predictors are more likely to be correct
- **Provides licensing flexibility**: Mix open-source and commercial-friendly tools
- **Enables database-free validation**: Use OmegaFold/ESMFold for screening, Boltz-1/Chai-1 for refinement

## Available Validators

| Validator | Speed | License | Complexes | Databases | Best For |
|-----------|-------|---------|-----------|-----------|----------|
| **AlphaFold3** | Slow | Non-commercial | Yes | 2.6TB | Final validation, highest accuracy |
| **Boltz-1** | Medium | MIT | Yes | None* | Commercial projects, complexes |
| **Chai-1** | Medium | Apache 2.0 | Yes | None* | Constraints, single-sequence |
| **OmegaFold** | Fast | Open | Monomers only | None | Quick screening, no DB |
| **ESMFold** | **Fastest** | MIT | Monomers only | None | Ultra-fast library screening |
| **Protenix** | Medium | Apache 2.0 | Yes | None* | Training-capable, inference scaling |
| **OpenFold3** | Medium | Apache 2.0 | Yes | pip install | AF3 parity, RNA support |

*Boltz-1, Chai-1, Protenix use built-in MSA servers by default

## Cross-Validation Strategies

### Strategy 1: Tiered Validation (Recommended)

Use fast tools for screening, slow tools for final candidates:

```
Step 1: ESMFold (screen 1000+ designs) → Filter to top 100
Step 2: OmegaFold (validate top 100) → Filter to top 20
Step 3: Boltz-1 + Chai-1 (cross-validate top 20) → Filter to top 10
Step 4: AlphaFold3 (final validation of top 10) → Final ranking
```

**Benefits:**
- ESMFold: ~2s/sequence, no DB needed
- OmegaFold: ~30s/sequence, no DB needed
- Boltz-1 + Chai-1: Independent predictions, agreement = confidence
- AlphaFold3: Gold standard for final candidates

### Strategy 2: Parallel Ensemble

Run all validators in parallel on the same designs, then aggregate:

```bash
# Design set: outputs/sequences/seqs.fa

# Run all validators in parallel (background jobs)
nohup python scripts/run_boltz.py --input outputs/seqs.fa --out-dir outputs/boltz/ > logs/boltz.log 2>&1 &
nohup python scripts/run_chai1.py --input outputs/seqs.fa --output-dir outputs/chai1/ > logs/chai1.log 2>&1 &
nohup python scripts/run_omegafold.py --input outputs/seqs.fa --output-dir outputs/omegafold/ > logs/omegafold.log 2>&1 &
nohup python scripts/run_esmfold.py --input outputs/seqs.fa --output-dir outputs/esmfold/ > logs/esmfold.log 2>&1 &

# Wait for all to complete
wait
```

**Aggregation script:**
```python
import json
from pathlib import Path

def aggregate_scores(design_id, validators):
    """Aggregate confidence scores from multiple validators."""
    scores = {}
    for validator, result_dir in validators.items():
        result_file = Path(result_dir) / design_id / "confidence.json"
        if result_file.exists():
            with open(result_file) as f:
                data = json.load(f)
            scores[validator] = {
                "plddt": data.get("plddt", 0),
                "iptm": data.get("iptm", 0),
                "ptm": data.get("ptm", 0),
            }
    
    # Compute ensemble metrics
    plddts = [s["plddt"] for s in scores.values()]
    iptms = [s.get("iptm", 0) for s in scores.values() if s.get("iptm")]
    
    return {
        "mean_plddt": sum(plddts) / len(plddts) if plddts else 0,
        "min_plddt": min(plddts) if plddts else 0,
        "std_plddt": (sum((x - sum(plddts)/len(plddts))**2 for x in plddts) / len(plddts))**0.5 if plddts else 0,
        "mean_iptm": sum(iptms) / len(iptms) if iptms else 0,
        "agreement": len([p for p in plddts if p > 70]) / len(plddts) if plddts else 0,
        "per_validator": scores,
    }
```

### Strategy 3: Consensus Filtering

Only keep designs that pass thresholds on ALL validators used:

| Criterion | ESMFold | OmegaFold | Boltz-1 | Chai-1 | AlphaFold3 |
|-----------|---------|-----------|---------|--------|------------|
| min pLDDT | 70 | 75 | 75 | 75 | 80 |
| min ipTM | — | — | 0.70 | 0.70 | 0.80 |
| min pTM | — | — | 0.60 | 0.60 | 0.70 |

### Strategy 4: Weighted Ranking

Assign weights based on validator reliability and compute weighted score:

```python
VALIDATOR_WEIGHTS = {
    "alphafold3": 0.30,
    "boltz": 0.20,
    "chai1": 0.20,
    "omegafold": 0.15,
    "esmfold": 0.15,
}

def weighted_score(design_scores, weights=VALIDATOR_WEIGHTS):
    total = 0
    weight_sum = 0
    for validator, score in design_scores.items():
        if validator in weights:
            total += score * weights[validator]
            weight_sum += weights[validator]
    return total / weight_sum if weight_sum > 0 else 0
```

## Pipeline Configurations

### Full Cross-Validation Pipeline (No DB Required)

```bash
# Stage 1: Generate backbones
python scripts/run_rfdiffusion.py \
    --contig "150-150" --num-designs 100 \
    --output-prefix outputs/design --verbose

# Stage 2: Design sequences
python scripts/run_proteinmpnn.py \
    --pdb-path "outputs/design_*.pdb" \
    --out-folder outputs/seqs/ --num-seq 8 --verbose

# Stage 3a: Ultra-fast screen with ESMFold
python scripts/run_esmfold.py \
    --input outputs/seqs/seqs.fa \
    --output-dir outputs/esmfold/ --verbose

# Stage 3b: Medium validation with Boltz-1
python scripts/run_boltz.py \
    --input outputs/seqs/seqs.fa \
    --out-dir outputs/boltz/ --verbose

# Stage 3c: Medium validation with Chai-1
python scripts/run_chai1.py \
    --input outputs/seqs/seqs.fa \
    --output-dir outputs/chai1/ --verbose

# Stage 4: Cross-validation filtering
python scripts/run_filtering.py \
    --output-dir outputs/ \
    --validators esmfold boltz chai1 \
    --min-plddt 75 --min-agreement 0.7 \
    --top-n 20 --verbose
```

### Commercial-Friendly Cross-Validation

For projects requiring permissive licenses (no AlphaFold3):

```bash
# Validators: Boltz-1 (MIT) + Chai-1 (Apache 2.0) + OmegaFold (Open)
# No AlphaFold3, no database downloads needed

python scripts/run_boltz.py --input seqs.fa --out-dir outputs/boltz/
python scripts/run_chai1.py --input seqs.fa --output-dir outputs/chai1/
python scripts/run_omegafold.py --input seqs.fa --output-dir outputs/omegafold/

# Consensus: design must have pLDDT > 75 on ALL THREE
```

### Binder Design Cross-Validation

For binder designs (requires interface metrics like ipTM):

```bash
# Stage 1: RFdiffusion binder design
# Stage 2: ProteinMPNN
# Stage 3: Validate complexes with Boltz-1 + Chai-1 + AlphaFold3

python scripts/run_boltz.py --input seqs.fa --out-dir outputs/boltz/
python scripts/run_chai1.py --input seqs.fa --output-dir outputs/chai1/

# Cross-validate interface metrics
python -c "
import json, glob
for design in glob.glob('outputs/*/confidence.json'):
    with open(design) as f:
        data = json.load(f)
    print(f'{design}: pLDDT={data.get(\"plddt\",0):.1f}, ipTM={data.get(\"iptm\",0):.3f}')
"
```

## Agreement Metrics

### Inter-Predictor Agreement

High agreement between independent predictors strongly indicates a reliable prediction:

| Agreement Level | Interpretation | Action |
|-----------------|---------------|--------|
| All validators agree (pLDDT > 75) | High confidence | Proceed to experimental validation |
| 3/4 agree | Moderate confidence | Visual inspection recommended |
| 2/4 agree | Low confidence | Regenerate or relax criteria |
| <2 agree | Unreliable | Discard or redesign |

### pLDDT Standard Deviation

Low std across validators = high consensus:
- std < 5: Excellent consensus
- std 5-10: Good consensus
- std > 10: Poor consensus, investigate

## Comparison with Single-Validator Pipelines

| Aspect | Single-Validator | Cross-Validation |
|--------|-----------------|------------------|
| Accuracy | Moderate | Higher |
| False positive rate | Higher | Lower |
| Compute cost | Lower | Higher (2-4x) |
| Time | Faster | Slower |
| Confidence | Lower | Higher |
| Best for | Quick screening | High-value targets |
| Database requirements | Depends on validator | Can avoid AF3 DB |
| License flexibility | Fixed | Flexible |

## Tips

1. **Start with fast validators**: ESMFold/OmegaFold for initial screening
2. **Use 2-3 validators minimum**: Single validator is not enough for robust ranking
3. **Weight by reliability**: AlphaFold3 > Boltz-1 ≈ Chai-1 > OmegaFold > ESMFold
4. **Agreement is more important than absolute score**: A design with pLDDT=80 on all validators is better than pLDDT=95 on one and 60 on another
5. **For binders**: ipTM agreement is critical — require ipTM > 0.7 on at least 2 validators
6. **Commercial projects**: Use Boltz-1 + Chai-1 + OpenFold3 (all permissive licenses)
7. **Budget-constrained**: ESMFold + OmegaFold is the cheapest cross-validation pair

## References

- See `boltz-validation` skill for Boltz-1 usage
- See `chai1-validation` skill for Chai-1 usage
- See `omegafold-validation` skill for OmegaFold usage
- See `esmfold-validation` skill for ESMFold usage
- See `openfold-validation` skill for OpenFold3 usage
- See `pipeline-selection` skill for choosing the right pipeline

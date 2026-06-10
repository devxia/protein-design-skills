---
name: quality-check
description: Interpret AlphaFold3 quality metrics and make design decisions
---

# Quality Check: Interpreting AlphaFold3 Results

## When to Trigger

- AlphaFold3 results are ready and user asks "are these good?"
- User wants to know if a design passes quality thresholds
- User needs help interpreting pLDDT, ipTM, pTM metrics
- User wants go/no-go decision on a design
- User asks "which design is best?"

## Quick Decision Matrix

Use this matrix for instant go/no-go decisions without additional tool calls:

### For Monomers (Single Chain)

| pLDDT | pTM | Decision | Action |
|-------|-----|----------|--------|
| >90 | >0.9 | ✅ Excellent | Proceed to experimental validation |
| 80-90 | 0.7-0.9 | ✅ Good | Proceed, but consider generating more variants |
| 70-80 | 0.5-0.7 | ⚠️ Acceptable | Marginal — try parameter tuning or more designs |
| <70 | <0.5 | ❌ Poor | Reject — regenerate backbones/sequences |
| has_clash=true | any | ❌ Reject | Severe atomic clashes — discard |

### For Binders (Multi-Chain Complex)

| ipTM | pLDDT | Decision | Action |
|------|-------|----------|--------|
| >0.9 | >85 | ✅ Excellent | Strong interface, proceed |
| 0.8-0.9 | 75-85 | ✅ Good | Good interface, proceed |
| 0.6-0.8 | 70-75 | ⚠️ Marginal | Weak interface — redesign or validate more seeds |
| <0.6 | <70 | ❌ Poor | Poor interface — reject and regenerate |
| has_clash=true | any | ❌ Reject | Interface clashes — discard |

### For Symmetric Oligomers

| pTM | pLDDT | Decision | Action |
|-----|-------|----------|--------|
| >0.9 | >85 | ✅ Excellent | Stable assembly |
| 0.7-0.9 | 75-85 | ✅ Good | Likely stable |
| 0.5-0.7 | 65-75 | ⚠️ Marginal | May dissociate — more validation needed |
| <0.5 | <65 | ❌ Poor | Unstable assembly — reject |

## Metric Interpretations

### pLDDT (Predicted Local Distance Difference Test)
- **Range**: 0-100
- **What it means**: Per-residue confidence in the predicted structure
- **Interpretation**:
  - >90: Very high confidence — structure is well-defined
  - 80-90: High confidence — reliable for most purposes
  - 70-80: Medium confidence — some flexible regions
  - 50-70: Low confidence — likely disordered regions
  - <50: Very low confidence — unreliable

### pTM (Predicted Template Modeling)
- **Range**: 0-1
- **What it means**: Overall topology confidence (entire structure)
- **Interpretation**:
  - >0.9: Correct fold very likely
  - 0.7-0.9: Correct fold likely
  - 0.5-0.7: Fold may be partially correct
  - <0.5: Fold may be incorrect

### ipTM (Interface Predicted Template Modeling)
- **Range**: 0-1
- **What it means**: Interface confidence between chains (critical for binders)
- **Interpretation**:
  - >0.9: Strong, specific interface
  - 0.8-0.9: Good interface
  - 0.6-0.8: Weak interface
  - <0.6: Poor interface — unlikely to bind

### has_clash
- **What it means**: True if severe atomic clashes detected
- **Action**: Always reject designs with clashes

### ranking_score
- **Range**: Approximately -100 to 1.5
- **What it means**: AlphaFold3's internal quality ranking
- **Higher is better** — use for ranking within a batch

## Per-Chain Analysis

For multi-chain complexes, check per-chain metrics:

```
Chain A (Target): pLDDT=85, pTM=0.92 → Good
Chain B (Binder):  pLDDT=72, pTM=0.65 → Marginal
```

**Decision**: If the target chain is good but the binder chain is marginal, the binder may be flexible or poorly folded. Consider:
1. Designing more sequences for the same backbone
2. Trying different backbones
3. Using partial diffusion to refine the binder region

## Composite Scoring

For ranking multiple designs, use a weighted score:

```python
def composite_score(design):
    plddt = design.get("mean_plddt", 0)
    iptm = design.get("iptm", 0) or design.get("ptm", 0)
    has_clash = design.get("has_clash", False)
    
    if has_clash:
        return -1000  # Penalize clashes heavily
    
    # Weighted score (adjust weights based on design type)
    # For binders:
    score = 0.4 * plddt + 0.6 * iptm * 100
    
    # For monomers:
    # score = 0.6 * plddt + 0.4 * ptm * 100
    
    return score
```

## Common Patterns

### Pattern 1: All metrics good except one
```
pLDDT=85, pTM=0.88, ipTM=0.55, has_clash=false
```
**Analysis**: Structure is well-folded but interface is weak.
**Action**: For binder design — reject. For monomer design — acceptable.

### Pattern 2: Low pLDDT but high pTM
```
pLDDT=65, pTM=0.85, has_clash=false
```
**Analysis**: Overall topology is correct but some regions are flexible/disordered.
**Action**: Check which regions have low pLDDT (usually termini or loops). If the functional region is well-defined, may be acceptable.

### Pattern 3: High pLDDT but low pTM
```
pLDDT=88, pTM=0.55, has_clash=false
```
**Analysis**: Local structure is confident but global topology may be wrong.
**Action**: Compare to expected topology. May indicate incorrect fold.

### Pattern 4: Clashes present
```
pLDDT=92, pTM=0.95, has_clash=true
```
**Analysis**: High confidence but physically impossible structure.
**Action**: Always reject. Clashes indicate the model has overlapping atoms.

## Action Recommendations

### If results are excellent (all green)
- Proceed to experimental validation
- Select top 3-5 designs for diversity
- Save sequences and structures for ordering

### If results are mixed (some good, some bad)
- Filter: keep designs with pLDDT > 75 and ipTM > 0.7
- For marginal designs: try more AlphaFold3 seeds
- Consider re-running ProteinMPNN with different temperatures

### If results are poor (mostly red)
- Go back to Stage 1: generate more backbones with different contigs
- Try partial diffusion to redesign problematic regions
- Check input PDB quality (run PDBFixer again)
- Consider using ESMFold for quick re-screening

### If interface is weak (low ipTM)
- Increase binder length (if too short)
- Add more hotspot residues
- Try different backbone orientations
- Use potentials to guide interface formation

## Tips

- **Always check has_clash first** — it's the fastest rejection criterion
- **ipTM is the most important metric for binders** — prioritize it over pLDDT
- **pTM is the most important metric for monomers** — prioritize it over pLDDT
- **Per-chain pLDDT** helps identify which chain is problematic
- **Ranking scores** are useful for comparing designs within a batch
- **Multiple seeds** increase confidence — if all seeds agree, the prediction is reliable

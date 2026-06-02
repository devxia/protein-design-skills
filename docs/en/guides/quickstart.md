---
title: Quick Start
source: README.md
---

# Quick Start

## Pipeline defaults

| Stage | Tool | Default Output | Parameter |
|-------|------|---------------|-----------|
| 1 — Backbone | RFdiffusion | **10** backbones | `num_designs` |
| 2 — Sequence | ProteinMPNN | **8** sequences per backbone | `num_seq_per_target` |
| 3 — Validation | AlphaFold3 | **5** predictions (1 seed × 5 samples) | `num_seeds` × `num_samples` |

**Full pipeline default**: 10 backbones × 8 sequences × 5 predictions = up to **400** AlphaFold3 results.

You can adjust these through natural language:

```
User: "Generate 50 backbones"
→ num_designs = 50

User: "Design 16 sequences for each backbone"
→ num_seq_per_target = 16

User: "Validate with 3 seeds"
→ num_seeds = 3
```

## Example 1: Design a 150-aa monomer

```
User: Generate a 150 amino acid protein backbone
→ Plugin auto-runs RFdiffusion with contig [150-150]
```

## Example 2: Design a binder for PD-L1

```
User: Design a binder targeting PD-L1
→ Stage 0: PDBFixer preprocesses target.pdb
→ Stage 1: RFdiffusion generates binder backbones
→ Stage 2: ProteinMPNN designs binder sequences
→ Stage 3: AlphaFold3 validates structures
→ Stage 4: Filter by ipTM > 0.8 and pLDDT > 80
```

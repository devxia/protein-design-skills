---
name: sequence-design
description: Amino acid sequence design with ProteinMPNN (Stage 2)
---

# Stage 2: Sequence Design (ProteinMPNN)

## When to Trigger

- User says "design sequences for this backbone", "run ProteinMPNN"
- User provides PDB and asks for amino acid sequences
- Follow-up to RFdiffusion output: "now design sequences for these backbones"

## ProteinMPNN Overview

ProteinMPNN assigns amino acid sequences to given backbone structures. It uses a graph neural network to predict the most likely residue type at each position, conditioned on the 3D backbone geometry.

## MCP Tool

```json
{
  "tool": "run_proteinmpnn",
  "params": {
    "pdb_path": "designs/design_0.pdb",
    "output_folder": "outputs/seqs",
    "num_seq_per_target": 8,
    "sampling_temp": "0.1",
    "seed": 37
  }
}
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `pdb_path` | ✅ | — | Input PDB file path |
| `output_folder` | ✅ | — | Output folder path |
| `num_seq_per_target` | ❌ | 8 | Sequences to generate per backbone |
| `sampling_temp` | ❌ | `"0.1"` | Temperature(s): `"0.1"` conservative, `"0.3"` moderate, `"0.5"` diverse |
| `model_name` | ❌ | `"v_48_020"` | Model variant: `v_48_002`, `v_48_010`, `v_48_020`, `v_48_030` |
| `pdb_path_chains` | ❌ | null | Chains to design, e.g. `"B"` (binder-only) |
| `fixed_positions_jsonl` | ❌ | null | Path to fixed positions JSONL |
| `use_soluble_model` | ❌ | false | Use soluble protein model |
| `seed` | ❌ | 37 | Random seed (0=random) |
| `omit_AAs` | ❌ | `"X"` | Exclude amino acids, e.g. `"AC"` excludes Ala and Cys |
| `backbone_noise` | ❌ | 0.00 | Gaussian noise on backbone (Å) |
| `save_score` | ❌ | false | Save scores to .npz |
| `save_probs` | ❌ | false | Save probabilities to .npz |

## Sampling Temperature Guide

| Temperature | Diversity | Use Case |
|------------|-----------|----------|
| 0.1 | Low (conservative) | High-confidence sequences, binder design |
| 0.2 | Medium | Balanced exploration |
| 0.3 | Higher | Diverse sequence library |
| 0.5 | High | Maximum diversity for screening |

Multiple temperatures: `"sampling_temp": "0.1 0.2 0.3"`

## Binder Design: Fixing Target Chain

When the input is a binder-target complex (from RFdiffusion binder mode):

```json
{
  "pdb_path": "binder_complex.pdb",
  "output_folder": "outputs/binder_seqs",
  "pdb_path_chains": "B",
  "num_seq_per_target": 8,
  "sampling_temp": "0.1"
}
```

This fixes chain A (target) and redesigns only chain B (binder).

## Fixed Positions JSONL Format

```json
{"design_0": {"A": [1, 2, 3, 4, 5], "B": []}}
```

## Output Format

```
output_folder/
├── seqs/
│   └── design_0.fa
└── scores/
    └── design_0.npz
```

**FASTA header format:**
```
>design_0, score=0.7291, global_score=0.9330, fixed_chains=['A'], designed_chains=['B'], model_name=v_48_020, seed=37
>T=0.1, sample=1, score=0.7291, global_score=0.9330, seq_recovery=0.5736
SEQUENCEHERE/SECONDCHAIN
```

- `score`: average negative log-prob of designed residues (lower=better)
- `global_score`: average negative log-prob of all residues
- `seq_recovery`: fraction matching native sequence (if available)
- Multi-chain: sequences separated by `/`, chains in alphabetical order

## Workflow

```
Input: PDB from Stage 1 (RFdiffusion) or user-provided
     ↓
Determine which chains to design
     ↓
submit_job("proteinmpnn", params)
     ↓
query_job polling → completed
     ↓
Return FASTA files → Stage 3 (validation)
```

## Tips

- For binder design, use `pdb_path_chains` to fix the target
- Lower temperature (0.1) gives more reliable sequences for validation
- Higher temperature (0.3+) useful for generating diverse libraries
- `use_soluble_model` if targeting soluble expression

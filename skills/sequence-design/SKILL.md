---
name: sequence-design
description: Amino acid sequence design with ProteinMPNN and alternatives (Stage 2)
---

# Stage 2: Sequence Design (ProteinMPNN + Alternatives)

## When to Trigger

- User says "design sequences for this backbone", "run ProteinMPNN"
- User provides PDB and asks for amino acid sequences
- Follow-up to RFdiffusion output: "now design sequences for these backbones"
- User requests advanced features: fixed positions, symmetry, bias, scoring
- User requests ligand-aware design: "design sequences considering the ligand"
- User requests soluble protein design: "make it soluble"

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

## Basic Parameters

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

## Advanced Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `jsonl_path` | str | Path to parsed PDBs in jsonl format (multi-chain workflow) |
| `chain_id_jsonl` | str | Path to chain assignment JSONL |
| `tied_positions_jsonl` | str | Path to tied (symmetric) positions JSONL |
| `bias_AA_jsonl` | str | Path to global AA bias JSONL |
| `bias_by_res_jsonl` | str | Path to per-position AA bias JSONL |
| `pssm_jsonl` | str | Path to PSSM bias JSONL |
| `pssm_multi` | float | PSSM weight [0.0, 1.0] |
| `score_only` | bool | Score input backbone-sequence pairs only |
| `path_to_fasta` | str | FASTA sequence to score |
| `ca_only` | bool | Use CA-only models |
| `batch_size` | int | Batch size (increase for larger GPUs) |

## Sampling Temperature Guide

| Temperature | Diversity | Use Case |
|------------|-----------|----------|
| 0.1 | Low (conservative) | High-confidence sequences, binder design |
| 0.2 | Medium | Balanced exploration |
| 0.3 | Higher | Diverse sequence library |
| 0.5 | High | Maximum diversity for screening |

Multiple temperatures: `"sampling_temp": "0.1 0.2 0.3"`

## Common Design Patterns

### Simple Monomer
```json
{
  "pdb_path": "designs/design_0.pdb",
  "output_folder": "outputs/seqs",
  "num_seq_per_target": 8,
  "sampling_temp": "0.1"
}
```

### Binder Design: Fixing Target Chain
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

### Soluble Protein Design
```json
{
  "pdb_path": "designs/design_0.pdb",
  "output_folder": "outputs/soluble_seqs",
  "num_seq_per_target": 8,
  "sampling_temp": "0.1",
  "use_soluble_model": true
}
```

### Multi-Chain Complex (JSONL Workflow)
For designing multiple chains in a complex:
```json
{
  "jsonl_path": "parsed_chains/pdbs.jsonl",
  "chain_id_jsonl": "chain_assignments.jsonl",
  "output_folder": "outputs/seqs",
  "num_seq_per_target": 8,
  "sampling_temp": "0.1"
}
```

**Preparing JSONL files:**
```bash
# Parse multiple PDBs to jsonl
python ProteinMPNN/helper_scripts/parse_multiple_chains.py \
    --input_path=./pdbs/ \
    --output_path=./parsed_chains/pdbs.jsonl

# Assign which chains to design vs fix
python ProteinMPNN/helper_scripts/assign_fixed_chains.py \
    --input_path=./parsed_chains/pdbs.jsonl \
    --output_path=./chain_assignments.jsonl \
    --chain_list "A B"
```

### Fixed Positions Design
Keep specific residues fixed while designing the rest:
```json
{
  "pdb_path": "designs/design_0.pdb",
  "output_folder": "outputs/fixed_seqs",
  "fixed_positions_jsonl": "fixed_positions.jsonl",
  "num_seq_per_target": 8,
  "sampling_temp": "0.1"
}
```

**Creating fixed positions JSONL:**
```bash
python ProteinMPNN/helper_scripts/make_fixed_positions_dict.py \
    --input_path=./parsed_chains/pdbs.jsonl \
    --output_path=./fixed_positions.jsonl \
    --chain_list "A" \
    --position_list "1 2 3 4 5 23 25"
```

JSONL format (1-based indices):
```json
{"5TTA": {"A": [1, 2, 3, 7, 8, 9, 22, 25], "B": []}}
```

### Tied Positions (Symmetry)
For symmetric oligomers, tie equivalent positions:
```json
{
  "pdb_path": "symmetric_design.pdb",
  "output_folder": "outputs/sym_seqs",
  "tied_positions_jsonl": "tied_positions.jsonl",
  "num_seq_per_target": 8
}
```

**Creating tied positions JSONL:**
```bash
# For homooligomers (auto-detect symmetry)
python ProteinMPNN/helper_scripts/make_tied_positions_dict.py \
    --input_path=./parsed_chains/pdbs.jsonl \
    --output_path=./tied_positions.jsonl \
    --homooligomer 1

# For manual specification
python ProteinMPNN/helper_scripts/make_tied_positions_dict.py \
    --input_path=./parsed_chains/pdbs.jsonl \
    --output_path=./tied_positions.jsonl \
    --chain_list "A C" \
    --position_list "1 2 3 4 5 6 7 8, 1 2 3 4 5 6 7 8"
```

### Amino Acid Bias
Bias toward or away from specific amino acids:
```json
{
  "pdb_path": "designs/design_0.pdb",
  "output_folder": "outputs/biased_seqs",
  "bias_AA_jsonl": "aa_bias.jsonl",
  "num_seq_per_target": 8
}
```

**Creating AA bias JSONL:**
```bash
python ProteinMPNN/helper_scripts/make_bias_AA.py \
    --output_path=./aa_bias.jsonl \
    --AA_list="D E H K N Q R S T W Y" \
    --bias_list="1.39 1.39 1.39 1.39 1.39 1.39 1.39 1.39 1.39 1.39 1.39"
```

### Scoring Mode (Evaluate Existing Sequences)
Score backbone-sequence pairs without generating new sequences:
```json
{
  "pdb_path": "designs/design_0.pdb",
  "output_folder": "outputs/scores",
  "score_only": true,
  "path_to_fasta": "sequences.fa"
}
```

### Backbone Noise for Robustness
Add noise to backbone to test sequence robustness:
```json
{
  "pdb_path": "designs/design_0.pdb",
  "output_folder": "outputs/noisy_seqs",
  "backbone_noise": 0.1,
  "num_seq_per_target": 16
}
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

## Alternative: LigandMPNN

[LigandMPNN](https://github.com/dauparas/LigandMPNN) is a successor that adds ligand-aware sequence design.

Key differences:
- Supports multiple model types: `protein_mpnn`, `ligand_mpnn`, `soluble_mpnn`
- Direct PDB residue IDs (e.g., `A23`, `B42D`)
- Side chain packing option
- Homooligomer auto-setup

### LigandMPNN Parameters

| Parameter | Description |
|-----------|-------------|
| `model_type` | `"protein_mpnn"`, `"ligand_mpnn"`, `"soluble_mpnn"` |
| `temperature` | Sampling temperature (default 0.1) |
| `fixed_residues` | Space-separated residue IDs (e.g. `"C1 C2 C3"`) |
| `redesigned_residues` | Space-separated residues to design |
| `bias_AA` | Global bias string (e.g. `"W:3.0,P:3.0"`) |
| `omit_AA` | Global omit string (e.g. `"CDFGHILMNPQRSTVWY"`) |
| `symmetry_residues` | Symmetry groups: `"C1,C2,C3\|C4,C5"` |
| `homo_oligomer` | 1 = auto-setup symmetry |
| `chains_to_design` | Chains to redesign (e.g. `"A,B"`) |
| `pack_side_chains` | 1 = also pack side chains |

## Tips

- For binder design, use `pdb_path_chains` to fix the target
- Lower temperature (0.1) gives more reliable sequences for validation
- Higher temperature (0.3+) useful for generating diverse libraries
- `use_soluble_model` if targeting soluble expression
- `backbone_noise` tests robustness but may decrease sequence quality
- `fixed_positions_jsonl` preserves important functional residues
- `tied_positions_jsonl` ensures symmetric positions get identical residues
- For scoring existing sequences, use `score_only` mode with `path_to_fasta`
- LigandMPNN is preferred when designing proteins with bound small molecules

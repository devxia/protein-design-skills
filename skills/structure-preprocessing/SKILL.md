---
name: structure-preprocessing
description: PDB structure preprocessing with PDBFixer (Stage 0)
---

# Stage 0: Structure Preprocessing (PDBFixer)

## When to Trigger

- User provides any PDB/CIF file before design
- Input contains non-standard residues (MSE, HIP, etc.)
- Input contains heterogens (ligands, ions, water)
- Missing atoms reported in structure
- Any tool fails with "missing atom" or "unknown residue" errors

## Why This is Mandatory

All user-provided structures **must** be preprocessed before entering RFdiffusion, ProteinMPNN, or AlphaFold3. Unprocessed structures cause cryptic failures in downstream tools.

## Processing Steps (in order)

1. **Chain filtering** (optional) — retain only specified chains
2. **Non-standard residue conversion** — MSE→MET, HIP→HIS, etc. (~160 built-in mappings)
3. **Heterogen removal** — delete all ligands, ions, water molecules
4. **Missing residue detection** — identify gaps, warn user, do NOT add (unreliable)
5. **Missing heavy atom reconstruction** — add N, CA, C, O where absent
6. **No hydrogen addition** — design tools don't need hydrogens
7. **No water box** — design tools don't need solvent

## MCP Tool

```json
{
  "tool": "run_pdbfixer",
  "params": {
    "input_pdb": "path/to/input.pdb",
    "output_pdb": "path/to/output_fixed.pdb",
    "keep_chains": ["A"],
    "seed": 42
  }
}
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `input_pdb` | ✅ | — | Input PDB/CIF file path |
| `output_pdb` | ❌ | auto | Output path (auto: `<input>_fixed.pdb`) |
| `keep_chains` | ❌ | all | List of chain IDs to retain |
| `seed` | ❌ | 42 | Random seed for atom placement |

## Common Non-Standard Residues

| Non-Standard | Standard | Context |
|--------------|----------|---------|
| MSE | MET | Selenomethionine |
| HIP | HIS | Protonated histidine |
| HIE | HIS | Neutral histidine |
| CYX | CYS | Disulfide cysteine |
| ASH | ASP | Protonated aspartate |
| GLH | GLU | Protonated glutamate |

## Output Log Format

```json
{
  "input": "input.pdb",
  "fixes": [
    "nonstandard_residues: [\"MSE→MET\"]",
    "removed_heterogens: [\"SO4\", \"HOH\"]",
    "added_missing_atoms: 3_residues"
  ],
  "output": "input_fixed.pdb"
}
```

## Warnings to Surface to User

- **Missing residues detected**: "Structure has gaps in the backbone. Automatic loop building is unreliable. Consider using a more complete experimental structure."
- **Non-standard residues replaced**: List which residues were changed
- **Heterogens removed**: List removed molecules

## Workflow Placement

```
User provides PDB
     ↓
run_pdbfixer (this stage)
     ↓
Clean PDB → RFdiffusion / ProteinMPNN / AlphaFold3
```

Always enforce: **no design tool runs without prior PDBFixer preprocessing**.

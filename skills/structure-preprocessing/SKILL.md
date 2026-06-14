---
name: structure-preprocessing
description: PDB structure preprocessing with PDBFixer (Stage 0)
---

# Stage 0: Structure Preprocessing (PDBFixer)

**This skill is the FIRST stage of the pipeline. ALWAYS run this before any design tool.**

**Quick entry:** If you have a PDB file and want to use it for design, you MUST preprocess it here first.

**Typical flow:** **THIS SKILL** (Stage 0) → `structure-generation` (Stage 1) → `sequence-design` (Stage 2) → `structure-validation` (Stage 3) → `filtering-ranking` (Stage 4)

## When to Use This Skill

- You have any PDB/CIF file to use as input for design
- Your input contains non-standard residues (MSE, HIP, etc.)
- Your input contains heterogens (ligands, ions, water) that need removal
- Missing atoms reported in structure
- Any downstream tool fails with "missing atom" or "unknown residue" errors

**Why mandatory:** All design tools (RFdiffusion, ProteinMPNN, AlphaFold3) require clean PDBs. Unprocessed structures cause cryptic failures.

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

## Standalone Script

```bash
python scripts/run_pdbfixer.py \
  --input path/to/input.pdb \
  --output path/to/output_fixed.pdb \
  --keep-chains A
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `input_pdb` | ✅ | — | Input PDB/CIF file path |
| `output_pdb` | ❌ | auto | Output path (auto: `<input>_fixed.pdb`) |
| `keep_chains` | ❌ | all | Comma-separated chain IDs to retain |
| `add_atoms` | ❌ | heavy | Atoms to add: `heavy`, `all`, `none` |
| `keep_heterogens` | ❌ | none | Heterogens to keep: `water`, `all`, or comma-separated IDs |
| `ph` | ❌ | 7.0 | pH for hydrogen addition |
| `verbose` | ❌ | false | Verbose output |

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
python scripts/run_pdbfixer.py (this stage)
     ↓
Clean PDB → RFdiffusion / ProteinMPNN / AlphaFold3
```

Always enforce: **no design tool runs without prior PDBFixer preprocessing**.

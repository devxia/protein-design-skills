---
name: ligandmpnn-design
description: Ligand-aware sequence design with LigandMPNN — alternative to ProteinMPNN
---

# Alternative Stage 2: LigandMPNN Sequence Design

## When to Trigger

- User says "LigandMPNN", "ligand-aware design", "design with ligand"
- User wants to design proteins that bind small molecules
- User wants nanobody/VHH design
- User wants membrane protein design
- User wants soluble protein design with better model
- User requests side chain packing alongside sequence design

## LigandMPNN Overview

[LigandMPNN](https://github.com/dauparas/LigandMPNN) is a successor to ProteinMPNN from the same authors. It extends ProteinMPNN with:
- **Ligand context awareness** — designs sequences considering bound small molecules
- **Multiple model variants** — protein, ligand, soluble, membrane
- **VHH framework mode** — specialized for nanobody design
- **Side chain packing** — packs side chains alongside sequence design
- **Direct PDB residue IDs** — uses ProDy for parsing (supports insertion codes)

## Installation

```bash
git clone https://github.com/dauparas/LigandMPNN.git
cd LigandMPNN
pip install -e .
```

## Model Types

| Model Type | Purpose | Best For |
|------------|---------|----------|
| `protein_mpnn` | Standard inverse folding | General protein design |
| `ligand_mpnn` | Ligand-aware design | Small molecule binding proteins |
| `soluble_mpnn` | Soluble proteins | Cytoplasmic expression |
| `global_label_membrane_mpnn` | Membrane proteins (global) | Transmembrane design |
| `per_residue_label_membrane_mpnn` | Membrane proteins (per-residue) | Complex membrane topology |

## Basic Usage

### Standard Protein Design (like ProteinMPNN)
```bash
python run.py \
    --model_type protein_mpnn \
    --pdb_path input.pdb \
    --out_folder outputs/ligandmpnn \
    --num_seq_per_target 8 \
    --temperature 0.1 \
    --chains_to_design A
```

### Ligand-Aware Design
```bash
python run.py \
    --model_type ligand_mpnn \
    --pdb_path protein_with_ligand.pdb \
    --out_folder outputs/ligand_design \
    --num_seq_per_target 8 \
    --temperature 0.1 \
    --chains_to_design A \
    --redesigned_residues "A1 A2 A3 A4 A5"  # Design only these residues
```

### Nanobody (VHH) Design
```bash
python run.py \
    --model_type protein_mpnn \
    --pdb_path nanobody_target.pdb \
    --out_folder outputs/vhh_design \
    --num_seq_per_target 16 \
    --temperature 0.1 \
    --chains_to_design H  # Heavy chain only
```

### Soluble Protein Design
```bash
python run.py \
    --model_type soluble_mpnn \
    --pdb_path input.pdb \
    --out_folder outputs/soluble \
    --num_seq_per_target 8 \
    --temperature 0.1
```

### With Side Chain Packing
```bash
python run.py \
    --model_type protein_mpnn \
    --pdb_path input.pdb \
    --out_folder outputs/packed \
    --num_seq_per_target 8 \
    --temperature 0.1 \
    --pack_side_chains 1 \
    --number_of_packs_per_design 5
```

## Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `model_type` | Model variant | `protein_mpnn`, `ligand_mpnn`, `soluble_mpnn` |
| `temperature` | Sampling temperature (0.1=conservative) | `0.1` |
| `fixed_residues` | Residues to keep fixed | `"C1 C2 C3"` |
| `redesigned_residues` | Residues to design | `"A1 A2 A3"` |
| `bias_AA` | Global AA bias | `"W:3.0,P:3.0,A:-3.0"` |
| `omit_AA` | Amino acids to omit | `"CDFGHILMNPQRSTVWY"` |
| `chains_to_design` | Chains to redesign | `"A,B"` |
| `symmetry_residues` | Symmetry groups | `"C1,C2,C3\|C4,C5"` |
| `homo_oligomer` | Auto symmetry for homooligomers | `1` |
| `pack_side_chains` | Also pack side chains | `1` |
| `number_of_packs_per_design` | Packing samples | `5` |
| `ligand_mpnn_use_atom_context` | Use ligand atoms | `1` |
| `ligand_mpnn_use_side_chain_context` | Use fixed side chains | `1` |

## Residue ID Format

LigandMPNN uses ProDy and supports **PDB-style residue IDs** with insertion codes:
- `A23` — Chain A, residue 23
- `B42D` — Chain B, residue 42, insertion code D
- `H100A` — Common in antibodies (CDR H3)

This is more intuitive than ProteinMPNN's 1-based indexing.

## Pipeline Integration

LigandMPNN replaces ProteinMPNN in Stage 2:

```
Standard:  Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → Stage 3 (AlphaFold3)
Ligand:    Stage 1 (RFdiffusion) → Stage 2 (LigandMPNN) → Stage 3 (AlphaFold3)
```

### Example: Design Ligand-Binding Protein

1. **Get protein-ligand structure** (from PDB or docking)
2. **Run LigandMPNN** with `model_type=ligand_mpnn`
3. **Validate** with AlphaFold3
4. **Check** ligand binding pose with molecular docking

### Example: Nanobody Design

1. **Prepare target structure** (antigen)
2. **Use RFdiffusion** or graft CDRs from known nanobody
3. **Run LigandMPNN** with `model_type=protein_mpnn`, `chains_to_design=H`
4. **Validate** with AlphaFold3 (check CDR loops)

## Comparison with ProteinMPNN

| Feature | ProteinMPNN | LigandMPNN |
|---------|-------------|------------|
| General design | ✓ Excellent | ✓ Excellent |
| Ligand-aware | ✗ No | ✓ Yes |
| Soluble model | ✓ Yes (flag) | ✓ Yes (separate model) |
| Membrane model | ✗ No | ✓ Yes |
| Side chain packing | ✗ No | ✓ Yes |
| PDB insertion codes | ✗ No | ✓ Yes |
| Nanobody/VHH | ✓ Possible | ✓ Better (framework mode) |
| Speed | Fast | Slightly slower |

## Tips

- Use `ligand_mpnn` model when the input structure contains a bound ligand
- Use `soluble_mpnn` for proteins intended for cytoplasmic expression
- Use `fixed_residues` to preserve binding site residues
- Side chain packing (`pack_side_chains=1`) adds runtime but gives more realistic structures
- For nanobodies, the `H` chain convention is standard
- LigandMPNN's scoring script (`score.py`) can evaluate existing sequences

## References

- [LigandMPNN GitHub](https://github.com/dauparas/LigandMPNN)
- [LigandMPNN Paper](https://www.biorxiv.org/content/10.1101/2024.10.22.619563)

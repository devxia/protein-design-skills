---
name: diffpepbuilder-design
description: Specialized peptide binder design with DiffPepBuilder (8-30aa peptides)
---

# Alternative Stage 1: DiffPepBuilder Peptide Design

> **Quick Entry**: Stage 1 alternative | 8-30aa peptides | peptide-protein interfaces | disulfide bonds | DiffPepDock
>
> **Upstream**: `structure-preprocessing` (PDBFixer target) | **Downstream**: `sequence-design` (ProteinMPNN, optional) → `structure-validation` (Boltz-1/AF3)

## When to Trigger

- User says "design a peptide", "peptide binder", "short peptide"
- User wants 8-30 residue peptides targeting a protein
- User needs peptide-protein interface design
- User wants disulfide-bonded cyclic peptides
- User requests peptide docking

## DiffPepBuilder Overview

[DiffPepBuilder](https://github.com/YuzheWangPKU/DiffPepBuilder) is a specialized diffusion model for **de novo peptide binder design** (8-30 residues). Unlike RFdiffusion which generates full proteins, DiffPepBuilder is specifically optimized for short peptides that bind protein targets.

### Key Differences from RFdiffusion

| Feature | DiffPepBuilder | RFdiffusion |
|---------|----------------|-------------|
| Target molecule | Short peptides (8-30aa) | Full proteins, binders, motifs |
| Peptide-protein interfaces | Specialized, optimized | Supported but not specialized |
| Sequence design | Integrated (with ESM) | Separate (ProteinMPNN) |
| Post-processing | AMBER + Rosetta relax | Not included |
| Docking | Built-in (DiffPepDock) | No |
| Disulfide bonds | Built-in support | No special support |
| GPU requirement | Multi-GPU (DDP, 8 GPUs) | Single GPU capable |
| Speed | Slower (peptide-specific) | Faster for general cases |

## Installation

```bash
git clone https://github.com/YuzheWangPKU/DiffPepBuilder.git
cd DiffPepBuilder
conda env create -f environment.yml
conda activate diffpepbuilder

# Extract SS builder library
cd SSbuilder && tar -xvf SSBLIB.tar.gz

# Install PyRosetta (required for post-processing)
# Get license from https://www.pyrosetta.org/
conda install pyrosetta -c https://conda.pyrosetta.org
```

## Two Modes

### Mode 1: De Novo Peptide Design

Generate peptide binders for a target protein given binding hotspots:

```bash
# Run inside the DiffPepBuilder repository
python DiffPepBuilder/scripts/design.py \
    --target_pdb target.pdb \
    --target_chain A \
    --hotspot_residues "A30 A33 A34" \
    --min_length 8 \
    --max_length 20 \
    --num_t 200 \
    --noise_scale 1.0 \
    --samples_per_length 8 \
    --build_ss_bond \
    --max_ss_bond 2 \
    --out_dir outputs/peptide_designs
```

### Mode 2: Peptide Docking (DiffPepDock)

Dock a known peptide sequence to a target protein:

```bash
# Run inside the DiffPepBuilder repository
python DiffPepBuilder/scripts/dock.py \
    --target_pdb target.pdb \
    --target_chain A \
    --peptide_sequence "CGVPAIQK" \
    --num_t 200 \
    --out_dir outputs/docked
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_pdb` | string | — | Target protein PDB file |
| `target_chain` | string | — | Target chain ID |
| `hotspot_residues` | string | — | Space-separated hotspot residues on target (e.g. "A30 A33") |
| `min_length` | int | 8 | Minimum peptide length |
| `max_length` | int | 30 | Maximum peptide length |
| `num_t` | int | 200 | Number of denoising steps |
| `noise_scale` | float | 1.0 | Sampling temperature analog |
| `samples_per_length` | int | 8 | Samples per sequence length |
| `seq_temperature` | float | 0.1 | Residue type sampling temperature |
| `build_ss_bond` | flag | True | Build disulfide bonds |
| `max_ss_bond` | int | 2 | Maximum disulfide bonds |

## Pipeline Integration

DiffPepBuilder replaces Stage 1 for peptide-specific designs:

### Peptide-Only Pipeline
```
Stage 0: PDBFixer (target structure)
    ↓
Stage 1: DiffPepBuilder (generate peptide binders 8-30aa)
    ↓
Post-processing: AMBER relax + Rosetta relax
    ↓
Stage 3: AlphaFold3 (validate peptide-target complex)
    ↓
Stage 4: Filtering + ddG calculation
```

### Comparison with RFdiffusion for Peptides

| Aspect | DiffPepBuilder | RFdiffusion |
|--------|----------------|-------------|
| 8-15 aa peptides | ✓ Excellent | ⚠️ Possible but not optimized |
| 15-30 aa peptides | ✓ Good | ✓ Good |
| >30 aa peptides | ✗ Too short | ✓ Good |
| Disulfide bonds | ✓ Built-in | ✗ Manual |
| Interface optimization | ✓ Specialized | ⚠️ General |
| Post-processing | ✓ Included | ✗ Not included |
| Speed | ⚠️ Slower | ✓ Faster |
| GPU requirement | ⚠️ Multi-GPU | ✓ Single GPU |

## Tips

- DiffPepBuilder is **the tool of choice** for peptide binder design (8-30aa)
- For larger designs (>30aa), use RFdiffusion instead
- Hotspot residues should be on the **target protein surface** (not the peptide)
- Disulfide bonds can dramatically improve peptide stability
- Post-processing (AMBER + Rosetta relax) is **essential** for realistic structures
- Binding ddG calculation helps rank designs

## When to Use DiffPepBuilder vs RFdiffusion

| Design Goal | Recommended Tool |
|-------------|-----------------|
| 8-15 aa peptide inhibitor | DiffPepBuilder |
| 15-30 aa peptide binder | DiffPepBuilder |
| Cyclic peptide with disulfides | DiffPepBuilder |
| Peptide docking (known sequence) | DiffPepDock |
| >30 aa protein binder | RFdiffusion |
| De novo protein (monomer) | RFdiffusion |
| Motif scaffolding | RFdiffusion |

## References

- [DiffPepBuilder GitHub](https://github.com/YuzheWangPKU/DiffPepBuilder)
- [DiffPepBuilder Paper](https://www.nature.com/articles/s43588-024-00637-0)

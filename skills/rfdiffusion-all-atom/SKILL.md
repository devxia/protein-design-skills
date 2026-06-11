---
name: rfdiffusion-all-atom
description: All-atom protein design with RFdiffusionAA — supports small molecule ligands, cofactors, and full side chain generation
---

# Alternative Stage 1: RFdiffusion-All-Atom (RFdiffusionAA)

> **Quick Entry**: Stage 1 alternative | ligand/cofactor-aware all-atom design | RFdiffusionAA
>
> **Upstream**: `structure-preprocessing` (PDB repair and preparation) | **Downstream**: `sequence-design` (LigandMPNN recommended) → `structure-validation`

## When to Trigger

- User says "design with ligand", "small molecule binder", "cofactor binding"
- User wants all-atom generation (not just backbone N/CA/C/O)
- User needs to design proteins around metal ions, heme, or other cofactors
- User wants to include non-protein molecules in the design context
- User says "RFdiffusionAA", "RF All Atom", "full atom design"

## RFdiffusionAA Overview

[RFdiffusion-All-Atom](https://github.com/baker-laboratory/rf_diffusion_all_atom) is an extension of RFdiffusion from the Baker Lab that generates **full all-atom protein structures** including side chains, and can design proteins around **small molecules, ligands, and cofactors**. Unlike standard RFdiffusion which only outputs backbone atoms, RFdiffusionAA models all atoms including ligands.

### Key Differences from Standard RFdiffusion

| Feature | RFdiffusion | RFdiffusionAA |
|---------|-------------|---------------|
| Output atoms | Backbone only (N/CA/C/O) | All atoms (including side chains) |
| Ligand support | No | Yes (small molecules, cofactors) |
| Metal ions | No | Yes |
| Heme binding | No | Yes (via heme_binder checkpoint) |
| Sequence output | No (need ProteinMPNN) | Partial (still need LigandMPNN for final seq) |
| Container | Conda env | Apptainer container |
| Speed | Faster | Slower (all-atom modeling) |
| Memory | Moderate | Higher |

## Installation

```bash
# Clone repository
git clone https://github.com/baker-laboratory/rf_diffusion_all_atom.git
cd rf_diffusion_all_atom

# Download pre-built container (Apptainer/Singularity)
wget http://files.ipd.uw.edu/pub/RF-All-Atom/containers/rf_se3_diffusion.sif

# Download model weights
wget http://files.ipd.uw.edu/pub/RF-All-Atom/weights/RFDiffusionAA_paper_weights.pt

# Initialize submodules
git submodule init
git submodule update

# Install Apptainer if not available
# https://apptainer.org/docs/admin/main/installation.html
```

## Design Modes

### Mode 1: Small Molecule Binder Design

Design a protein that binds a specific small molecule ligand:

```bash
/usr/bin/apptainer run --nv rf_se3_diffusion.sif \
    -u run_inference.py \
    inference.deterministic=True \
    diffuser.T=100 \
    inference.output_prefix=output/ligand_binder/sample \
    inference.input_pdb=input/7v11.pdb \
    contigmap.contigs=['150-150'] \
    inference.ligand=OQO \
    inference.num_designs=10 \
    inference.design_startnum=0
```

**Key parameters:**
- `inference.ligand=OQO` — Ligand residue name from input PDB
- `contigmap.contigs=['150-150']` — Generated protein length
- `diffuser.T=100` — Denoising steps (100-200)
- `inference.deterministic=True` — Reproducible results

### Mode 2: Ligand + Protein Motif Design

Design a binder around both a ligand AND a conserved protein motif:

```bash
/usr/bin/apptainer run --nv rf_se3_diffusion.sif \
    -u run_inference.py \
    inference.deterministic=True \
    diffuser.T=200 \
    inference.output_prefix=output/ligand_protein_motif/sample \
    inference.input_pdb=input/1haz.pdb \
    contigmap.contigs=['10-120,A84-87,10-120'] \
    contigmap.length="150-150" \
    inference.ligand=CYC \
    inference.num_designs=10
```

**Key parameters:**
- `contigmap.contigs=['10-120,A84-87,10-120']` — Scaffold around motif A84-87
- `inference.ligand=CYC` — Include ligand in design

### Mode 3: Heme Binder Design

Design proteins that bind heme cofactors (requires heme_binder checkpoint):

```bash
/usr/bin/apptainer run --nv rf_se3_diffusion.sif \
    -u run_inference.py \
    --config-name heme_binder \
    inference.deterministic=True \
    diffuser.T=200 \
    inference.output_prefix=output/heme_binder/sample \
    inference.input_pdb=input/heme_target.pdb \
    contigmap.contigs=['150-150'] \
    inference.num_designs=10
```

## Parameters Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `inference.input_pdb` | string | — | Input PDB with ligand/co-crystal |
| `inference.ligand` | string | — | Ligand residue name (e.g., "OQO", "CYC", "HEM") |
| `contigmap.contigs` | list | — | Contig strings for design regions |
| `diffuser.T` | int | 50 | Denoising steps (higher = better quality) |
| `inference.num_designs` | int | 1 | Number of designs to generate |
| `inference.output_prefix` | string | — | Output path prefix |
| `inference.deterministic` | bool | False | Reproducible seeding |
| `inference.design_startnum` | int | 0 | Starting design index |
| `inference.cautious` | bool | False | Skip if output exists |

## Output Files

For each design N:
- `sample_N.pdb` — Final idealized design with all atoms
- `unidealized/sample_N.pdb` — Unidealized structure
- `traj/sample_N_Xt-1_traj.pdb` — Denoising trajectory
- `traj/sample_N_X0-1_traj.pdb` — Ground truth predictions at each step
- `sample_N.trb` — Metadata (config, mappings, etc.)

## Pipeline Integration

### Full Pipeline with Ligand-Aware Design (5 stages)
```
Stage 0: PDBFixer (prepare input with ligand)
    ↓
Stage 1: RFdiffusionAA (generate all-atom structure with ligand)
    ↓
Stage 2: LigandMPNN (design sequence considering ligand context)
    ↓
Stage 3: AlphaFold3 or OmegaFold (validate structure)
    ↓
Stage 4: Filtering + Docking validation
```

### Lightweight Pipeline (4 stages)
```
Stage 0: PDBFixer
    ↓
Stage 1: RFdiffusionAA (all-atom backbone + partial sequence)
    ↓
Stage 2: LigandMPNN (full sequence design with ligand)
    ↓
Stage 3: OmegaFold (fast validation, no MSA needed)
    ↓
Stage 4: Filtering
```

### Why RFdiffusionAA + LigandMPNN?
- RFdiffusionAA outputs **all-atom structures** but sequences are not reliable
- LigandMPNN's `ligand_mpnn` model specifically handles bound ligands
- Together they enable **true ligand-aware de novo design**

## Comparison: Standard vs All-Atom Pipeline

| Design Goal | Standard Pipeline | All-Atom Pipeline |
|-------------|-------------------|-------------------|
| Simple monomer | RFdiffusion + ProteinMPNN | RFdiffusionAA + LigandMPNN |
| Ligand binder | Not supported | RFdiffusionAA + LigandMPNN |
| Heme binding | Not supported | RFdiffusionAA (heme checkpoint) + LigandMPNN |
| Metal site | Not supported | RFdiffusionAA + LigandMPNN |
| Peptide binder | RFdiffusion | RFdiffusion (still better for peptides) |
| Speed | Faster | Slower |

## Tips

- **Ligand naming**: The ligand residue name in `inference.ligand=` must match exactly what's in the input PDB (check with PyMOL or `grep HETATM`)
- **Input preparation**: The input PDB should contain the ligand in the correct binding pose (from co-crystal or docking)
- **Contig syntax**: Same as standard RFdiffusion, but ligand is automatically included
- **Sequence reliability**: RFdiffusionAA's output sequences are partial — always run LigandMPNN after
- **Container execution**: The `--nv` flag is required for GPU; omit for CPU-only
- **Memory**: All-atom generation requires more GPU memory than backbone-only RFdiffusion
- **End-to-end example**: See [heme_binder_diffusion](https://github.com/ikalvet/heme_binder_diffusion) for a complete pipeline

## References

- [RFdiffusionAA GitHub](https://github.com/baker-laboratory/rf_diffusion_all_atom)
- [Baker Lab RFdiffusionAA Page](http://files.ipd.uw.edu/pub/RF-All-Atom/)
- [Heme Binder Diffusion Pipeline](https://github.com/ikalvet/heme_binder_diffusion)

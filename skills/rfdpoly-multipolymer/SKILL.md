---
name: rfdpoly-multipolymer
description: Multi-polymer design with RFDpoly — extend RFdiffusion to DNA, RNA, proteins, and mixed nucleoprotein assemblies using Apptainer/Singularity
---

# Alternative: RFDpoly Multi-Polymer Design

## Quick Entry

**Use this skill when you need to design DNA, RNA, or mixed nucleoprotein complexes — not just proteins.** The only tool in the ecosystem with multi-polymer support.

**Typical flow:** Input sequences → **RFDpoly** (design complex) → `sequence-design` (Stage 2, for protein chains) → `structure-validation` (Stage 3) → `filtering-ranking` (Stage 4)

## When to Trigger

- User says "RFDpoly", "multi-polymer", "DNA protein complex", "RNA binding"
- User wants to design **mixed nucleoprotein assemblies**
- User needs **DNA-binding protein** design
- User says "RNA-binding protein", "nucleoprotein", "DNA complex"
- User wants to design **RNA-binding proteins** or **DNA-protein complexes**
- User needs **transcription factor** design or **CRISPR** systems

## RFDpoly Overview

[RFDpoly](https://github.com/RosettaCommons/RFDpoly) extends RFdiffusion to **multi-polymer design**. Unlike standard RFdiffusion which only designs proteins, RFDpoly can simultaneously design **DNA, RNA, proteins, and mixed nucleoprotein assemblies**.

### Key Differences from Standard RFdiffusion

| Feature | RFdiffusion | RFDpoly |
|---------|------------|---------|
| Polymers | Protein only | **DNA + RNA + Protein** |
| Complexes | Protein-protein | **Nucleoprotein complexes** |
| Motif support | Protein motifs | **DNA/RNA motifs** |
| Container | None | **Apptainer/Singularity** |
| Use case | General protein design | **Nucleic acid interactions** |

## System Requirements

- **OS**: Linux (tested on Ubuntu 24.04.3 LTS)
- **Container**: [Apptainer](https://apptainer.org/) ≥ 1.1 (or Singularity)
- **GPU**: NVIDIA GPU with ≥ 16GB VRAM (recommended)
- **RAM**: Minimum 16GB
- **Disk**: 40GB free space

## Installation

```bash
# 1. Clone repository
git clone https://github.com/RosettaCommons/RFDpoly.git
cd RFDpoly

# 2. Set environment variables
export RFDPOLY_DIR=/path/to/RFDpoly
export WEIGHTS_DIR=/path/to/RFDpoly/weights
export ENV_DIR=/path/to/RFDpoly/exec
export DESIGN_DIR=/path/to/your/output/directory
mkdir -p $WEIGHTS_DIR $ENV_DIR $DESIGN_DIR

# 3. Download model weights
cd $WEIGHTS_DIR

# Best weights for RNA-only design:
curl -O https://files.ipd.uw.edu/pub/2025_RFDpoly/train_session2024-06-27_1719522052_BFF_7.00.pt

# Best weights for generalized design across ALL polymer classes:
curl -O https://files.ipd.uw.edu/pub/2025_RFDpoly/train_session2024-07-08_1720455712_BFF_3.00.pt

# Set active weights (choose based on your task)
export RFDPOLY_CKPT_PATH=$WEIGHTS_DIR/train_session2024-07-08_1720455712_BFF_3.00.pt

# 4. Download Apptainer container
cd $ENV_DIR
curl -O https://files.ipd.uw.edu/pub/2025_RFDpoly/SE3nv.sif
export APPTAINER_PATH=$ENV_DIR/SE3nv.sif
```

**Alternative installation** (native/Conda without Apptainer):
See [external documentation](https://rosettacommons.github.io/RFDpoly/) for Conda setup on macOS/Windows (CPU only unless CUDA wheels installed).

## Usage

### Basic Multi-Polymer Design

Design a single structure with three chains: DNA (33 nt) + RNA (33 nt) + Protein (75 aa):

```bash
cd $DESIGN_DIR

apptainer run --nv $APPTAINER_PATH \
    $RFDPOLY_DIR/rf_diffusion/run_inference.py \
    --config-name=multi_polymer \
    diffuser.T=50 \
    inference.ckpt_path=$RFDPOLY_CKPT_PATH \
    inference.num_designs=1 \
    'contigmap.contigs=[\'33 33 75\']' \
    "contigmap.polymer_chains=['dna','rna','protein']" \
    inference.output_prefix=$DESIGN_DIR/test_outputs/basic_uncond_test01
```

**Critical flags:**
- `--config-name=multi_polymer` — **Required**. Ensures all settings work together correctly.
- `--nv` — Passes NVIDIA GPU to container
- `diffuser.T=50` — Diffusion timesteps
- `inference.ckpt_path` — Path to model weights
- `contigmap.contigs` — Length specification (space-separated, no commas inside)
- `contigmap.polymer_chains` — Polymer type for each chain

### Conditional Design (with Input PDB)

If unconditional design fails (model may search for input PDB even for unconditional):

```bash
apptainer run --nv $APPTAINER_PATH \
    $RFDPOLY_DIR/rf_diffusion/run_inference.py \
    --config-name=multi_polymer \
    diffuser.T=50 \
    inference.ckpt_path=$RFDPOLY_CKPT_PATH \
    inference.input_pdb=$RFDPOLY_DIR/rf_diffusion/test_data/DBP035.pdb \
    inference.num_designs=1 \
    'contigmap.contigs=[\'33 33 75\']' \
    "contigmap.polymer_chains=['dna','rna','protein']" \
    inference.output_prefix=$DESIGN_DIR/test_outputs/conditional_test01
```

### DNA-Binding Protein Design

```bash
apptainer run --nv $APPTAINER_PATH \
    $RFDPOLY_DIR/rf_diffusion/run_inference.py \
    --config-name=multi_polymer \
    diffuser.T=50 \
    inference.ckpt_path=$RFDPOLY_CKPT_PATH \
    inference.num_designs=10 \
    'contigmap.contigs=[\'20 100\']' \
    "contigmap.polymer_chains=['dna','protein']" \
    inference.output_prefix=$DESIGN_DIR/dna_binder
```

### RNA-Protein Complex

```bash
apptainer run --nv $APPTAINER_PATH \
    $RFDPOLY_DIR/rf_diffusion/run_inference.py \
    --config-name=multi_polymer \
    diffuser.T=50 \
    inference.ckpt_path=$RFDPOLY_CKPT_PATH \
    inference.num_designs=10 \
    'contigmap.contigs=[\'25 120\']' \
    "contigmap.polymer_chains=['rna','protein']" \
    inference.output_prefix=$DESIGN_DIR/rna_binder
```

## Parameters

### Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--config-name` | str | multi_polymer | **Required.** Use `multi_polymer` for all designs |
| `diffuser.T` | int | 50 | Diffusion timesteps |
| `inference.ckpt_path` | str | — | Path to model weights (.pt file) |
| `inference.num_designs` | int | 1 | Number of designs to generate |
| `contigmap.contigs` | list | — | Chain lengths (space-separated in quotes) |
| `contigmap.polymer_chains` | list | — | Polymer types: `dna`, `rna`, `protein` |
| `inference.output_prefix` | str | — | Output path prefix |
| `inference.input_pdb` | str | null | Input PDB (even unconditional may need dummy) |

### Polymer Chain Types

| Type | Contig Format | Example |
|------|--------------|---------|
| `dna` | Integer = nucleotides | `33` = 33bp DNA |
| `rna` | Integer = nucleotides | `33` = 33nt RNA |
| `protein` | Integer = residues | `75` = 75 aa protein |

### Model Weights Selection

| Weights File | Best For | Polymers |
|-------------|----------|----------|
| `train_session2024-06-27...BFF_7.00.pt` | RNA-only design | RNA |
| `train_session2024-07-08...BFF_3.00.pt` | Generalized design | DNA + RNA + Protein |

### Contig Syntax for Multi-Polymer

```python
# Two chains: DNA (20 nt) + Protein (100 aa)
contigmap.contigs=['20 100']
contigmap.polymer_chains=['dna', 'protein']

# Three chains: DNA + RNA + Protein
contigmap.contigs=['33 33 75']
contigmap.polymer_chains=['dna', 'rna', 'protein']

# With fixed motif (e.g., fixed DNA target)
contigmap.contigs=['A1-20/0 100']  # Fix DNA chain A 1-20, design 100 aa protein
```

## Pipeline Integration

### Option 1: DNA-Binding Protein Pipeline
```
Input: Target DNA sequence
    ↓
RFDpoly (design DNA-binding protein)
    ↓
ProteinMPNN (design protein sequence)
    ↓
AlphaFold3 (validate protein structure)
    ↓
DNA docking (validate DNA-protein interaction)
    ↓
Filtering
```

### Option 2: RNA-Binding Protein Pipeline
```
Input: Target RNA sequence
    ↓
RFDpoly (design RNA-binding protein)
    ↓
ProteinMPNN (design protein sequence)
    ↓
AlphaFold3 (validate protein-RNA complex)
    ↓
Filtering
```

### Option 3: Nucleoprotein Assembly Pipeline
```
Input: DNA + RNA sequences
    ↓
RFDpoly (design multi-polymer assembly)
    ↓
ProteinMPNN (design protein sequences)
    ↓
Molecular dynamics (validate assembly stability)
    ↓
Filtering
```

## Output

```
output_prefix/
├── {prefix}_0.pdb       # Generated structure (all chains)
├── {prefix}_0.trb       # Metadata
├── {prefix}_1.pdb
├── ...
```

**Note:** Output is poly-Gly for protein chains (backbone only). Run ProteinMPNN for sequence design. DNA/RNA chains have standard bases.

## Comparison with Other Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| General protein design | RFdiffusion | Mature, well-tested |
| DNA-binding proteins | **RFDpoly** | Only tool with DNA support |
| RNA-binding proteins | **RFDpoly** | Only tool with RNA support |
| Nucleoprotein complexes | **RFDpoly** | Multi-polymer capability |
| Protein-protein | RFdiffusion | Better tested |
| Transcription factors | **RFDpoly** | DNA + protein co-design |
| CRISPR systems | **RFDpoly** | RNA + protein co-design |

## Tips

- **Always use `--config-name=multi_polymer`** — This ensures all settings are consistent with manuscript behavior.
- **Apptainer required** — Primary workflow uses Apptainer container. Native Conda install is possible but less tested.
- **First run slow** — IGSO3 cache precomputation on first run. Subsequent runs are faster (~50s per trajectory).
- **Input PDB workaround** — Even unconditional designs may need a real PDB file path. Use `test_data/DBP035.pdb` as dummy.
- **Weight selection** — Use `BFF_3.00.pt` for mixed polymers, `BFF_7.00.pt` for RNA-only.
- **Contig format** — Space-separated lengths in single quotes: `'33 33 75'`. No commas inside.
- **Polymer chains** — Must match contig length count exactly.
- **Validation** — Always use DNA/RNA docking to validate complexes. Consider PyRosetta for post-processing.

## Full Tutorial

The complete design tutorial with many example commands is available:
- [RFDpoly_tutorial.pdf](https://github.com/RosettaCommons/RFDpoly/blob/main/RFDpoly_tutorial.pdf)
- [External documentation](https://rosettacommons.github.io/RFDpoly/)

## References

- [RFDpoly GitHub](https://github.com/RosettaCommons/RFDpoly)
- [RFDpoly Paper](https://www.biorxiv.org/content/10.1101/2025.10.01.679929v1)
- [RFdiffusion (base model)](https://github.com/RosettaCommons/RFdiffusion)
- [Rosetta Commons](https://www.rosettacommons.org/)

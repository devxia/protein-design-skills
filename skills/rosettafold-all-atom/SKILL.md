---
name: rosettafold-all-atom
description: Alternative Stage 3 validator for all-atom biomolecular complexes — proteins + small molecules + nucleic acids + metals
---

# Alternative Stage 3: RoseTTAFold All-Atom (RFAA)

> **Quick Entry**: Stage 3 alternative | all-atom complex prediction | ligands / DNA / RNA / metals
>
> **Upstream**: `sequence-design` (ProteinMPNN / LigandMPNN) | **Downstream**: `filtering-ranking`

## When to Trigger

- User says "validate with ligand", "predict protein-ligand complex", "protein-DNA complex"
- User wants a structure predictor that natively handles **small molecules**, **DNA/RNA**, or **metal ions**
- AlphaFold3 fails on a particular ligand or nucleic acid input
- User wants confidence metrics that include ligand-interface quality (`pae_inter`)
- User says "RFAA", "RoseTTAFold All-Atom", "Baker lab all-atom predictor"

## What is RFAA?

[RoseTTAFold All-Atom](https://github.com/baker-laboratory/RoseTTAFold-All-Atom) (RFAA) is a generalized biomolecular structure-prediction network from the Baker Lab. Unlike AlphaFold3, which focuses on protein + nucleic acid + limited ligand support, RFAA is built natively for **all-atom biomolecular complexes** from the ground up.

It combines a residue-based representation for amino acids / DNA bases with an atomic representation for all other chemical groups.

### Supported Complex Types

| Molecule Type | RFAA Support | AlphaFold3 Support |
|---------------|--------------|-------------------|
| Protein monomer | ✅ Native | ✅ Native |
| Protein-protein complex | ✅ Native | ✅ Native |
| Protein + DNA/RNA | ✅ Native | ✅ Limited |
| Protein + small molecule | ✅ Native | ⚠️ Ligand list restricted |
| Protein + metal ion | ✅ Native | ⚠️ Limited |
| Covalent modifications | ✅ Native | ⚠️ Limited |
| Higher-order mixed complexes | ✅ Native | ⚠️ Limited |

### Key Output Metrics

- **`mean_plddt`** — per-atom predicted lDDT (B-factors in output PDB)
- **`pae`** — predicted aligned error matrix
- **`pde`** — predicted distance error
- **`pae_inter`** — **interface PAE** (primary quality metric for docks; < 10 = high quality)
- **`pae_prot`** — protein-only PAE

**Paper**: *Generalized biomolecular modeling and design with RoseTTAFold All-Atom* — Science, 2024 — [DOI](https://doi.org/10.1126/science.adl2528)

## Installation

```bash
# Clone repository
git clone https://github.com/baker-laboratory/RoseTTAFold-All-Atom.git
cd RoseTTAFold-All-Atom

# Create conda environment
conda env create -f environment.yaml
conda activate RFAA

# Install SE3Transformer dependency
pip install -e rf2aa/SE3Transformer/

# Install other dependencies
bash install_dependencies.sh

# Download model weights
mkdir weights
# Get RFAA_paper_weights.pt from the repo release instructions
# Typical: wget http://files.ipd.uw.edu/pub/RFAA/RFAA_paper_weights.pt

# Set up databases (~400 GB total)
# UniRef30 (~46 GB), BFD (~272 GB), pdb100 templates (~81 GB), BLAST 2.2.26
export DB_UR30=/path/to/uniref30
export DB_BFD=/path/to/bfd
export BLASTMAT=/path/to/blast-2.2.26/data
```

## When to Use RFAA vs AlphaFold3

| Scenario | Recommended Validator | Why |
|----------|----------------------|-----|
| Standard protein / binder | AlphaFold3 | Best-in-class accuracy on proteins |
| Protein + ligand not in AF3 ligand list | **RFAA** | Broader small-molecule support |
| Protein + DNA/RNA complex | **RFAA** | Native nucleic-acid modeling |
| Protein + metal ion / cofactor | **RFAA** | Native metal support |
| Covalently modified residue | **RFAA** | Covalent bond syntax built-in |
| Need `pae_inter` for docking confidence | **RFAA** | Explicit interface PAE metric |

## Running RFAA as a Standalone Validator

RFAA uses **Hydra** configs. The repository ships configs in `rf2aa/config/inference/`.

### Example 1: Protein Monomer Validation

```bash
python -m rf2aa.run_inference --config-name protein \
  job_name=my_protein
```

Config file (`my_protein.yaml` or passed overrides):

```yaml
defaults:
  - base
  - _self_

job_name: my_protein

protein_inputs:
  A:
    fasta_file: inputs/design.fasta
```

### Example 2: Protein + Small Molecule Validation

```bash
python -m rf2aa.run_inference --config-name protein_sm \
  job_name=protein_ligand
```

Config file:

```yaml
defaults:
  - base
  - protein_sm
  - _self_

job_name: protein_ligand

protein_inputs:
  A:
    fasta_file: inputs/design.fasta

sm_inputs:
  B:
    input: inputs/ligand.sdf
    input_type: sdf
```

### Example 3: Protein-DNA Complex Validation

```bash
python -m rf2aa.run_inference --config-name nucleic_acid \
  job_name=protein_dna
```

Config file:

```yaml
defaults:
  - base
  - nucleic_acid
  - _self_

job_name: protein_dna

protein_inputs:
  A:
    fasta_file: inputs/protein.fasta

na_inputs:
  B:
    fasta: inputs/dna.fasta
    input_type: dna
```

### Example 4: Higher-Order Mixed Complex

```bash
python -m rf2aa.run_inference --config-name protein_na_sm \
  job_name=mixed_complex
```

Config file:

```yaml
defaults:
  - base
  - protein_na_sm
  - _self_

job_name: mixed_complex

protein_inputs:
  A:
    fasta_file: inputs/protein.fasta

na_inputs:
  B:
    fasta: inputs/rna.fasta
    input_type: rna

sm_inputs:
  C:
    input: inputs/ligand.sdf
    input_type: sdf
```

## Covalent Bonds

RFAA supports explicit covalent bond definitions:

```yaml
covalent_bonds:
  - "A,74,ND2:B,1:CW,null"
```

Format: `protein_chain,residue_number,atom_name:sm_chain,atom_index:chiral_1,chiral_2`

Residue numbers and atom indices are **1-indexed**. Use `null` for non-chiral atoms.

## Pipeline Integration

Use RFAA as Stage 3 validation in a custom pipeline:

```
PDBFixer → RFdiffusion / RFdiffusionAA → ProteinMPNN / LigandMPNN → RFAA → Filtering
```

For ligand-aware design specifically:

```bash
# Stage 0
python scripts/run_pdbfixer.py --input target.pdb --output target_fixed.pdb

# Stage 1 (all-atom backbone + ligand context)
/usr/bin/apptainer run --nv rf_se3_diffusion.sif \
    -u run_inference.py \
    inference.deterministic=True \
    diffuser.T=100 \
    inference.output_prefix=outputs/rfaa_stage1/sample \
    inference.input_pdb=target_fixed.pdb \
    contigmap.contigs=['150-150'] \
    inference.ligand=OQO \
    inference.num_designs=10

# Stage 2
python scripts/run_proteinmpnn.py --pdb-path "outputs/rfaa_stage1/*.pdb" --out-folder outputs/seqs/

# Stage 3 (validate with RFAA)
# Build RFAA config pointing at each sequence FASTA + ligand SDF
python -m rf2aa.run_inference --config-name protein_sm \
  job_name=design_0 \
  protein_inputs.A.fasta_file=outputs/seqs/design_0.fa \
  sm_inputs.B.input=inputs/ligand.sdf \
  sm_inputs.B.input_type=sdf

# Stage 4
python scripts/run_filtering.py --results-dir outputs/rfaa/ --custom-metric pae_inter --threshold 10.0
```

## Quality Thresholds

| Metric | Acceptable | Good | Excellent |
|--------|-----------|------|-----------|
| mean_plddt | >60 | >75 | >85 |
| pae_inter | <20 | <15 | <10 |
| pae_prot | <20 | <15 | <10 |

**Note**: RFAA pLDDT tends to be slightly lower than AlphaFold3 pLDDT for the same protein. Use `pae_inter` as the primary ligand-docking quality metric.

## Tips

- If RFAA fails on a hard case, try increasing `loader_params.MAXCYCLE` from 4 to 10 in the config
- RFAA requires SignalP-6 for some features; install separately if needed (licensed)
- Docker is available if conda setup conflicts: `docker build . -t rosetta-fold-all-atom:latest`
- For large complexes, RFAA is memory-hungry — consider reducing batch size or using A100 GPU
- PDB outputs contain predicted lDDT as B-factors for visualization in PyMOL/ChimeraX

## See Also

- `rfdiffusion-all-atom` skill — for **generating** all-atom backbones around ligands
- `boltz-validation` skill — another database-free alternative validator
- `chai1-validation` skill — Apache 2.0 licensed alternative
- `structure-validation` skill — standard AlphaFold3 validation

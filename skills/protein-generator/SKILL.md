---
name: protein-generator
description: Joint sequence + structure generation via RoseTTAFold sequence-space diffusion — motif scaffolding, multistate design, custom potentials
---

# Alternative Stage 1+2: ProteinGenerator

> **Quick Entry**: Stages 1+2 alternative | joint seq+struct generation | motif scaffolding | custom potentials
>
> **Upstream**: `structure-preprocessing` (PDB repair) | **Downstream**: `structure-validation` (AlphaFold3 / Boltz-1 / RFAA)

## When to Trigger

- User says "joint sequence and structure generation", "seq+struct co-design"
- User wants to scaffold a motif with **simultaneous sequence design**
- User needs **multistate design** or sequence-activity relationships
- User wants **custom guidance potentials** (composition, symmetry, contacts)
- User says "ProteinGenerator", "RoseTTAFold sequence diffusion", "Lisanza"
- Standard RFdiffusion → ProteinMPNN feels too decoupled for the design goal

## What is ProteinGenerator?

[ProteinGenerator](https://github.com/RosettaCommons/protein_generator) (Lisanza et al., *Nature Biotechnology* 2023) is a **sequence-space diffusion model** built on RoseTTAFold. Unlike RFdiffusion which diffuses in backbone-coordinate space and requires ProteinMPNN for sequences, ProteinGenerator jointly generates **sequence and structure** in a single pass.

### Key Differences

| Feature | RFdiffusion + ProteinMPNN | ProteinGenerator |
|---------|---------------------------|------------------|
| Diffusion space | Backbone coordinates | Sequence tokens |
| Sequence design | Separate (ProteinMPNN) | Built-in |
| Structure design | Yes | Yes (via RoseTTAFold head) |
| Motif scaffolding | Structure-only context | Sequence + structure context |
| Custom potentials | Potentials in RFdiffusion | `utils/potentials.py` |
| Multi-state design | Difficult | Native support |
| Amino-acid composition | Indirect | Direct control via potentials |
| Best for | Geometric scaffolding | Sequence-aware / multistate / functional design |

### When to Prefer ProteinGenerator

- **Motif scaffolding with sequence constraints**: you need both motif structure AND partial motif sequence preserved
- **Multistate design**: one sequence must adopt multiple conformations
- **Sequence-activity optimization**: you have activity data to guide sequence generation
- **Amino-acid composition control**: e.g., enrich hydrophobics, limit certain residues
- **Repeat / symmetry design**: via custom potentials

### When to Prefer RFdiffusion Instead

- Pure geometric motif scaffolding (especially large proteins >200 aa)
- Unconditional generation of diverse backbones
- When you want the most mature, community-tested tool

## Installation

```bash
# Clone repository
git clone https://github.com/RosettaCommons/protein_generator.git
cd protein_generator

# Create environment
conda env create -f environment.yml
conda activate proteingenerator

# Adjust CUDA / DGL versions in environment.yml if needed for your GPU
# See https://www.dgl.ai/pages/start.html

# Download checkpoints (~2-4 GB each)
mkdir checkpoints
wget http://files.ipd.uw.edu/pub/sequence_diffusion/checkpoints/SEQDIFF_221219_equalTASKS_nostrSELFCOND_mod30.pt \
  -O checkpoints/base.pt
wget http://files.ipd.uw.edu/pub/sequence_diffusion/checkpoints/SEQDIFF_230205_dssp_hotspots_25mask_EQtasks_mod30.pt \
  -O checkpoints/dssp_hotspot.pt

# Optional: add as Jupyter kernel
python -m ipykernel install --user --name proteingenerator --display-name "Python (proteingenerator)"
```

## Running ProteinGenerator

### Interactive Mode (Recommended for Exploration)

```bash
jupyter notebook protein_generator.ipynb
```

The notebook lets you:
1. Load a motif PDB
2. Define which residues to fix vs generate
3. Set composition / symmetry / contact potentials
4. Run the sampler interactively
5. Export an `args.json` for production runs

### Production Mode

After exporting `args.json` from the notebook:

```bash
python ./inference.py -input_json ./examples/out/design_000000_args.json
```

### Example Design Strategies

The `examples/` folder in the repository contains JSON templates for common tasks:

| Example | Purpose |
|---------|---------|
| Motif scaffolding | Fix motif structure + sequence, generate surrounding scaffold |
| Unconditional | De novo sequence-structure generation |
| Symmetry | Repeat-protein design |
| Composition | Amino-acid composition constraints |
| Multistate | One sequence, multiple structural states |

## Motif Scaffolding Workflow

```bash
# 1. Preprocess the motif
python scripts/run_pdbfixer.py --input motif.pdb --output motif_fixed.pdb --keep-chains A

# 2. Interactive: open protein_generator.ipynb
#    - Load motif_fixed.pdb
#    - Mask motif residues you want to keep
#    - Set scaffold length / contiguity potentials
#    - Generate 50 designs
#    - Export args.json

# 3. Production inference
python ./inference.py -input_json ./my_motor_scaffold_args.json

# 4. Validate with AlphaFold3 or RFAA
python scripts/run_alphafold3.py --json af3_input.json --output-dir outputs/af3/

# 5. Filter
python scripts/run_filtering.py --results-dir outputs/af3/ --min-plddt 75
```

## Pipeline Integration

Use ProteinGenerator as a **Stage 1+2 replacement**:

```
PDBFixer → ProteinGenerator → AlphaFold3 / Boltz-1 / RFAA → Filtering
```

Compared to the standard pipeline:

```
PDBFixer → RFdiffusion → ProteinMPNN → AlphaFold3 → Filtering
```

**Trade-off**: ProteinGenerator gives you tighter sequence-structure coupling but is less mature for large unconditional generation.

## Custom Potentials

Add new potentials in `utils/potentials.py`. The repository provides a template class at the top with required methods. A dictionary at the bottom maps argument names to class names.

Example potential ideas:
- **Hydrophobic core** — encourage hydrophobic residues in the core
- **Surface charge** — limit charged residues in the core
- **Interface contacts** — enforce specific residue-residue contacts
- **Symmetry** — repeat-protein design

## Quality Thresholds

Validation is the same as standard pipeline:

| Metric | Acceptable | Good | Excellent |
|--------|-----------|------|-----------|
| pLDDT | >70 | >80 | >90 |
| ipTM (binders) | >0.6 | >0.8 | >0.9 |
| pTM | >0.5 | >0.7 | >0.9 |

## Tips

- Start with the notebook for every new design task — it's the primary interface
- Use the **DSSP + hotspot checkpoint** when secondary structure or hotspot constraints matter
- For motif scaffolding, provide both motif structure AND sequence to the model
- When designing repeat proteins, combine symmetry potentials with length constraints
- Save `args.json` from every successful notebook run — it makes reproduction trivial
- If generation is slow, reduce the number of diffusion steps or use a smaller model

## Common Issues

### "CUDA out of memory"
- Reduce batch size in the notebook
- Use shorter proteins (<250 aa)
- Lower the number of sampled designs per batch

### "Motif not preserved"
- Ensure motif residues are explicitly masked in the input
- Increase the weight of the motif-preservation potential
- Use the DSSP + hotspot checkpoint for stronger conditioning

## See Also

- `structure-generation` skill — RFdiffusion-based backbone generation
- `sequence-design` skill — ProteinMPNN for fixed backbones
- `multiflow-codesign` skill — another joint seq+struct approach
- `chroma-backbone` skill — natural-language-driven joint generation
- `design-patterns` skill — motif scaffolding patterns

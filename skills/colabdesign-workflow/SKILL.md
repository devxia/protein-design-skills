---
name: colabdesign-workflow
description: Alternative end-to-end protein design using ColabDesign — hallucination, inpainting, and fixed backbone design via Google Colab or local install
---

# Alternative Full Pipeline: ColabDesign

## When to Trigger

- User says "ColabDesign", "Google Colab", "halucinate protein", "AF design"
- User wants to design proteins using AlphaFold-based hallucination
- User needs a **free, cloud-based** alternative to local ML tools
- User wants fixed-backbone design without RFdiffusion
- User wants to design proteins by specifying function/constraints rather than structure
- User says "I don't have a GPU" or "I want to use Colab"
- User wants TrRosetta-based design (TrDesign)

## ColabDesign Overview

[ColabDesign](https://github.com/sokrypton/ColabDesign) by Sergey Ovchinnikov is a Python library that makes protein design accessible via **Google Colab** (free GPU) or local installation. It provides multiple design paradigms:

| Module | What It Does | Best For |
|--------|--------------|----------|
| **AfDesign** (`af/`) | AlphaFold-based hallucination and inpainting | De novo design, binder design, motif scaffolding |
| **TrDesign** (`tr/`) | TrRosetta-based design | Fast fixed-backbone design |
| **ProteinMPNN** (`mpnn/`) | Sequence design on fixed backbone | Inverse folding (same as standalone ProteinMPNN) |
| **Rfdiffusion** (`rf/`) | RFdiffusion wrapper | Backbone generation (same as standalone) |

### Why ColabDesign?

| Aspect | Local Pipeline | ColabDesign |
|--------|---------------|-------------|
| GPU required | Yes (local) | Free Colab GPU |
| Setup | Complex (conda, deps) | One-click in browser |
| Cost | Hardware + electricity | Free (or Colab Pro) |
| Accessibility | Requires Linux/CUDA | Any device with browser |
| Reproducibility | Environment-dependent | Cloud snapshots |
| Batch size | Limited by local GPU | Colab GPU limits |
| Customization | Full control | Notebook-based |

## Installation (Local)

```bash
# Install from PyPI
pip install colabdesign

# Or from source
git clone https://github.com/sokrypton/ColabDesign.git
cd ColabDesign
pip install -e .
```

## Design Workflows

### Workflow 1: AfDesign — Hallucination

Generate de novo protein structures by "hallucinating" sequences that AlphaFold predicts with high confidence:

```python
from colabdesign import mk_afdesign_model, clear_mem

# Initialize hallucination model
clear_mem()
af_model = mk_afdesign_model(protocol="hallucination")

# Hallucinate a 100-residue protein
af_model.prep_inputs(length=100)

# Run design
af_model.design_logits(iters=100)
af_model.design_semigreedy(iters=100)

# Save result
af_model.save_pdb("hallucinated_design.pdb")
af_model.plot()
```

**What happens:**
1. Start with random sequence
2. AlphaFold predicts structure
3. Optimize sequence to maximize pLDDT + pTM
4. Result: novel protein with predicted structure

### Workflow 2: AfDesign — Binder Design

Design a protein binder to a specific target:

```python
from colabdesign import mk_afdesign_model, clear_mem

clear_mem()
af_model = mk_afdesign_model(protocol="binder")

# Load target structure
af_model.prep_inputs(pdb_filename="target.pdb",
                     chain="A",
                     hotspot="A30,A33,A34",  # Target hotspots
                     binder_length=100)       # Binder size

# Design binder
af_model.design_logits(iters=100)
af_model.design_semigreedy(iters=100)

# Save
af_model.save_pdb("binder_design.pdb")
```

### Workflow 3: AfDesign — Motif Scaffolding

Scaffold a functional motif into a new protein:

```python
from colabdesign import mk_afdesign_model, clear_mem

clear_mem()
af_model = mk_afdesign_model(protocol="fixed")

# Load motif structure
af_model.prep_inputs(pdb_filename="motif.pdb",
                     chain="A",
                     pos="A10-30",      # Motif positions to keep
                     length=150)         # Total protein length

# Design scaffold around motif
af_model.design_logits(iters=100)
af_model.design_semigreedy(iters=100)

af_model.save_pdb("scaffolded_design.pdb")
```

### Workflow 4: TrDesign — Fast Fixed-Backbone

For quick fixed-backbone sequence design (faster than AfDesign):

```python
from colabdesign import mk_trdesign_model

# Initialize TrRosetta model
tr_model = mk_trdesign_model("xx")  # Model version

# Load backbone
tr_model.prep_inputs(pdb_filename="backbone.pdb")

# Design sequence
tr_model.design(iters=100)

# Save
sequence = tr_model.get_seq()
print(f"Designed sequence: {sequence}")
```

### Workflow 5: ProteinMPNN (in ColabDesign)

Same functionality as standalone ProteinMPNN but integrated:

```python
from colabdesign.mpnn import mk_mpnn_model

mpnn_model = mk_mpnn_model()

# Design on backbone
mpnn_model.prep_inputs(pdb_filename="backbone.pdb",
                       chain="A")

# Sample sequences
sequences = mpnn_model.sample(num=8, temperature=0.1)
for i, seq in enumerate(sequences):
    print(f">design_{i}")
    print(seq)
```

## Key Parameters

### Hallucination Parameters

| Parameter | Description | Typical Value |
|-----------|-------------|---------------|
| `length` | Protein length | 50-500 |
| `iters` | Optimization iterations | 50-200 |
| `num_models` | Number of AlphaFold models | 1-5 (more = slower but better) |
| `recycles` | AlphaFold recycling cycles | 0-3 |

### Binder Design Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `pdb_filename` | Target structure | `"target.pdb"` |
| `chain` | Target chain | `"A"` |
| `hotspot` | Target hotspot residues | `"A30,A33,A34"` |
| `binder_length` | Length of binder to design | 50-150 |

### Loss Functions (Design Objectives)

```python
# Available loss terms for optimization
af_model.set_opt(
    plddt=True,      # Maximize pLDDT (structure confidence)
    ptm=True,        # Maximize pTM (template modeling score)
    i_ptm=True,      # Maximize ipTM (interface quality for binders)
    rmsd=True,       # Minimize RMSD to target
    con=True,        # Secondary structure constraints
    dgram_cce=True,  # Distance map loss
)
```

## Pipeline Integration

### ColabDesign-Only Pipeline
```
Option A: Hallucination
  AfDesign hallucination → Save PDB → Validate with AlphaFold3/OmegaFold

Option B: Binder Design  
  AfDesign binder → Save PDB + sequence → Validate with AlphaFold3 multimer

Option C: Motif Scaffold
  AfDesign fixed → Save PDB → ProteinMPNN → AlphaFold3
```

### Hybrid Pipeline (ColabDesign + Local Tools)
```
Stage 1: ColabDesign (AfDesign hallucination on free Colab GPU)
    ↓
Stage 2: Local ProteinMPNN (batch sequence design)
    ↓
Stage 3: Local AlphaFold3 (validate top designs)
    ↓
Stage 4: Local Filtering
```

**Why hybrid:**
- Use free Colab GPU for expensive hallucination/binder design
- Use local resources for batch sequence design and validation
- Best of both worlds

### Comparison with Standard Pipeline

| Task | Standard Pipeline | ColabDesign Pipeline |
|------|-------------------|---------------------|
| De novo monomer | RFdiffusion + ProteinMPNN | AfDesign hallucination |
| Binder design | RFdiffusion + ProteinMPNN | AfDesign binder |
| Motif scaffold | RFdiffusion + ProteinMPNN | AfDesign fixed backbone |
| Fixed backbone design | ProteinMPNN | TrDesign or ProteinMPNN |
| Cost | Requires GPU | Free (Colab) |
| Speed | Fast (local GPU) | Moderate (Colab GPU queue) |
| Batch processing | Yes | Limited |

## Google Colab Notebooks

ColabDesign provides ready-to-use notebooks:

| Notebook | Purpose | Link |
|----------|---------|------|
| AfDesign Hallucination | De novo design | [Open in Colab](https://colab.research.google.com/github/sokrypton/ColabDesign/blob/main/af/design.ipynb) |
| AfDesign Binder | Binder design | [Open in Colab](https://colab.research.google.com/github/sokrypton/ColabDesign/blob/main/af/examples/binder_design.ipynb) |
| AfDesign Motif | Motif scaffolding | [Open in Colab](https://colab.research.google.com/github/sokrypton/ColabDesign/blob/main/af/examples/motif_scaffolding.ipynb) |
| TrDesign | Fixed backbone design | [Open in Colab](https://colab.research.google.com/github/sokrypton/ColabDesign/blob/main/tr/design.ipynb) |
| ProteinMPNN | Sequence design | [Open in Colab](https://colab.research.google.com/github/sokrypton/ColabDesign/blob/main/mpnn/design.ipynb) |

## Tips

- **Start with Colab**: Try designs in Google Colab first (free), then scale to local
- **Hallucination length**: Start with 50-150 residues for best results
- **Binder hotspots**: Choose exposed residues on target surface (check with PyMOL)
- **Loss weights**: Adjust loss term weights based on design goal
- **Multiple seeds**: Run multiple designs with different random seeds
- **Model ensemble**: Use `num_models=5` for more robust predictions (slower)
- **Recycling**: Use `recycles=3` for better accuracy at the cost of speed
- **TrDesign speed**: TrDesign is ~10x faster than AfDesign for fixed-backbone tasks
- **Discord community**: Join [ColabDesign Discord](https://discord.gg/gna8maru7d) for help

## When to Use ColabDesign vs Standard Pipeline

| Scenario | Recommended Approach |
|----------|---------------------|
| No local GPU | ColabDesign on Google Colab |
| Quick prototyping | ColabDesign (faster iteration) |
| De novo design | Either (both work well) |
| Binder design | Either (AfDesign binder is excellent) |
| Batch processing (100+ designs) | Standard pipeline (local GPU) |
| Custom constraints | ColabDesign (more flexible loss functions) |
| Production pipeline | Standard pipeline (more reproducible) |

## References

- [ColabDesign GitHub](https://github.com/sokrypton/ColabDesign)
- [ColabDesign Discord](https://discord.gg/gna8maru7d)
- [Sergey Ovchinnikov's Talk](https://www.youtube.com/watch?v=2HmXwlKWMVs)
- [ColabDesign Slides](https://docs.google.com/presentation/d/1Zy7lf_LBK0_G3e7YQLSPP5aj_-AR5I131fTsxJrLdg4/)

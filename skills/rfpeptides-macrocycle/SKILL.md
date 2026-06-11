---
name: rfpeptides-macrocycle
description: Macrocyclic peptide design with RFpeptides (RFdiffusion 2025 protocol) — 12-18 aa cyclic peptide binders and monomers
---

# Alternative Stage 1: RFpeptides Macrocyclic Peptide Design

## When to Trigger

- User says "macrocyclic peptide", "cyclic peptide", "macrocycle binder"
- User wants 12-18 residue cyclic peptides with atomic accuracy
- User needs peptide binders with head-to-tail cyclization
- User requests disulfide-free cyclic peptide design
- User wants to design cyclic peptide inhibitors

## RFpeptides Overview

[RFpeptides](https://github.com/RosettaCommons/RFdiffusion) is a protocol published in 2025 (Rettie, Juergens, Adebomi, et al.) for designing **macrocyclic peptides** (12-18 aa) that bind target proteins with atomic accuracy using RFdiffusion. Unlike DiffPepBuilder which uses DDP and PyRosetta, RFpeptides uses the standard RFdiffusion inference pipeline with two additional flags.

### Key Differences from DiffPepBuilder

| Feature | RFpeptides | DiffPepBuilder |
|---------|-----------|----------------|
| Peptide length | 12-18 aa (macrocyclic) | 8-30 aa (linear or disulfide) |
| Cyclization | Head-to-tail macrocycle | Disulfide bonds |
| Diffusion model | RFdiffusion (standard) | Custom diffusion |
| GPU requirement | Single GPU | Multi-GPU (DDP) |
| Post-processing | Not included | AMBER + Rosetta |
| Docking | Not included | Built-in DiffPepDock |
| License | BSD (open) | Academic |
| Speed | Faster (single GPU) | Slower |

## Requirements

- RFdiffusion installed (standard SE3nv environment)
- Model checkpoints downloaded (same as standard RFdiffusion)
- Input target PDB (for binder design)

## Two Modes

### Mode 1: Macrocyclic Binder Design

Design a head-to-tail cyclic peptide that binds a target protein:

```bash
conda run -n SE3nv python scripts/run_inference.py \
    --config-name base \
    inference.output_prefix=outputs/macrocycle_binder \
    inference.num_designs=50 \
    'contigmap.contigs=[12-18 A3-117/0]' \
    inference.input_pdb=input_pdbs/target.pdb \
    inference.cyclic=True \
    diffuser.T=50 \
    inference.cyc_chains='a' \
    ppi.hotspot_res=[A51,A52,A50,A48,A62,A65] \
    inference.output_prefix=outputs/macrocycle_binder
```

**Key flags:**
- `inference.cyclic=True`: Enable macrocycle design
- `inference.cyc_chains='a'`: Specify which chain(s) to cyclize (can be 'abcd' for multiple)

**Note:** The contig should place the generated peptide chain first, followed by `/0` and the target chain. In the example above, the peptide is chain A (generated, 12-18 aa) and the target is chain A3-117 (from input PDB).

### Mode 2: Macrocyclic Monomer Design

Design a standalone cyclic peptide (no target):

```bash
conda run -n SE3nv python scripts/run_inference.py \
    --config-name base \
    inference.output_prefix=outputs/macrocycle_monomer \
    inference.num_designs=50 \
    'contigmap.contigs=[12-18]' \
    inference.cyclic=True \
    inference.cyc_chains='a' \
    diffuser.T=50
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `inference.cyclic` | bool | False | **Required.** Enable macrocyclic peptide design |
| `inference.cyc_chains` | str | 'a' | Chain letter(s) to cyclize (e.g., 'a', 'ab', 'abcd') |
| `contig` | str | — | Contig string. For binder: `[12-18 TARGET_CHAIN/0]`. For monomer: `[12-18]` |
| `input_pdb` | str | null | Target PDB (required for binder design) |
| `hotspot_res` | list | null | Hotspot residues on target (binder design) |
| `diffuser.T` | int | 50 | Diffusion steps (50 is standard) |
| `num_designs` | int | 10 | Number of designs to generate |
| `output_prefix` | str | — | Output path prefix |

## Pipeline Integration

### Macrocyclic Peptide Binder Pipeline
```
Stage 0: PDBFixer (target structure)
    ↓
Stage 1: RFpeptides (generate 12-18aa macrocyclic binders)
    ↓
Stage 2: ProteinMPNN (design sequences for backbones)
    ↓
Stage 3: AlphaFold3 / Boltz-1 (validate peptide-target complex)
    ↓
Stage 4: Filtering + Interface Analysis
```

### Macrocyclic Monomer Pipeline
```
Stage 1: RFpeptides (generate 12-18aa cyclic monomers)
    ↓
Stage 2: ProteinMPNN (design sequences)
    ↓
Stage 3: AlphaFold3 / OmegaFold (validate structure)
    ↓
Stage 4: Filtering
```

## Standalone Script Usage

```bash
python scripts/run_rfdiffusion.py \
    --contig "[12-18 A3-117/0]" \
    --input-pdb target.pdb \
    --num-designs 50 \
    --output-prefix outputs/macrocycle \
    --verbose
```

**Note:** The standalone script may not yet support `--cyclic` flag. If not supported, use direct RFdiffusion execution or update the script.

## Output Characteristics

- **Backbone**: Poly-Glycine, N/CA/C/O only (standard RFdiffusion output)
- **Cyclization**: Head-to-tail bond implied by design; sidechain cyclization not supported
- **Sequence**: Designed separately with ProteinMPNN (Stage 2)
- **Validation**: Use AlphaFold3 or Boltz-1 for peptide-target complex prediction

## Tips

- Peptide length 12-18 aa is the sweet spot for RFpeptides
- For binder design, hotspots should be on the **target protein surface**
- `cyc_chains` is zero-indexed chain letter (usually 'a' for single peptide)
- Multiple chains can be cyclized: `cyc_chains='abcd'` if contig supports it
- Cyclic peptides often have higher stability than linear peptides
- For therapeutic applications, consider ADMET properties in Stage 4 filtering

## Comparison with Other Peptide Tools

| Tool | Cyclization | Length | Best For |
|------|------------|--------|----------|
| **RFpeptides** | Head-to-tail | 12-18 aa | Macrocyclic binders, single GPU |
| **DiffPepBuilder** | Disulfide | 8-30 aa | Disulfide-bonded peptides, docking |
| **RFdiffusion (cyclic)** | Head-to-tail | Any | General cyclic proteins |

## When to Use RFpeptides vs DiffPepBuilder

| Design Goal | Recommended Tool |
|-------------|-----------------|
| 12-18 aa head-to-tail macrocycle | **RFpeptides** (faster, single GPU) |
| 8-15 aa disulfide-bonded peptide | **DiffPepBuilder** |
| Peptide docking (known sequence) | **DiffPepDock** |
| >30 aa cyclic protein | **RFdiffusion** with `cyclic=True` |

## References

- [RFdiffusion GitHub — RFpeptides Section](https://github.com/RosettaCommons/RFdiffusion#macrocyclic-peptide-design-with-rfpeptides)
- Rettie, Juergens, Adebomi, et al. (2025). "De novo design of macrocyclic peptides..."
- [RFdiffusion Paper](https://www.biorxiv.org/content/10.1101/2022.12.09.519842v1)

---
name: igdiff-antibody
description: De novo antibody design with IgDiff — SE(3) diffusion model specialized for antibody variable domains with 74% CDR H3 design success
---

# Specialized Antibody Design: IgDiff

## When to Trigger

- User says "IgDiff", "antibody diffusion", "design antibody"
- User needs **de novo antibody variable domain** generation
- User wants to redesign **CDR loops** (especially CDR H3)
- User needs **light chain pairing** for existing heavy chain
- User wants antibody-specific design (better than general RFdiffusion)
- User says "design CDR", "antibody humanization", "CDR grafting"

## IgDiff Overview

[IgDiff](https://github.com/amelie-iska/IgDiff) is a **specialized antibody diffusion model** based on FrameDiff's SE(3) framework. Developed by Exscientia and Oxford University, it's specifically trained on ~150,000 synthetic antibody structures and achieves **superior results on antibody tasks** compared to general-purpose models like RFdiffusion.

### Key Differences from RFdiffusion for Antibodies

| Feature | RFdiffusion | IgDiff |
|---------|-------------|--------|
| Training data | General proteins (~20k) | Antibodies (~150k) |
| CDR H3 success | **6%** | **74%** |
| Light chain pairing | **0%** | **93%** |
| Self-consistency | Variable | **88% < 2Å RMSD** |
| Heavy+light chains | Limited | **Native support** |
| Experimental validation | N/A | **28/28 expressed** |
| Experimental yield | N/A | **High yield** |

**Key insight**: IgDiff is **the tool of choice** for antibody design. RFdiffusion's general architecture performs poorly on antibody-specific tasks.

## Installation

```bash
# Clone repository
git clone https://github.com/amelie-iska/IgDiff.git
cd IgDiff

# Download model weights
git clone https://huggingface.co/AmelieSchreiber/IgDiff huggingface_weights

# Create conda environment
conda env create -f se3.yml
conda activate igdiff
```

## Design Modes

### Mode 1: Unconditional Antibody Generation

Generate complete antibody variable domains (VH + VL):

```bash
python experiments/inference_se3_diffusion.py \
    --model_path huggingface_weights/ \
    --output_dir outputs/unconditional \
    --num_samples 50
```

### Mode 2: CDR Loop Redesign

Redesign all CDR loops while keeping the framework fixed:

```bash
python experiments/inference_se3_diffusion.py \
    --model_path huggingface_weights/ \
    --input_pdb input_antibody.pdb \
    --redesign_cdrs H1,H2,H3,L1,L2,L3 \
    --output_dir outputs/cdr_redesign \
    --num_samples 50
```

### Mode 3: CDR H3 Design (Most Common)

Design CDR H3 with specific length:

```bash
python experiments/inference_se3_diffusion.py \
    --model_path huggingface_weights/ \
    --input_pdb input_antibody.pdb \
    --redesign_cdrs H3 \
    --cdr_h3_length 12 \
    --output_dir outputs/cdr_h3 \
    --num_samples 100
```

**Key parameters:**
- `--cdr_h3_length`: Target CDR H3 length (typically 5-25 residues)
- Higher sampling = more diversity

### Mode 4: Light Chain Pairing

Design a light chain for an existing heavy chain:

```bash
python experiments/inference_se3_diffusion.py \
    --model_path huggingface_weights/ \
    --heavy_chain_pdb heavy_chain_only.pdb \
    --output_dir outputs/light_chain \
    --num_samples 50
```

### Mode 5: Full Light Chain Design

Generate complete light chain with heavy chain fixed:

```bash
python experiments/inference_se3_diffusion.py \
    --model_path huggingface_weights/ \
    --input_pdb heavy_chain_only.pdb \
    --design_light_chain \
    --output_dir outputs/full_light \
    --num_samples 50
```

## Parameters Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--model_path` | string | — | Path to model weights |
| `--output_dir` | string | outputs/ | Output directory |
| `--num_samples` | int | 10 | Number of designs |
| `--input_pdb` | string | — | Input antibody structure |
| `--redesign_cdrs` | string | — | Comma-separated CDRs to redesign |
| `--cdr_h3_length` | int | — | Target CDR H3 length |
| `--heavy_chain_pdb` | string | — | Heavy chain only (for light chain pairing) |
| `--design_light_chain` | flag | False | Design full light chain |
| `--temperature` | float | 1.0 | Sampling temperature |

## Pipeline Integration

### Antibody Design Pipeline
```
Stage 0: PDBFixer (prepare input antibody)
    ↓
Stage 1: IgDiff (generate/redesign antibody)
    ↓
Stage 2: AbMPNN (antibody sequence design on IgDiff backbones)
    ↓
Stage 3: ABodyBuilder3 or AlphaFold3 (validate structure)
    ↓
Stage 4: Filtering (pLDDT > 80, CDR RMSD < 2Å)
```

### Comparison: General vs Specialized Antibody Pipeline

| Pipeline | Stage 1 | Best For |
|----------|---------|----------|
| General | RFdiffusion | General proteins |
| Specialized | IgDiff | **Antibodies** |

### Why IgDiff + AbMPNN?
- IgDiff generates **antibody-specific backbones** with correct CDR geometry
- AbMPNN (antibody variant of ProteinMPNN) designs sequences on IgDiff backbones
- Together they achieve much higher experimental success than RFdiffusion + ProteinMPNN

## Tips

- **CDR H3 is hardest**: Focus computational budget on CDR H3 (most variable, often determines binding)
- **Framework preservation**: Use `--redesign_cdrs` to keep framework constant (maintains stability)
- **Length matters**: CDR H3 length strongly correlates with binding properties
- **Pairing check**: Always validate heavy-light chain packing after design
- **Experimental validation**: IgDiff has strong experimental track record (28/28 expressed)
- **Humanization**: Use IgDiff to redesign CDRs while keeping human framework
- **Affinity maturation**: Start with known binder, redesign CDRs for improved affinity

## References

- [IgDiff GitHub](https://github.com/amelie-iska/IgDiff)
- [IgDiff HuggingFace](https://huggingface.co/AmelieSchreiber/IgDiff)
- [IgDiff Paper](https://arxiv.org/abs/2405.07622)
- [ABodyBuilder3](https://github.com/Exscientia/ABodyBuilder3)
- [FrameDiff (base framework)](https://github.com/jasonkyuyim/se3_diffusion)

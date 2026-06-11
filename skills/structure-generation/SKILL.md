---
name: structure-generation
description: Protein backbone generation with RFdiffusion (Stage 1) — all modes including advanced features
---

# Stage 1: Structure Generation (RFdiffusion)

## When to Trigger

- User says "generate a protein", "design a backbone", "create a scaffold"
- User requests binder design: "design a binder for X"
- User requests motif scaffolding: "scaffold around this motif"
- User requests symmetric oligomer: "design a trimer"
- User requests partial redesign: "redesign this loop", "mutate this region"
- User requests cyclic peptide: "design a cyclic peptide"
- User requests secondary structure specification: "design with helix here"

## RFdiffusion Overview

RFdiffusion generates protein backbone structures (poly-Glycine, only N/CA/C/O atoms) using a diffusion model. The contig parameter is the single most important argument — it defines what to generate and what to keep.

## Model Checkpoints (Auto-selected)

| Checkpoint | Auto-selected When | Purpose |
|------------|-------------------|---------|
| `Base_ckpt.pt` | Default (no special flags) | Unconditional, motif scaffolding |
| `Complex_base_ckpt.pt` | `ppi.hotspot_res` set | Binder design (PPI) |
| `Complex_Fold_base_ckpt.pt` | `scaffoldguided=True` | Scaffold-guided + complex |
| `InpaintSeq_ckpt.pt` | `inpaint_seq` or `provide_seq` or `inpaint_str` set | Inpainting |
| `ActiveSite_ckpt.pt` | Manual override only | Very small motif scaffolding |
| `Base_epoch8_ckpt.pt` | Manual override only | Alternative base model (symmetric motifs) |

You can override with `ckpt_override_path` if needed.

## Contig Syntax (Core!)

| Pattern | Meaning | Example Use Case |
|---------|---------|-----------------|
| `[150-150]` | Unconditional monomer, 150 aa | De novo protein |
| `[10-40/A163-181/10-40]` | Motif scaffolding | Keep A163-181, generate flanks |
| `[B1-100/0 100-100]` | Binder design | 100-res binder for target B1-100 |
| `[A1-50/0 10-20/A71-150]` | Partial diffusion | Keep termini, redesign loop |
| `[360]` | Symmetric oligomer | 360-res symmetric assembly |
| `[12-18]` | Macrocyclic peptide | 12-18 aa cyclic peptide |

**Syntax elements:**
- `X-Y`: Generate X to Y residues (range)
- `AX-Y`: Fix chain A residues X to Y from input PDB
- `0`: Chain break (binder design: target/binder interface)
- `/`: Region separator

## Standalone Script

```bash
python scripts/run_rfdiffusion.py \
  --output-prefix outputs/design \
  --contig "[150-150]" \
  --num-designs 10 \
  --diffuser-T 50
```

For motif/binder/partial designs, provide `--input-pdb`:

```bash
python scripts/run_rfdiffusion.py \
  --input-pdb target_fixed.pdb \
  --output-prefix outputs/binder \
  --contig "[B1-100/0 100-100]" \
  --num-designs 50 \
  --hotspot-res A30 A33 A34 \
  --diffuser-T 50
```

## Basic Parameters

| Parameter | CLI Flag | Required | Default | Description |
|-----------|----------|----------|---------|-------------|
| `output_prefix` | `--output-prefix` | ✅ | — | Output path prefix |
| `contig` | `--contig` | ✅ | — | Contig string (use single quotes in shell) |
| `num_designs` | `--num-designs` | ❌ | 10 | Number of backbones to generate |
| `input_pdb` | `--input-pdb` | ❌ | — | Required for motif/binder/partial |
| `hotspot_res` | `--hotspot-res` | ❌ | — | Hotspot residues (binder design) |
| `symmetry` | `--symmetry` | ❌ | — | `c2`, `d2`, `tetrahedral`, `octahedral`, `icosahedral` |
| `diffuser_T` | `--diffuser-T` | ❌ | 50 | Diffusion timesteps (lower=faster) |
| `ckpt_override_path` | `--checkpoint` | ❌ | — | Custom model checkpoint |
| `skip_preprocessing` | `--skip-preprocessing` | ❌ | false | Skip auto PDBFixer |
| `keep_chains` | `--keep-chains` | ❌ | — | Chains to keep in preprocessing |

## Advanced Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `partial_T` | int | Partial diffusion: noise for N steps then denoise (e.g., 10) |
| `provide_seq` | str | Keep sequence fixed during partial diffusion (e.g., "[172-205]") |
| `inpaint_seq` | str | Mask sequence identity of residues (e.g., "[A163-168/A170-171]") |
| `inpaint_str` | str | Mask 3D structure while keeping sequence (e.g., "[B165-178]") |
| `inpaint_str_helix` | str | Specify masked residues as helix |
| `inpaint_str_strand` | str | Specify masked residues as strand |
| `inpaint_str_loop` | str | Specify masked residues as loop |
| `scaffoldguided` | bool | Enable fold conditioning (secondary structure + block adjacency) |
| `scaffold_dir` | str | Directory with scaffold ss/adj files |
| `cyclic` | bool | Design macrocyclic peptides |
| `cyc_chains` | str | Chain(s) to cyclize (default: 'a') |
| `potentials` | list | Guiding potentials for design constraints |
| `final_step` | int | Stop trajectory early (e.g., 25 instead of 50). Speeds up inference. |
| `noise_scale_ca` | float | Scale CA noise during sampling [0.0-1.0]. Lower = less diversity, higher quality. Default 1.0. |
| `noise_scale_frame` | float | Scale frame noise during sampling [0.0-1.0]. Lower = less diversity, higher quality. Default 1.0. |

## Common Design Patterns

### Unconditional Monomer (150 aa)
```bash
python scripts/run_rfdiffusion.py \
  --contig "[150-150]" \
  --output-prefix outputs/monomer \
  --num-designs 20
```

### Motif Scaffolding (fix A163-181, generate 10-40 aa flanks)
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb inputs/5TPN.pdb \
  --contig "[10-40/A163-181/10-40]" \
  --output-prefix outputs/motif \
  --num-designs 5
```

### Binder Design (100-res binder for target B1-100, hotspots A30,A33,A34)
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb inputs/target.pdb \
  --contig "[B1-100/0 100-100]" \
  --hotspot-res A30 A33 A34 \
  --output-prefix outputs/binder \
  --num-designs 50
```

### Partial Diffusion (keep A1-50 and A71-150, redesign 10-20 aa loop)
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb inputs/structure.pdb \
  --contig "[A1-50/0 10-20/A71-150]" \
  --output-prefix outputs/partial \
  --num-designs 5 \
  --diffuser-T 25
```

## Advanced Design Patterns

### Partial Diffusion with Fixed Sequence
Keep some sequence fixed while diffusing structure:
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb inputs/structure.pdb \
  --contig "[A1-50/0 10-20/A71-150]" \
  --partial-T 10 \
  --provide-seq "[172-205]" \
  --output-prefix outputs/partial_seq \
  --num-designs 10
```

### Sequence Inpainting (Mask Sequence Identity)
Redesign sequence of specific residues while keeping structure:
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb inputs/structure.pdb \
  --contig "[A1-150]" \
  --inpaint-seq "[A30-40/A60-70]" \
  --output-prefix outputs/inpaint_seq \
  --num-designs 20
```

### Structure Inpainting (Redesign Structure of Region)
Redesign structure while keeping sequence identity:
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb inputs/structure.pdb \
  --contig "[A1-150]" \
  --inpaint-str "[B165-178]" \
  --output-prefix outputs/inpaint_str \
  --num-designs 20
```

### Secondary Structure Specification
Specify helix/strand/loop for masked regions:
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb inputs/structure.pdb \
  --contig "[A1-50/0 20-30/A81-150]" \
  --inpaint-str-helix "[A51-60]" \
  --inpaint-str-strand "[A61-70]" \
  --output-prefix outputs/ss_spec \
  --num-designs 10
```

### Fold Conditioning (Scaffold-Guided)
Use secondary structure and block adjacency to guide design:
```bash
python scripts/run_rfdiffusion.py \
  --contig "[150-150]" \
  --scaffoldguided \
  --scaffold-dir path/to/scaffold/files \
  --output-prefix outputs/scaffoldguided \
  --num-designs 20
```

### Macrocyclic Peptide Design
```bash
python scripts/run_rfdiffusion.py \
  --contig "[12-18]" \
  --cyclic \
  --cyc-chains a \
  --output-prefix outputs/cyclic \
  --num-designs 50
```

### Macrocyclic Binder Design
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb inputs/target.pdb \
  --contig "[B1-50/0 12-18]" \
  --hotspot-res A30 A33 \
  --cyclic \
  --cyc-chains b \
  --output-prefix outputs/cyclic_binder \
  --num-designs 50
```

### Potentials-Guided Design
Use auxiliary potentials to guide diffusion:
```bash
python scripts/run_rfdiffusion.py \
  --contig "[100-100]" \
  --potentials "type:monomer_ROG,weight:1.0" \
  --output-prefix outputs/potential \
  --num-designs 20
```

### Symmetric Oligomers
```bash
python scripts/run_rfdiffusion.py \
  --contig "[100]" \
  --symmetry c4 \
  --output-prefix outputs/c4 \
  --num-designs 20
```

**Supported symmetries:** `c2`, `c3`, `c4`, `c5`, `c6`, `d2`, `d3`, `d4`, `tetrahedral`, `octahedral`, `icosahedral`

### Enzyme Active Site Scaffolding
For very small motifs, use the ActiveSite checkpoint:
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb inputs/enzyme.pdb \
  --contig "[10-20/A50-55/10-20]" \
  --checkpoint models/ActiveSite_ckpt.pt \
  --output-prefix outputs/enzyme \
  --num-designs 50
```

## Output Format

```
outputs/
├── design_0.pdb      # Final backbone (poly-Gly, t=1)
├── design_0.trb      # Metadata (pickle)
├── design_1.pdb
├── design_1.trb
└── traj/             # Optional trajectory
```

**PDB characteristics:**
- Residue type: all Glycine (no sequence information yet)
- Atoms: N, CA, C, O only (backbone)
- B-factor: 0=diffused region, 1=fixed motif
- Chain IDs: auto-assigned (design=A, target=next letter)

## Workflow

```
User requests backbone generation
     ↓
Determine design type from contig + context
     ↓
If --input-pdb provided → auto-run PDBFixer (unless --skip-preprocessing)
     ↓
python scripts/run_rfdiffusion.py --contig ... --output-prefix ...
     ↓
Track progress with python scripts/summarize_outputs.py --output-dir outputs/
     ↓
PDB list ready → Stage 2 (ProteinMPNN)
```

## Inference-Time Optimization Parameters

Based on the RFdiffusion GitHub documentation, these parameters can improve quality or speed:

| Parameter | Effect | Recommendation |
|-----------|--------|---------------|
| `inference.final_step=25` | Stop diffusion at step 25 | **Speedup** with minimal quality loss |
| `denoiser.noise_scale_ca=0.5` | Reduce CA noise | **Higher quality**, less diversity |
| `denoiser.noise_scale_frame=0.5` | Reduce frame noise | **Higher quality**, less diversity |
| `denoiser.noise_scale_ca=0` | No CA noise | Maximum quality, minimum diversity |
| `diffuser.T=25` | Fewer diffusion steps | **5-10x speedup** for screening |

### Speed vs Quality Trade-off

```bash
# Fast screening (lower quality, much faster)
conda run -n SE3nv python scripts/run_inference.py \
    'contigmap.contigs=[150-150]' \
    inference.output_prefix=outputs/fast \
    inference.num_designs=100 \
    diffuser.T=25 \
    inference.final_step=20

# High quality (slower, better structures)
conda run -n SE3nv python scripts/run_inference.py \
    'contigmap.contigs=[150-150]' \
    inference.output_prefix=outputs/highq \
    inference.num_designs=10 \
    diffuser.T=50 \
    denoiser.noise_scale_ca=0.5 \
    denoiser.noise_scale_frame=0.5
```

## Key Tips

- **Contig must be shell-quoted**: `'contigmap.contigs=[150-150]'`
- `model`, `diffuser`, `preprocess` configs are auto-loaded from checkpoint
- For binder design, always provide `input_pdb` with target structure
- For motif scaffolding, residue numbers in contig must match input PDB exactly
- Lower `diffuser_T` (25) for partial diffusion (faster, more conservative)
- `partial_T` adds noise for N steps then denoises — good for generating diversity around a structure
- `inpaint_seq` masks sequence identity but keeps 3D structure — use for redesigning sequence of a region
- `inpaint_str` masks 3D structure but keeps sequence — use for redesigning structure while preserving sequence
- Cyclic peptides: contig length range should match desired peptide length (e.g., `[12-18]`)
- **Noise scale reduction**: Try `denoiser.noise_scale_ca=0.5` for constrained designs — improves quality at the cost of diversity
- **Early stopping**: `inference.final_step=25` provides significant speedup with minimal quality loss

## RFdiffusion Not Installed?

You have alternatives:

| Alternative | Install | License | Notes |
|-------------|---------|---------|-------|
| Chroma | `pip install chroma-ai` | MIT | Fast, good for unconditional designs |
| FoldFlow | See foldflow docs | MIT | SE(3) flow matching |
| FrameDiff | See framediff docs | MIT | MIT-licensed diffusion |
| Genie 3 | See genie3 docs | MIT | Good for novel topologies |

**Quick start with Chroma:**
```bash
pip install chroma-ai
# Generate 10 backbones of 150 residues
python -c "
from chroma import Chroma
model = Chroma()
backbones = model.sample(10, lengths=[150]*10)
backbones.save('outputs/chroma_designs/')
"
```

**No GPU?** Use Google Colab with RFdiffusion or Chroma pre-installed.

See `install-guide` skill for full RFdiffusion installation instructions.

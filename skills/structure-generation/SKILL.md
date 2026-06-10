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

## MCP Tool

```json
{
  "tool": "run_rfdiffusion",
  "params": {
    "output_prefix": "outputs/design",
    "contig": "[150-150]",
    "num_designs": 10,
    "input_pdb": null,
    "diffuser_T": 50
  }
}
```

## Basic Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `output_prefix` | ✅ | — | Output path prefix |
| `contig` | ✅ | — | Contig string (use single quotes in shell) |
| `num_designs` | ❌ | 10 | Number of backbones to generate |
| `input_pdb` | ❌ | null | Required for motif/binder/partial |
| `hotspot_res` | ❌ | null | Hotspot residues (binder design) |
| `symmetry` | ❌ | null | `c2`, `d2`, `tetrahedral`, `octahedral`, `icosahedral` |
| `diffuser_T` | ❌ | 50 | Diffusion timesteps (lower=faster) |
| `ckpt_override_path` | ❌ | null | Custom model checkpoint |
| `skip_preprocessing` | ❌ | false | Skip auto PDBFixer |
| `keep_chains` | ❌ | null | Chains to keep in preprocessing |

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

## Common Design Patterns

### Unconditional Monomer (150 aa)
```json
{"contig": "[150-150]", "output_prefix": "outputs/monomer", "num_designs": 20}
```

### Motif Scaffolding (fix A163-181, generate 10-40 aa flanks)
```json
{
  "contig": "[10-40/A163-181/10-40]",
  "output_prefix": "outputs/motif",
  "input_pdb": "inputs/5TPN.pdb",
  "num_designs": 5
}
```

### Binder Design (100-res binder for target B1-100, hotspots A30,A33,A34)
```json
{
  "contig": "[B1-100/0 100-100]",
  "hotspot_res": ["A30", "A33", "A34"],
  "output_prefix": "outputs/binder",
  "input_pdb": "inputs/target.pdb",
  "num_designs": 50
}
```

### Partial Diffusion (keep A1-50 and A71-150, redesign 10-20 aa loop)
```json
{
  "contig": "[A1-50/0 10-20/A71-150]",
  "output_prefix": "outputs/partial",
  "input_pdb": "inputs/structure.pdb",
  "num_designs": 5,
  "diffuser_T": 25
}
```

## Advanced Design Patterns

### Partial Diffusion with Fixed Sequence
Keep some sequence fixed while diffusing structure:
```json
{
  "contig": "[A1-50/0 10-20/A71-150]",
  "input_pdb": "inputs/structure.pdb",
  "partial_T": 10,
  "provide_seq": "[172-205]",
  "output_prefix": "outputs/partial_seq",
  "num_designs": 10
}
```

### Sequence Inpainting (Mask Sequence Identity)
Redesign sequence of specific residues while keeping structure:
```json
{
  "contig": "[A1-150]",
  "input_pdb": "inputs/structure.pdb",
  "inpaint_seq": "[A30-40/A60-70]",
  "output_prefix": "outputs/inpaint_seq",
  "num_designs": 20
}
```

### Structure Inpainting (Redesign Structure of Region)
Redesign structure while keeping sequence identity:
```json
{
  "contig": "[A1-150]",
  "input_pdb": "inputs/structure.pdb",
  "inpaint_str": "[B165-178]",
  "output_prefix": "outputs/inpaint_str",
  "num_designs": 20
}
```

### Secondary Structure Specification
Specify helix/strand/loop for masked regions:
```json
{
  "contig": "[A1-50/0 20-30/A81-150]",
  "input_pdb": "inputs/structure.pdb",
  "inpaint_str_helix": "[A51-60]",
  "inpaint_str_strand": "[A61-70]",
  "output_prefix": "outputs/ss_spec",
  "num_designs": 10
}
```

### Fold Conditioning (Scaffold-Guided)
Use secondary structure and block adjacency to guide design:
```json
{
  "contig": "[150-150]",
  "scaffoldguided": true,
  "scaffold_dir": "path/to/scaffold/files",
  "output_prefix": "outputs/scaffoldguided",
  "num_designs": 20
}
```

### Macrocyclic Peptide Design
```json
{
  "contig": "[12-18]",
  "cyclic": true,
  "cyc_chains": "a",
  "output_prefix": "outputs/cyclic",
  "num_designs": 50
}
```

### Macrocyclic Binder Design
```json
{
  "contig": "[B1-50/0 12-18]",
  "input_pdb": "inputs/target.pdb",
  "hotspot_res": ["A30", "A33"],
  "cyclic": true,
  "cyc_chains": "b",
  "output_prefix": "outputs/cyclic_binder",
  "num_designs": 50
}
```

### Potentials-Guided Design
Use auxiliary potentials to guide diffusion:
```json
{
  "contig": "[100-100]",
  "potentials": ["type:monomer_ROG,weight:1.0"],
  "output_prefix": "outputs/potential",
  "num_designs": 20
}
```

### Symmetric Oligomers
```json
{
  "contig": "[100]",
  "symmetry": "c4",
  "output_prefix": "outputs/c4",
  "num_designs": 20
}
```

**Supported symmetries:** `c2`, `c3`, `c4`, `c5`, `c6`, `d2`, `d3`, `d4`, `tetrahedral`, `octahedral`, `icosahedral`

### Enzyme Active Site Scaffolding
For very small motifs, use the ActiveSite checkpoint:
```json
{
  "contig": "[10-20/A50-55/10-20]",
  "input_pdb": "inputs/enzyme.pdb",
  "ckpt_override_path": "models/ActiveSite_ckpt.pt",
  "output_prefix": "outputs/enzyme",
  "num_designs": 50
}
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
If input_pdb provided → auto-run PDBFixer (unless skipped)
     ↓
submit_job("rfdiffusion", params)
     ↓
query_job polling → completed
     ↓
Return PDB list → Stage 2 (ProteinMPNN)
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

---
name: structure-generation
description: Protein backbone generation with RFdiffusion (Stage 1)
---

# Stage 1: Structure Generation (RFdiffusion)

## When to Trigger

- User says "generate a protein", "design a backbone", "create a scaffold"
- User requests binder design: "design a binder for X"
- User requests motif scaffolding: "scaffold around this motif"
- User requests symmetric oligomer: "design a trimer"

## RFdiffusion Overview

RFdiffusion generates protein backbone structures (poly-Glycine, only N/CA/C/O atoms) using a diffusion model. The contig parameter is the single most important argument — it defines what to generate and what to keep.

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

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `output_prefix` | ✅ | — | Output path prefix |
| `contig` | ✅ | — | Contig string (use single quotes in shell) |
| `num_designs` | ❌ | 10 | Number of backbones to generate |
| `input_pdb` | ❌ | null | Required for motif/binder/partial |
| `hotspot_res` | ❌ | null | Hotspot residues (binder design) |
| `symmetry` | ❌ | null | `c2`, `d2`, `tetrahedral`, etc. |
| `diffuser_T` | ❌ | 50 | Diffusion steps (lower=faster) |
| `ckpt_override_path` | ❌ | null | Custom model checkpoint |
| `skip_preprocessing` | ❌ | false | Skip auto PDBFixer |
| `keep_chains` | ❌ | null | Chains to keep in preprocessing |

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
  "num_designs": 5
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

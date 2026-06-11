---
name: rfdiffusion3-workflow
description: Guide for using RFdiffusion3 (RFD3) for all-atom biomolecular interaction design including proteins, DNA, RNA, small molecules, and enzymes
---

# RFdiffusion3 Workflow Guide

**RFdiffusion3 (RFD3)** is the third-generation diffusion model from the Institute for Protein Design / Rosetta Commons, released December 2025. It is a complete rewrite (shares no code with RFdiffusion/RFdiffusion2) that designs protein structures under complex all-atom constraints.

---

## What Makes RFdiffusion3 Different

| Feature | RFdiffusion (v1/v2) | RFdiffusion3 |
|---------|---------------------|--------------|
| Architecture | SE(3) diffusion | Efficient transformers |
| Design unit | Backbone atoms | All atoms (including sidechains) |
| Speed | Baseline | ~10× faster than RFdiffusion2 |
| Codebase | Standalone repo | Part of Rosetta Commons Foundry |
| Training code | Weights only | Training code + weights released |
| Molecules supported | Proteins, some ligands (RFD-AA) | Proteins, DNA, RNA, small molecules, metals |
| Installation | Conda env + manual weights | `pip install rc-foundry[rfd3]` |

**Use RFD3 when:**
- You need all-atom control (not just backbone)
- Your design involves DNA/RNA/small molecules/metals
- You want faster inference than RFdiffusion2
- You need a single unified model instead of multiple specialist tools
- You want to fine-tune on your own data (training code available)

**Use classic RFdiffusion when:**
- You already have a working RFdiffusion pipeline
- You only need backbone/motif scaffolding
- Your cluster lacks the Foundry dependencies

---

## Installation (Document-Only — Do Not Install)

RFD3 is distributed through the **Rosetta Commons Foundry** repository, not the old `RFdiffusion` repo.

```bash
# Install RFD3 only
pip install "rc-foundry[rfd3]"

# Or install all Foundry models
pip install "rc-foundry[all]"

# Download model weights
foundry install rfd3 --checkpoint-dir ~/.foundry/checkpoints

# Optional: HBPLUS for hydrogen-bond conditioning
# Install HBPLUS and set HBPLUS_PATH in foundry/.env
```

Foundry discovers checkpoints in `~/.foundry/checkpoints` and any paths listed in `$FOUNDRY_CHECKPOINT_DIRS`. List installed models with `foundry list-installed`.

**Sources:**
- [RFdiffusion3 announcement](https://www.ipd.uw.edu/2025/12/rfdiffusion3-now-available/)
- [Foundry repository](https://github.com/RosettaCommons/foundry)
- [RFD3 README](https://github.com/RosettaCommons/foundry/blob/production/models/rfd3/README.md)

---

## Quickstart

```bash
rfd3 design \
  out_dir=outputs/rfd3_demo/0 \
  inputs=models/rfd3/docs/examples/demo.json \
  skip_existing=False \
  dump_trajectories=True \
  prevalidate_inputs=True
```

Only `inputs` (JSON/YAML) and `out_dir` are required.

| Useful flag | Purpose |
|-------------|---------|
| `dump_trajectories` | Save intermediate diffusion trajectories for debugging |
| `prevalidate_inputs` | Validate inputs before loading checkpoints |
| `skip_existing` | Skip designs already present in `out_dir` |

---

## Input Format

RFD3 accepts **JSON or YAML** input files. The full specification is in the [Foundry input docs](https://rosettacommons.github.io/foundry/models/rfd3/input.html).

### Common fields

```yaml
my_design:
  input: path/to/target.pdb        # Required: input structure
  contig: 40-120,/0,A6-155         # Designed region + preserved region
  length: 190-270                  # Total length range
  select_hotspots:                 # Atoms forced near binder interface
    A64: CG,CZ
  infer_ori_strategy: hotspots     # How to place orientation token
  is_non_loopy: true               # Reduce loops in PPI design
```

### Contig string syntax

| Token | Meaning |
|-------|---------|
| `40-120` | Design a new chain of 40–120 residues |
| `/0` | Chain break |
| `A6-155` | Preserve chain A residues 6–155 from input |
| `B1-100` | Preserve chain B residues 1–100 |

### Key design options

| Option | When to use |
|--------|-------------|
| `select_hotspots` | Force target atoms within 4.5 Å of binder |
| `select_fixed_atoms` | Fix specific atoms in space |
| `select_unfixed_sequence` | Allow residue identity to change while backbone is fixed |
| `select_buried` / `select_exposed` | Control ligand burial via RASA conditioning |
| `unindex` | Remove residue numbering constraints (useful for enzymes) |
| `ori_token` | Manually set center of mass for designed portion |
| `ligand` | Reference a ligand chain (e.g., `l:g`) |

---

## Application Workflows

### 1. Protein Binder Design (PPI)

```yaml
insulinr:
  input: 4zxb_cropped.pdb
  contig: 40-120,/0,E6-155
  length: 190-270
  select_hotspots:
    E64: CD2,CZ
    E88: CG,CZ
    E96: CD1,CZ
  infer_ori_strategy: hotspots
  is_non_loopy: true
```

```bash
rfd3 design out_dir=outputs/rfd3_ppi/0 \
  inputs=ppi_config.yaml \
  ckpt_path=~/.foundry/checkpoints/rfd3_latest.ckpt
```

Outputs: `ppi_insulinr_0_model_n.cif.gz` + `.json` files.

**Next steps:** Sequence design with ProteinMPNN or LigandMPNN → validate with AlphaFold3 / RFAA / Boltz-1.

### 2. Enzyme Design (Small Molecule / Cofactor)

```json
{
  "cys_1euv_lig": {
    "input": "1euv_lig.pdb",
    "ligand": "l:g",
    "unindex": "A514,A531,A574,A579-581",
    "length": "100-200",
    "ori_token": [0,1,0],
    "select_fixed_atoms": {
      "A514": "NE2,CE1,ND1,CD2,CG,CB",
      "A531": "OD1,CG,OD2,CB",
      "A574": "NE2,CD,OE1,CG",
      "A579": "C,O,CA,N",
      "A580": "SG,CB,CA,N,C,O",
      "A581": "C,O,CA,N"
    },
    "select_buried": { "l:g": "O1,C8,O3,C4,C5,C23,C24,C25,C26,C27" },
    "select_exposed": { "l:g": "C2,C22,C19,C18,C17,C20,C16,C15,O21,O14,C13,C12" },
    "select_unfixed_sequence": "A579,A581"
  }
}
```

```bash
rfd3 design out_dir=outputs/rfd3_enzyme/0 \
  inputs=enzyme_config.json \
  ckpt_path=~/.foundry/checkpoints/rfd3_latest.ckpt
```

**Next steps:** Sequence design with LigandMPNN → validate with RFAA (ligand-aware) or AlphaFold3.

### 3. Nucleic Acid Binder Design

RFD3 can design proteins that bind DNA or RNA. See the [NA binder tutorial](https://rosettacommons.github.io/foundry/models/rfd3/tutorials/na_binder_tutorial.html).

### 4. Symmetric Design

See [symmetry docs](https://github.com/RosettaCommons/foundry/blob/production/models/rfd3/docs/symmetry.md).

---

## Output Format

By default, RFD3 writes:

- **`.cif.gz`** — Generated structure(s) in mmCIF format (gzipped)
- **`.json`** — Metadata and conditioning information
- **Trajectories** — If `dump_trajectories=True`

Number of designs per run is controlled by `diffusion_batch_size`. Use multiple batches (`n_batches`) to vary length.

---

## Pipeline Integration

RFD3 can replace **Stage 1** (backbone generation) in the standard pipeline. Because it outputs all-atom structures, Stage 2 may be optional in some cases.

| Stage | Classic Pipeline | RFD3 Pipeline |
|-------|-----------------|---------------|
| 0 | PDBFixer | PDBFixer |
| 1 | RFdiffusion | **RFD3** |
| 2 | ProteinMPNN | ProteinMPNN / LigandMPNN *(often still recommended)* |
| 3 | AlphaFold3 | AlphaFold3 / RFAA / Boltz-1 |
| 4 | Filtering | Filtering |

**Recommended pairings:**
- General proteins → RFD3 → ProteinMPNN → AlphaFold3
- Enzymes / ligands → RFD3 → LigandMPNN → RFAA
- DNA/RNA binders → RFD3 → ProteinMPNN → AlphaFold3 / RFAA
- Commercial use → RFD3 → ProteinMPNN → Boltz-1 / Chai-1

---

## Training / Fine-Tuning

RFD3 includes training code. Launch with:

```bash
uv run python models/rfd3/src/rfd3/train.py \
  experiment=pretrain \
  ckpt_path=/path/to/rfd3_latest.ckpt
```

Supports Weights & Biases (`logger=wandb`) and distributed training via Lightning Fabric.

---

## License

RFdiffusion3 is released through Rosetta Commons. Check the [Foundry repository](https://github.com/RosettaCommons/foundry) for the latest license terms. The original RFdiffusion was BSD (free for non-profit and for-profit use); Foundry models may have different terms.

---

## Citation

Butcher et al., "De novo Design of All-atom Biomolecular Interactions with RFdiffusion3," *bioRxiv*, 2025. DOI: [10.1101/2025.09.18.676967](https://doi.org/10.1101/2025.09.18.676967)

---

## See Also

- `structure-generation` — Classic RFdiffusion backbone generation
- `rfdiffusion-all-atom` — RFdiffusion All-Atom (prior-generation ligand-aware)
- `ligandmpnn-design` — Sequence design for ligand-aware designs
- `rosettafold-all-atom` — Validation of ligand/DNA/RNA/metal complexes
- `enzyme-design` — General enzyme design strategies
- `pipeline-selection` — Choose the right pipeline

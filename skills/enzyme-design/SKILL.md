---
name: enzyme-design
description: Enzyme design workflows including active site design, substrate specificity, and catalytic efficiency
---

# Enzyme Design

## When to Trigger

- User says "enzyme", "catalyst", "active site", "substrate", "reaction"
- User wants to design an enzyme for a specific reaction
- User asks about catalytic residues or transition state
- User wants to improve enzyme activity or specificity
- User needs to engineer thermostability into an enzyme

## Overview

Enzyme design is a specialized protein design workflow that focuses on:
1. **Active site design** — Creating catalytic residues in the right geometry
2. **Substrate specificity** — Ensuring the enzyme binds the correct substrate
3. **Catalytic efficiency** — Maximizing kcat/KM
4. **Thermostability** — Maintaining activity at high temperatures

## Enzyme Structure Basics

```
Enzyme structure:
  - Active site: Pocket where catalysis occurs
  - Catalytic residues: Directly participate in reaction
  - Binding pocket: Recognizes substrate
  - Allosteric sites: Regulate activity

Key concepts:
  - Transition state stabilization
  - Substrate binding energy
  - Catalytic triad (e.g., Ser-His-Asp in proteases)
  - Cofactor binding (metal ions, coenzymes)
```

## Pipeline 1: Active Site Scaffolding

**Goal:** Scaffold a catalytic motif within a stable protein framework.

### Stage 0: Prepare catalytic motif

```json
{"tool": "run_pdbfixer", "params": {
  "input_pdb": "catalytic_motif.pdb",
  "output_pdb": "outputs/motif_fixed.pdb"
}}
```

### Stage 1: Generate scaffolds around motif

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "outputs/motif_fixed.pdb",
  "contig": "[30-50/A55-58/30-50]",
  "ckpt_override_path": "models/ActiveSite_ckpt.pt",
  "output_prefix": "outputs/enzyme_scaffold/design",
  "num_designs": 100,
  "diffuser_T": 50
}}
```

**Important:** Use `ActiveSite_ckpt.pt` for small motifs (<10 residues).

### Stage 2: Design sequences with fixed catalytic residues

```json
{"tool": "run_proteinmpnn", "params": {
  "pdb_path": "outputs/enzyme_scaffold/design_0.pdb",
  "output_folder": "outputs/enzyme_seqs",
  "num_seq_per_target": 8,
  "sampling_temp": "0.1",
  "fixed_positions_jsonl": "catalytic_residues.jsonl"
}}
```

**Fixed positions:**
```json
{"design_0": {"A": [55, 56, 57, 58], "B": []}}
```

### Stage 3: Validate structure

```json
{"tool": "run_alphafold3", "params": {
  "json_path": "outputs/enzyme_seqs/design_0_af3_input.json",
  "output_dir": "outputs/af3/enzyme",
  "num_seeds": 1,
  "num_samples": 5
}}
```

### Stage 4: Check active site geometry

```python
# Check catalytic geometry
from Bio.PDB import PDBParser
import numpy as np

parser = PDBParser(QUIET=True)
structure = parser.get_structure("enzyme", "outputs/af3/enzyme/design_0_model.cif")

# Measure distances between catalytic residues
cat1 = structure[0]["A"][55]["CA"]
cat2 = structure[0]["A"][56]["CA"]
cat3 = structure[0]["A"][57]["CA"]

dist_12 = np.linalg.norm(cat1.coord - cat2.coord)
dist_13 = np.linalg.norm(cat1.coord - cat3.coord)
dist_23 = np.linalg.norm(cat2.coord - cat3.coord)

print(f"Catalytic distances: {dist_12:.2f}, {dist_13:.2f}, {dist_23:.2f} Å")
```

## Pipeline 2: Substrate Specificity Engineering

**Goal:** Modify enzyme to bind a new substrate.

### Step 1: Identify binding pocket residues

```python
# Find residues within 5Å of substrate
binding_pocket = find_residues_within_distance(
    structure, substrate, cutoff=5.0
)
print(f"Binding pocket: {binding_pocket}")
```

### Step 2: Design new binding pocket

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "enzyme_substrate_complex.pdb",
  "contig": "[A1-100]",
  "inpaint_str": "[B1-20]",
  "output_prefix": "outputs/binding_pocket/design",
  "num_designs": 50,
  "diffuser_T": 25
}}
```

### Step 3: Validate with new substrate

```python
# Dock new substrate into designed pocket
# Use molecular docking software (e.g., AutoDock, Rosetta)
```

## Pipeline 3: Thermostability Engineering

**Goal:** Improve enzyme thermostability without losing activity.

### Option A: Using ThermoGFN-IF (if available)

```bash
python ThermoGFN-IF/run.py \
    --student-ckpt checkpoint.pt \
    --seed-dataset enzyme_sequences.jsonl \
    --num-candidates 256 \
    --target-reward 80.0 \
    --tolerance 5.0
```

### Option B: Traditional approach

**Step 1:** Introduce disulfide bonds

```python
# Find pairs of cysteines that can form disulfides
disulfide_pairs = find_disulfide_pairs(structure)
```

**Step 2:** Optimize surface charge

```python
# Reduce surface charge density
surface_residues = get_surface_residues(structure)
for res in surface_residues:
    if res.resname == "LYS" and is_exposed(res):
        mutate_to(res, "ARG")  # More stable at high pH
```

**Step 3:** Fill cavities

```python
# Fill internal cavities with larger residues
cavities = find_cavities(structure)
for cavity in cavities:
    fill_cavity(cavity, "LEU")  # Leucine is stable and compact
```

## Pipeline 4: Catalytic Efficiency Optimization

**Goal:** Maximize kcat/KM for a given reaction.

### Step 1: Generate transition state model

```python
# Build transition state structure
# Use QM/MM or empirical force fields
ts_structure = build_transition_state(substrate, reaction_type)
```

### Step 2: Design enzyme to stabilize TS

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "transition_state.pdb",
  "contig": "[50-100]",
  "potentials": ["type:substrate_contacts,weight:2.0"],
  "output_prefix": "outputs/ts_stabilization/design",
  "num_designs": 100
}}
```

### Step 3: Score designs for TS stabilization

```python
# Calculate binding energy to TS
for design in designs:
    ts_energy = calculate_ts_binding_energy(design, ts_structure)
    scores.append((design, ts_energy))
```

## Tips

- **Active site geometry is critical** — distances and angles must match the reaction mechanism
- **Cofactor compatibility** — Ensure designed enzyme can bind required cofactors
- **Substrate access** — Design substrate channel for easy access to active site
- **Product release** — Ensure product can exit the active site
- **pH optimum** — Design active site residues for desired pH
- **Thermostability** — Introduce disulfide bonds, salt bridges, and hydrophobic cores
- **Expression** — Optimize for soluble expression in E. coli or yeast

## Quality Metrics for Enzymes

| Metric | Acceptable | Good | Excellent |
|--------|-----------|------|-----------|
| Active site pLDDT | >70 | >80 | >90 |
| Substrate pocket pLDDT | >75 | >85 | >95 |
| Overall pTM | >0.5 | >0.7 | >0.9 |
| Catalytic geometry | Within 1Å | Within 0.5Å | Within 0.2Å |
| Cavity volume | <500 Å³ | 200-500 Å³ | 200-400 Å³ |

## References

- [RFdiffusion for enzyme design](https://www.nature.com/articles/s41586-023-06415-8)
- [ProteinMPNN for active site design](https://www.science.org/doi/10.1126/science.add2187)
- [ThermoGFN-IF](https://github.com/amelie-iska/ThermoGFN-IF)
- [EnzyMiner](https://github.com/EnzyMiner/EnzyMiner) — Enzyme mining database

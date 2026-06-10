---
name: design-patterns
description: Ready-to-use protein design pattern templates for common scenarios
---

# Design Pattern Templates

## When to Trigger

- User says "design a monomer", "design a binder", "design a scaffold"
- User provides a specific target or goal without detailed parameters
- User wants a quick start with sensible defaults
- User says "template", "pattern", "preset", "recipe"

## Overview

These are pre-configured design patterns with sensible defaults for common protein design scenarios. Each pattern includes:
- Recommended pipeline parameters
- Quality thresholds
- Expected runtime
- Next steps

## Pattern 1: De Novo Monomer (150 aa)

**Goal:** Generate a stable, soluble 150-residue protein from scratch.

```json
{"tool": "run_rfdiffusion", "params": {
  "contig": "[150-150]",
  "output_prefix": "outputs/monomer_150/design",
  "num_designs": 50,
  "diffuser_T": 50
}}
```

→ ProteinMPNN: `sampling_temp="0.1"`, `num_seq_per_target=8`
→ AlphaFold3: `num_samples=5`, `run_data_pipeline=false` (for screening)
→ Filtering: `min_plddt=80`, `min_ptm=0.7`

**Expected:** 50 backbones × 8 seqs = 400 sequences → top 5-10 pass filter
**Runtime:** ~30 min (RFdiffusion) + ~2 hours (ESMFold screening) + ~3 hours (AF3 top 10)

## Pattern 2: PD-L1 Binder Design

**Goal:** Design a protein binder targeting PD-L1.

```json
{"tool": "run_pdbfixer", "params": {
  "input_pdb": "pd-l1_target.pdb",
  "output_pdb": "outputs/pd-l1_fixed.pdb"
}}
```

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "outputs/pd-l1_fixed.pdb",
  "contig": "[B1-150/0 100-100]",
  "hotspot_res": ["A30", "A33", "A34", "A56"],
  "output_prefix": "outputs/pd-l1_binder/design",
  "num_designs": 100,
  "diffuser_T": 50
}}
```

→ ProteinMPNN: `pdb_path_chains="B"`, `sampling_temp="0.1"`, `num_seq_per_target=8`
→ convert_format with `receptor_pdb="outputs/pd-l1_fixed.pdb"`
→ AlphaFold3: `num_samples=5`
→ Filtering: `min_iptm=0.8`, `min_plddt=80`

**Expected:** 100 backbones × 8 seqs = 800 sequences → top 5-15 pass filter
**Runtime:** ~1 hour (RFdiffusion) + ~3 hours (ESMFold screening) + ~5 hours (AF3 top 15)

## Pattern 3: Motif Scaffolding (Active Site)

**Goal:** Scaffold a conserved catalytic motif within a new protein framework.

```json
{"tool": "run_pdbfixer", "params": {
  "input_pdb": "enzyme.pdb",
  "output_pdb": "outputs/enzyme_fixed.pdb",
  "keep_chains": ["A"]
}}
```

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "outputs/enzyme_fixed.pdb",
  "contig": "[20-40/A50-60/20-40]",
  "output_prefix": "outputs/enzyme_scaffold/design",
  "num_designs": 50,
  "diffuser_T": 50
}}
```

→ ProteinMPNN: `sampling_temp="0.1"`, consider `use_soluble_model=true`
→ AlphaFold3: standard validation
→ Filtering: `min_plddt=75`, `min_ptm=0.6`

**Tip:** For very small motifs (<10 residues), use `ckpt_override_path=models/ActiveSite_ckpt.pt`

## Pattern 4: Symmetric Cyclic Peptide Binder

**Goal:** Design a cyclic peptide that binds a target protein.

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "outputs/target_fixed.pdb",
  "contig": "[B1-100/0 12-18]",
  "hotspot_res": ["A30", "A33"],
  "cyclic": true,
  "cyc_chains": "b",
  "output_prefix": "outputs/cyclic_binder/design",
  "num_designs": 200,
  "diffuser_T": 25
}}
```

→ ProteinMPNN: `pdb_path_chains="B"`, `sampling_temp="0.1"`
→ AlphaFold3: standard validation
→ Filtering: `min_iptm=0.75`, `min_plddt=70`

**Expected:** Higher num_designs needed due to short peptide length
**Tip:** Cyclic peptides often have lower pLDDT — adjust thresholds accordingly

## Pattern 5: Partial Diffusion (Loop Redesign)

**Goal:** Redesign a flexible loop while keeping the rest of the structure fixed.

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "outputs/structure_fixed.pdb",
  "contig": "[A1-50/0 10-20/A71-150]",
  "partial_T": 10,
  "output_prefix": "outputs/loop_redesign/design",
  "num_designs": 20,
  "diffuser_T": 25
}}
```

→ ProteinMPNN: standard parameters
→ AlphaFold3: `run_data_pipeline=false` (structure already known)
→ Filtering: compare RMSD to original structure, keep pLDDT > 75

**Tip:** Lower `diffuser_T` (25) and `partial_T` (10) for conservative redesign

## Pattern 6: Sequence Inpainting (Variant Library)

**Goal:** Generate a diverse sequence library around a binding interface.

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "outputs/binder_complex_fixed.pdb",
  "contig": "[A1-150]",
  "inpaint_seq": "[A30-40/A60-70]",
  "output_prefix": "outputs/variant_library/design",
  "num_designs": 50,
  "diffuser_T": 50
}}
```

→ ProteinMPNN: `sampling_temp="0.3 0.5"` for maximum diversity
→ AlphaFold3: standard validation
→ Filtering: standard thresholds

**Tip:** Use `inpaint_seq` to mask residues you want to redesign while keeping structure

## Pattern 7: Fast Screening (100+ Designs)

**Goal:** Rapidly screen many designs using ESMFold instead of AlphaFold3.

```json
{"tool": "run_rfdiffusion", "params": {
  "contig": "[150-150]",
  "output_prefix": "outputs/fast_screen/design",
  "num_designs": 50
}}
```

→ ProteinMPNN: `num_seq_per_target=8` → 400 sequences
→ **ESMFold** (not AlphaFold3): predict all 400 in ~1 hour
→ Filter: pLDDT > 75 → ~50 candidates
→ **AlphaFold3** (top 20 only): validate best candidates

**Time saved:** ~15 hours vs full AlphaFold3 on all 400

## Pattern 8: Symmetric Oligomer (C4 Tetramer)

**Goal:** Design a symmetric C4 tetramer.

```json
{"tool": "run_rfdiffusion", "params": {
  "contig": "[100]",
  "symmetry": "c4",
  "output_prefix": "outputs/c4_tetramer/design",
  "num_designs": 50,
  "diffuser_T": 50
}}
```

→ ProteinMPNN: `tied_positions_jsonl` for symmetric positions
→ AlphaFold3: standard validation
→ Filtering: `min_ptm=0.7`, `min_plddt=75`

**Tip:** Contig length = monomer length (100), not total assembly length

## Pattern 9: Fold Conditioning (TIM Barrel)

**Goal:** Design a protein with a specific fold topology (e.g., TIM barrel).

```json
{"tool": "run_rfdiffusion", "params": {
  "contig": "[300-350]",
  "scaffoldguided": true,
  "scaffold_dir": "path/to/tim_barrel_scaffolds",
  "output_prefix": "outputs/tim_barrel/design",
  "num_designs": 50,
  "diffuser_T": 50
}}
```

→ ProteinMPNN: standard parameters
→ AlphaFold3: standard validation
→ Filtering: `min_ptm=0.8` (high topology confidence needed)

**Tip:** Prepare scaffold_dir with secondary structure and block adjacency files

## Pattern 10: Enzyme Active Site Scaffolding

**Goal:** Scaffold a very small catalytic motif (3-10 residues).

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "outputs/enzyme_fixed.pdb",
  "contig": "[30-50/A55-58/30-50]",
  "ckpt_override_path": "models/ActiveSite_ckpt.pt",
  "output_prefix": "outputs/enzyme_scaffold/design",
  "num_designs": 100,
  "diffuser_T": 50
}}
```

→ ProteinMPNN: standard parameters, consider `fixed_positions_jsonl` for catalytic residues
→ AlphaFold3: standard validation
→ Filtering: `min_plddt=70`

**Tip:** Use ActiveSite_ckpt.pt for motifs < 10 residues. Standard Base_ckpt.pt works poorly.

## Advanced Patterns

### Pattern 11: Antibody CDR Design

**Goal:** Design complementarity-determining regions (CDRs) for an antibody targeting a specific antigen.

```json
{"tool": "run_pdbfixer", "params": {
  "input_pdb": "antibody_antigen_complex.pdb",
  "output_pdb": "outputs/ab_fixed.pdb",
  "keep_chains": ["H", "L", "A"]
}}
```

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "outputs/ab_fixed.pdb",
  "contig": "[H95-100/0 10-20/H101-110]",
  "output_prefix": "outputs/cdr_design/design",
  "num_designs": 50,
  "diffuser_T": 25,
  "partial_T": 10
}}
```

→ ProteinMPNN: `pdb_path_chains="H L"`, `fixed_positions_jsonl` for framework residues
→ AlphaFold3: validate with antigen present
→ Filtering: `min_iptm=0.75`, `min_plddt=75`

**Tip:** Use partial diffusion with low diffuser_T for conservative CDR redesign

### Pattern 12: Membrane Protein Design

**Goal:** Design a transmembrane protein with specified topology.

```json
{"tool": "run_rfdiffusion", "params": {
  "contig": "[200-250]",
  "output_prefix": "outputs/membrane/design",
  "num_designs": 50,
  "diffuser_T": 50
}}
```

→ ProteinMPNN: `use_soluble_model=false`, consider `omit_AAs` for charged residues
→ AlphaFold3: standard validation
→ Filtering: `min_plddt=70`, check per-residue pLDDT in TM regions

**Tip:** Use LigandMPNN's `per_residue_label_membrane_mpnn` model for membrane-specific design

### Pattern 13: Multi-Domain Protein

**Goal:** Design a protein with multiple independent domains connected by linkers.

```json
{"tool": "run_rfdiffusion", "params": {
  "contig": "[50-60/0 10-15/50-60]",
  "output_prefix": "outputs/multidomain/design",
  "num_designs": 30,
  "diffuser_T": 50
}}
```

→ ProteinMPNN: `num_seq_per_target=8`, `sampling_temp="0.1"`
→ AlphaFold3: validate full structure
→ Filtering: `min_plddt=75`, `min_ptm=0.6`

**Tip:** Each domain should independently fold; check per-domain pLDDT

### Pattern 14: Protein-Ligand Interface Design

**Goal:** Design a protein that binds a specific small molecule.

```json
{"tool": "run_pdbfixer", "params": {
  "input_pdb": "protein_with_ligand.pdb",
  "output_pdb": "outputs/protein_ligand_fixed.pdb",
  "keep_chains": ["A"]
}}
```

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "outputs/protein_ligand_fixed.pdb",
  "contig": "[A1-50/0 20-30/A71-150]",
  "output_prefix": "outputs/ligand_interface/design",
  "num_designs": 50,
  "diffuser_T": 25
}}
```

→ LigandMPNN: `model_type=ligand_mpnn`, `ligand_mpnn_use_atom_context=1`
→ AlphaFold3: include ligand in JSON input
→ Filtering: `min_plddt=75`

**Tip:** LigandMPNN considers bound ligand context during sequence design

### Pattern 15: Protein-DNA Interface Design

**Goal:** Design a protein that recognizes and binds a specific DNA sequence.

```json
{"tool": "run_pdbfixer", "params": {
  "input_pdb": "transcription_factor_dna.pdb",
  "output_pdb": "outputs/tf_dna_fixed.pdb",
  "keep_chains": ["A", "B", "C"]
}}
```

```json
{"tool": "run_rfdiffusion", "params": {
  "input_pdb": "outputs/tf_dna_fixed.pdb",
  "contig": "[A1-30/0 10-20/A31-100]",
  "output_prefix": "outputs/dna_interface/design",
  "num_designs": 50,
  "diffuser_T": 25
}}
```

→ ProteinMPNN: `pdb_path_chains="A"` (fix DNA chains)
→ AlphaFold3: include DNA in JSON input
→ Filtering: `min_iptm=0.7`

**Tip:** AlphaFold3 can predict protein-DNA complexes

## How to Use Patterns

1. **Pick a pattern** based on your design goal
2. **Adjust parameters** as needed (length, num_designs, etc.)
3. **Run the pipeline** step by step
4. **Iterate** based on results

Each pattern is a starting point — feel free to customize!

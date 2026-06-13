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

```bash
python scripts/run_rfdiffusion.py \
  --contig "[150-150]" \
  --output-prefix outputs/monomer_150/design \
  --num-designs 50 \
  --diffuser-t 50
```

→ ProteinMPNN: `--temp 0.1 --num-seq 8`
→ AlphaFold3: `--num-samples 5 --no-msa` (for screening)
→ Filtering: `--min-plddt 80 --min-ptm 0.7`

**Expected:** 50 backbones × 8 seqs = 400 sequences → top 5-10 pass filter
**Runtime:** ~30 min (RFdiffusion) + ~2 hours (ESMFold screening) + ~3 hours (AF3 top 10)

## Pattern 2: PD-L1 Binder Design

**Goal:** Design a protein binder targeting PD-L1.

```bash
python scripts/run_pdbfixer.py \
  --input pd-l1_target.pdb \
  --output outputs/pd-l1_fixed.pdb
```

```bash
python scripts/run_rfdiffusion.py \
  --input-pdb outputs/pd-l1_fixed.pdb \
  --contig "[B1-150/0 100-100]" \
  --hotspot-res A30 A33 A34 A56 \
  --output-prefix outputs/pd-l1_binder/design \
  --num-designs 100 \
  --diffuser-t 50
```

→ ProteinMPNN: `--chains B --temp 0.1 --num-seq 8`
→ convert_format with `--receptor-pdb outputs/pd-l1_fixed.pdb`
→ AlphaFold3: `--num-samples 5`
→ Filtering: `--min-iptm 0.8 --min-plddt 80`

**Expected:** 100 backbones × 8 seqs = 800 sequences → top 5-15 pass filter
**Runtime:** ~1 hour (RFdiffusion) + ~3 hours (ESMFold screening) + ~5 hours (AF3 top 15)

## Pattern 3: Motif Scaffolding (Active Site)

**Goal:** Scaffold a conserved catalytic motif within a new protein framework.

```bash
python scripts/run_pdbfixer.py \
  --input enzyme.pdb \
  --output outputs/enzyme_fixed.pdb \
  --keep-chains A
```

```bash
python scripts/run_rfdiffusion.py \
  --input-pdb outputs/enzyme_fixed.pdb \
  --contig "[20-40/A50-60/20-40]" \
  --output-prefix outputs/enzyme_scaffold/design \
  --num-designs 50 \
  --diffuser-t 50
```

→ ProteinMPNN: `--temp 0.1`, consider `--soluble`
→ AlphaFold3: standard validation
→ Filtering: `--min-plddt 75 --min-ptm 0.6`

**Tip:** For very small motifs (<10 residues), use `--checkpoint models/ActiveSite_ckpt.pt`

## Pattern 4: Symmetric Cyclic Peptide Binder

**Goal:** Design a cyclic peptide that binds a target protein.

```bash
python scripts/run_rfdiffusion.py \
  --input-pdb outputs/target_fixed.pdb \
  --contig "[B1-100/0 12-18]" \
  --hotspot-res A30 A33 \
  --cyclic \
  --cyc-chains b \
  --output-prefix outputs/cyclic_binder/design \
  --num-designs 200 \
  --diffuser-t 25
```

→ ProteinMPNN: `--chains B --temp 0.1`
→ AlphaFold3: standard validation
→ Filtering: `--min-iptm 0.75 --min-plddt 70`

**Expected:** Higher num_designs needed due to short peptide length
**Tip:** Cyclic peptides often have lower pLDDT — adjust thresholds accordingly

## Pattern 5: Partial Diffusion (Loop Redesign)

**Goal:** Redesign a flexible loop while keeping the rest of the structure fixed.

```bash
python scripts/run_rfdiffusion.py \
  --input-pdb outputs/structure_fixed.pdb \
  --contig "[A1-50/0 10-20/A71-150]" \
  --partial-T 10 \
  --output-prefix outputs/loop_redesign/design \
  --num-designs 20 \
  --diffuser-t 25
```

→ ProteinMPNN: standard parameters
→ AlphaFold3: `--no-msa` (structure already known)
→ Filtering: compare RMSD to original structure, keep pLDDT > 75

**Tip:** Lower `--diffuser-t` (25) and `--partial-T` (10) for conservative redesign

## Pattern 6: Sequence Inpainting (Variant Library)

**Goal:** Generate a diverse sequence library around a binding interface.

```bash
python scripts/run_rfdiffusion.py \
  --input-pdb outputs/binder_complex_fixed.pdb \
  --contig "[A1-150]" \
  --inpaint-seq "[A30-40/A60-70]" \
  --output-prefix outputs/variant_library/design \
  --num-designs 50 \
  --diffuser-t 50
```

→ ProteinMPNN: `--temp 0.3 0.5` for maximum diversity
→ AlphaFold3: standard validation
→ Filtering: standard thresholds

**Tip:** Use `--inpaint-seq` to mask residues you want to redesign while keeping structure

## Pattern 7: Fast Screening (100+ Designs)

**Goal:** Rapidly screen many designs using ESMFold instead of AlphaFold3.

```bash
python scripts/run_rfdiffusion.py \
  --contig "[150-150]" \
  --output-prefix outputs/fast_screen/design \
  --num-designs 50
```

→ ProteinMPNN: `--num-seq 8` → 400 sequences
→ **ESMFold** (not AlphaFold3): predict all 400 in ~1 hour
→ Filter: pLDDT > 75 → ~50 candidates
→ **AlphaFold3** (top 20 only): validate best candidates

**Time saved:** ~15 hours vs full AlphaFold3 on all 400

## Pattern 8: Symmetric Oligomer (C4 Tetramer)

**Goal:** Design a symmetric C4 tetramer.

```bash
python scripts/run_rfdiffusion.py \
  --contig "[100]" \
  --symmetry c4 \
  --output-prefix outputs/c4_tetramer/design \
  --num-designs 50 \
  --diffuser-t 50
```

→ ProteinMPNN: `tied_positions_jsonl` for symmetric positions
→ AlphaFold3: standard validation
→ Filtering: `min_ptm=0.7`, `min_plddt=75`

**Tip:** Contig length = monomer length (100), not total assembly length

## Pattern 9: Fold Conditioning (TIM Barrel)

**Goal:** Design a protein with a specific fold topology (e.g., TIM barrel).

```bash
python scripts/run_rfdiffusion.py \
  --contig "[300-350]" \
  --scaffoldguided \
  --scaffold-dir path/to/tim_barrel_scaffolds \
  --output-prefix outputs/tim_barrel/design \
  --num-designs 50 \
  --diffuser-t 50
```

→ ProteinMPNN: standard parameters
→ AlphaFold3: standard validation
→ Filtering: `--min-ptm 0.8` (high topology confidence needed)

**Tip:** Prepare scaffold_dir with secondary structure and block adjacency files

## Pattern 10: Enzyme Active Site Scaffolding

**Goal:** Scaffold a very small catalytic motif (3-10 residues).

```bash
python scripts/run_rfdiffusion.py \
  --input-pdb outputs/enzyme_fixed.pdb \
  --contig "[30-50/A55-58/30-50]" \
  --checkpoint models/ActiveSite_ckpt.pt \
  --output-prefix outputs/enzyme_scaffold/design \
  --num-designs 100 \
  --diffuser-t 50
```

→ ProteinMPNN: standard parameters, consider `--fixed-positions` for catalytic residues
→ AlphaFold3: standard validation
→ Filtering: `--min-plddt 70`

**Tip:** Use ActiveSite_ckpt.pt for motifs < 10 residues. Standard Base_ckpt.pt works poorly.

## Advanced Patterns

### Pattern 11: Antibody CDR Design

**Goal:** Design complementarity-determining regions (CDRs) for an antibody targeting a specific antigen.

```bash
python scripts/run_pdbfixer.py \
  --input antibody_antigen_complex.pdb \
  --output outputs/ab_fixed.pdb \
  --keep-chains H L A
```

```bash
python scripts/run_rfdiffusion.py \
  --input-pdb outputs/ab_fixed.pdb \
  --contig "[H95-100/0 10-20/H101-110]" \
  --output-prefix outputs/cdr_design/design \
  --num-designs 50 \
  --diffuser-t 25 \
  --partial-T 10
```

→ ProteinMPNN: `--chains "H L" --fixed-positions framework_positions.jsonl`
→ AlphaFold3: validate with antigen present
→ Filtering: `--min-iptm 0.75 --min-plddt 75`

**Tip:** Use partial diffusion with low --diffuser-t for conservative CDR redesign

### Pattern 12: Membrane Protein Design

**Goal:** Design a transmembrane protein with specified topology.

```bash
python scripts/run_rfdiffusion.py \
  --contig "[200-250]" \
  --output-prefix outputs/membrane/design \
  --num-designs 50 \
  --diffuser-t 50
```

→ ProteinMPNN: omit `--soluble`, consider `--omit-aas` for charged residues
→ AlphaFold3: standard validation
→ Filtering: `--min-plddt 70`, check per-residue pLDDT in TM regions

**Tip:** Use LigandMPNN's `per_residue_label_membrane_mpnn` model for membrane-specific design

### Pattern 13: Multi-Domain Protein

**Goal:** Design a protein with multiple independent domains connected by linkers.

```bash
python scripts/run_rfdiffusion.py \
  --contig "[50-60/0 10-15/50-60] \
  --output-prefix outputs/multidomain/design \
  --num-designs 30 \
  --diffuser-t 50
```

→ ProteinMPNN: `--num-seq 8 --temp 0.1`
→ AlphaFold3: validate full structure
→ Filtering: `--min-plddt 75 --min-ptm 0.6`

**Tip:** Each domain should independently fold; check per-domain pLDDT

### Pattern 14: Protein-Ligand Interface Design

**Goal:** Design a protein that binds a specific small molecule.

```bash
python scripts/run_pdbfixer.py \
  --input protein_with_ligand.pdb \
  --output outputs/protein_ligand_fixed.pdb \
  --keep-chains A
```

```bash
python scripts/run_rfdiffusion.py \
  --input-pdb outputs/protein_ligand_fixed.pdb \
  --contig "[A1-50/0 20-30/A71-150]" \
  --output-prefix outputs/ligand_interface/design \
  --num-designs 50 \
  --diffuser-t 25
```

→ LigandMPNN: `--model-type ligand_mpnn --use-atom-context`
→ AlphaFold3: include ligand in JSON input
→ Filtering: `--min-plddt 75`

**Tip:** LigandMPNN considers bound ligand context during sequence design

### Pattern 15: Protein-DNA Interface Design

**Goal:** Design a protein that recognizes and binds a specific DNA sequence.

```bash
python scripts/run_pdbfixer.py \
  --input transcription_factor_dna.pdb \
  --output outputs/tf_dna_fixed.pdb \
  --keep-chains A B C
```

```bash
python scripts/run_rfdiffusion.py \
  --input-pdb outputs/tf_dna_fixed.pdb \
  --contig "[A1-30/0 10-20/A31-100]" \
  --output-prefix outputs/dna_interface/design \
  --num-designs 50 \
  --diffuser-t 25
```

→ ProteinMPNN: `--chains A` (fix DNA chains)
→ AlphaFold3: include DNA in JSON input
→ Filtering: `--min-iptm 0.7`

**Tip:** AlphaFold3 can predict protein-DNA complexes

## How to Use Patterns

1. **Pick a pattern** based on your design goal
2. **Adjust parameters** as needed (length, num_designs, etc.)
3. **Run the pipeline** step by step
4. **Iterate** based on results

Each pattern is a starting point — feel free to customize!

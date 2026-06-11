---
name: antibody-design
description: Antibody design workflows including CDR design, humanization, and affinity maturation
---

# Antibody Design

## When to Trigger

- User says "antibody", "VHH", "nanobody", "Fab", "scFv", "CDR", "paratope"
- User wants to design an antibody targeting a specific antigen
- User asks about CDR grafting or humanization
- User wants to improve antibody affinity
- User needs to reduce antibody immunogenicity

## Overview

Antibody design is a specialized protein design workflow that focuses on:
1. **CDR (Complementarity-Determining Region) design** — The variable loops that bind antigen
2. **Humanization** — Reducing immunogenicity while maintaining binding
3. **Affinity maturation** — Improving binding strength
4. **Stability engineering** — Improving expression and shelf life

## Antibody Structure Basics

```
Heavy Chain (H): VH - CH1 - hinge - CH2 - CH3
                     |
Light Chain (L): VL - CL
                     |
                Fab (antigen binding)
                Fc (effector functions)

CDRs:
  H1: ~10 residues (H26-H35)
  H2: ~17 residues (H50-H65)
  H3: ~10 residues (H95-H102) — most variable
  L1: ~11 residues (L24-L34)
  L2: ~7 residues (L50-L56)
  L3: ~9 residues (L89-L97)
```

## Pipeline 1: De Novo Antibody Design

### Stage 0: Prepare antigen structure
```bash
python scripts/run_pdbfixer.py \
  --input antigen.pdb \
  --output outputs/antigen_fixed.pdb
```

### Stage 1: Generate antibody scaffold

Option A: Use known antibody framework (recommended)
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb outputs/antigen_fixed.pdb \
  --contig "[H1-120/0 L1-110]" \
  --output-prefix outputs/antibody/design \
  --num-designs 50 \
  --diffuser-T 50
```

Option B: Design CDRs on fixed framework
```bash
python scripts/run_rfdiffusion.py \
  --input-pdb antibody_framework.pdb \
  --contig "[H1-25/0 H10-20/H36-49/0 H10-20/H66-94/0 H10-15/H103-120]" \
  --output-prefix outputs/cdr_redesign/design \
  --num-designs 100 \
  --diffuser-T 25 \
  --partial-T 10
```

Option C: **Use IgDiff (Recommended for antibodies)**
- 74% CDR H3 design success vs 6% for RFdiffusion
- 93% light chain pairing success vs 0% for RFdiffusion
- See `igdiff-antibody` skill for detailed usage
```bash
python experiments/inference_se3_diffusion.py \
    --model_path huggingface_weights/ \
    --input_pdb antibody_framework.pdb \
    --redesign_cdrs H1,H2,H3,L1,L2,L3 \
    --output_dir outputs/igdiff_cdr \
    --num_samples 50
```

### Stage 2: Design sequences with constraints

```bash
python scripts/run_proteinmpnn.py \
  --pdb-path outputs/antibody/design_0.pdb \
  --out-folder outputs/antibody_seqs \
  --num-seq-per-target 16 \
  --sampling-temp 0.1 \
  --fixed-positions framework_positions.jsonl
```

**Framework positions to fix:**
```json
{"design_0": {"H": [1,2,3,...,25,36,37,...,49,66,67,...,94,103,104,...,120], "L": [1,2,3,...,110]}}
```

### Stage 3: Validate with antigen present

```bash
python scripts/convert_format.py \
  --from fasta \
  --to alphafold3_json \
  --input outputs/antibody_seqs/design_0.fa \
  --receptor-pdb outputs/antigen_fixed.pdb \
  --receptor-chain A \
  --job-name antibody_antigen \
  --output outputs/antibody_seqs/design_0_af3_input.json
```

```bash
python scripts/run_alphafold3.py \
  --json outputs/antibody_seqs/design_0_af3_input.json \
  --output-dir outputs/af3/antibody \
  --num-seeds 1 \
  --num-samples 5
```

### Stage 4: Filter for binding

```bash
python scripts/run_filtering.py \
  --results-dir outputs/af3/antibody \
  --min-iptm 0.75 \
  --min-plddt 75
```

## Pipeline 2: CDR Grafting

**Goal:** Transfer CDRs from a donor antibody to a human framework.

### Step 1: Identify donor CDRs

```python
# Parse donor antibody
from Bio.PDB import PDBParser
parser = PDBParser(QUIET=True)
donor = parser.get_structure("donor", "donor_antibody.pdb")

# Extract CDR sequences
cdrs = {
    "H1": extract_region(donor, "H", 26, 35),
    "H2": extract_region(donor, "H", 50, 65),
    "H3": extract_region(donor, "H", 95, 102),
    "L1": extract_region(donor, "L", 24, 34),
    "L2": extract_region(donor, "L", 50, 56),
    "L3": extract_region(donor, "L", 89, 97),
}
```

### Step 2: Select human framework

Common human frameworks:
- VH: IGHV1-2, IGHV3-23
- VL: IGKV1-39, IGLV3-21

### Step 3: Graft CDRs onto human framework

```python
# Build grafted antibody
grafted = build_grafted_antibody(human_framework, donor_cdrs)
```

### Step 4: Validate structure

```bash
python scripts/run_alphafold3.py \
  --json grafted_antibody.json \
  --output-dir outputs/af3/grafted
```

## Pipeline 3: Affinity Maturation

**Goal:** Improve binding affinity while maintaining specificity.

### Step 1: Identify mutation positions

```python
# Focus on CDR residues
# Positions with low pLDDT or high B-factor are good candidates
mutation_positions = identify_flexible_positions(antibody_structure)
```

### Step 2: Generate variants

```python
variants = []
for pos in mutation_positions:
    for aa in "ACDEFGHIKLMNPQRSTVWY":
        variant = mutate_sequence(wildtype, pos, aa)
        variants.append(variant)
```

### Step 3: Score variants

Option A: ProteinMPNN scoring
```bash
python scripts/run_proteinmpnn.py \
  --pdb-path antibody_antigen_complex.pdb \
  --out-folder outputs/scoring \
  --score-only \
  --path-to-fasta variants.fa
```

Option B: ESM-IF1 scoring
```python
from esm.inverse_folding import util

for variant in variants:
    ll, _ = util.score_sequence(model, alphabet, coords, variant)
    scores.append((variant, ll))
```

### Step 4: Select top variants

```python
top_variants = sorted(scores, key=lambda x: x[1], reverse=True)[:20]
```

### Step 5: Validate top variants

```bash
python scripts/run_alphafold3.py \
  --json top_variants.json \
  --output-dir outputs/af3/maturation
```

## Pipeline 4: Humanization

**Goal:** Reduce immunogenicity while maintaining binding.

### Step 1: Identify non-human residues

```python
# Compare CDR residues to human germline
human_residues = get_human_germline(framework_type)
non_human = identify_non_human_residues(cdr_sequence, human_residues)
```

### Step 2: Design humanized variants

```python
# Mutate non-human residues to human equivalents
humanized = []
for pos, aa in non_human.items():
    human_aa = get_human_equivalent(pos, framework_type)
    variant = mutate_sequence(original, pos, human_aa)
    humanized.append(variant)
```

### Step 3: Validate binding retained

```bash
python scripts/run_alphafold3.py \
  --json humanized_variants.json \
  --output-dir outputs/af3/humanization
```

### Step 4: Check for immunogenicity

```python
# Identify T-cell epitopes
epitopes = predict_t_cell_epitopes(sequence)
if epitopes:
    print("Warning: Potential T-cell epitopes detected")
    print(f"Positions: {epitopes}")
```

## Tips

- **CDR-H3 is the most important** for binding specificity
- **Framework residues should be fixed** during design
- **ipTM > 0.75** indicates good antibody-antigen interface
- **Check for aggregation** — antibodies with exposed hydrophobic patches may aggregate
- **Consider developability** — high charge, low stability, and poor solubility are common issues
- **Humanization** typically starts with CDR grafting then affinity maturation
- **VHH (nanobody)** design is simpler — single domain, no light chain

## References

- [AbLang](https://github.com/oxpig/AbLang) — Antibody language model
- [IgFold](https://github.com/sokrypton/IgFold) — Antibody structure prediction
- [BioPhi](https://github.com/Merck/BioPhi) — Antibody humanization
- [AntiBERTa](https://github.com/alchemab/antiberta) — Antibody-specific transformer

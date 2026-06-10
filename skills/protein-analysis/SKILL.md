---
name: protein-analysis
description: Analyze protein structures and sequences using built-in tools (no external ML models required)
---

# Protein Analysis (No External Tools Required)

## When to Trigger

- User says "analyze this structure", "check quality", "calculate RMSD"
- User wants to understand a PDB file without running predictions
- User needs sequence statistics, structural metrics, or comparisons
- User wants to validate a structure before running expensive ML tools

## Overview

These analyses use only Python/BioPython — no external ML models needed. They help validate structures and make informed decisions before running the full pipeline.

## Structure Analysis

### Parse and Inspect a PDB

```python
from Bio.PDB import PDBParser

parser = PDBParser(QUIET=True)
structure = parser.get_structure("protein", "design.pdb")

# Basic info
for model in structure:
    for chain in model:
        residues = list(chain)
        print(f"Chain {chain.id}: {len(residues)} residues")
        
        # Atom count
        atoms = [atom for residue in residues for atom in residue]
        print(f"  Total atoms: {len(atoms)}")
        
        # Check for CA-only
        ca_atoms = [a for a in atoms if a.id == 'CA']
        print(f"  CA atoms: {len(ca_atoms)}")
        print(f"  Is CA-only: {len(atoms) == len(ca_atoms)}")
```

### Calculate Radius of Gyration (ROG)

```python
import numpy as np
from Bio.PDB import PDBParser

parser = PDBParser(QUIET=True)
structure = parser.get_structure("protein", "design.pdb")

coords = []
for atom in structure.get_atoms():
    if atom.id == 'CA':
        coords.append(atom.coord)

coords = np.array(coords)
center = coords.mean(axis=0)
rog = np.sqrt(np.mean(np.sum((coords - center)**2, axis=1)))
print(f"Radius of gyration: {rog:.2f} Å")

# Typical ROG for protein of length N: ~2.2 * N^0.38 Å
expected_rog = 2.2 * len(coords) ** 0.38
print(f"Expected ROG: {expected_rog:.2f} Å")
print(f"Compactness ratio: {rog/expected_rog:.2f}")
```

### Calculate RMSD Between Two Structures

```python
import numpy as np
from Bio.PDB import PDBParser, Superimposer

parser = PDBParser(QUIET=True)
struct1 = parser.get_structure("s1", "design1.pdb")
struct2 = parser.get_structure("s2", "design2.pdb")

# Extract CA atoms
atoms1 = [a for a in struct1.get_atoms() if a.id == 'CA']
atoms2 = [a for a in struct2.get_atoms() if a.id == 'CA']

# Ensure same length
n = min(len(atoms1), len(atoms2))
atoms1 = atoms1[:n]
atoms2 = atoms2[:n]

# Superimpose
sup = Superimposer()
sup.set_atoms(atoms1, atoms2)
sup.apply(atoms2)

print(f"RMSD: {sup.rms:.3f} Å")
print(f"Rotation matrix:\n{sup.rotran[0]}")
print(f"Translation: {sup.rotran[1]}")
```

### Check for Atomic Clashes

```python
from Bio.PDB import PDBParser
from scipy.spatial import cKDTree
import numpy as np

parser = PDBParser(QUIET=True)
structure = parser.get_structure("protein", "design.pdb")

# Collect all heavy atom coordinates
atoms = []
coords = []
for atom in structure.get_atoms():
    if atom.element != 'H':  # Skip hydrogens
        atoms.append(atom)
        coords.append(atom.coord)

coords = np.array(coords)

# Find pairs within 2.5 Å (clashing)
tree = cKDTree(coords)
clashes = tree.query_pairs(r=2.5)

# Filter out bonded neighbors (sequential residues)
real_clashes = []
for i, j in clashes:
    a1, a2 = atoms[i], atoms[j]
    # Skip if same residue
    if a1.get_parent() == a2.get_parent():
        continue
    # Skip if adjacent residues and backbone atoms
    res1, res2 = a1.get_parent(), a2.get_parent()
    if abs(res1.id[1] - res2.id[1]) <= 1:
        if a1.id in ('N', 'CA', 'C', 'O') and a2.id in ('N', 'CA', 'C', 'O'):
            continue
    real_clashes.append((a1, a2))

print(f"Total clash pairs: {len(real_clashes)}")
for a1, a2 in real_clashes[:5]:
    dist = np.linalg.norm(a1.coord - a2.coord)
    print(f"  {a1.get_parent().id[1]}{a1.id} - {a2.get_parent().id[1]}{a2.id}: {dist:.2f} Å")
```

## Sequence Analysis

### Parse FASTA and Get Statistics

```python
from Bio import SeqIO
from collections import Counter

record = SeqIO.read("design.fa", "fasta")
sequence = str(record.seq)

print(f"Sequence length: {len(sequence)}")
print(f"Header: {record.description}")

# Amino acid composition
aa_counts = Counter(sequence)
print("\nAmino acid composition:")
for aa, count in sorted(aa_counts.items()):
    pct = 100 * count / len(sequence)
    print(f"  {aa}: {count} ({pct:.1f}%)")

# Hydrophobic ratio
hydrophobic = 'AILMFWVC'
hp_count = sum(aa_counts.get(aa, 0) for aa in hydrophobic)
print(f"\nHydrophobic ratio: {100*hp_count/len(sequence):.1f}%")

# Charge at pH 7
positive = sequence.count('K') + sequence.count('R') + sequence.count('H')
negative = sequence.count('D') + sequence.count('E')
net_charge = positive - negative
print(f"Net charge at pH 7: {net_charge:+d}")
print(f"  Positive (K+R+H): {positive}")
print(f"  Negative (D+E): {negative}")
```

### Calculate Isoelectric Point (pI)

```python
from Bio.SeqUtils import ProtParam

sequence = "MKTLLILTGLVAGES..."
analysis = ProtParam.ProteinAnalysis(sequence)

print(f"Molecular weight: {analysis.molecular_weight():.1f} Da")
print(f"Isoelectric point (pI): {analysis.isoelectric_point():.2f}")
print(f"Aromaticity: {analysis.aromaticity():.3f}")
print(f"Instability index: {analysis.instability_index():.2f}")
print(f"Is stable: {analysis.is_stable()}")
print(f"GRAVY (hydrophobicity): {analysis.gravy():.3f}")

# Secondary structure fraction
ss_frac = analysis.secondary_structure_fraction()
print(f"\nSecondary structure fraction:")
print(f"  Helix: {ss_frac[0]:.3f}")
print(f"  Sheet: {ss_frac[1]:.3f}")
print(f"  Turn:  {ss_frac[2]:.3f}")
```

### Check for Problematic Motifs

```python
import re

sequence = "MKTLLILTGLVAGES..."

# Common problematic motifs
problems = {
    'N-glycosylation': r'N[^P][ST]',  # N-X-S/T
    'Cysteine pairs': r'C.{1,3}C',     # Potential disulfides
    'Proline knots': r'PPP',           # Cis-proline issues
    'Methionine oxidation': r'M',      # Oxidation prone
    'Asp-Pro bonds': r'DP',            # Acid cleavage
    'Asp-Gly bonds': r'DG',            # Isomerization
}

for name, pattern in problems.items():
    matches = list(re.finditer(pattern, sequence))
    print(f"{name}: {len(matches)} matches")
    for m in matches:
        print(f"  Position {m.start()}: {m.group()}")
```

## Structural Quality Metrics

### Calculate B-Factor Statistics

```python
from Bio.PDB import PDBParser
import numpy as np

parser = PDBParser(QUIET=True)
structure = parser.get_structure("protein", "design.pdb")

bfactors = []
for atom in structure.get_atoms():
    bfactors.append(atom.get_bfactor())

bfactors = np.array(bfactors)
print(f"Mean B-factor: {bfactors.mean():.2f}")
print(f"Median B-factor: {np.median(bfactors):.2f}")
print(f"Std B-factor: {bfactors.std():.2f}")
print(f"Min B-factor: {bfactors.min():.2f}")
print(f"Max B-factor: {bfactors.max():.2f}")

# For RFdiffusion: B=0 means diffused, B=1 means fixed
unique_bfactors = set(bfactors)
if unique_bfactors == {0.0, 1.0}:
    fixed = sum(bfactors == 1.0)
    diffused = sum(bfactors == 0.0)
    print(f"\nRFdiffusion output detected:")
    print(f"  Fixed atoms (B=1): {fixed}")
    print(f"  Diffused atoms (B=0): {diffused}")
```

### Ramachandran Analysis (Simplified)

```python
from Bio.PDB import PDBParser
import math

parser = PDBParser(QUIET=True)
structure = parser.get_structure("protein", "design.pdb")

for model in structure:
    for chain in model:
        residues = list(chain)
        for i in range(1, len(residues)-1):
            res = residues[i]
            try:
                n = res['N'].get_vector()
                ca = res['CA'].get_vector()
                c = res['C'].get_vector()
                
                # Phi (previous C - N - CA - C)
                prev_c = residues[i-1]['C'].get_vector()
                phi = math.degrees(calc_dihedral(prev_c, n, ca, c))
                
                # Psi (N - CA - C - next N)
                next_n = residues[i+1]['N'].get_vector()
                psi = math.degrees(calc_dihedral(n, ca, c, next_n))
                
                # Classify
                region = "other"
                if -180 < phi < 0 and -100 < psi < 50:
                    region = "beta"  # Beta sheet
                elif -180 < phi < 0 and 50 < psi < 180:
                    region = "alpha"  # Alpha helix
                elif phi > 0:
                    region = "left-handed"  # Left-handed helix
                
                print(f"Residue {res.id[1]}: phi={phi:.1f}, psi={psi:.1f} → {region}")
            except KeyError:
                continue

from Bio.PDB.vectors import calc_dihedral
```

## Comparison Utilities

### Compare Multiple Designs

```python
import glob
from Bio.PDB import PDBParser

parser = PDBParser(QUIET=True)

results = []
for pdb_file in sorted(glob.glob("outputs/design_*.pdb"))[:10]:
    structure = parser.get_structure("design", pdb_file)
    
    # Count residues
    n_residues = sum(1 for _ in structure.get_residues())
    
    # Count atoms
    n_atoms = sum(1 for _ in structure.get_atoms())
    
    # CA-only check
    is_ca_only = all(a.id == 'CA' for a in structure.get_atoms())
    
    results.append({
        'file': pdb_file,
        'residues': n_residues,
        'atoms': n_atoms,
        'ca_only': is_ca_only,
    })

# Print summary
print(f"{'File':<30} {'Residues':<10} {'Atoms':<8} {'CA-only':<8}")
print("-" * 60)
for r in results:
    print(f"{r['file']:<30} {r['residues']:<10} {r['atoms']:<8} {str(r['ca_only']):<8}")
```

## Tips

- These analyses are **fast** (seconds) vs ML tools (minutes/hours)
- Use them to **validate inputs** before running expensive pipelines
- **RMSD < 2Å** between predicted and design = good structural match
- **ROG** close to expected = compact, well-folded protein
- **Net charge** near neutral (0±5) = better solubility
- **pI** 5-9 = typical for soluble proteins
- **Instability index < 40** = stable protein
- Check for **clashes** before submitting to AlphaFold3
- **CA-only structures** need ProteinMPNN before validation

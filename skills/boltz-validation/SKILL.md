---
name: boltz-validation
description: Biomolecular structure prediction with Boltz-1 — fully open-source AlphaFold3 alternative supporting proteins, nucleic acids, small molecules, and complexes
---

# Alternative Stage 3: Boltz-1 Structure Validation

> **Quick Entry**: Stage 3 alternative | MIT license | complexes | covalent modifications
>
> **Upstream**: `sequence-design` (ProteinMPNN/LigandMPNN/ESM-IF1) | **Downstream**: `filtering-ranking`

## When to Trigger

- User says "Boltz", "Boltz-1", "Boltz-2"
- User wants open-source structure prediction with **commercial-friendly license**
- User needs to predict **complexes** (protein+ligand, protein+DNA, etc.)
- User wants MIT-licensed alternative to AlphaFold3
- User needs structure prediction for **RNA/DNA** or **modified residues**
- User says "I need a commercially usable structure predictor"

## Boltz-1 Overview

[Boltz-1](https://github.com/jwohlwend/boltz) is a fully open-source biomolecular structure prediction model from MIT researchers. Released in **November 2024**, it's the first open-source model to achieve **AlphaFold3-level accuracy** across proteins, nucleic acids, small molecules, and their complexes.

### Key Differences from AlphaFold3

| Feature | AlphaFold3 | Boltz-1 |
|---------|------------|---------|
| License | Non-commercial research only | **MIT (fully open)** |
| Commercial use | ❌ No | ✅ Yes |
| Molecules | Protein, DNA, RNA, ligand | Protein, DNA, RNA, ligand, ions, glycans |
| Modified residues | Limited | ✅ Supported |
| Covalent ligands | Limited | ✅ Supported |
| MSA server | Required setup | Built-in web service |
| Installation | Complex | `pip install boltz` |
| Speed | Slow | Comparable to AF3 |
| Binding affinity | No | ✅ Boltz-2 (2025) |

**Key insight**: Boltz-1 is the **best choice** when you need AlphaFold3-level accuracy with a permissive license, especially for commercial drug discovery.

## Installation

```bash
# Recommended: fresh Python environment (Python 3.11+)
pip install boltz[cuda] -U

# For CPU-only
pip install boltz -U

# From source (latest updates)
git clone https://github.com/jwohlwend/boltz.git
cd boltz
pip install -e .[cuda]
```

## Usage

### Command Line

```bash
# Basic prediction with MSA server
boltz predict input.fasta --use_msa_server

# Batch prediction from directory
boltz predict input_dir/ --use_msa_server --out_dir outputs/

# With custom config
boltz predict input.yaml --out_dir outputs/
```

### Input Formats

#### FASTA Format
```
>A|protein|C1
MKTLLILTGLVAGESKTVLQYF...

>B|protein|C2
GSHMQSITDFGT...

>C|ligand|L1
CC(C)Cc1ccc(cc1)C(C)C(=O)O
```

#### YAML Schema (Advanced)
```yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: MKTLLILTGLVAGESKTVLQYF...
  - protein:
      id: B
      sequence: GSHMQSITDFGT...
  - ligand:
      id: C
      smiles: "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
```

### Python API

```python
import boltz

# Load model
model = boltz.Boltz1Model(device="cuda")

# Predict structure
result = model.predict(
    sequences=[
        {"protein": {"id": "A", "sequence": "MKTLLIL..."}},
        {"ligand": {"id": "L", "smiles": "CC(C)Cc1..."}},
    ],
    use_msa_server=True,
)

# Save results
result.save_pdb("output.pdb")
result.save_confidence("confidence.json")
```

## Boltz-2: Structure + Affinity Prediction (2025)

Boltz-2 extends Boltz-1 to jointly predict **structures AND binding affinities**:

```bash
# Boltz-2 predicts both structure and binding affinity
boltz predict input.yaml --model boltz2 --out_dir outputs/
```

**Capabilities:**
- Approaches physics-based FEP accuracy
- **1000× faster** than traditional FEP methods
- Enables practical in silico screening
- Predicts ΔG of binding

## Pipeline Integration

### Option 1: Boltz-1 as AlphaFold3 Replacement
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → Boltz-1 (validation)
                                                        ↓
                                        Stage 4 (Filtering)
```

### Option 2: Boltz-1 for Complex Validation
```
Stage 1 (RFdiffusion binder) → Stage 2 (ProteinMPNN)
                                    ↓
                        Boltz-1 (validate binder-target complex)
                                    ↓
                        Filter by confidence + binding pose
```

### Option 3: Boltz-2 for Affinity Screening
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → Boltz-2 (structure + affinity)
                                                        ↓
                                        Rank by predicted ΔG
```

## Comparison with Other Stage 3 Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| Commercial drug discovery | **Boltz-1** | MIT license, fully open |
| Academic research | AlphaFold3 or Boltz-1 | Both excellent |
| Protein-ligand complexes | **Boltz-1** | Native ligand support |
| RNA/DNA structures | **Boltz-1** | Native nucleic acid support |
| Modified residues | **Boltz-1** | Better support |
| Speed | OmegaFold or ESMFold | Faster but less accurate |
| Binding affinity | **Boltz-2** | Only tool with ΔG prediction |
| Monomer only | OmegaFold | Simpler, no DB needed |

## Confidence Metrics

Boltz-1 outputs multiple confidence metrics:

| Metric | Description | Good Threshold |
|--------|-------------|----------------|
| pLDDT | Per-atom confidence | >70 |
| pTM | Topology confidence | >0.7 |
| ipTM | Interface confidence | >0.8 |
| ΔG (Boltz-2) | Predicted binding free energy | < -7 kcal/mol |

```python
# Extract confidence metrics
import json

with open("boltz_output_confidence.json") as f:
    confidence = json.load(f)

print(f"pLDDT: {confidence['plddt']:.1f}")
print(f"pTM: {confidence['ptm']:.3f}")
print(f"ipTM: {confidence['iptm']:.3f}")
if 'dg' in confidence:
    print(f"ΔG: {confidence['dg']:.2f} kcal/mol")
```

## Tips

- **License advantage**: Boltz-1's MIT license makes it ideal for commercial pipelines
- **MSA server**: Use `--use_msa_server` for automatic MSA generation (no local DBs)
- **Complexes**: Boltz-1 excels at protein-ligand and protein-nucleic acid complexes
- **Modified residues**: Use SMILES for modified residues or non-standard amino acids
- **Boltz-2 affinity**: For drug discovery, Boltz-2's ΔG prediction is invaluable
- **Batch mode**: Process multiple inputs by pointing to a directory
- **Memory**: Large complexes may require significant GPU memory (A100 recommended)

## Extensions

- **boltz_ext** (`github.com/cddlab/boltz_ext`): Community extension with restraint-guided inference for improved ligand stereochemistry

## References

- [Boltz-1 GitHub](https://github.com/jwohlwend/boltz)
- [Boltz-1 Technical Report](https://doi.org/10.1101/2024.11.19.624167)
- [MIT Jameel Clinic Announcement](https://jclinic.mit.edu/democratizing-science-boltz-1/)
- [Boltz-2 Paper](https://www.biorxiv.org/content/10.1101/2025.XX.XX.XXXXXXv1)

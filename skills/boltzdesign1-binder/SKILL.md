---
name: boltzdesign1-binder
description: Guide for using BoltzDesign1, an MIT-licensed all-atom biomolecular binder design tool that inverts Boltz-1 for proteins, small molecules, RNA, DNA, and metals
---

# BoltzDesign1 All-Atom Binder Design Guide

**BoltzDesign1** is an **MIT-licensed open-source tool** from MIT (Yehlin Cho and Sergey Ovchinnikov's lab) for **generalized biomolecular binder design**. Instead of fine-tuning a generative model, it **inverts the Boltz-1 structure prediction model** (open-source AlphaFold3) to design protein binders against proteins, small molecules, RNA, DNA, metal ions, and post-translationally modified residues.

Use BoltzDesign1 when you want:
- **All-atom binder design** without training or fine-tuning a new model
- Support for **diverse target modalities**: proteins, small molecules, nucleic acids, metals, PTMs
- A **permissive MIT license** for academic and commercial work
- A design method powered directly by an **AlphaFold3-class structure predictor**
- To cross-validate designs with **AlphaFold3** (optional) before ordering experiments

---

## What Makes BoltzDesign1 Different

| Feature | BindCraft | RFdiffusionAA + LigandMPNN | BoltzDesign1 |
|---------|-----------|----------------------------|--------------|
| Underlying model | AlphaFold2 hallucination | RFdiffusion + MPNN | **Inverts Boltz-1 (AlphaFold3-class)** |
| Target modalities | Protein binders | Ligands, cofactors | **Protein / small molecule / RNA / DNA / metal / PTM** |
| Requires fine-tuning? | No | No | **No** |
| License | Non-commercial / PyRosetta | Mixed | **MIT** |
| AF3 cross-validation | Built-in AF2 | External | **Built-in optional AlphaFold3** |

BoltzDesign1 is especially attractive for **novel target types** that lack large training datasets, because it leverages Boltz-1's generalization without modifying its weights.

---

## Installation (Document-Only — Do Not Install)

```bash
git clone https://github.com/yehlincho/BoltzDesign1.git
cd BoltzDesign1
chmod +x setup.sh
./setup.sh
```

`setup.sh` will:
- Create a conda environment with Python 3.10
- Install dependencies and register a Jupyter kernel
- Download Boltz-1 model weights
- Configure LigandMPNN and ProteinMPNN
- Optionally install PyRosetta

**Note:** AlphaFold3 is **not** installed by the script; set it up separately if you want `--run_alphafold True` cross-validation.

**Sources:**
- [GitHub repository](https://github.com/yehlincho/BoltzDesign1)
- [Paper — bioRxiv 2025](https://www.biorxiv.org/content/10.1101/2025.04.06.647261v1)
- [Colab notebook](https://colab.research.google.com/github/yehlincho/BoltzDesign1/blob/main/Boltzdesign1.ipynb)

---

## Quickstart: Design a Small-Molecule Binder

```bash
python boltzdesign.py \
  --target_name 7v11 \
  --target_type small_molecule \
  --target_mols OQO \
  --gpu_id 0 \
  --design_samples 2 \
  --suffix 1
```

- `--target_name` — PDB code or custom name
- `--target_type` — `small_molecule`, `dna`, `rna`, `protein`, `metal`, etc.
- `--target_mols` — CCD code(s) for ligand target(s)
- `--design_samples` — number of independent designs to generate
- `--suffix` — run identifier appended to output folder

### Design a DNA binder from a PDB

```bash
python boltzdesign.py \
  --target_name 5zmc \
  --target_type dna \
  --pdb_target_ids C,D \
  --gpu_id 0 \
  --design_samples 5 \
  --suffix 1
```

### Use a custom target PDB

```bash
python boltzdesign.py \
  --target_name 7v11 \
  --pdb_path /path/to/your_target.pdb \
  --target_type small_molecule \
  --target_mols OQO \
  --gpu_id 0 \
  --design_samples 2 \
  --suffix own
```

---

## Design Algorithm

BoltzDesign1 optimizes directly on Boltz-1's **distogram** using only the **Pairformer and Confidence modules**, which keeps compute costs low compared to full diffusion inversion.

Default configuration:

```python
config = {
    'mutation_rate': 1,
    'learning_rate_pre': 0.2,
    'learning_rate': 0.1,
    'pre_iteration': 30,
    'soft_iteration': 75,
    'temp_iteration': 45,
    'hard_iteration': 5,
    'semi_greedy_steps': 0,
    'design_algorithm': '3stages',
}
```

You can override these in the script or via a JSON config file.

### Sequence redesign
- **Protein–protein interfaces** → ProteinMPNN
- **Protein–ligand / non-protein interfaces** → LigandMPNN
- Interface residues (default `< 4 Å`) are fixed during design

---

## Output Files

Successful designs are saved under:

```
your_output_folder/ligandmpnn_cutoff_(interface_threshold)/03_af_pdb_success/
```

Key files:

| File | Content |
|------|---------|
| `*.pdb` | Designed binder + target complex |
| `high_iptm_confidence_scores.csv` | Summary of ipTM / confidence scores |
| Trajectory files | If `--save_trajectory True` is enabled |

Use `scripts/summarize_outputs.py` to aggregate counts and top designs across runs.

---

## Optional AlphaFold3 Cross-Validation

BoltzDesign1 can re-predict its own designs with AlphaFold3 for an independent confidence check:

```bash
python boltzdesign.py ... \
  --alphafold_dir ~/alphafold3 \
  --af3_docker_name alphafold3 \
  --af3_database_settings /path/to/db/settings \
  --af3_hmmer_path /path/to/hmmer
```

Disable AF3 validation with:

```bash
python boltzdesign.py ... --run_alphafold False
```

---

## Pipeline Integration

BoltzDesign1 is a **specialized Stage 1–2 binder design pipeline** that internally uses Boltz-1 for structure awareness:

| Stage | BoltzDesign1 Component | Purpose |
|-------|------------------------|---------|
| 0 | PDBFixer / input PDB | Prepare target structure |
| 1 | `boltzdesign.py` | All-atom binder hallucination via Boltz-1 inversion |
| 2 | LigandMPNN / ProteinMPNN | Redesign interface sequences |
| 3 | Optional AF3 / Boltz-2 | Independent validation |
| 4 | `high_iptm_confidence_scores.csv` + filtering | Rank and select best designs |

### Recommended pairings
- Small-molecule binder campaign → **BoltzDesign1** → `boltz2-validation` or `diffdock-ligand`
- DNA/RNA binder design → **BoltzDesign1** → `rfdiffusion3-workflow` comparison
- Protein binder with PTMs/metals → **BoltzDesign1** → `rosettafold-all-atom` validation

---

## Hardware & Timing

- **GPU required** (the script selects the GPU with `--gpu_id`)
- Typical designs take minutes to tens of minutes depending on target size and iteration budget
- AlphaFold3 cross-validation adds additional GPU time and requires AF3 databases

---

## Interpreting Success

The authors report in silico success rates up to ~90% for small-molecule binder benchmarks under relaxed criteria. In practice, filter designs by:

| Metric | Suggested threshold |
|--------|---------------------|
| ipTM | ≥ 0.7 |
| Confidence score (Boltz-1) | Top 20% of generated samples |
| AF3 cross-validation pLDDT | ≥ 80 (if AF3 is run) |

**Important:** BoltzDesign1 is experimental and, as of the 2025 preprint, has not yet been experimentally validated. Treat designs as high-priority candidates for ordering, not guaranteed binders.

---

## Strengths and Limitations

**Strengths:**
- MIT license (commercial-friendly)
- No model fine-tuning required
- Generalizes across proteins, small molecules, RNA, DNA, metals, and PTMs
- Built on Boltz-1, an open AlphaFold3-class model
- Optional AlphaFold3 cross-validation
- Active Colab notebook for quick tests

**Limitations:**
- Experimental; no published wet-lab validation yet
- Requires GPU and Boltz-1 weights
- AlphaFold3 cross-validation is optional but adds significant setup burden
- Success metrics are in silico; experimental confirmation is essential
- PyRosetta is optional but recommended for some downstream steps

---

## Citation

Cho et al., "BoltzDesign1: Inverting All-Atom Structure Prediction Model for Generalized Biomolecular Binder Design," *bioRxiv*, 2025. DOI: [10.1101/2025.04.06.647261](https://doi.org/10.1101/2025.04.06.647261)

```bibtex
@article{cho2025boltzdesign1,
  author = {Cho, Yehlin and Pacesa, Martin and Zhang, Zhidian and Correia, Bruno E. and Ovchinnikov, Sergey},
  title = {BoltzDesign1: Inverting All-Atom Structure Prediction Model for Generalized Biomolecular Binder Design},
  journal = {bioRxiv},
  year = {2025},
  doi = {10.1101/2025.04.06.647261}
}
```

---

## See Also

- `bindcraft-workflow` — Automated binder design with AF2 hallucination
- `boltz-validation` — Boltz-1 structure validation
- `boltz2-validation` — Boltz-2 structure + affinity prediction
- `rfdiffusion-all-atom` — RFdiffusion for ligand/cofactor-aware design
- `rfdiffusion3-workflow` — All-atom DNA/RNA/ligand/enzyme design
- `diffdock-ligand` — Blind small-molecule docking
- `rosettafold-all-atom` — Validate protein-ligand complexes
- `pipeline-selection` — Choose the right workflow
- `periodic-summary` — Track design outputs

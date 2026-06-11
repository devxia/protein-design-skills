---
name: boltzgen-binder-design
description: Guide for using BoltzGen, an MIT-licensed universal binder design model for proteins, peptides, small molecules, antibodies, and nanobodies
---

# BoltzGen Universal Binder Design Guide

**BoltzGen** is an **MIT-licensed all-atom generative model** for universal binder design. It can design proteins and peptides that bind to proteins, peptides, small molecules, antibodies, nanobodies, and other biomolecular targets. It is developed by Hannes Stärk and collaborators at MIT Jameel Clinic.

Use BoltzGen when you want:
- A **unified design + folding** pipeline for binder generation
- Support for **multiple modalities**: protein, peptide, small molecule, antibody, nanobody
- An **end-to-end pipeline**: design → inverse folding → validation folding → analysis → filtering/ranking
- A **permissive MIT license** for both academic and commercial use
- Strong experimental validation (8 wet-lab campaigns, nanomolar binders for 66% of novel targets)

---

## What Makes BoltzGen Different

| Feature | RFdiffusion + ProteinMPNN + AlphaFold3 | BindCraft | BoltzGen |
|---------|----------------------------------------|-----------|----------|
| Target modalities | Protein / peptide / some ligands | Protein binders | **Protein / peptide / small molecule / antibody / nanobody** |
| Design + validation folding | Separate tools | AF2-based | **Unified Boltz-2 co-folding representation** |
| Pipeline | Multi-script | End-to-end | **End-to-end single command** |
| Output filtering | Manual / external | Built-in | **Built-in analysis + filtering + ranking** |
| License | Mixed | Non-commercial / PyRosetta | **MIT** |

BoltzGen is especially attractive for **binder design campaigns** because it wraps the entire workflow — from a design specification YAML to a ranked set of final designs — in a single `boltzgen run` command.

---

## Installation (Document-Only — Do Not Install)

```bash
# Requires Python >= 3.11
pip install boltzgen
```

Or install from source:

```bash
git clone https://github.com/HannesStark/boltzgen.git
cd boltzgen
pip install -e .
```

### Docker

```bash
docker build -t boltzgen .
mkdir -p workdir cache example
# Run an example
docker run --rm --gpus all \
  -v "$(realpath workdir)":/workdir \
  -v "$(realpath cache)":/cache \
  -v "$(realpath example)":/example boltzgen \
  boltzgen run /example/vanilla_protein/1g13prot.yaml \
    --output /workdir/test \
    --protocol protein-anything \
    --num_designs 2
```

### Model weights

`boltzgen run` downloads ~6 GB of models to `~/.cache` on first use. You can override the cache location with `--cache YOUR_PATH` or by setting `$HF_HOME`.

**Sources:**
- [GitHub repository](https://github.com/HannesStark/boltzgen)
- [Paper PDF](https://hannes-stark.com/assets/boltzgen.pdf)
- [MIT Jameel Clinic project page](https://jclinic.mit.edu/research-project/boltzgen/)
- [boltzgen-view community tool](https://github.com/rhyschappell/boltzgen-view)

---

## Quickstart: Design a Protein Binder

### 1. Write a design specification YAML

```yaml
entities:
  # Designed protein binder with random length between 80 and 140 residues
  - protein:
      id: B
      sequence: 80..140

  # Target extracted from a .cif file
  - file:
      path: 6m1u.cif
      include:
        - chain:
            id: A
```

### 2. Validate the specification

```bash
boltzgen check example/vanilla_protein/1g13prot.yaml
```

This produces an `.mmcif` file you can inspect in PyMOL, Chimera, or [Mol*](https://molstar.org/viewer/) to verify the binding site is highlighted correctly.

### 3. Run the full pipeline

```bash
boltzgen run example/vanilla_protein/1g13prot.yaml \
  --output workbench/test_run \
  --protocol protein-anything \
  --num_designs 10 \
  --budget 2
```

- `--num_designs 10` — number of intermediate designs to generate (in practice, use 10,000–60,000)
- `--budget 2` — number of designs in the final diversity-optimized set
- `--reuse` — resume an interrupted run without losing progress

### 4. Rerun filtering with custom criteria

```bash
boltzgen run example/vanilla_protein/1g13prot.yaml \
  --output workbench/test_run \
  --protocol protein-anything \
  --steps filtering \
  --refolding_rmsd_threshold 3.0 \
  --filter_biased=false \
  --additional_filters 'ALA_fraction<0.3' 'filter_rmsd_design<2.5'
```

Or use the provided `filter.ipynb` Jupyter notebook for interactive filtering.

---

## Supported Protocols

| Protocol | Design Target | Notable Options |
|----------|---------------|-----------------|
| `protein-anything` | Protein binders for proteins/peptides | Includes `design_folding` step |
| `peptide-anything` | Cyclic/linear peptide binders | No Cys generated; no `design_folding` |
| `protein-small_molecule` | Small-molecule binding proteins | Includes affinity prediction |
| `antibody-anything` | Antibody CDR redesign | No Cys generated; no `design_folding` |
| `nanobody-anything` | Nanobody CDR redesign | Same settings as antibody |
| `protein-redesign` | Redesign/optimize existing proteins | Uses `design_mask` for template definition |

---

## Pipeline Output

```
workbench/test_run/
├── config/
├── steps.yaml
├── intermediate_designs/
│   ├── *.cif              # Designed structures before inverse folding
│   └── *.npz              # Metadata
├── intermediate_designs_inverse_folded/
│   ├── *.cif              # After inverse folding
│   ├── refold_cif/        # Refolded complexes (target + binder)
│   ├── refold_design_cif/ # Refolded binders alone
│   ├── aggregate_metrics_analyze.csv
│   └── per_target_metrics_analyze.csv
└── final_ranked_designs/
    ├── intermediate_ranked_N_designs/
    ├── final_BUDGET_designs/
    ├── all_designs_metrics.csv
    ├── final_designs_metrics_BUDGET.csv
    └── results_overview.pdf
```

---

## Running Individual Steps

```bash
# Only design + inverse folding
boltzgen run example/cyclotide/3ivq.yaml \
  --output workbench/partial \
  --protocol peptide-anything \
  --steps design inverse_folding \
  --num_designs 2

# Only inverse folding on a fully specified structure
boltzgen run example/inverse_folding/1brs.yaml \
  --output workbench/if-only \
  --only_inverse_fold \
  --inverse_fold_num_sequences 2

# Only filtering
boltzgen run example/vanilla_protein/1g13prot.yaml \
  --output workbench/test_run \
  --protocol protein-anything \
  --steps filtering
```

Available steps: `design`, `inverse_folding`, `design_folding`, `folding`, `affinity`, `analysis`, `filtering`.

---

## Merging Multiple Runs

If you parallelized designs across multiple outputs:

```bash
boltzgen merge workbench/run_a workbench/run_b workbench/run_c \
  --output workbench/merged

# Re-filter the merged set
boltzgen run example/vanilla_protein/1g13prot.yaml \
  --steps filtering \
  --output workbench/merged \
  --protocol protein-anything \
  --budget 60 \
  --alpha 0.05
```

---

## Pipeline Integration

BoltzGen is an **end-to-end Stage 1–4 replacement** for binder design. You can use it standalone:

| Stage | BoltzGen Component | Purpose |
|-------|-------------------|---------|
| 0 | `boltzgen check` + input YAML | Validate target / binding site |
| 1 | `design` step | Generate binder backbones |
| 2 | `inverse_folding` step | Design sequences |
| 3 | `folding` / `design_folding` step | Validate structures with Boltz-2 |
| 4 | `analysis` + `filtering` steps | Rank and select best designs |

If you want to integrate BoltzGen into a broader pipeline, you can:
1. Export `intermediate_designs/` PDB/CIF to run ProteinMPNN / PiFold externally
2. Export `refold_cif/` for additional validation with AlphaFold3 or Chai-1
3. Use `scripts/summarize_outputs.py` on `final_ranked_designs/` for project-wide reporting

### Recommended pairings
- Fast academic binder campaign → BoltzGen standalone → filter with `filter.ipynb`
- Multi-method comparison → BoltzGen + BindCraft + RFdiffusion → cross-validation
- Commercial pipeline → BoltzGen (MIT) → Chai-1 validation (Apache 2.0)

---

## When to Use BoltzGen vs Other Binder Tools

| Your Goal | Best Tool |
|-----------|-----------|
| General-purpose binder with maximum community support | RFdiffusion + ProteinMPNN + AlphaFold3 |
| Automated binder design with high experimental success | BindCraft |
| **Universal binder design (protein / peptide / small molecule / antibody / nanobody)** | **BoltzGen** |
| **End-to-end single-command pipeline with built-in filtering** | **BoltzGen** |
| MIT-licensed binder design | **BoltzGen** |
| HPC/cloud production binder pipeline | nf-binder-design |

---

## Strengths and Limitations

**Strengths:**
- MIT license (commercial-friendly)
- All-atom universal binder design across multiple modalities
- Unified design and validation folding with Boltz-2 representations
- End-to-end pipeline in a single command
- Built-in inverse folding, analysis, and filtering
- Strong experimental validation with wet-lab campaigns
- Active Slack community and viewer tools (boltzgen-view)

**Limitations:**
- Requires ~6 GB model download on first run
- GPU required for practical use
- Large-scale campaigns need 10,000–60,000 designs for best results
- Newer than RFdiffusion; fewer third-party tutorials
- Protein-redesign protocol is less mature than dedicated tools like ProteinMPNN

---

## Citation

Stark et al., "BoltzGen: Toward Universal Binder Design," *bioRxiv*, 2025.

```bibtex
@article{stark2025boltzgen,
  author = {Stark, Hannes and Faltings, Felix and Choi, MinGyu and Xie, Yuxin and Hur, Eunsu and O'Donnell, Timothy John and Bushuiev, Anton and U{\c c}ar, Talip and Passaro, Saro and Mao, Weian and Reveiz, Mateo and Bushuiev, Roman and Pluskal, Tom{\'a}{\v s} and Sivic, Josef and Kreis, Karsten and Vahdat, Arash and Ray, Shamayeeta and Goldstein, Jonathan T. and Savinov, Andrew and Hambalek, Jacob A. and Gupta, Anshika and Taquiri-Diaz, Diego A. and Zhang, Yaotian and Hatstat, A. Katherine and Arada, Angelika and Kim, Nam Hyeong and Tackie-Yarboi, Ethel and Boselli, Dylan and Schnaider, Lee and Liu, Chang C. and Li, Gene-Wei and Hnisz, Denes and Sabatini, David M. and DeGrado, William F. and Wohlwend, Jeremy and Corso, Gabriele and Barzilay, Regina and Jaakkola, Tommi},
  title = {BoltzGen: Toward Universal Binder Design},
  year = {2025},
  doi = {10.1101/2025.11.20.689494},
  journal = {bioRxiv}
}
```

---

## See Also

- `bindcraft-workflow` — Automated binder design with high experimental success
- `rfdiffusion3-workflow` — All-atom biomolecular interaction design
- `pocketgen-ligand` — Pocket redesign around ligands
- `protpardelle-allatom` — All-atom seq+struct motif scaffolding
- `nf-binder-design` — HPC/cloud Nextflow binder pipeline
- `pipeline-selection` — Choose the right workflow
- `periodic-summary` — Track progress across stages

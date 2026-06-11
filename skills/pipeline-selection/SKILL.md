---
name: pipeline-selection
description: Guide users in selecting the optimal protein design pipeline from 7+ available options based on their goals, resources, and constraints
---

# Pipeline Selection Guide

**Not sure which pipeline to use? This guide will match you to the right one in 30 seconds.**

## Beginner's Recommendation

**New to protein design? Start here:**

| Step | Action | Tool | Time |
|------|--------|------|------|
| 1 | Install PDBFixer | `conda install -c conda-forge pdbfixer openmm` | 30s |
| 2 | Install ESMFold | `pip install fair-esm` | 1min |
| 3 | Get a PDB file | Download from [RCSB PDB](https://www.rcsb.org/) | 1min |
| 4 | Run the pipeline | `python scripts/run_pdbfixer.py -i target.pdb -o fixed.pdb` | 5s |

**Then add RFdiffusion + ProteinMPNN for full design capabilities.**

See `install-guide` skill for detailed installation instructions.

## Immediate Match: What describes your project?

| My situation is... | Recommended Pipeline | Read This Skill |
|--------------------|---------------------|-----------------|
| I just want to design a protein (general purpose) | **Standard** | `full-pipeline` |
| I need to design something FAST without big databases | **Fast Screening** | `fast-screening` |
| I'm designing a short peptide (8-30 amino acids) | **Peptide** | `diffpepbuilder-design` |
| I'm designing a macrocyclic peptide (12-18 aa, cyclic) | **RFpeptides** | `rfpeptides-macrocycle` |
| I want automated binder design with high experimental success | **BindCraft** | `bindcraft-workflow` |
| I want to invert Boltz-1 / AlphaFold3 for all-atom binder design | **BoltzDesign1** | `boltzdesign1-binder` |
| I want HPC/cloud binder design with multiple methods | **nf-binder-design** | `nf-binder-design` |
| My design needs to bind a small molecule / cofactor | **Ligand-Aware** | `rfdiffusion-all-atom` |
| I need to validate with ligands / DNA / RNA / metals (AF3 can't) | **RFAA** | `rosettafold-all-atom` |
| I want to redesign an existing pocket around a ligand | **PocketGen** | `pocketgen-ligand` |
| I want to dock a small molecule into my protein (blind docking) | **DiffDock** | `diffdock-ligand` |
| I want the most reliable results (multiple validators) | **Cross-Validation** | `cross-validation` |
| I want to save compute by pre-screening | **Score-First** | `score-first-screening` |
| I want latent-space optimization toward a fitness label | **ReLSO** | `relso-sequence-optimization` |
| I want conformational ensembles from a sequence | **BioEmu** | `bioemu-ensemble` |
| I'm designing an antibody / nanobody | **Antibody** | `igdiff-antibody` |
| I don't have a local GPU | **ColabDesign** | `colabdesign-workflow` |
| I need maximum sequence diversity | **Ensemble** | `esm-if1-design` |
| I want autoregressive sequence generation + zero-shot fitness scoring | **ProGen2** | `progen2-sequence` |
| I want all-atom generation with natural language | **Chroma** | `chroma-backbone` |
| I want programmable generation from function / GO terms | **ESM3** | `esm3-generative` |
| I want joint sequence + structure generation | **ProteinGenerator** | `protein-generator` |
| I'm redesigning a specific region/loop | **Partial Diffusion** | `structure-generation` |
| I need commercially licensed tools only | **Boltz-1** or **Chai-1** | `boltz-validation` / `chai1-validation` |
| I want to predict binding affinity along with structure | **Boltz-2** | `boltz2-validation` |

## Quick Decision Tree

```
Do you have a local GPU?
├── No → ColabDesign Pipeline (free Colab GPU)
│
└── Yes → What are you designing?
    ├── Small molecule binder / Cofactor / Enzyme
    │   └── Ligand-Aware Pipeline (RFdiffusionAA + LigandMPNN)
    │
    ├── Peptide (8-30 aa) / Cyclic peptide
    │   └── Peptide Pipeline (DiffPepBuilder)
    │
    ├── Antibody / Nanobody
    │   └── Standard or ColabDesign Pipeline
    │
    ├── Need maximum diversity / High-value target
    │   └── Ensemble Pipeline (ProteinMPNN + ESM-IF1)
    │
    ├── Want all-atom generation / Natural language design
    │   └── Chroma Pipeline (joint structure + sequence)
    │
    ├── No database access / Need fast screening
    │   └── Fast Screening Pipeline (OmegaFold replaces AlphaFold3)
    │
    └── General protein (monomer, binder, motif)
        └── Standard Pipeline (RFdiffusion + ProteinMPNN + AlphaFold3)
```

## Pipeline Comparison Matrix

| Pipeline | Stage 1 | Stage 2 | Stage 3 | Best For | Tools to Install | Speed |
|----------|---------|---------|---------|----------|-----------------|-------|
| **Standard** | RFdiffusion | ProteinMPNN | AlphaFold3 | General purpose | RFdiffusion + ProteinMPNN + AF3 (2.6TB DB) | Medium |
| **Fast Screening** | RFdiffusion | ProteinMPNN | OmegaFold/ESMFold | Quick validation, no DB | RFdiffusion + ProteinMPNN + ESMFold | **Fast** |
| **Ligand-Aware** | RFdiffusionAA | LigandMPNN | AlphaFold3 | Ligands, cofactors | RFdiffusionAA + LigandMPNN + AF3 | Slow |
| **RFAA** | RFdiffusionAA / ProteinMPNN | — | RFAA | Ligands, DNA, RNA, metals | RFAA (~400GB DB) | Medium |
| **Chroma** | Chroma | Chroma (built-in) | AlphaFold3 | All-atom, NL design | Chroma + AF3 | Medium |
| **ESM3** | ESM3 | ESM3 | AlphaFold3 / Boltz-1 | Programmable from function/GO terms | ESM3 + AF3/Boltz-1 | Medium |
| **ProteinGenerator** | ProteinGenerator | ProteinGenerator | AlphaFold3 / Boltz-1 / RFAA | Joint seq+struct, motif scaffolding | ProteinGenerator + AF3 | Medium |
| **ColabDesign** | AfDesign | AfDesign (built-in) | AF3/OmegaFold | No local GPU | None (uses Colab) | Medium |
| **Peptide** | DiffPepBuilder | Built-in + ESM | AlphaFold3 | 8-30aa peptides | Multi-GPU | Slow |
| **Ensemble** | RFdiffusion | ProteinMPNN + ESM-IF1 | AlphaFold3 | Max diversity | GPU + 2.6TB DB | Slow |
| **Boltz-1** | RFdiffusion | ProteinMPNN | Boltz-1 | Commercial use, complexes | GPU | Medium |
| **Boltz-2** | RFdiffusion | ProteinMPNN | Boltz-2 | Structure + binding affinity prediction | GPU | Medium |
| **Chai-1** | RFdiffusion | ProteinMPNN | Chai-1 | Apache license, constraints | GPU | Medium |
| **ESMFold** | RFdiffusion | ProteinMPNN | ESMFold | Ultra-fast screening | GPU only | **Fastest** |
| **FoldFlow** | FoldFlow | ProteinMPNN | AlphaFold3 | Fast flow matching | GPU | **Fast** |
| **FrameDiff** | FrameDiff | ProteinMPNN | AlphaFold3 / Boltz-1 | SE(3) diffusion backbones, MIT license | GPU | Medium |
| **Protpardelle-1c** | Protpardelle-1c | ProteinMPNN / LigandMPNN | AlphaFold3 / Boltz-1 | All-atom seq+struct, motif scaffolding, binder | GPU | Medium |
| **PiFold** | RFdiffusion / FrameDiff | PiFold | AlphaFold3 / Boltz-1 | Fast MIT inverse folding for fixed backbones | GPU | **Fast** |
| **FADiff** | FADiff | ProteinMPNN | AlphaFold3 / Boltz-1 | Multi-motif scaffolding with floating anchors | GPU | Medium |
| **BoltzGen** | BoltzGen | BoltzGen (built-in) | BoltzGen (Boltz-2) | Universal MIT binder design | GPU | Medium |
| **BoltzDesign1** | BoltzDesign1 | LigandMPNN / ProteinMPNN | AlphaFold3 / Boltz-2 | Invert Boltz-1 for all-atom binder design | GPU | Medium |
| **OpenFold3** | RFdiffusion | ProteinMPNN | OpenFold3 | pip install, AF3 parity | GPU | Medium |
| **RFpeptides** | RFdiffusion | ProteinMPNN | AlphaFold3/Boltz-1 | Macrocyclic peptides (12-18aa) | GPU | Medium |
| **Score-First** | RFdiffusion | ProteinMPNN + score_only | AlphaFold3 | Pre-screen with MPNN scores | GPU | Medium |
| **BindCraft** | BindCraft (built-in) | BindCraft (built-in) | AlphaFold2 monomer | Automated binder design | GPU + 32GB VRAM | Slow |
| **nf-binder-design** | RFdiffusion / BindCraft / BoltzGen | ProteinMPNN / built-in | AlphaFold2 / Boltz-2 | HPC/cloud binder pipeline | GPU + Nextflow | Medium |
| **PocketGen** | PocketGen | PocketGen | AlphaFold3 / Boltz-1 | Pocket redesign around ligand | GPU | Medium |
| **DiffDock** | — | — | DiffDock | Blind small-molecule docking | GPU | Medium |
| **RFdiffusion3** | RFdiffusion3 | ProteinMPNN / LigandMPNN | AlphaFold3 / RFAA / Boltz-1 | All-atom DNA/RNA/ligand/enzyme design | GPU | **Fast** |
| **TopoDiff** | TopoDiff | ProteinMPNN | AlphaFold3 / Boltz-1 / OmegaFold | Unconditional topology-aware backbones | GPU | Medium |
| **PRO-LDM** | RFdiffusion / TopoDiff | PRO-LDM | AlphaFold3 / Boltz-1 | Fitness-guided sequence optimization | GPU | Medium |
| **ReLSO** | Seed sequences / dataset | ReLSO (latent optimization) | ESMFold / AlphaFold3 / Boltz-1 | Transformer VAE + gradient-based fitness optimization | GPU | Medium |
| **ProtComposer** | ProtComposer | ProteinMPNN | AlphaFold3 / Boltz-1 | Ellipsoid-guided compositional generation | GPU | Medium |
| **ProteinDT** | ProteinDT | — | ESMFold / AlphaFold3 | Text-guided protein sequence generation | GPU | Medium |
| **DiMA** | DiMA | — | ESMFold / AlphaFold3 | Latent diffusion on pLM representations | GPU | Medium |
| **ProGen2** | ProGen2 | — | ESMFold / AlphaFold3 | Autoregressive PLM generation + fitness scoring | GPU + ~10GB weights | Medium |

## Detailed Pipeline Descriptions

### 1. Standard Pipeline
**Tools:** PDBFixer → RFdiffusion → ProteinMPNN → AlphaFold3 → Filtering

**When to use:**
- De novo protein design (monomers)
- Protein-protein binder design
- Motif scaffolding
- Symmetric oligomer design
- You have a local GPU and AlphaFold3 databases

**Pros:**
- Most battle-tested pipeline
- Fast backbone generation with RFdiffusion
- Excellent documentation and community support

**Cons:**
- Requires 2.6TB databases for AlphaFold3
- No ligand support in RFdiffusion
- Backbone-only output from Stage 1

**Skill reference:** `full-pipeline`, `structure-generation`, `sequence-design`

---

### 2. Ligand-Aware Pipeline
**Tools:** PDBFixer → RFdiffusionAA → LigandMPNN → AlphaFold3 → Filtering

**When to use:**
- Small molecule binder design
- Heme/cofactor binding proteins
- Metal ion coordination sites
- Enzyme active site design
- Any design involving non-protein molecules

**Pros:**
- All-atom generation (including side chains)
- Native ligand/cofactor support
- Can design around existing binding sites

**Cons:**
- Requires Apptainer/Singularity
- Slower than standard RFdiffusion
- Higher GPU memory requirements
- Still requires LigandMPNN for reliable sequences

**Skill reference:** `rfdiffusion-all-atom`, `ligandmpnn-design`

---

### 3. RFAA Validation Pipeline
**Tools:** PDBFixer → RFdiffusionAA / ProteinMPNN → RFAA → Filtering

**When to use:**
- Validation includes small molecules AlphaFold3 does not support
- Protein-DNA or protein-RNA complex validation
- Metal-ion or cofactor coordination assessment
- Need explicit ligand-interface confidence (`pae_inter`)
- Covalent modifications or unnatural residues

**Pros:**
- Broadest small-molecule / nucleic-acid / metal support
- Native all-atom modeling of mixed complexes
- `pae_inter` directly measures docking/interface quality
- Can validate outputs from RFdiffusionAA natively

**Cons:**
- Requires ~400GB of databases (UniRef30, BFD, pdb100)
- Slightly lower protein-only accuracy than AlphaFold3
- More complex Hydra config system
- SignalP-6 required for full feature set (licensed)

**Skill reference:** `rosettafold-all-atom`

---

### 4. Fast Screening Pipeline
**Tools:** PDBFixer → RFdiffusion → ProteinMPNN → OmegaFold → Filtering

**When to use:**
- Screening large libraries (100+ designs)
- No access to AlphaFold3 databases
- Limited GPU memory
- CPU-only environment
- Quick prototyping and iteration

**Pros:**
- No databases required (~2.6TB saved)
- 10-100x faster validation than AlphaFold3
- Adjustable memory usage (subbatch_size)
- Simple pip install

**Cons:**
- Monomer-only (no complexes)
- Slightly lower accuracy than AlphaFold3
- No interface metrics (ipTM)

**Skill reference:** `omegafold-validation`, `fast-screening`

---

### 5. Chroma Pipeline
**Tools:** PDBFixer → Chroma → AlphaFold3 → Filtering

**When to use:**
- All-atom structure generation in one step
- Natural language protein design prompts
- Very long proteins (>500 residues, sub-quadratic scaling)
- Symmetric proteins with composable conditioners
- Side chain packing needed

**Pros:**
- Joint structure + sequence generation
- All-atom output (no need for Stage 2 sometimes)
- Natural language prompting
- Sub-quadratic scaling for long proteins
- Composable design constraints

**Cons:**
- Requires API key for weights
- Less battle-tested than RFdiffusion
- Higher GPU memory requirements
- Limited binder design support

**Skill reference:** `chroma-backbone`

---

### 6. ESM3 Pipeline
**Tools:** ESM3 → AlphaFold3 / Boltz-1 → Filtering

**When to use:**
- Want to generate proteins from functional descriptions or GO terms
- Have partial sequence, structure, or function and want to fill in missing tracks
- Need programmable biology — multi-track prompting
- Exploring novel proteins distant from known folds
- Designing from keywords like "ATP binding" or "green fluorescent protein"

**Pros:**
- Joint generation across sequence, structure, and function
- Programmable via partial prompts on any track
- Can generate from natural language function descriptions
- Open 1.4B model available for research

**Cons:**
- Generative structure track should be validated independently (AF3/Boltz-1)
- Non-commercial license for open weights
- Larger models require cloud/API access
- High expertise for effective prompting

**Skill reference:** `esm3-generative`

---

### 7. ProteinGenerator Pipeline
**Tools:** PDBFixer → ProteinGenerator (notebook + inference.py) → AlphaFold3 / Boltz-1 / RFAA → Filtering

**When to use:**
- Joint sequence + structure generation in one model
- Motif scaffolding with explicit sequence constraints
- Multistate design (one sequence, multiple conformations)
- Sequence-activity guided generation
- Custom composition / symmetry / contact potentials
- Tighter coupling between sequence and structure than RFdiffusion + ProteinMPNN

**Pros:**
- Native joint sequence-structure diffusion
- Built on RoseTTAFold — predicts structure during generation
- Custom potentials for composition, symmetry, contacts
- Strong for functional / multistate design

**Cons:**
- Less mature than RFdiffusion for large unconditional generation
- Primary interface is a Jupyter notebook
- Requires checkpoint downloads (~4 GB)
- Slightly steeper learning curve for custom potentials

**Skill reference:** `protein-generator`

---

### 8. ColabDesign Pipeline
**Tools:** AfDesign (on Google Colab) → AlphaFold3/OmegaFold → Filtering

**When to use:**
- No local GPU available
- Free compute is preferred
- Quick experiments and prototyping
- Custom loss functions needed
- Binder hallucination
- Fixed-backbone design without RFdiffusion

**Pros:**
- Free GPU on Google Colab
- No local installation needed
- Highly flexible (custom loss terms)
- Excellent for education and exploration
- Multiple design modes (hallucination, binder, fixed)

**Cons:**
- Internet required
- Colab GPU queue times
- Less suitable for batch processing
- Limited to notebook-based workflows

**Skill reference:** `colabdesign-workflow`

---

### 9. Peptide Pipeline
**Tools:** PDBFixer → DiffPepBuilder → AMBER/Rosetta → AlphaFold3 → Filtering

**When to use:**
- 8-30 amino acid peptide design
- Peptide binders to protein targets
- Cyclic peptides with disulfide bonds
- Peptide-protein interface design
- Peptide docking (known sequence)

**Pros:**
- Specialized for short peptides
- Built-in disulfide bond support
- Integrated peptide docking (DiffPepDock)
- Post-processing included (AMBER + Rosetta)

**Cons:**
- Multi-GPU recommended (DDP)
- Requires PyRosetta license
- Slower than general-purpose tools
- Limited to peptides (not full proteins)

**Skill reference:** `diffpepbuilder-design`

---

### 10. Ensemble Pipeline
**Tools:** PDBFixer → RFdiffusion → ProteinMPNN + ESM-IF1 → AlphaFold3 → Filtering

**When to use:**
- High-value targets requiring maximum success rate
- Need maximum sequence diversity
- Partial backbone redesign needed
- Variant scoring required
- Can afford extra compute

**Pros:**
- Combines complementary methods
- ProteinMPNN: proven experimental success
- ESM-IF1: better partial masking and variant scoring
- Union captures more diverse designs

**Cons:**
- 2x compute for Stage 2
- More complex workflow
- Requires managing two sequence sets

**Skill reference:** `esm-if1-design`

---

### 11. BindCraft Pipeline
**Tools:** BindCraft (end-to-end: AF2 Multimer co-design + ProteinMPNN + AF2 monomer validation)

**When to use:**
- Designing protein binders to a target (the primary use case)
- Want automated, one-shot binder design
- Need highest reported experimental success rates
- Willing to trade general flexibility for binder-specific optimization

**Pros:**
- Single command from target PDB to ranked binders
- Co-designs backbone, sequence, and interface simultaneously
- 10–100% experimental success rate reported in Nature
- No 2.6TB AlphaFold3 databases needed (~5GB AF2 weights)
- Flexible target representation (side-chain and backbone)

**Cons:**
- Binder design only (not general proteins)
- Requires 32GB+ VRAM
- Linux only
- PyRosetta license needed for commercial use
- Slower than RFdiffusion for backbone-only generation

**Skill reference:** `bindcraft-workflow`

---

### 12. nf-binder-design Pipeline
**Tools:** Target PDB → Nextflow (`rfd` / `rfd_partial` / `bindcraft` / `boltzgen` / `boltz_pulldown`) → Ranked binders

**When to use:**
- Binder design on HPC cluster or cloud
- Want to compare multiple binder methods in one command
- Need parallel execution across multiple GPUs
- Production pipeline with built-in filtering and scoring
- Already using Nextflow / Apptainer in your lab

**Pros:**
- One command runs complete method
- HPC-ready SLURM configs included
- Built-in filtering (e.g., `rg<20`) and BindCraft-derived scoring
- Containerized — reproducible across machines
- Switches methods via `--method` flag

**Cons:**
- Requires Nextflow + Apptainer
- Container images are very large
- Less fine-grained control than manual scripts
- Some methods depend on PyRosetta (non-commercial)

**Skill reference:** `nf-binder-design`

---

### 13. PocketGen Pipeline
**Tools:** PocketGen → AlphaFold3 / Boltz-1 → Filtering

**When to use:**
- Redesigning an existing protein pocket around a known ligand
- Enzyme active site engineering for new substrates/cofactors
- Optimizing a binding pocket for improved affinity
- Have a protein scaffold + ligand SDF and want pocket-only co-design

**Pros:**
- 10× faster than physics-based methods
- Co-designs pocket sequence and structure
- Preserves the rest of the protein scaffold
- Strong reported success rate (95% improve Vina score)

**Cons:**
- Requires a starting scaffold and ligand pose
- Less general than RFdiffusionAA
- Needs PyTorch Geometric and Vina setup
- Expertise: high

**Skill reference:** `pocketgen-ligand`

---

### 14. RFdiffusion3 Pipeline
**Tools:** PDBFixer → RFdiffusion3 → ProteinMPNN / LigandMPNN → AlphaFold3 / RFAA / Boltz-1 → Filtering

**When to use:**
- All-atom design of proteins, DNA binders, RNA binders, small-molecule binders, or enzymes
- You want ~10× faster inference than RFdiffusion2
- You need a single unified model instead of multiple specialist tools
- You want training/fine-tuning code included
- Your design involves nucleic acids or cofactors not handled well by RFdiffusion

**Pros:**
- All-atom biomolecular interaction design (protein, DNA, RNA, ligand, metal)
- ~10× faster than RFdiffusion2
- Training code and weights fully released
- pip-installable via `rc-foundry[rfd3]`
- Native contig-string + JSON/YAML input interface

**Cons:**
- New codebase — less community troubleshooting than classic RFdiffusion
- Requires Rosetta Commons Foundry ecosystem
- Checkpoint download needed (~GB scale)
- Still validate with AF3/RFAA/Boltz-1 before experimental work

**Skill reference:** `rfdiffusion3-workflow`

---

### 15. TopoDiff Pipeline
**Tools:** TopoDiff → ProteinMPNN → AlphaFold3 / Boltz-1 / OmegaFold → Filtering

**When to use:**
- Unconditional protein backbone generation (no target structure required)
- Length-controlled exploration (50–250 residues)
- You want topology-aware latent control over generated structures
- MIT license is required
- You need a lightweight Stage 1 alternative to RFdiffusion
- Benchmarking coverage and diversity against known folds

**Pros:**
- **MIT license** — permissive for academic and commercial use
- Strong reported coverage and diversity metrics
- Global-geometry-aware latent encoding improves controllability
- Multiple sampling modes: `base`, `designability`, `novelty`, `all_round`
- Compact codebase compared to RFdiffusion
- Web server available for quick tests

**Cons:**
- Unconditional / length-controlled only (no target-aware binder mode)
- Limited to ~50–250 residues
- Requires separate Stage 2 (ProteinMPNN) for sequences
- Smaller community than RFdiffusion

**Skill reference:** `topodiff-workflow`

---

### 16. PRO-LDM Pipeline
**Tools:** RFdiffusion / TopoDiff → PRO-LDM → AlphaFold3 / Boltz-1 → Filtering

**When to use:**
- You have a backbone scaffold and want fitness-guided sequence design
- You want to optimize sequences toward a target property or fitness label
- You need out-of-distribution (OOD) variants for functional optimization
- You have labeled training data for your protein family of interest
- You prefer latent-space diffusion over autoregressive (ProteinMPNN) or inpainting (ESM-IF1) approaches

**Pros:**
- **MIT license**
- Conditional generation guided by fitness labels
- Integrated fitness prediction (no separate scoring model needed)
- Classifier-free guidance for controllable OOD design
- Latent-space diffusion is computationally efficient
- Strong results on benchmark variant datasets (TAPE, GFP, etc.)

**Cons:**
- Requires labeled training data for conditional tasks
- Does **not** take PDB structure as direct input (sequence / MSA based)
- Training from scratch can take hours on 4×V100
- Smaller community than ProteinMPNN / ESM-IF1

**Skill reference:** `pro-ldm-workflow`

---

### 17. ProtComposer Pipeline
**Tools:** ProtComposer → ProteinMPNN / LigandMPNN → AlphaFold3 / Boltz-1 → Filtering

**When to use:**
- You want explicit 3D spatial control over protein substructures
- You need to generate proteins from customizable layouts (ellipsoids)
- You are exploring compositional protein design
- You want to redesign connectivity between existing protein domains
- You prefer flow matching over diffusion

**Pros:**
- Unique ellipsoid-based geometric conditioning
- Strong layout adherence via invariant cross-attention
- Three layout modes: statistical, hand-designed, extracted from existing proteins
- Builds on solid MultiFlow foundation
- ICLR 2025 Oral

**Cons:**
- **Research / non-commercial license only** — not suitable for commercial projects
- Complex dependency stack with pinned older versions
- Requires understanding ellipsoid parameterization for manual layouts
- Training from scratch needs 8 GPUs
- Smaller community than RFdiffusion

**Skill reference:** `protcomposer-workflow`

---

### 18. ProteinDT Pipeline
**Tools:** ProteinDT → ESMFold / AlphaFold3 / Boltz-1 → Filtering

**When to use:**
- You want to generate protein sequences from a text description
- You have a functional description in UniProt style and want sequence diversity
- You want to edit an existing protein toward a text-specified property
- You prefer a pure text interface over structure-conditioned generation
- MIT license is required

**Pros:**
- **MIT license**
- Direct text-to-sequence generation
- Zero-shot text-guided editing without retraining
- Strong protein-language alignment via ProteinCLAP
- Pretrained checkpoints on HuggingFace
- Published in *Nature Machine Intelligence* 2025

**Cons:**
- Generates sequences only — requires Stage 3 structure prediction
- Prompts work best in UniProt style, not free-form natural language
- Less precise than structure-conditioned tools for scaffolds/binders
- Complex 5-step training pipeline if adapting to new data

**Skill reference:** `proteindt-workflow`

---

### 19. DiMA Pipeline
**Tools:** DiMA → ESMFold / AlphaFold3 / Boltz-1 → Filtering

**When to use:**
- You want to generate protein sequences from protein language model (pLM) latent representations
- You need an encoder-agnostic sequence generator (ESM-2, ESMc, CHEAP, SaProt)
- You want a lightweight 35M-parameter diffusion denoiser
- You need family-specific generation, motif scaffolding, infilling, or fold-conditioned design
- MIT license is required

**Pros:**
- **MIT license**
- Encoder-agnostic: works with ESM-2, ESMc, CHEAP, SaProt
- Very small denoiser (35M parameters)
- Operates in continuous pLM latent space
- Supports joint sequence-structure decoders (CHEAP/SaProt)
- Accepted at ICML 2025

**Cons:**
- Generates sequences primarily — structure only with CHEAP/SaProt decoders
- Requires pretrained pLM encoder as dependency
- Multi-GPU training recommended
- Less mature than ProteinMPNN for structure-conditioned design
- Smaller community than RFdiffusion

**Skill reference:** `dima-workflow`

---

### 20. FrameDiff Pipeline
**Tools:** PDBFixer → FrameDiff → ProteinMPNN → AlphaFold3 / Boltz-1 → Filtering

**When to use:**
- You want an MIT-licensed backbone generator
- You prefer direct SE(3) diffusion without relying on a pretrained folding network
- Unconditional monomer design up to ~500 residues
- Motif scaffolding with fixed substructures

**Pros:**
- MIT license (commercial-friendly)
- Does not require AlphaFold2/3 distillation
- Training and inference code are available
- Bundled ProteinMPNN path provides sequence design + self-consistency evaluation

**Cons:**
- Backbone-only output
- Designability lags RFdiffusion on some benchmarks
- Requires ~1 TB PDB download if training from scratch
- Multi-GPU training recommended for large-scale fine-tuning

**Skill reference:** `framediff-backbone`

---

### 21. Protpardelle-1c Pipeline
**Tools:** PDBFixer → Protpardelle-1c → (optional ProteinMPNN / LigandMPNN) → AlphaFold3 / Boltz-1 → Filtering

**When to use:**
- All-atom protein design (backbone + side chains) in a single generative step
- Motif scaffolding with side-chain conditioning
- Binder generation with hotspot conditioning
- Multichain / complex generation
- You need a permissive MIT license

**Pros:**
- MIT license (commercial-friendly)
- ~22M parameters — compact and fast sampling
- Strong MotifBench performance with side-chain conditioning
- Native support for binder and multichain tasks
- Sequence and structure co-design

**Cons:**
- Requires CUDA ≥ 12.4 and gcc ≥ 12.4
- Needs external tools (Foldseek, ProteinMPNN, LigandMPNN, ESMFold)
- Training setup assumes SLURM
- All-atom models use more GPU memory than backbone-only alternatives

**Skill reference:** `protpardelle-allatom`

---

### 22. PiFold Sequence Design Pipeline
**Tools:** PDBFixer → RFdiffusion / FrameDiff → PiFold → AlphaFold3 / Boltz-1 → Filtering

**When to use:**
- You already have backbones and need sequences designed quickly
- High-throughput fixed-backbone sequence design
- You prefer an MIT-licensed inverse-folding model
- Inference speed is more important than the absolute highest recovery

**Pros:**
- MIT license
- ~70× faster inference than autoregressive competitors
- One-shot decoder (no iterative unmasking)
- Strong recovery on CATH, TS50, and TS500 benchmarks
- Easy Colab notebooks for quick testing

**Cons:**
- Fixed-backbone only (no native ligand awareness)
- Official repo is training-centric; inference API less polished than ProteinMPNN
- Recovery slightly below top autoregressive methods on some tasks
- Smaller ecosystem of wrappers and tutorials

**Skill reference:** `pifold-sequence-design`

---

### 23. FADiff Multi-Motif Scaffolding Pipeline
**Tools:** PDBFixer → FADiff → ProteinMPNN → AlphaFold3 / Boltz-1 → Filtering

**When to use:**
- You need to scaffold **multiple functional motifs** into one protein
- Relative motif positions are unknown and should be learned automatically
- You want a **guarantee of motif presence** in generated backbones
- Academic/non-commercial use (BSD-2 license)

**Pros:**
- Handles arbitrary numbers of motifs (generalizes from 2-motif training)
- Floating-anchor formulation removes the need to manually place motifs
- Built on the well-documented FrameDiff codebase
- Strong ICML 2024 theoretical foundation

**Cons:**
- BSD-2 license restricted to non-commercial academic use
- Backbone-only output (no side chains)
- Requires PDB mirror for training
- Multi-GPU training recommended
- Smaller community than RFdiffusion

**Skill reference:** `fadiff-multimotif`

---

### 24. BoltzGen Universal Binder Design Pipeline
**Tools:** PDBFixer → BoltzGen (design → inverse folding → folding → analysis → filtering)

**When to use:**
- You want a single command that goes from a design spec to ranked binders
- You need to design binders for proteins, peptides, small molecules, antibodies, or nanobodies
- You prefer an MIT-licensed end-to-end binder pipeline
- You want built-in inverse folding, Boltz-2 validation folding, analysis, and filtering

**Pros:**
- MIT license (commercial-friendly)
- Supports multiple target modalities in one tool
- Unified Boltz-2 representations for design and validation folding
- Built-in analysis and diversity-aware filtering
- Strong experimental validation (nanomolar binders for 66% of novel targets)
- Simple `pip install boltzgen` and `boltzgen run` workflow

**Cons:**
- Requires GPU for practical use
- Needs ~6 GB model download on first run
- Large campaigns require 10,000–60,000 designs for best results
- Newer than BindCraft / RFdiffusion; fewer long-term community benchmarks
- Less modular than multi-tool pipelines if you want custom Stage 2/3 replacements

**Skill reference:** `boltzgen-binder-design`

---

### 25. BioEmu Conformational Ensemble Pipeline
**Tools:** Sequence → BioEmu `sample` → optional `sidechain_relax` → ensemble analysis

**When to use:**
- You need an equilibrium conformational ensemble from a single sequence
- You want to identify cryptic pockets, local unfolding, or domain motions
- You need relative free-energy estimates without running molecular dynamics
- You want to compare designed sequences for conformational stability
- You prefer an MIT-licensed ensemble generator

**Pros:**
- MIT license (commercial-friendly)
- Thousands of independent conformations per GPU hour
- Direct free-energy estimates (~1 kcal/mol vs MD/experiment)
- Captures rare conformations missed by single-structure predictors
- No MD expertise or force-field setup required

**Cons:**
- Linux-only pip package
- Monomer-only (no native multimer support)
- Requires ~3.5 GB AlphaFold2 weight download on first run
- Best for 50–600 residue proteins
- Does not design sequences; must pair with a design stage

**Skill reference:** `bioemu-ensemble`

---

### 26. DiffDock Small-Molecule Docking Pipeline
**Tools:** Protein PDB + ligand SMILES/SDF → DiffDock → ranked docked poses

**When to use:**
- You need to dock a small-molecule ligand into a protein without defining a binding box
- You want a diffusion-based pose generator with a learned confidence model
- You are running a virtual screen of many ligands against one or more proteins
- You want to validate ligand placement after a ligand-aware design campaign
- You prefer an MIT-licensed docking tool

**Pros:**
- MIT license (commercial-friendly)
- Blind docking — no pocket definition required
- State-of-the-art pose prediction on standard benchmarks
- Supports batch virtual screening via CSV input
- Can fold protein sequences on the fly with ESMFold
- Fast GPU inference (seconds to minutes per complex)

**Cons:**
- Heavy conda environment (PyTorch Geometric, RDKit, ESM)
- GPU strongly recommended; CPU is very slow
- Confidence score is not a binding affinity estimate
- Best for monomers; multimer docking requires caution
- Requires careful interpretation of confidence cutoffs

**Skill reference:** `diffdock-ligand`

---

### 27. ProGen2 Autoregressive Sequence Generation Pipeline
**Tools:** Context sequence → ProGen2 `sample.py` → generated sequences → ESMFold / AlphaFold3 validation

**When to use:**
- You want de novo protein sequence generation without a structural template
- You need zero-shot fitness scoring of variants or generated sequences
- You prefer a BSD-3 licensed autoregressive language model
- You are exploring large sequence spaces and will fold downstream with ESMFold
- You want a specialized antibody checkpoint (`progen2-oas`)

**Pros:**
- BSD-3-Clause license (commercial-friendly)
- Massive scale up to 6.4B parameters
- Zero-shot log-likelihood fitness proxy without labeled data
- Simple CLI: `sample.py` and `likelihood.py`
- Antibody/OAS checkpoint available

**Cons:**
- Sequence-only: no explicit structure constraints during generation
- Large checkpoints require significant VRAM (`large` ~2.7B, `xlarge` ~6.4B)
- Generation can be slow for long proteins
- Must pair with a structure predictor for validation

**Skill reference:** `progen2-sequence`

---

### 28. Boltz-2 Structure + Affinity Validation Pipeline
**Tools:** YAML input → `boltz predict` → predicted structure + confidence + optional affinity

**When to use:**
- You want an MIT-licensed AlphaFold3 alternative for structure validation
- You need **binding affinity predictions** alongside structures (hit discovery / ligand optimization)
- You are running a commercial or commercially-adjacent project
- You want FEP-like affinity accuracy ~1000× faster than physics-based methods
- You are validating protein-ligand, protein-protein, or nucleic-acid complexes

**Pros:**
- MIT license (commercial-friendly)
- Joint structure + affinity prediction in a single `boltz predict` call
- ~18 s per protein-ligand affinity prediction on a consumer GPU
- Handles ligands, DNA, RNA, covalent modifications, and post-translational modifications
- Backward-compatible YAML format with Boltz-1

**Cons:**
- Affinity module optimized for ligands ≤ ~56 heavy atoms
- GPU strongly recommended; CPU is much slower
- Large complexes require high-VRAM GPUs
- Affinity scores are predictions, not a substitute for experimental assays

**Skill reference:** `boltz2-validation`

---

### 29. BoltzDesign1 All-Atom Binder Design Pipeline
**Tools:** Target PDB/YAML → `boltzdesign.py` → Boltz-1 inversion → LigandMPNN / ProteinMPNN → optional AF3 / Boltz-2 validation

**When to use:**
- You want to design binders by inverting an AlphaFold3-class model (Boltz-1)
- Your target is a small molecule, RNA, DNA, metal ion, PTM, or protein
- You prefer an MIT-licensed binder design method
- You do not want to fine-tune a diffusion model
- You want optional AlphaFold3 cross-validation built into the pipeline

**Pros:**
- MIT license (commercial-friendly)
- No fine-tuning required; inverts pretrained Boltz-1
- Generalizes across proteins, small molecules, nucleic acids, metals, PTMs
- Uses only Boltz-1 Pairformer + Confidence modules for efficient optimization
- Built-in sequence redesign with LigandMPNN / ProteinMPNN
- Optional AlphaFold3 re-prediction for independent validation

**Cons:**
- Experimental; no wet-lab validation published as of 2025
- Requires GPU and Boltz-1 weights
- Optional AF3 cross-validation adds heavy setup and database requirements
- Interface residue fixing defaults may need tuning for exotic chemistries
- PyRosetta is optional but recommended for some downstream steps

**Skill reference:** `boltzdesign1-binder`

---

### 30. ReLSO Latent-Space Sequence Optimization Pipeline
**Tools:** Dataset / seed sequences → `train_relso.py` (optional) → `run_optim.py` → optimized sequences → ESMFold / AlphaFold3 validation

**When to use:**
- You have a labeled fitness or property dataset and want to optimize sequences in latent space
- You prefer gradient-based optimization over diffusion or autoregressive sampling
- You want an Apache 2.0 licensed fitness-optimization method
- You need a lightweight complement to structure-aware inverse folding
- You are exploring a local sequence landscape around a known family

**Pros:**
- Apache 2.0 license (very permissive)
- Learns a smooth, regularized latent space from sequence data
- Gradient-based latent optimization can be more sample-efficient than brute-force sampling
- Includes benchmark datasets (GB1, GFP, TAPE) and pretrained weights
- Can be trained on custom property labels

**Cons:**
- Requires a labeled dataset or pretrained checkpoint for the target property
- Sequence-only: no explicit structural constraint during optimization
- Property predictor quality limits optimization ceiling
- Training from scratch takes GPU time
- Best for local optimization; may struggle with very long proteins

**Skill reference:** `relso-sequence-optimization`

## Resource Requirements Summary

| Resource | Standard | Ligand-Aware | RFAA | Fast | Chroma | ESM3 | ProteinGenerator | ColabDesign | Peptide | Ensemble | Boltz-1 | Boltz-2 | Chai-1 | Protenix | RFpeptides | Score-First | BindCraft | nf-binder-design | PocketGen | RFdiffusion3 | TopoDiff | PRO-LDM | ProtComposer | ProteinDT | DiMA | FrameDiff | Protpardelle-1c | PiFold | FADiff | BoltzGen | BioEmu | DiffDock | ProGen2 | BoltzDesign1 | ReLSO |
|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| GPU | Required | Required | Required | Required | Required | Required | Required | Free Colab | Multi-GPU | Required | Required | Required | Required | Required | Required | Required | Required (32GB+) | Required | Required | Required | Required | Required | Required | Required | Required | Required | Required | Required | Required | Required | Required | Required | Required | Required | Required |
| Databases | 2.6TB | 2.6TB | ~400GB | None | 2.6TB | ~5GB | ~5GB | Optional | 2.6TB | 2.6TB | None* | None* | None* | None* | None* | 2.6TB | ~5GB AF2 | Varies | ~5GB | ~5GB | None | None* | None* | None* | None* | None* | ~5GB | ~5GB | None* | ~6GB | ~4GB | ~2GB | ~10GB | None* | None |
| Disk space | ~3TB | ~3TB | ~400GB | ~100GB | ~3TB | ~20GB | ~20GB | Minimal | ~3TB | ~3TB | ~3TB | ~3TB | ~3TB | ~3TB | ~100GB | ~3TB | ~50GB | ~50-100GB | ~20GB | ~20GB | ~20GB | ~10GB | ~20GB | ~20GB | ~20GB | ~20GB | ~20GB | ~5GB | ~20GB | ~20GB | ~20GB | ~10GB | ~20GB | ~20GB | ~10GB |
| Setup time | Hours | Hours | Hours | Minutes | Hours | Hours | Hours | Minutes | Hours | Hours | Minutes | Minutes | Minutes | Hours | Minutes | Hours | Hours | Hours | Hours | Hours | Minutes | Minutes | Hours | Hours | Hours | Hours | Hours | Minutes | Hours | Minutes | Minutes | Hours | Hours | Hours | Hours |
| Expertise | Medium | High | High | Low | Medium | High | High | Low | High | High | Medium | Medium | Medium | High | Medium | Medium | Medium | Medium | High | High | Medium | Medium | High | Medium | High | High | High | Medium | High | Medium | Medium | Medium | Medium | High | High |

*Boltz-1, BoltzDesign1, Chai-1, Protenix use built-in MSA servers by default

## My Specific Scenario

### "I want to design a protein binder to a target"
→ **BindCraft Pipeline** for highest experimental success (automated end-to-end)
→ **Standard Pipeline** if you prefer modular control and have AF3 databases
→ **Fast Screening Pipeline** if you want quick results
→ **ColabDesign Pipeline** if you have no GPU
→ **Ensemble Pipeline** if this is critical and you want maximum diversity

### "I want to design an enzyme that binds a small molecule"
→ **Ligand-Aware Pipeline** for *de novo* ligand-aware protein design
→ **PocketGen Pipeline** for redesigning an existing pocket around the ligand

### "I want to design a cyclic peptide inhibitor"
→ **Peptide Pipeline** (DiffPepBuilder is specialized for this)

### "I have 1000 designs to validate but no AlphaFold3 databases"
→ **Fast Screening Pipeline** with OmegaFold

### "I want the fastest possible turnaround"
→ **ESMFold Pipeline** (no MSA, ~2 seconds per sequence)
→ **FoldFlow Pipeline** (flow matching, faster than diffusion)

### "I want the highest possible accuracy"
→ **Standard Pipeline** with AlphaFold3 (full MSA)
→ Or **Ensemble Pipeline** for maximum diversity
→ Or **Protenix Pipeline** with 1000 samples (inference-time scaling)

### "I'm a beginner with no GPU"
→ **ColabDesign Pipeline** on Google Colab

### "I want the easiest setup"
→ **OpenFold3 Pipeline** (`pip install openfold3`)

### "I need RNA structure prediction"
→ **OpenFold3 Pipeline** (only open-source matching AF3 on RNA)

### "I need a commercially licensed predictor"
→ **Boltz-1 Pipeline** (MIT license)
→ **Chai-1 Pipeline** (Apache 2.0)
→ **Protenix Pipeline** (Apache 2.0)

### "I want to train/fine-tune my own model"
→ **Protenix Pipeline** (only tool with training support)

### "I'm designing intrinsically disordered proteins"
→ **EvoDiff Pipeline** (sequence-only, IDR support)

### "I want inference-time scaling for better accuracy"
→ **Protenix Pipeline** (log-linear improvements with more samples)

### "I want the most robust validation possible"
→ **Cross-Validation Pipeline** (Boltz-1 + Chai-1 + OmegaFold ensemble)

### "I want to avoid validating poor designs"
→ **Score-First Pipeline** (ProteinMPNN score_only pre-screening)

### "I want to design a macrocyclic peptide inhibitor"
→ **RFpeptides Pipeline** (12-18aa head-to-tail cyclic peptides)

### "I need to validate a protein-ligand or protein-DNA complex"
→ **RFAA Validation Pipeline** (broader small-molecule / nucleic-acid support than AlphaFold3)

### "I want to run binder design on my HPC cluster"
→ **nf-binder-design Pipeline** (Nextflow, SLURM-ready, multiple methods)

### "I want joint sequence + structure generation in one model"
→ **ProteinGenerator Pipeline** (RoseTTAFold sequence-space diffusion)
→ **Chroma Pipeline** (natural-language joint generation)
→ **MultiFlow Pipeline** (flow-matching co-design)

### "I have an existing protein and want to redesign its pocket around a ligand"
→ **PocketGen Pipeline** (pocket-only co-design)
→ **Ligand-Aware Pipeline** if you want full *de novo* scaffold generation

## Tips for Pipeline Selection

1. **Start simple**: Begin with Standard or Fast Screening pipeline
2. **Validate with the cheapest tool first**: Use OmegaFold for initial screening
3. **Scale up**: Move to AlphaFold3 only for top candidates
4. **Consider ColabDesign for exploration**: Test ideas before committing local resources
5. **Use the right tool for the job**: Don't force a general pipeline onto a specialized problem (e.g., peptides)
6. **Hybrid approaches**: Mix and match stages (e.g., RFdiffusion + LigandMPNN for soluble proteins)

## References

- See individual skills for detailed tool usage
- See `full-pipeline` skill for orchestration guidance
- See `install-guide` skill for setup instructions

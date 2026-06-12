# Protein Design Skills Index

Complete index of all available skills in the protein design plugin.

## Pipeline Selection & Orchestration

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `pipeline-selection` | Choose from 30+ design pipelines | Any time you need to pick a workflow |
| `full-pipeline` | End-to-end orchestration guidance | Running complete 5-stage design |
| `batch-submission` | Submit and manage multiple jobs | Running 10+ designs |
| `nf-binder-design` | Nextflow HPC binder design pipeline | Production / cloud / HPC runs |
| `design-patterns` | Common design patterns and recipes | Standard scenarios (binder, scaffold, etc.) |
| `quickstart-guide` | Zero-to-first-design in 10 minutes | New users |
| `next-steps` | What to run next after each stage | After completing a pipeline stage |

## Documentation & Maintenance

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `gen-docs` | Generate and maintain product documentation | After adding/modifying scripts or skills |
| `sync-changelog` | Sync changelog from git history | Before releases or after meaningful changes |
| `translate-docs` | Translate and sync bilingual docs | After updating docs in either language |

## Stage-Specific Skills

### Stage 0: Preprocessing
| Skill | Purpose |
|-------|---------|
| `structure-preprocessing` | PDBFixer usage and tips |

### Stage 1: Backbone Generation
| Skill | Tool | Best For |
|-------|------|----------|
| `structure-generation` | RFdiffusion | General backbone generation |
| `rfdiffusion-all-atom` | RFdiffusionAA | Ligand/cofactor-aware all-atom design |
| `rfdiffusion3-workflow` | RFdiffusion3 | All-atom biomolecular interactions (DNA/RNA/ligand/enzyme) |
| `topodiff-workflow` | TopoDiff | Topology-aware backbone generation (50–250 aa, MIT) |
| `protcomposer-workflow` | ProtComposer | Ellipsoid-guided compositional structure generation (flow matching) |
| `chroma-backbone` | Chroma | Joint structure+sequence, natural language |
| `foldflow-backbone` | FoldFlow | Flow matching, fast prototyping |
| `framediff-backbone` | FrameDiff | SE(3) diffusion backbone generation, MIT license |
| `diffpepbuilder-design` | DiffPepBuilder | 8-30aa peptide binders (disulfide) |
| `rfpeptides-macrocycle` | RFdiffusion | 12-18aa macrocyclic peptides (head-to-tail) |
| `colabdesign-workflow` | AfDesign | Free Colab GPU, hallucination |
| `genie3-backbone` | Genie 3 | All-atom generation (backbone + sidechains) |
| `la-proteina-backbone` | La-Proteina | NVIDIA joint seq+structure, full atoms |
| `proteina-complexa-binder` | Proteina-Complexa | NVIDIA binder design with optimization |
| `protpardelle-allatom` | Protpardelle-1c | MIT-licensed all-atom seq+struct generation, motif scaffolding |
| `fadiff-multimotif` | FADiff | Multi-motif scaffolding with floating anchors (ICML 2024) |

### Stage 2: Sequence Design
| Skill | Tool | Best For |
|-------|------|----------|
| `sequence-design` | ProteinMPNN | General sequence design |
| `ligandmpnn-design` | LigandMPNN | Ligand-aware sequence design |
| `esm-if1-design` | ESM-IF1 | Partial masking, variant scoring |
| `pifold-sequence-design` | PiFold | Fast MIT-licensed inverse folding (70× speedup) |
| `pro-ldm-workflow` | PRO-LDM | Conditional latent diffusion + fitness optimization |
| `relso-sequence-optimization` | ReLSO | Transformer VAE + latent-space gradient optimization (Apache 2.0) |

### Stage 3: Structure Validation
| Skill | Tool | Speed | License | Best For |
|-------|------|-------|---------|----------|
| `structure-validation` | AlphaFold3 | Slow | Non-commercial | Best accuracy |
| `omegafold-validation` | OmegaFold | Fast | Open | No databases needed |
| `esmfold-validation` | ESMFold | **Fastest** | MIT | Ultra-fast screening |
| `boltz-validation` | Boltz-1 | Medium | MIT | Commercial use, complexes |
| `boltz2-validation` | Boltz-2 | Medium | MIT | Structure + binding affinity prediction |
| `chai1-validation` | Chai-1 | Medium | Apache 2.0 | Single-sequence, constraints |
| `rosettafold-all-atom` | RFAA | Medium | Open | Ligands / DNA / RNA / metals |
| `protenix-validation` | Protenix | Medium | Apache 2.0 | Training + inference scaling |
| `protenix-training` | Protenix | — | Apache 2.0 | Fine-tuning and training |
| `openfold-validation` | OpenFold3 | Medium | Apache 2.0 | pip install, AF3 parity |
| `colabfold-alternative` | ColabFold | Medium | Open | MMseqs2 MSA server |

### Stage 4: Filtering & Analysis
| Skill | Purpose |
|-------|---------|
| `filtering-ranking` | Filter and rank by confidence metrics |
| `quality-check` | Validate design quality |
| `protein-analysis` | Analyze structures and sequences |
| `structure-validation` | Interpret pLDDT, pTM, ipTM |
| `cross-validation` | Multi-validator ensemble ranking |
| `score-first-screening` | ProteinMPNN score-only pre-filter |

### Alternative: Sequence-Only Generation
| Skill | Tool | Best For |
|-------|------|----------|
| `dima-workflow` | DiMA | Latent diffusion on pLM representations (ESM/SaProt/CHEAP) |
| `evodiff-sequence` | EvoDiff | IDR design, no structural template |
| `protein-generator` | ProteinGenerator | Joint seq+struct via RoseTTAFold diffusion |
| `multiflow-codesign` | MultiFlow | Joint sequence+backbone co-design |
| `bcdesign-inverse` | BCDesign | Property-constrained sequence design |
| `proteindt-workflow` | ProteinDT | Text-guided protein sequence generation and editing |
| `progen2-sequence` | ProGen2 | Autoregressive PLM generation + zero-shot fitness scoring (BSD-3) |

## Specialized Design Domains

| Skill | Domain | Key Tool |
|-------|--------|----------|
| `antibody-design` | Antibodies / Nanobodies | RFdiffusion + ProteinMPNN |
| `bindcraft-workflow` | Automated binder design | BindCraft (end-to-end) |
| `boltzgen-binder-design` | Universal binder design | BoltzGen (MIT, protein/peptide/small molecule/antibody/nanobody) |
| `boltzdesign1-binder` | All-atom biomolecular binder design | BoltzDesign1 (inverts Boltz-1, MIT) |
| `igdiff-antibody` | Antibodies (specialized) | IgDiff + AbMPNN |
| `ablang-antibody` | Antibody sequence analysis | AbLang (embeddings, completion) |
| `enzyme-design` | Enzymes / Active sites | RFdiffusionAA + LigandMPNN |
| `esm3-generative` | Programmable generation | ESM3 (seq + struct + function tracks) |
| `pocketgen-ligand` | Pocket redesign | PocketGen (ligand-aware pocket co-design) |
| `diffdock-ligand` | Small-molecule docking | DiffDock (blind diffusion docking, MIT) |
| `fast-screening` | Large library screening | ESMFold / OmegaFold |
| `alphaflow-ensemble` | Conformational ensembles | AlphaFlow (dynamics) |
| `bioemu-ensemble` | Conformational ensembles | BioEmu (generative equilibrium ensembles, MIT) |
| `framedipt-inpainting` | Region redesign | FrameDiPT (inpainting) |
| `aligninversepro-optimization` | Inference optimization | AlignInversePro (reward guidance) |
| `evolla-llm` | Protein Q&A / reasoning | EvoLLa (conversational protein LLM) |
| `rfdpoly-multipolymer` | DNA/RNA-protein complex | RFDpoly (multi-polymer design) |

## Setup & Configuration

| Skill | Purpose |
|-------|---------|
| `install-guide` | Install all external tools |
| `config-management` | Configure tool paths and settings |
| `protein-design-context` | Session-start context injection |

## Progress Tracking & Monitoring

| Skill | Purpose |
|-------|---------|
| `periodic-summary` | Set up periodic progress summaries and live dashboards |
| `next-steps` | Decide what command to run next based on current pipeline state |

## Troubleshooting & Support

| Skill | Purpose |
|-------|---------|
| `troubleshooting` | Common errors and solutions |
| `error-recovery` | Recover from failed jobs |

## Total: 79 Skills

```
skills/
├── ablang-antibody/
├── aligninversepro-optimization/
├── alphaflow-ensemble/
├── antibody-design/
├── bioemu-ensemble/
├── batch-submission/
├── bcdesign-inverse/
├── bindcraft-workflow/
├── boltz-validation/
├── boltz2-validation/
├── boltzdesign1-binder/
├── boltzgen-binder-design/
├── chai1-validation/
├── chroma-backbone/
├── colabdesign-workflow/
├── colabfold-alternative/
├── config-management/
├── cross-validation/
├── design-patterns/
├── diffdock-ligand/
├── diffpepbuilder-design/
├── dima-workflow/
├── enzyme-design/
├── error-recovery/
├── esm-if1-design/
├── esm3-generative/
├── esmfold-validation/
├── evodiff-sequence/
├── evolla-llm/
├── fadiff-multimotif/
├── fast-screening/
├── filtering-ranking/
├── foldflow-backbone/
├── framediff-backbone/
├── framedipt-inpainting/
├── full-pipeline/
├── genie3-backbone/
├── igdiff-antibody/
├── install-guide/
├── la-proteina-backbone/
├── ligandmpnn-design/
├── multiflow-codesign/
├── next-steps/
├── nf-binder-design/
├── omegafold-validation/
├── openfold-validation/
├── periodic-summary/
├── pifold-sequence-design/
├── pipeline-selection/
├── pocketgen-ligand/
├── pro-ldm-workflow/
├── progen2-sequence/
├── protcomposer-workflow/
├── protein-analysis/
├── protein-design-context/
├── protein-generator/
├── proteina-complexa-binder/
├── proteindt-workflow/
├── protenix-training/
├── protenix-validation/
├── protpardelle-allatom/
├── quality-check/
├── quickstart-guide/
├── relso-sequence-optimization/
├── rfdiffusion-all-atom/
├── rfdiffusion3-workflow/
├── rfdpoly-multipolymer/
├── topodiff-workflow/
├── rfpeptides-macrocycle/
├── rosettafold-all-atom/
├── score-first-screening/
├── sequence-design/
├── structure-generation/
├── structure-preprocessing/
├── structure-validation/
└── troubleshooting/
```

## Skills by Goal

| Goal | Recommended Skills |
|------|-------------------|
| Design a binder | `pipeline-selection` → `structure-generation` → `sequence-design` → `structure-validation` |
| Design an antibody | `igdiff-antibody` (specialized, recommended) or `antibody-design` (general) |
| Design with a ligand | `rfdiffusion-all-atom` → `ligandmpnn-design` → `rosettafold-all-atom` |
| Design a peptide | `diffpepbuilder-design` → `boltz-validation` |
| Design a macrocyclic peptide | `rfpeptides-macrocycle` → `boltz-validation` |
| Quick screen many designs | `fast-screening` → `esmfold-validation` → `omegafold-validation` |
| Most robust validation | `cross-validation` → `boltz-validation` + `chai1-validation` |
| Avoid poor validations | `score-first-screening` → `structure-validation` |
| No local GPU | `colabdesign-workflow` → `chai1-validation` |
| Maximum diversity | `design-patterns` → `esm-if1-design` → `ensemble approach` |
| HPC / cloud binder design | `nf-binder-design` (Nextflow, SLURM-ready) |
| Commercial project | `boltz-validation` or `chai1-validation` or `protenix-validation` (permissive licenses) |
| Training/fine-tuning | `protenix-training` (fine-tuning guide) + `protenix-validation` (inference) |
| IDR / disordered proteins | `evodiff-sequence` (sequence-only generation) |
| Inference-time scaling | `protenix-validation` (log-linear improvements) |
| All-atom generation | `genie3-backbone` (native sidechains) or `rfdiffusion-all-atom` (ligand-aware) |
| Programmable generation from function | `esm3-generative` (sequence + structure + function tracks) |
| Conformational ensembles | `alphaflow-ensemble` (dynamics) or `foldflow-backbone` (flow matching) |
| Region redesign / inpainting | `framedipt-inpainting` (CDR loops, active sites, interfaces) |
| Joint seq+structure | `protein-generator` (RoseTTAFold diffusion) or `multiflow-codesign` or `chroma-backbone` or `la-proteina-backbone` |
| NVIDIA-backed generation | `la-proteina-backbone` (joint seq+structure) or `proteina-complexa-binder` (binder design) |
| Inference optimization | `aligninversepro-optimization` (reward-guided generation) |
| Binder with optimization | `proteina-complexa-binder` (inference-time optimization) |
| DNA/RNA-protein complex | `rfdpoly-multipolymer` (multi-polymer design) |
| Protein Q&A / reasoning | `evolla-llm` (conversational protein LLM) |
| Biochem-aware sequences | `bcdesign-inverse` (property-constrained design) |

#!/usr/bin/env python3
"""PreToolUse hook: recommend alternative tools based on user requirements.

When a user requests a protein design task, this hook analyzes their
requirements and suggests the best tool combination from available options.
"""
import traceback
import json
from typing import Any
import sys


PIPELINE_OPTIONS: list[dict[str, Any]] = [
    {
        "name": "Standard Pipeline",
        "tools": ["PDBFixer", "RFdiffusion", "ProteinMPNN", "AlphaFold3", "Filtering"],
        "strengths": ["General purpose", "Well-tested", "Fast backbone generation"],
        "best_for": ["De novo proteins", "Binders", "Motif scaffolding", "Symmetric oligomers"],
        "requirements": ["Local GPU", "AlphaFold3 databases (2.6TB)"],
        "stage1": "RFdiffusion",
        "stage2": "ProteinMPNN",
        "stage3": "AlphaFold3",
    },
    {
        "name": "Ligand-Aware Pipeline",
        "tools": ["PDBFixer", "RFdiffusionAA", "LigandMPNN", "AlphaFold3", "Filtering"],
        "strengths": ["All-atom design", "Ligand support", "Cofactor binding"],
        "best_for": ["Small molecule binders", "Heme proteins", "Metal sites", "Enzyme design"],
        "requirements": ["Local GPU", "Apptainer", "Ligand structure"],
        "stage1": "RFdiffusionAA",
        "stage2": "LigandMPNN",
        "stage3": "AlphaFold3",
    },
    {
        "name": "RFAA Validation Pipeline",
        "tools": ["PDBFixer", "RFdiffusionAA / ProteinMPNN", "RFAA", "Filtering"],
        "strengths": ["All-atom complex prediction", "Ligand/DNA/RNA/Metal support", "Explicit pae_inter metric"],
        "best_for": ["Protein-ligand validation", "Protein-DNA/RNA complexes", "Metal cofactors", "Covalent modifications"],
        "requirements": ["Local GPU", "~400GB databases (UniRef30/BFD/pdb100)"],
        "stage1": "RFdiffusionAA / ProteinMPNN",
        "stage2": "—",
        "stage3": "RFAA",
    },
    {
        "name": "Fast Screening Pipeline",
        "tools": ["PDBFixer", "RFdiffusion", "ProteinMPNN", "OmegaFold", "Filtering"],
        "strengths": ["No databases needed", "Fast validation", "Lightweight"],
        "best_for": ["Quick prototyping", "Large libraries", "No database access", "CPU fallback"],
        "requirements": ["Local GPU (or CPU)", "No databases"],
        "stage1": "RFdiffusion",
        "stage2": "ProteinMPNN",
        "stage3": "OmegaFold",
    },
    {
        "name": "Chroma Pipeline",
        "tools": ["PDBFixer", "Chroma", "AlphaFold3", "Filtering"],
        "strengths": ["Joint structure+sequence", "All-atom output", "Natural language prompting"],
        "best_for": ["All-atom generation", "Natural language design", "Symmetric proteins", "Long proteins"],
        "requirements": ["Local GPU", "Chroma API key", "Higher GPU memory"],
        "stage1": "Chroma (replaces Stage 1+2)",
        "stage2": "Chroma (built-in)",
        "stage3": "AlphaFold3",
    },
    {
        "name": "ColabDesign Pipeline",
        "tools": ["ColabDesign (AfDesign)", "AlphaFold3/OmegaFold", "Filtering"],
        "strengths": ["Free GPU (Colab)", "No local setup", "Flexible constraints"],
        "best_for": ["No local GPU", "Quick experiments", "Custom loss functions", "Binder hallucination"],
        "requirements": ["Google account", "Internet"],
        "stage1": "AfDesign (hallucination/binder)",
        "stage2": "AfDesign (built-in sequence)",
        "stage3": "AlphaFold3 or OmegaFold",
    },
    {
        "name": "Peptide Pipeline",
        "tools": ["PDBFixer", "DiffPepBuilder", "AMBER/Rosetta", "AlphaFold3", "Filtering"],
        "strengths": ["Specialized for peptides", "Disulfide support", "Built-in docking"],
        "best_for": ["8-30 aa peptides", "Cyclic peptides", "Peptide binders", "Disulfide bonds"],
        "requirements": ["Multi-GPU (recommended)", "PyRosetta license"],
        "stage1": "DiffPepBuilder",
        "stage2": "Built-in (with ESM)",
        "stage3": "AlphaFold3",
    },
    {
        "name": "Ensemble Pipeline",
        "tools": ["PDBFixer", "RFdiffusion", "ProteinMPNN + ESM-IF1", "AlphaFold3", "Filtering"],
        "strengths": ["Maximum diversity", "Complementary methods", "Better coverage"],
        "best_for": ["High-value targets", "Maximum success rate", "Diverse libraries"],
        "requirements": ["Local GPU", "AlphaFold3 databases"],
        "stage1": "RFdiffusion",
        "stage2": "ProteinMPNN + ESM-IF1 (ensemble)",
        "stage3": "AlphaFold3",
    },
    {
        "name": "BindCraft Pipeline",
        "tools": ["BindCraft (AF2 Multimer co-design + MPNN + AF2 monomer validation)"],
        "strengths": ["Automated binder design", "High experimental success", "End-to-end"],
        "best_for": ["Protein binders", "Target-to-binder", "High-value binder targets"],
        "requirements": ["Linux", "GPU with 32GB+ VRAM", "PyRosetta license for commercial use"],
        "stage1": "BindCraft",
        "stage2": "BindCraft (built-in MPNN)",
        "stage3": "BindCraft (built-in AF2 validation)",
    },
    {
        "name": "nf-binder-design Pipeline",
        "tools": ["Nextflow", "RFdiffusion / BindCraft / BoltzGen / Boltz-2", "Filtering"],
        "strengths": ["HPC/cloud ready", "Multiple methods in one pipeline", "Built-in filtering and scoring"],
        "best_for": ["Production binder design", "HPC cluster runs", "Cloud deployment", "Method comparison"],
        "requirements": ["Nextflow", "Apptainer/Singularity", "GPU", "Cluster or multi-GPU local"],
        "stage1": "RFdiffusion / BindCraft / BoltzGen",
        "stage2": "ProteinMPNN / built-in",
        "stage3": "AlphaFold2 / Boltz-2",
    },
    {
        "name": "PocketGen Pipeline",
        "tools": ["PocketGen", "AlphaFold3 / Boltz-1", "Filtering"],
        "strengths": ["Pocket-only redesign", "Ligand-aware co-design", "Preserves scaffold"],
        "best_for": ["Pocket redesign", "Enzyme engineering", "Ligand optimization"],
        "requirements": ["GPU", "Starting scaffold + ligand SDF", "PyTorch Geometric + Vina"],
        "stage1": "PocketGen",
        "stage2": "PocketGen (built-in sequence+structure)",
        "stage3": "AlphaFold3 / Boltz-1",
    },
    {
        "name": "ESM3 Pipeline",
        "tools": ["ESM3", "AlphaFold3 / Boltz-1", "Filtering"],
        "strengths": ["Programmable generation", "Function-aware design", "Multi-track prompting"],
        "best_for": ["Design from GO terms", "Partial prompt completion", "Novel function design"],
        "requirements": ["GPU", "HuggingFace access", "Non-commercial license (open model)"],
        "stage1": "ESM3",
        "stage2": "ESM3 (built-in sequence+structure)",
        "stage3": "AlphaFold3 / Boltz-1",
    },
    {
        "name": "ProteinGenerator Pipeline",
        "tools": ["PDBFixer", "ProteinGenerator", "AlphaFold3 / Boltz-1 / RFAA", "Filtering"],
        "strengths": ["Joint sequence+structure diffusion", "Motif scaffolding with seq constraints", "Custom potentials"],
        "best_for": ["Multistate design", "Sequence-aware motif scaffolding", "Composition control", "Functional design"],
        "requirements": ["GPU", "Conda env", "~4GB checkpoints"],
        "stage1": "ProteinGenerator (replaces Stage 1+2)",
        "stage2": "ProteinGenerator (built-in)",
        "stage3": "AlphaFold3 / Boltz-1 / RFAA",
    },
    {
        "name": "RFdiffusion3 Pipeline",
        "tools": ["PDBFixer", "RFdiffusion3", "ProteinMPNN / LigandMPNN", "AlphaFold3 / RFAA / Boltz-1", "Filtering"],
        "strengths": ["All-atom biomolecular design", "~10× faster than RFD2", "DNA/RNA/ligand/enzyme support", "Training code available"],
        "best_for": ["Protein-DNA complexes", "Protein-RNA complexes", "Enzyme design", "All-atom interaction design", "Fine-tuning on custom data"],
        "requirements": ["GPU", "pip install rc-foundry[rfd3]", "~GB checkpoints"],
        "stage1": "RFdiffusion3",
        "stage2": "ProteinMPNN / LigandMPNN",
        "stage3": "AlphaFold3 / RFAA / Boltz-1",
    },
    {
        "name": "TopoDiff Pipeline",
        "tools": ["TopoDiff", "ProteinMPNN", "AlphaFold3 / Boltz-1 / OmegaFold", "Filtering"],
        "strengths": ["MIT license", "Topology-aware latent encoding", "Length-controlled sampling", "Lightweight Stage 1"],
        "best_for": ["Unconditional backbone generation", "50-250 residue designs", "Diverse backbone libraries", "Coverage benchmarks"],
        "requirements": ["GPU", "conda env", "Zenodo weights"],
        "stage1": "TopoDiff",
        "stage2": "ProteinMPNN",
        "stage3": "AlphaFold3 / Boltz-1 / OmegaFold",
    },
    {
        "name": "PRO-LDM Pipeline",
        "tools": ["RFdiffusion / TopoDiff", "PRO-LDM", "AlphaFold3 / Boltz-1", "Filtering"],
        "strengths": ["MIT license", "Fitness-conditional sequence design", "Integrated fitness prediction", "Classifier-free guidance"],
        "best_for": ["Sequence optimization", "OOD functional variants", "Labeled fitness datasets", "Latent-space sequence diffusion"],
        "requirements": ["GPU", "Python 3.8", "Labeled training data or pre-trained checkpoint"],
        "stage1": "RFdiffusion / TopoDiff",
        "stage2": "PRO-LDM",
        "stage3": "AlphaFold3 / Boltz-1",
    },
    {
        "name": "ProtComposer Pipeline",
        "tools": ["ProtComposer", "ProteinMPNN / LigandMPNN", "AlphaFold3 / Boltz-1", "Filtering"],
        "strengths": ["3D ellipsoid layout control", "Flow matching", "Compositional generation", "Substructure editing"],
        "best_for": ["Layout-controlled design", "Domain connectivity redesign", "Compositional proteins", "Ellipsoid-guided generation"],
        "requirements": ["GPU", "CUDA 11.3 PyTorch", "MultiFlow dependencies", "Research/non-commercial license"],
        "stage1": "ProtComposer",
        "stage2": "ProteinMPNN / LigandMPNN",
        "stage3": "AlphaFold3 / Boltz-1",
    },
    {
        "name": "ProteinDT Pipeline",
        "tools": ["ProteinDT", "ESMFold / AlphaFold3 / Boltz-1", "Filtering"],
        "strengths": ["MIT license", "Text-to-protein generation", "Zero-shot text-guided editing", "Protein-language alignment"],
        "best_for": ["Text-guided sequence design", "Functional descriptions", "Zero-shot protein editing", "UniProt-style prompts"],
        "requirements": ["GPU", "Python 3.7", "HuggingFace checkpoints"],
        "stage1": "ProteinDT (sequence generation)",
        "stage2": "—",
        "stage3": "ESMFold / AlphaFold3 / Boltz-1",
    },
    {
        "name": "DiMA Pipeline",
        "tools": ["DiMA", "ESMFold / AlphaFold3 / Boltz-1", "Filtering"],
        "strengths": ["MIT license", "Latent diffusion on pLM representations", "Encoder-agnostic (ESM-2/ESMc/CHEAP/SaProt)", "35M-parameter denoiser"],
        "best_for": ["Sequence generation from pLM latents", "Motif scaffolding in latent space", "Family-specific generation", "Infilling", "Fold-conditioned design"],
        "requirements": ["GPU", "Python 3.8+", "HuggingFace checkpoints", "Pretrained pLM encoder"],
        "stage1": "DiMA (sequence generation from pLM latents)",
        "stage2": "—",
        "stage3": "ESMFold / AlphaFold3 / Boltz-1",
    },
    {
        "name": "FrameDiff Pipeline",
        "tools": ["PDBFixer", "FrameDiff", "ProteinMPNN", "AlphaFold3 / Boltz-1", "Filtering"],
        "strengths": ["MIT license", "SE(3) diffusion on rigid residue frames", "No pretrained folding network required", "Generates up to ~500 residues"],
        "best_for": ["Unconditional monomer generation", "Motif scaffolding", "MIT-licensed backbone generation", "Direct SE(3) diffusion"],
        "requirements": ["GPU", "conda env from se3.yml", "PDB for training (optional)"],
        "stage1": "FrameDiff",
        "stage2": "ProteinMPNN",
        "stage3": "AlphaFold3 / Boltz-1",
    },
    {
        "name": "Protpardelle-1c Pipeline",
        "tools": ["PDBFixer", "Protpardelle-1c", "ProteinMPNN / LigandMPNN", "AlphaFold3 / Boltz-1", "Filtering"],
        "strengths": ["MIT license", "All-atom sequence+structure co-design", "Side-chain conditioned motif scaffolding", "Binder + multichain support", "~22M parameters"],
        "best_for": ["All-atom protein generation", "Motif scaffolding", "Binder design", "Multichain complexes", "Commercial projects"],
        "requirements": ["GPU", "CUDA >= 12.4", "Foldseek", "ProteinMPNN + LigandMPNN + ESMFold weights"],
        "stage1": "Protpardelle-1c (all-atom generation)",
        "stage2": "ProteinMPNN / LigandMPNN (optional redesign)",
        "stage3": "AlphaFold3 / Boltz-1",
    },
    {
        "name": "PiFold Sequence Design Pipeline",
        "tools": ["PDBFixer", "RFdiffusion / FrameDiff", "PiFold", "AlphaFold3 / Boltz-1", "Filtering"],
        "strengths": ["MIT license", "70× faster than autoregressive methods", "One-shot sequence decoder", "Strong inverse-folding recovery"],
        "best_for": ["High-throughput fixed-backbone sequence design", "Large libraries", "Fast sequence recovery", "MIT-licensed Stage 2"],
        "requirements": ["GPU (or CPU)", "PyTorch + PyTorch Geometric", "CATH or custom backbone structures"],
        "stage1": "RFdiffusion / FrameDiff / TopoDiff (backbone generation)",
        "stage2": "PiFold",
        "stage3": "AlphaFold3 / Boltz-1 / ESMFold",
    },
    {
        "name": "FADiff Multi-Motif Scaffolding Pipeline",
        "tools": ["PDBFixer", "FADiff", "ProteinMPNN", "AlphaFold3 / Boltz-1", "Filtering"],
        "strengths": ["Multi-motif scaffolding", "Floating anchor formulation", "Guarantees motif presence", "Generalizes to arbitrary motif counts"],
        "best_for": ["Multiple functional motifs", "Unknown motif positions", "Academic motif scaffolding", "Built on FrameDiff"],
        "requirements": ["GPU", "conda env from FADiff.yml", "PDB mirror for training (optional for inference)"],
        "stage1": "FADiff",
        "stage2": "ProteinMPNN",
        "stage3": "AlphaFold3 / Boltz-1",
    },
    {
        "name": "BoltzGen Universal Binder Design Pipeline",
        "tools": ["BoltzGen (design → inverse folding → folding → analysis → filtering)"],
        "strengths": ["MIT license", "Universal binder design", "End-to-end single command", "Built-in inverse folding + filtering", "Boltz-2 co-folding validation"],
        "best_for": ["Protein binders", "Peptide binders", "Small-molecule binders", "Antibody / nanobody design", "MIT-licensed binder campaigns"],
        "requirements": ["GPU", "Python >=3.11", "~6 GB model download", "Hugging Face access for weights"],
        "stage1": "BoltzGen (all-atom design)",
        "stage2": "BoltzGen (built-in inverse folding)",
        "stage3": "BoltzGen (Boltz-2 validation folding)",
    },
    {
        "name": "BioEmu Conformational Ensemble Pipeline",
        "tools": ["BioEmu (sequence → ensemble → sidechain_relax → analysis)"],
        "strengths": ["MIT license", "Generative equilibrium ensembles", "Thousands of conformations per GPU hour", "Free-energy estimates", "Cryptic-pocket capture"],
        "best_for": ["Conformational ensemble prediction", "Cryptic-pocket detection", "Stability estimation", "Comparing designed sequences", "Dynamics without MD"],
        "requirements": ["Linux GPU", "Python >=3.10", "~3.5 GB AlphaFold2 weights", "Hugging Face access for BioEmu checkpoints"],
        "stage1": "—",
        "stage2": "—",
        "stage3": "BioEmu (ensemble generation + analysis)",
    },
    {
        "name": "DiffDock Small-Molecule Docking Pipeline",
        "tools": ["DiffDock (protein + ligand → diffusion poses → confidence ranking)"],
        "strengths": ["MIT license", "Blind docking", "No binding box required", "Batch virtual screening", "State-of-the-art pose prediction"],
        "best_for": ["Small-molecule docking", "Virtual screening", "Ligand pose prediction", "Ligand-aware design validation", "No-pocket docking"],
        "requirements": ["GPU (strongly recommended)", "Conda env with PyTorch Geometric + RDKit", "~2 GB model weights"],
        "stage1": "—",
        "stage2": "—",
        "stage3": "DiffDock (pose generation + confidence scoring)",
    },
    {
        "name": "ProGen2 Autoregressive Sequence Generation Pipeline",
        "tools": ["ProGen2 (context → autoregressive sequence generation → ESMFold validation)"],
        "strengths": ["BSD-3 license", "Up to 6.4B parameters", "Zero-shot fitness scoring", "Autoregressive sampling", "Antibody OAS checkpoint"],
        "best_for": ["Sequence-only generation", "Zero-shot fitness scoring", "Large-scale sequence exploration", "Antibody sequence generation", "No structural template needed"],
        "requirements": ["GPU (strongly recommended for large/xlarge)", "Python 3.8+", "~10 GB checkpoint download", "Google Cloud Storage access for checkpoints"],
        "stage1": "ProGen2 (sequence generation)",
        "stage2": "—",
        "stage3": "ESMFold / AlphaFold3 / OmegaFold",
    },
    {
        "name": "Boltz-2 Structure + Affinity Validation Pipeline",
        "tools": ["Boltz-2 (YAML → structure prediction + confidence + affinity)"],
        "strengths": ["MIT license", "Structure + binding affinity", "FEP-like accuracy ~1000× faster", "Ligand / DNA / RNA / covalent modifications", "Single consumer GPU inference"],
        "best_for": ["Structure validation", "Affinity prediction", "Hit discovery", "Ligand optimization", "Commercial use"],
        "requirements": ["GPU (strongly recommended)", "pip install boltz[cuda]", "Model cache download", "Optional ColabFold MSA server"],
        "stage1": "RFdiffusion / RFdiffusionAA",
        "stage2": "ProteinMPNN / LigandMPNN",
        "stage3": "Boltz-2 (structure + affinity)",
    },
    {
        "name": "BoltzDesign1 All-Atom Binder Design Pipeline",
        "tools": ["BoltzDesign1 (Boltz-1 inversion → LigandMPNN / ProteinMPNN → optional AF3 / Boltz-2)"],
        "strengths": ["MIT license", "Inverts Boltz-1 (AlphaFold3-class)", "No fine-tuning", "Protein / small molecule / RNA / DNA / metal / PTM binders", "Optional AF3 cross-validation"],
        "best_for": ["All-atom binder design", "Novel target modalities", "Small-molecule binders", "Nucleic-acid binders", "Metal/PTM binder design"],
        "requirements": ["GPU", "Boltz-1 weights", "LigandMPNN + ProteinMPNN", "Optional AlphaFold3 for cross-validation"],
        "stage1": "BoltzDesign1 (Boltz-1 inversion)",
        "stage2": "LigandMPNN / ProteinMPNN (built-in redesign)",
        "stage3": "AlphaFold3 / Boltz-2 (optional validation)",
    },
]


def _analyze_request(request_text: str) -> dict[str, Any]:
    """Analyze user request text to determine requirements."""
    text_lower = request_text.lower()

    signals: dict[str, list[str]] = {
        "ligand": ["ligand", "small molecule", "cofactor", "heme", "metal", "enzyme",
                   "substrate", "inhibitor", "binding pocket", "active site"],
        "peptide": ["peptide", "cyclic peptide", "macrocycle", "8-30", "short peptide"],
        "fast": ["fast", "quick", "screen", "many designs", "batch", "library",
                 "no database", "lightweight", "cpu"],
        "colab": ["colab", "google colab", "no gpu", "free", "cloud", "browser"],
        "chroma": ["chroma", "all-atom", "natural language", "joint design",
                   "side chain", "full atom"],
        "ensemble": ["ensemble", "multiple methods", "maximum diversity", "best chance",
                     "high value", "combine"],
        "bindcraft": ["bindcraft", "automated binder", "one-shot binder", "de novo binder",
                      "target-to-binder", "binder design", "design a binder", "design binders"],
        "pocketgen": ["pocketgen", "pocket design", "redesign pocket", "pocket redesign",
                      "ligand-binding pocket", "active site redesign", "enzyme pocket"],
        "esm3": ["esm3", "evolutionaryscale", "programmable protein", "generate from function",
                 "go terms", "gene ontology", "function-based design", "esm gfp", "esmgfp"],
        "protein_generator": ["protein generator", "proteingenerator", "sequence diffusion",
                              "rosetta sequence", "joint sequence structure", "multistate design",
                              "motif scaffolding with sequence", "lisanza"],
        "rfdiffusion3": ["rfdiffusion3", "rfd3", "rf diffusion 3", "rf-diffusion-3",
                         "all-atom interaction", "biomolecular interaction", "dna binder",
                         "rna binder", "nucleic acid binder", "foundry", "rosetta commons foundry",
                         "train rfdiffusion", "fine-tune rfdiffusion", "rfdiffusion3 tutorial"],
        "topodiff": ["topodiff", "topology aware", "topology-aware", "global geometry",
                     "latent encoding", "unconditional backbone", "length controlled",
                     "length-controlled", "backbone coverage", "backbone diversity",
                     "tsinghua topodiff", "gong lab"],
        "pro_ldm": ["pro-ldm", "pro ldm", "conditional latent diffusion",
                    "fitness optimization", "sequence optimization", "functional optimization",
                    "classifier-free guidance", "ood design", "out-of-distribution",
                    "fitness label", "variant design", "jiang zixuan", "azusaxuan"],
        "protcomposer": ["protcomposer", "prot-composer", "ellipsoid", "3d ellipsoid",
                         "compositional generation", "layout control", "spatial layout",
                         "flow matching", "nvlabs", "nvidia protein", "substructure",
                         "domain connectivity", "multi-flow", "multiflow"],
        "proteindt": ["proteindt", "protein-dt", "text guided", "text-guided",
                      "text to protein", "text-to-protein", "proteinclap",
                      "text prompt protein", "natural language protein",
                      "uniprot text", "protein language", "chao1224"],
        "dima": ["dima", "diffusion on language model", "plm latent", "protein language model diffusion",
                 "encoder agnostic", "encoder-agnostic", "meshchaninov", "icml 2025",
                 "esm2 diffusion", "esm-2 diffusion", "cheap diffusion", "saprot diffusion",
                 "latent sequence generation", "plm representation", "protein lm diffusion",
                 "35m denoiser", "family specific generation", "fold conditioned", "motif scaffolding latent"],
        "framediff": ["framediff", "frame diff", "se3 diffusion", "se(3) diffusion",
                      "jason yim", "yim se3", "rigid body diffusion", "residue frame diffusion",
                      "manifold diffusion", "se3 backbone", "no folding network",
                      "mit backbone diffusion", "backbone only diffusion"],
        "protpardelle": ["protpardelle", "prot-pardelle", "protpardelle-1c", "all-atom protein generative",
                         "stanford protein design lab", "po-ssu huang", "side-chain conditioning",
                         "superposition state", "motifbench protpardelle", "multichain generation",
                         "allatom seq struct", "all-atom sequence structure", "compact protein diffusion",
                         "binder protpardelle", "hotspot conditioning"],
        "pifold": ["pifold", "pi-fold", "prodesign", "inverse folding", "structure based sequence design",
                   "fixed backbone design", "one shot sequence decoder", "70x faster", "70 times faster",
                   "pignn", "virtual atoms", "cath recovery", "zhangyang gao", "westlake pifold"],
        "fadiff": ["fadiff", "fa-diff", "floating anchor", "multi motif", "multi-motif",
                   "multiple motifs", "motif scaffolding", "floating anchors", "rigid anchor",
                   "aim uofa fadiff", "ke liu fadiff", "chunhua shen fadiff", "icml 2024 fadiff"],
        "boltzgen": ["boltzgen", "boltz gen", "universal binder", "binder design",
                     "hannes stark", "mit jameel clinic", "boltz 2 binder",
                     "design specification yaml", "protein anything", "peptide anything",
                     "antibody anything", "nanobody anything", "small molecule binder",
                     "end to end binder", "pip install boltzgen"],
        "bioemu": ["bioemu", "bio emu", "conformational ensemble", "equilibrium ensemble",
                   "protein dynamics", "cryptic pocket", "local unfolding", "domain motion",
                   "free energy estimate", "microsoft bioemu", "md emulation",
                   "ensemble generation", "conformational landscape", "folding free energy",
                   "pip install bioemu", "sidechain_relax"],
        "diffdock": ["diffdock", "diff dock", "blind docking", "small molecule docking",
                     "protein ligand docking", "virtual screening", "docking pose",
                     "no binding box", "diffusion docking", "gcorso diffdock",
                     "hannes stark diffdock", "ligand pose", "dock ligand",
                     "molecular docking", "smiles docking"],
        "progen2": ["progen2", "progen", "salesforce progen", "autoregressive protein",
                    "protein language model generation", "zero shot fitness", "zero-shot fitness",
                    "fitness scoring", "sequence generation plm", "progen2 sample",
                    "progen2 likelihood", "progen2-oas", "plm generation", "nijkamp progen"],
        "boltz2": ["boltz2", "boltz 2", "boltz-2", "binding affinity prediction",
                   "affinity prediction", "structure and affinity", "fep accuracy",
                   "fep speed", "boltz predict affinity", "jwohlwend boltz",
                   "mit recursion boltz", "boltz bio", "affinityProbability",
                   "affinity_pred_value", "boltz affinity"],
        "boltzdesign1": ["boltzdesign1", "boltzdesign", "boltz design", "invert boltz",
                         "invert boltz-1", "invert alphafold3", "all atom binder design",
                         "yehlin cho", "ovchinnikov binder", "mit binder design 2025",
                         "boltzdesign1.py", "small molecule binder design boltz",
                         "dna binder design", "rna binder design", "metal binder design",
                         "ptm binder design"],
        "rfaa": ["rfaa", "rosettafold all-atom", "rosettafold-all-atom", "pae_inter",
                 "protein-ligand complex", "protein-dna", "protein-rna", "metal ion",
                 "covalent modification", "all-atom validation"],
        "nf_binder_design": ["nf-binder-design", "nextflow", "hpc", "cluster", "slurm",
                             "apptainer", "singularity", "cloud binder", "australian protein design initiative",
                             "apdi", "multiple methods", "production pipeline"],
        "antibody": ["antibody", "nanobody", "vhh", "cdr", "fab", "mab"],
    }

    detected: dict[str, float] = {}
    for category, keywords in signals.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            detected[category] = score

    return detected


def _recommend_pipelines(detected: dict[str, float], text_lower: str = "") -> list[dict[str, Any]]:
    """Recommend pipelines based on detected signals."""
    scores: dict[int, float] = {i: 0.0 for i in range(len(PIPELINE_OPTIONS))}

    # Ligand-aware signals
    if "ligand" in detected:
        scores[1] += detected["ligand"] * 2.0  # Ligand-Aware Pipeline
        scores[0] -= 1.0  # Standard less suitable

    # RFAA signals (validation of complexes with ligands/DNA/RNA/metals)
    if "rfaa" in detected:
        scores[2] += detected["rfaa"] * 3.0  # RFAA Validation Pipeline

    # Fast/lightweight signals
    if "fast" in detected:
        scores[3] += detected["fast"] * 2.0  # Fast Screening Pipeline
        scores[0] -= 0.5

    # Colab signals
    if "colab" in detected:
        scores[4] += detected["colab"] * 2.0  # Chroma Pipeline
        scores[5] += detected["colab"] * 2.5  # ColabDesign Pipeline (stronger)

    # Chroma signals
    if "chroma" in detected:
        scores[4] += detected["chroma"] * 2.5  # Chroma Pipeline

    # Peptide signals
    if "peptide" in detected:
        scores[6] += detected["peptide"] * 2.0  # Peptide Pipeline
        scores[0] -= 0.5

    # Ensemble signals
    if "ensemble" in detected:
        scores[7] += detected["ensemble"] * 2.5  # Ensemble Pipeline

    # BindCraft signals (strong preference for binder-specific language)
    if "bindcraft" in detected:
        scores[8] += detected["bindcraft"] * 3.0  # BindCraft Pipeline

    # nf-binder-design signals (HPC/cloud Nextflow pipeline)
    if "nf_binder_design" in detected:
        scores[9] += detected["nf_binder_design"] * 3.0  # nf-binder-design Pipeline

    # PocketGen signals
    if "pocketgen" in detected:
        scores[10] += detected["pocketgen"] * 3.0  # PocketGen Pipeline

    # ESM3 signals
    if "esm3" in detected:
        scores[11] += detected["esm3"] * 3.0  # ESM3 Pipeline

    # ProteinGenerator signals (joint seq+struct, multistate, custom potentials)
    if "protein_generator" in detected:
        scores[12] += detected["protein_generator"] * 3.0  # ProteinGenerator Pipeline

    # RFdiffusion3 signals (all-atom biomolecular interactions, DNA/RNA/ligand/enzyme)
    if "rfdiffusion3" in detected:
        scores[13] += detected["rfdiffusion3"] * 3.0  # RFdiffusion3 Pipeline

    # TopoDiff signals (topology-aware unconditional backbone generation)
    if "topodiff" in detected:
        scores[14] += detected["topodiff"] * 3.0  # TopoDiff Pipeline

    # PRO-LDM signals (fitness-conditional sequence design / functional optimization)
    if "pro_ldm" in detected:
        scores[15] += detected["pro_ldm"] * 3.0  # PRO-LDM Pipeline

    # ProtComposer signals (ellipsoid-guided compositional generation)
    if "protcomposer" in detected:
        scores[16] += detected["protcomposer"] * 3.0  # ProtComposer Pipeline

    # ProteinDT signals (text-guided protein sequence generation / editing)
    if "proteindt" in detected:
        scores[17] += detected["proteindt"] * 3.0  # ProteinDT Pipeline

    # DiMA signals (latent diffusion on pLM representations)
    if "dima" in detected:
        scores[18] += detected["dima"] * 3.0  # DiMA Pipeline

    # FrameDiff signals (SE(3) diffusion backbone generation)
    if "framediff" in detected:
        scores[19] += detected["framediff"] * 3.0  # FrameDiff Pipeline

    # Protpardelle-1c signals (all-atom seq+struct co-design, motif scaffolding, binder, multichain)
    if "protpardelle" in detected:
        scores[20] += detected["protpardelle"] * 3.0  # Protpardelle-1c Pipeline

    # PiFold signals (fast MIT inverse folding / structure-based sequence design)
    if "pifold" in detected:
        scores[21] += detected["pifold"] * 3.0  # PiFold Sequence Design Pipeline

    # FADiff signals (multi-motif scaffolding with floating anchors)
    if "fadiff" in detected:
        scores[22] += detected["fadiff"] * 3.0  # FADiff Multi-Motif Scaffolding Pipeline

    # BoltzGen signals (universal MIT binder design, end-to-end single command)
    if "boltzgen" in detected:
        scores[23] += detected["boltzgen"] * 3.0  # BoltzGen Universal Binder Design Pipeline

    # BioEmu signals (generative equilibrium ensembles, cryptic pockets, dynamics without MD)
    if "bioemu" in detected:
        scores[24] += detected["bioemu"] * 3.0  # BioEmu Conformational Ensemble Pipeline

    # DiffDock signals (blind small-molecule docking, virtual screening, ligand pose prediction)
    if "diffdock" in detected:
        scores[25] += detected["diffdock"] * 3.0  # DiffDock Small-Molecule Docking Pipeline

    # ProGen2 signals (autoregressive sequence generation, zero-shot fitness scoring)
    if "progen2" in detected:
        scores[26] += detected["progen2"] * 3.0  # ProGen2 Autoregressive Sequence Generation Pipeline

    # Boltz-2 signals (structure + binding affinity prediction, FEP-like accuracy)
    if "boltz2" in detected:
        scores[27] += detected["boltz2"] * 3.0  # Boltz-2 Structure + Affinity Validation Pipeline

    # BoltzDesign1 signals (all-atom biomolecular binder design by inverting Boltz-1)
    if "boltzdesign1" in detected:
        scores[28] += detected["boltzdesign1"] * 3.0  # BoltzDesign1 All-Atom Binder Design Pipeline

    # Generic binder signals (boost BindCraft, nf-binder-design, and BoltzGen if explicit binder language)
    binder_kws = ["binder", "bind to", "binding protein", "protein binder"]
    binder_score = sum(1 for kw in binder_kws if kw in text_lower)
    if binder_score > 0:
        scores[8] += binder_score * 1.0  # mild boost for BindCraft
        scores[9] += binder_score * 0.5  # mild boost for nf-binder-design
        scores[23] += binder_score * 0.7  # mild boost for BoltzGen

    # Pocket / active site signals (boost PocketGen)
    pocket_kws = ["pocket", "active site", "substrate binding", "cofactor binding"]
    pocket_score = sum(1 for kw in pocket_kws if kw in text_lower)
    if pocket_score > 0:
        scores[10] += pocket_score * 0.8  # mild boost for PocketGen

    # Function / GO term signals (boost ESM3)
    function_kws = ["go term", "gene ontology", "function description", "generate from function",
                    "programmable protein"]
    function_score = sum(1 for kw in function_kws if kw in text_lower)
    if function_score > 0:
        scores[11] += function_score * 1.0  # mild boost for ESM3

    # Joint seq+struct / multistate / custom potential signals (boost ProteinGenerator)
    proteingenerator_kws = ["multistate", "custom potential", "composition control",
                            "sequence activity", "repeat symmetry", "joint generation",
                            "sequence and structure"]
    pg_score = sum(1 for kw in proteingenerator_kws if kw in text_lower)
    if pg_score > 0:
        scores[12] += pg_score * 0.8  # mild boost for ProteinGenerator

    # Complex validation signals (boost RFAA and RFdiffusion3)
    complex_kws = ["dna", "rna", "nucleic acid", "metal ion", "small molecule validation",
                   "covalent", "pae_inter"]
    complex_score = sum(1 for kw in complex_kws if kw in text_lower)
    if complex_score > 0:
        scores[2] += complex_score * 0.8  # mild boost for RFAA
        scores[13] += complex_score * 0.5  # mild boost for RFdiffusion3

    # Enzyme / all-atom interaction signals (boost RFdiffusion3)
    rfd3_kws = ["enzyme design", "all-atom generation", "foundry", "rfdiffusion3",
                "dna binder", "rna binder", "biomolecular interaction"]
    rfd3_score = sum(1 for kw in rfd3_kws if kw in text_lower)
    if rfd3_score > 0:
        scores[13] += rfd3_score * 1.0  # mild boost for RFdiffusion3

    # Topology / coverage / diversity signals (boost TopoDiff)
    topodiff_kws = ["topology", "coverage", "diverse backbone", "unconditional generation",
                    "mit license", "length range", "50 residues", "250 residues"]
    topodiff_score = sum(1 for kw in topodiff_kws if kw in text_lower)
    if topodiff_score > 0:
        scores[14] += topodiff_score * 0.8  # mild boost for TopoDiff

    # Fitness / optimization / latent diffusion signals (boost PRO-LDM)
    proldm_kws = ["fitness", "optimize", "functional", "latent diffusion", "conditional generation",
                  "variant", "sequence design", "property"]
    proldm_score = sum(1 for kw in proldm_kws if kw in text_lower)
    if proldm_score > 0:
        scores[15] += proldm_score * 0.8  # mild boost for PRO-LDM

    # Ellipsoid / layout / compositional signals (boost ProtComposer)
    protcomposer_kws = ["ellipsoid", "layout", "compositional", "substructure",
                        "spatial control", "3d layout", "domain connectivity"]
    protcomposer_score = sum(1 for kw in protcomposer_kws if kw in text_lower)
    if protcomposer_score > 0:
        scores[16] += protcomposer_score * 0.8  # mild boost for ProtComposer

    # Text / natural language / UniProt signals (boost ProteinDT)
    proteindt_kws = ["text", "natural language", "uniprot", "description",
                     "text prompt", "language model", "protein editing"]
    proteindt_score = sum(1 for kw in proteindt_kws if kw in text_lower)
    if proteindt_score > 0:
        scores[17] += proteindt_score * 0.8  # mild boost for ProteinDT

    # pLM latent / encoder-agnostic / ICML / lightweight diffusion signals (boost DiMA)
    dima_kws = ["plm", "protein language model", "encoder agnostic", "encoder-agnostic",
                "meshchaninov", "icml 2025", "latent diffusion", "35m", "family specific",
                "fold conditioned", "infilling", "cheap encoder", "saprot"]
    dima_score = sum(1 for kw in dima_kws if kw in text_lower)
    if dima_score > 0:
        scores[18] += dima_score * 0.8  # mild boost for DiMA

    # SE(3) / rigid-frame / manifold / no-folding-network signals (boost FrameDiff)
    framediff_kws = ["se3", "se(3)", "rigid frame", "residue frame", "manifold diffusion",
                     "no alphafold", "no folding network", "backbone only generation",
                     "mit license backbone"]
    framediff_score = sum(1 for kw in framediff_kws if kw in text_lower)
    if framediff_score > 0:
        scores[19] += framediff_score * 0.8  # mild boost for FrameDiff

    # All-atom / side-chain / superposition / multichain / compact diffusion signals (boost Protpardelle-1c)
    protpardelle_kws = ["all-atom", "side chain", "sidechain", "superposition state",
                        "stanford protein design lab", "compact diffusion", "22m parameters",
                        "codesign", "sequence and structure", "joint seq struct"]
    protpardelle_score = sum(1 for kw in protpardelle_kws if kw in text_lower)
    if protpardelle_score > 0:
        scores[20] += protpardelle_score * 0.8  # mild boost for Protpardelle-1c

    # Fast inverse folding / high-throughput sequence design / one-shot decoder signals (boost PiFold)
    pifold_kws = ["inverse folding", "structure based sequence design", "fixed backbone",
                  "one-shot decoder", "70x faster", "70 times faster", "sequence recovery",
                  "high throughput sequence", "fast sequence design"]
    pifold_score = sum(1 for kw in pifold_kws if kw in text_lower)
    if pifold_score > 0:
        scores[21] += pifold_score * 0.8  # mild boost for PiFold

    # Multi-motif / floating anchor / arbitrary motif count signals (boost FADiff)
    fadiff_kws = ["multiple motif", "multi motif", "floating anchor", "motif scaffolding",
                  "rigid anchor", "unknown motif position", "arbitrary motif"]
    fadiff_score = sum(1 for kw in fadiff_kws if kw in text_lower)
    if fadiff_score > 0:
        scores[22] += fadiff_score * 0.8  # mild boost for FADiff

    # Universal binder / MIT / end-to-end / antibody / nanobody / small-molecule signals (boost BoltzGen)
    boltzgen_kws = ["universal binder", "mit license binder", "end to end binder", "end-to-end binder",
                    "peptide binder", "small molecule binder", "antibody design", "nanobody design",
                    "built-in filtering", "single command binder", "boltz 2 binder"]
    boltzgen_score = sum(1 for kw in boltzgen_kws if kw in text_lower)
    if boltzgen_score > 0:
        scores[23] += boltzgen_score * 0.8  # mild boost for BoltzGen

    # Ensemble / dynamics / cryptic pocket / free-energy signals (boost BioEmu)
    bioemu_kws = ["conformational ensemble", "equilibrium ensemble", "cryptic pocket",
                  "protein dynamics", "local unfolding", "domain motion", "free energy",
                  "folding stability", "md emulation", "microsoft bioemu", "ensemble generation"]
    bioemu_score = sum(1 for kw in bioemu_kws if kw in text_lower)
    if bioemu_score > 0:
        scores[24] += bioemu_score * 0.8  # mild boost for BioEmu

    # Docking / virtual screening / ligand pose signals (boost DiffDock)
    diffdock_kws = ["docking", "dock a ligand", "virtual screen", "pose prediction",
                    "protein ligand", "smiles docking", "small molecule pose",
                    "no binding box", "blind dock", "diffusion docking"]
    diffdock_score = sum(1 for kw in diffdock_kws if kw in text_lower)
    if diffdock_score > 0:
        scores[25] += diffdock_score * 0.8  # mild boost for DiffDock

    # Autoregressive PLM / zero-shot fitness / large language model signals (boost ProGen2)
    progen2_kws = ["autoregressive", "protein language model", "plm generation",
                   "zero shot fitness", "zero-shot fitness", "fitness score",
                   "log likelihood protein", "sequence-only generation", "salesforce progen",
                   "antibody sequence generation", "oas checkpoint"]
    progen2_score = sum(1 for kw in progen2_kws if kw in text_lower)
    if progen2_score > 0:
        scores[26] += progen2_score * 0.8  # mild boost for ProGen2

    # Affinity / FEP / structure+affinity / commercial validation signals (boost Boltz-2)
    boltz2_kws = ["binding affinity", "affinity prediction", "fep", "free energy perturbation",
                  "ic50 prediction", "predict affinity", "structure and affinity",
                  "commercial validation", "boltz predict", "boltz-2", "mit boltz"]
    boltz2_score = sum(1 for kw in boltz2_kws if kw in text_lower)
    if boltz2_score > 0:
        scores[27] += boltz2_score * 0.8  # mild boost for Boltz-2

    # Boltz-1 inversion / all-atom binder / nucleic acid / metal / PTM signals (boost BoltzDesign1)
    boltzdesign1_kws = ["invert boltz", "invert alphafold3", "all-atom binder",
                        "small molecule binder", "rna binder", "dna binder", "metal binder",
                        "ptm binder", "nucleic acid binder", "boltzdesign", "yehlin cho"]
    boltzdesign1_score = sum(1 for kw in boltzdesign1_kws if kw in text_lower)
    if boltzdesign1_score > 0:
        scores[28] += boltzdesign1_score * 0.8  # mild boost for BoltzDesign1

    # HPC / cloud / production signals (boost nf-binder-design)
    hpc_kws = ["nextflow", "slurm", "cluster", "hpc", "production", "multiple methods"]
    hpc_score = sum(1 for kw in hpc_kws if kw in text_lower)
    if hpc_score > 0:
        scores[9] += hpc_score * 1.0  # mild boost for nf-binder-design

    # Antibody signals (default to standard or ColabDesign)
    if "antibody" in detected:
        scores[0] += detected["antibody"] * 0.5
        scores[5] += detected["antibody"] * 0.5

    # Sort by score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    recommendations = []
    for idx, score in ranked:
        if score >= 0:
            pipeline = PIPELINE_OPTIONS[idx].copy()
            pipeline["match_score"] = score
            recommendations.append(pipeline)

    return recommendations


def main() -> int:
    """Main entry point for hook."""
    try:
        input_data = sys.stdin.read()
        data = json.loads(input_data) if input_data.strip() else {}
    except json.JSONDecodeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    # Only process tool use requests for protein design tools
    tool_name = data.get("tool", "")
    if tool_name not in {"run_rfdiffusion", "run_proteinmpnn", "run_alphafold3",
                         "run_pdbfixer", "submit_job", "get_tool_info"}:
        return 0

    # Get the user's original query from context (if available)
    context = data.get("context", "")
    if not context and "params" in data:
        # Use params as fallback context
        context = json.dumps(data.get("params", {}))

    if not context:
        return 0

    detected = _analyze_request(context)
    if not detected:
        return 0

    recommendations = _recommend_pipelines(detected, context.lower())
    if not recommendations:
        return 0

    # Output recommendation
    top = recommendations[0]
    output = f"""[Alternative Tool Recommender] Based on your request, consider these pipeline options:

**Top Recommendation: {top['name']}**
- Tools: {' → '.join(top['tools'])}
- Best for: {', '.join(top['best_for'][:3])}
- Requirements: {', '.join(top['requirements'])}
- Stage mapping: Stage 1={top['stage1']}, Stage 2={top['stage2']}, Stage 3={top['stage3']}
"""

    if len(recommendations) > 1:
        output += "\n**Alternative Options:**\n"
        for alt in recommendations[1:3]:
            output += f"\n{alt['name']}: {' → '.join(alt['tools'])}\n"
            output += f"  Best for: {', '.join(alt['best_for'][:2])}\n"

    output += """\n**Skill References:**
- For automated binder design: see `bindcraft-workflow` skill
- For BoltzGen (universal MIT binder design, protein/peptide/small molecule/antibody/nanobody): see `boltzgen-binder-design` skill
- For BioEmu (conformational ensembles, cryptic pockets, dynamics without MD): see `bioemu-ensemble` skill
- For DiffDock (blind small-molecule docking, virtual screening): see `diffdock-ligand` skill
- For ProGen2 (autoregressive PLM generation + zero-shot fitness): see `progen2-sequence` skill
- For Boltz-2 (structure + binding affinity prediction): see `boltz2-validation` skill
- For BoltzDesign1 (invert Boltz-1 / AlphaFold3 for all-atom binders): see `boltzdesign1-binder` skill
- For HPC/cloud binder pipelines: see `nf-binder-design` skill
- For pocket redesign: see `pocketgen-ligand` skill
- For programmable / function-aware generation: see `esm3-generative` skill
- For joint seq+struct generation: see `protein-generator` skill
- For RFdiffusion3 (DNA/RNA/ligand/enzyme all-atom design): see `rfdiffusion3-workflow` skill
- For TopoDiff (topology-aware unconditional backbones, MIT license): see `topodiff-workflow` skill
- For PRO-LDM (fitness-guided sequence optimization): see `pro-ldm-workflow` skill
- For ProtComposer (3D ellipsoid layout control): see `protcomposer-workflow` skill
- For ProteinDT (text-guided protein design): see `proteindt-workflow` skill
- For DiMA (latent diffusion on pLM representations): see `dima-workflow` skill
- For FrameDiff (SE(3) diffusion backbone generation, MIT): see `framediff-backbone` skill
- For Protpardelle-1c (MIT all-atom seq+struct, motif scaffolding): see `protpardelle-allatom` skill
- For PiFold (fast MIT inverse folding): see `pifold-sequence-design` skill
- For FADiff (multi-motif scaffolding with floating anchors): see `fadiff-multimotif` skill
- For ligand design: see `rfdiffusion-all-atom` skill
- For RFAA validation (ligands/DNA/RNA/metals): see `rosettafold-all-atom` skill
- For fast validation: see `omegafold-validation` skill
- For Colab: see `colabdesign-workflow` skill
- For peptides: see `diffpepbuilder-design` skill
- For Chroma: see `chroma-backbone` skill
- For ensemble: see `esm-if1-design` skill (Stage 2 ensemble)
"""

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

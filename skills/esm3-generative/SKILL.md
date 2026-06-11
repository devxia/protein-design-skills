---
name: esm3-generative
description: Programmable protein generation with ESM3 — frontier generative model that jointly reasons across sequence, structure, and function tracks via prompts
---

# ESM3 Generative Workflow: Programmable Protein Design

## When to Trigger

- User says "ESM3", "EvolutionaryScale", "programmable protein generation"
- User wants to **generate proteins from functional descriptions** or **GO terms**
- User has **partial sequence, structure, or function** and wants ESM3 to fill in the rest
- User asks about **esmGFP**-style design or "simulate evolution with a language model"
- User wants **sequence + structure co-generation** from a text prompt
- User mentions "protein language model generation", "mask-filling", "track-based generation"

## What is ESM3?

[ESM3](https://github.com/evolutionaryscale/esm) is a **frontier generative model for biology** from EvolutionaryScale. Unlike structure-based diffusion models (RFdiffusion, Chroma) or sequence-only models (EvoDiff, ProteinMPNN), ESM3 jointly reasons across three biological properties as **discrete token tracks**:

1. **Sequence** — amino acid residues
2. **Structure** — 3D atomic coordinates (backbone + sidechains)
3. **Function** — Gene Ontology (GO) terms, InterPro domains, keywords

You can prompt ESM3 with **any combination of partial inputs** across these tracks, and it will generate the missing information.

### Key Differences from Other Tools

| Feature | RFdiffusion | EvoDiff | **ESM3** |
|---------|-------------|---------|----------|
| Input | Structure constraints | Sequence prompt | **Any mix of seq / struct / function** |
| Output | Backbone (poly-Gly) | Sequence | **Full sequence + structure + function** |
| Prompting | Contig / hotspots | Sequence | **Partial sequence + GO terms + structure** |
| Size | ~500M–1B | ~640M | **1.4B–98B parameters** |
| License | Academic | MIT | **Non-commercial (open)** / Commercial (API)** |

## System Requirements

- **OS**: Linux/macOS (Windows via WSL)
- **Python**: 3.9–3.11
- **GPU**: NVIDIA GPU strongly recommended (1.4B model runs on single consumer GPU; 7B/98B need multi-GPU or cloud)
- **Memory**: ~16GB VRAM for 1.4B model inference; ~80GB+ for 7B; ~600GB+ for 98B
- **License**: `esm3-sm-open-v1` is available for non-commercial research use

## Installation

```bash
# Install from GitHub
pip install esm@git+https://github.com/evolutionaryscale/esm.git@main

# Or install released package
pip install esm

# Login to HuggingFace to download weights
huggingface-cli login
# or in Python:
# from huggingface_hub import login; login()
```

## Quickstart: Local Inference

```python
from huggingface_hub import login
from esm.models.esm3 import ESM3
from esm.sdk.api import ESMProtein, GenerationConfig

login()
model = ESM3.from_pretrained("esm3_sm_open_v1").to("cuda")

# Prompt with a partial sequence (underscores = masked positions)
prompt = "DQATSLRILNNGHAFNVEFDDSQDKAVLKGGPLDGTYRLIQFHFHWGSLDGQGSEHTVDKKKYAAELHLVHWNTKYGDFGKAVQQPDGLAVLGIFLKVGSAKPGLQKVVDVLDSIKTKGKSADFTNFDPRGLLPESLDYWTYPGSLTTPP"
prompt = "_" * 50 + prompt + "_" * 50  # Mask N- and C-termini

protein = ESMProtein(sequence=prompt)

# Generate sequence for masked positions
protein = model.generate(
    protein,
    GenerationConfig(track="sequence", num_steps=8, temperature=0.7)
)

# Generate structure for the full sequence
protein = model.generate(
    protein,
    GenerationConfig(track="structure", num_steps=8)
)

# Save to PDB
protein.to_pdb("./generation.pdb")
print("Generated sequence:", protein.sequence)
```

## Core Concepts

### Tracks

ESM3 represents proteins as **three parallel tracks** of discrete tokens:

| Track | Representation | How to prompt |
|-------|---------------|---------------|
| **Sequence** | Amino acid tokens | String like `"MALWK..."`; use `_` for masked positions |
| **Structure** | 3D coordinates + confidence | Provide `ESMProtein(coordinates=...)` or generate from sequence |
| **Function** | GO terms / keywords / InterPro | Pass as functional annotations string or list |

### Generation Config

```python
from esm.sdk.api import GenerationConfig

# Generate only sequence
gen_seq = GenerationConfig(track="sequence", num_steps=8, temperature=0.7)

# Generate only structure from a fixed sequence
gen_struct = GenerationConfig(track="structure", num_steps=8)

# Generate function annotations
gen_func = GenerationConfig(track="function", num_steps=8, temperature=0.5)
```

| Parameter | Description |
|-----------|-------------|
| `track` | Which track to generate: `"sequence"`, `"structure"`, `"function"` |
| `num_steps` | Number of iterative unmasking steps (more = higher quality, slower) |
| `temperature` | Sampling temperature for sequence/function (lower = more deterministic) |

### Round-Trip Design (Inverse Folding + Refolding)

```python
# Start from partial sequence + structure constraints
protein = ESMProtein(sequence=prompt_partial, coordinates=some_coords)

# 1. Generate full sequence
protein = model.generate(protein, GenerationConfig(track="sequence", num_steps=8))

# 2. Generate structure from sequence
protein = model.generate(protein, GenerationConfig(track="structure", num_steps=8))

# 3. Inverse fold: forget sequence, keep structure
protein.sequence = None
protein = model.generate(protein, GenerationConfig(track="sequence", num_steps=8))

# 4. Refold: forget structure, keep new sequence
protein.coordinates = None
protein = model.generate(protein, GenerationConfig(track="structure", num_steps=8))
```

## Common Design Patterns

### Pattern 1: Generate from Function Description

```python
# Prompt with GO terms / keywords
protein = ESMProtein(
    function=["molecular function: ATP binding", "molecular function: kinase activity"]
)

# Generate sequence from function
protein = model.generate(protein, GenerationConfig(track="sequence", num_steps=16))

# Generate structure
protein = model.generate(protein, GenerationConfig(track="structure", num_steps=8))
protein.to_pdb("atp_binding_protein.pdb")
```

### Pattern 2: Redesign a Loop While Preserving Fold

```python
# Start from known structure, mask a loop region
sequence = "M" + "_" * 20 + "ALWK..."  # Mask residues 2-21
protein = ESMProtein(sequence=sequence)

# Generate sequence + structure for the masked region
protein = model.generate(protein, GenerationConfig(track="sequence", num_steps=8))
protein = model.generate(protein, GenerationConfig(track="structure", num_steps=8))
```

### Pattern 3: Scaffold-Guided Generation

```python
# Provide secondary structure or SASA constraints
# (requires ESM3's additional tracks: secondary_structure, sasa)
protein = ESMProtein(
    sequence="_" * 150,  # Fully masked sequence
    secondary_structure="HHHHHHHHH________EEEEEEEEEE...",  # H=helix, E=sheet, _=loop
)

protein = model.generate(protein, GenerationConfig(track="sequence", num_steps=16))
protein = model.generate(protein, GenerationConfig(track="structure", num_steps=8))
```

### Pattern 4: De Novo Protein from Keywords

```python
# Design a fluorescent protein-like sequence
protein = ESMProtein(
    function=["green fluorescent protein", "chromophore formation"]
)

# Longer generation for de novo design
protein = model.generate(protein, GenerationConfig(track="sequence", num_steps=32, temperature=0.8))
protein = model.generate(protein, GenerationConfig(track="structure", num_steps=16))
protein.to_pdb("novel_gfp.pdb")
```

## Pipeline Integration

### Option 1: ESM3 as Standalone Generator
```
Prompt (seq / struct / function)
    ↓
ESM3.generate() → sequence + structure
    ↓
Optional: AlphaFold3 / Boltz-1 validation
    ↓
Filtering / experimental validation
```

### Option 2: ESM3 + Structure Diffusion Ensemble
```
ESM3 (generate diverse sequence ideas from function)
    ↓
RFdiffusion / Chroma (generate backbones for selected sequences)
    ↓
ProteinMPNN (refine sequences)
    ↓
AlphaFold3 / Boltz-1 (validate)
    ↓
Filtering
```

### Option 3: ESM3 for Functional Annotation of Designs
```
Generated design from standard pipeline
    ↓
ESM3 predicts function track
    ↓
Check if predicted GO terms match target function
    ↓
Use as additional filter criterion
```

## Output Format

ESM3 returns an `ESMProtein` object containing:

```python
protein.sequence    # str: generated amino acid sequence
protein.coordinates # torch.Tensor or np.ndarray: [L, 37, 3] atom coordinates
protein.function    # list: predicted function annotations
protein.to_pdb("output.pdb")  # Save structure
```

**Output files:**
- `*.pdb` — Full-atom structure (backbone + predicted side chains)
- Sequence string — Can be saved to FASTA for downstream tools

## Interpreting Results

### Quality Metrics

| Metric | Source | Good Value |
|--------|--------|------------|
| **pLDDT** | From structure track confidence | >80 |
| **pTM** | From structure track | >0.7 |
| **Perplexity** | From sequence generation | Lower is better |
| **Function confidence** | From function track logits | Higher is better |

### Validation Strategy

ESM3's structure track is **generative**, not a dedicated structure predictor. For critical designs:

1. Run ESM3 to generate candidate sequence + structure
2. **Validate with AlphaFold3 / Boltz-1 / Chai-1** for independent structure prediction
3. Compare ESM3-generated structure vs. AF3-predicted structure (RMSD)
4. Check pLDDT, pTM, ipTM from validator

## Comparison with Other Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| *De novo* backbone generation | RFdiffusion | Specialized for physical backbones |
| Sequence from function | **ESM3** | Only tool with function track |
| Pocket redesign | PocketGen | Ligand-aware pocket co-design |
| Automated binder design | BindCraft | Highest experimental success reported |
| Sequence on fixed backbone | ProteinMPNN | Fast and experimentally validated |
| All-atom generation from text | Chroma | Natural language + joint seq/struct |
| Programmable biology | **ESM3** | Multi-track prompting, function-aware |

## Tips for Best Results

1. **Start with the open 1.4B model** (`esm3_sm_open_v1`) for exploration; scale to larger models only when needed
2. **Use masks (`_`) strategically** — mask the regions you want redesigned, keep known regions fixed
3. **Iterate generation** — ESM3 is autoregressive/masked; longer `num_steps` generally improves quality
4. **Round-trip design** improves consistency: seq → struct → seq (inverse fold) → struct (refold)
5. **Validate with structure predictors** — ESM3 structure track is generative; AF3/Boltz-1 provide independent validation
6. **Function prompts work best with known GO terms** — be specific (e.g., "ATP binding" vs. "binds ATP")
7. **For de novo designs**, generate many candidates and filter by pLDDT / diversity

## Hardware & Scaling Notes

| Model | Parameters | VRAM | Best For |
|-------|------------|------|----------|
| `esm3_sm_open_v1` | 1.4B | ~16GB | Research, prototyping |
| `esm3-medium-2024-08` | 7B | ~80GB | Higher quality generation |
| `esm3-large-*` | 98B | ~600GB+ | Frontier quality (cloud/API) |

For models larger than 1.4B, use the [EvolutionaryScale API / AWS SageMaker / NVIDIA BioNemo](https://www.evolutionaryscale.ai/).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| CUDA OOM on 1.4B | Reduce batch size / sequence length; use `cpu` |
| HuggingFace download fails | Run `huggingface-cli login` and accept model license |
| Generated structure looks unfolded | Increase `num_steps`; validate with AlphaFold3 |
| Function track is uninformative | Use more specific GO terms; increase temperature |
| Sequence has repeated motifs | Lower temperature; add structure constraints |

## References

- [EvolutionaryScale ESM GitHub](https://github.com/evolutionaryscale/esm)
- [ESM3 Paper: "Simulating 500 million years of evolution with a language model"](https://www.biorxiv.org/content/10.1101/2024.07.01.600583) — Hayes et al., bioRxiv 2024
- [EvolutionaryScale](https://www.evolutionaryscale.ai/)
- [esmGFP Paper: "Simulating 500 million years of evolution with a language model"](https://www.biorxiv.org/content/10.1101/2024.07.01.600583) — Novel green fluorescent protein design
- [Cogibra/esm3 Examples](https://github.com/Cogibra/esm3) — Practical notebooks (`generate.ipynb`, `gfp_design.ipynb`)

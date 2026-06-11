---
name: protcomposer-workflow
description: Guide for using ProtComposer to generate protein structures from customizable 3D ellipsoid layouts via flow matching
---

# ProtComposer Workflow Guide

**ProtComposer** is a flow-matching generative model for **compositional protein structure generation** from **3D ellipsoids**, presented at **ICLR 2025 (Oral)**. It is developed by NVIDIA and MIT.

Use ProtComposer when you want:
- Explicit spatial control over protein substructures via 3D ellipsoids
- To design proteins by composing semantic substructure layouts
- To redesign connectivity between existing protein domains
- A flow-matching Stage 1 alternative with geometric conditioning

---

## What Makes ProtComposer Different

| Feature | RFdiffusion | TopoDiff | ProtComposer |
|---------|-------------|----------|--------------|
| Conditioning | Contig strings / motifs | Length only | **3D ellipsoid layouts** |
| Generative model | Diffusion | Diffusion | **Flow matching** |
| Control level | Backbone scaffolds | Unconditional | **Substructure shape, location, SS** |
| Built on | SE(3) transformers | Custom VAE + diffusion | **MultiFlow** |
| License | BSD / various | MIT | **Research / non-commercial** |

ProtComposer is unique because you can **draw or statistically sample 3D ellipsoids** that represent desired substructures, and the model generates a full protein backbone that realizes that layout.

---

## Installation (Document-Only — Do Not Install)

```bash
# Clone repository
git clone https://github.com/NVlabs/protcomposer.git
cd protcomposer

# Create environment
conda create -n protcomposer python=3.9
conda activate protcomposer

# Core dependencies
pip install jupyterlab
pip install numpy==1.21.2 pandas==1.5.3
pip install torch==1.12.1+cu113 -f https://download.pytorch.org/whl/torch_stable.html
pip install biopython==1.79 dm-tree==0.1.6 modelcif==0.7 ml-collections==0.1.0 scipy==1.7.1 absl-py einops
pip install pytorch_lightning==2.0.4 fair-esm
pip install 'openfold @ git+https://github.com/aqlaboratory/openfold.git@5484c38'
pip install matplotlib==3.7.2
pip install pydssp biotite omegaconf wandb
pip install numpy==1.21.2  # reinstall to avoid contourpy issues
pip install torch-scatter -f https://data.pyg.org/whl/torch-1.12.1+cu113
pip3 install -U scikit-learn
pip install gpustat
```

### Model weights

Two pretrained checkpoints are provided in `model_weights/`:

```bash
model_weights/trained_on_afdb.ckpt    # Trained on AlphaFold Database
model_weights/trained_on_pdb.ckpt     # Trained on Protein Data Bank
```

**Sources:**
- [GitHub repository](https://github.com/NVlabs/protcomposer)
- [ICLR 2025 paper](https://openreview.net/forum?id=0ctvBgKFgc)
- [arXiv preprint](https://arxiv.org/abs/2503.05025)
- [MultiFlow codebase](https://github.com/jasonkyuyim/multiflow) (foundation

---

## Quickstart

### Generate from statistical ellipsoids

```bash
python sample.py \
  --guidance 1.0 \
  --num_prots 6 \
  --nu 5 \
  --sigma 6 \
  --helix_frac 0.4 \
  --num_blobs 9 \
  --seed 1 \
  --outdir outputs/protcomposer \
  --ckpt "model_weights/trained_on_pdb.ckpt"
```

**Key flags:**

| Flag | Meaning |
|------|---------|
| `--guidance` | Guidance scale for layout adherence |
| `--num_prots` | Number of proteins to generate |
| `--nu` | Ellipsoid distribution parameter |
| `--sigma` | Ellipsoid spread parameter |
| `--helix_frac` | Target helix fraction |
| `--num_blobs` | Number of ellipsoid substructures |
| `--seed` | Random seed |
| `--outdir` | Output directory |
| `--ckpt` | Checkpoint path |

### Evaluate outputs

```bash
# Designability (can sequences be designed for these backbones?)
python -m scripts.evaluate_designability --dir outputs/protcomposer

# Ellipsoid adherence (how well do outputs match the specified layout?)
python -m scripts.evaluate_alignment --dir outputs/protcomposer
```

---

## Three Ways to Specify Ellipsoids

### 1. Statistical model (easiest)
Use the built-in ellipsoid sampler as shown in `sample.py`:

```bash
python sample.py --num_blobs 9 --helix_frac 0.4 ...
```

The model samples a layout and then generates proteins conditioned on it. Useful for unconditional generation with layout control.

### 2. Hand-designed ellipsoids
Specify ellipsoid parameters directly in code: center position, radii, orientation, and semantic label (e.g., helix, sheet, loop). This gives maximum user control but requires understanding the ellipsoid parameterization.

### 3. Extract from existing proteins
Use existing PDB structures to extract ellipsoid representations, then modify connectivity or substructure properties to create edited designs.

---

## Output Format

Generated structures are saved in the output directory as PDB files. Each output corresponds to one sampled protein realization of the ellipsoid layout. The outputs are backbone-only and require Stage 2 sequence design.

---

## Pipeline Integration

ProtComposer can replace **Stage 1** when you need explicit layout control.

| Stage | Tool | Purpose |
|-------|------|---------|
| 0 | PDBFixer (if editing existing structure) | Fix input |
| 1 | **ProtComposer** | Generate backbone from ellipsoid layout |
| 2 | ProteinMPNN / LigandMPNN | Design sequences |
| 3 | AlphaFold3 / Boltz-1 / RFAA | Validate structures |
| 4 | Filtering | Rank by quality |

**Recommended pairings:**
- Layout-controlled design → ProtComposer → ProteinMPNN → AlphaFold3
- Commercial validation → ProtComposer → ProteinMPNN → Boltz-1 / Chai-1

---

## When to Use ProtComposer vs Other Stage 1 Tools

| Your Goal | Best Tool |
|-----------|-----------|
| General backbone generation | RFdiffusion |
| Unconditional diverse backbones | TopoDiff |
| All-atom biomolecular interactions | RFdiffusion3 |
| Natural language design | Chroma |
| **Explicit 3D layout control** | **ProtComposer** |
| Joint seq+structure generation | ProteinGenerator / La-Proteina |
| MIT license required | TopoDiff |
| Commercial use | Avoid ProtComposer (NVIDIA research license) |

---

## Strengths and Limitations

**Strengths:**
- Unique ellipsoid-based conditioning
- Flow matching enables efficient sampling
- Can generate from hand-drawn or statistical layouts
- Strong ICLR 2025 Oral recognition
- Builds on solid MultiFlow foundation

**Limitations:**
- **Research / non-commercial license only** — not suitable for commercial projects
- Complex installation with pinned older dependencies
- Requires understanding of ellipsoid parameterization for manual layouts
- Training requires 8 GPUs and MultiFlow dataset
- Smaller community than RFdiffusion

---

## Citation

Stärk et al., "ProtComposer: Compositional Protein Structure Generation with 3D Ellipsoids," *ICLR*, 2025.

```bibtex
@inproceedings{stark2025protcomposer,
  title={ProtComposer: Compositional Protein Structure Generation with 3D Ellipsoids},
  author={Stärk, Hannes and Jing, Bowen and Geffner, Tomas and Yim, Jason and Jaakkola, Tommi and Vahdat, Arash and Kreis, Karsten},
  booktitle={The Thirteenth International Conference on Learning Representations (ICLR)},
  year={2025},
  url={https://openreview.net/forum?id=0ctvBgKFgc}
}
```

---

## See Also

- `structure-generation` — Classic RFdiffusion backbone generation
- `rfdiffusion3-workflow` — All-atom biomolecular interaction design
- `topodiff-workflow` — Topology-aware unconditional backbone generation
- `chroma-backbone` — Natural language programmable generation
- `protein-generator` — Joint sequence + structure diffusion
- `sequence-design` — Stage 2 with ProteinMPNN
- `pipeline-selection` — Choose the right workflow

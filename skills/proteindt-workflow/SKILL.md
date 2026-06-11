---
name: proteindt-workflow
description: Guide for using ProteinDT for text-guided protein design, generation, and editing via protein-language alignment
---

# ProteinDT Workflow Guide

**ProteinDT** is a **text-guided protein design framework** published in *Nature Machine Intelligence* (2025). It aligns protein sequences and natural language descriptions via contrastive learning (ProteinCLAP), then generates or edits proteins from text prompts.

Use ProteinDT when you want:
- **Text-to-protein generation** from a functional description
- **Zero-shot text-guided editing** of existing proteins (stability, structure, binding)
- A language-driven alternative to structure-conditioned tools like RFdiffusion or ESM3
- MIT-licensed text-guided protein design

---

## What Makes ProteinDT Different

| Feature | ESM3 | Chroma | ProteinDT |
|---------|------|--------|-----------|
| Conditioning | Multi-track (seq/struct/function) | Natural language + structure | **Natural text only** |
| Generation type | Sequence + structure tokens | Structure + sequence | **Sequence from text** |
| Editing | Prompted completion | Limited | **Zero-shot text-guided editing** |
| Alignment | ESM-3 pretraining | Proprietary | **ProteinCLAP (contrastive)** |
| License | Non-commercial (open) | Various | **MIT** |

ProteinDT is the most direct "type a description, get a protein" tool in the workflow map. Unlike ESM3, which uses specialized tracks, ProteinDT is built on standard protein-language alignment and works with UniProt-style text.

---

## Installation (Document-Only — Do Not Install)

```bash
# Clone repository
git clone https://github.com/chao1224/ProteinDT.git
cd ProteinDT

# Create environment
conda create -n ProteinDT python=3.7
conda activate ProteinDT

# Core dependencies
conda install -y numpy networkx scikit-learn
pip install torch==1.10.*
pip install transformers lxml

# TAPE benchmarks
pip install lmdb seqeval

# Protein structure / folding tools
pip install "fair-esm[esmfold]"
pip install dm-tree omegaconf ml-collections einops
pip install fair-esm[esmfold]==2.0.0 --no-dependencies
pip install 'dllogger @ git+https://github.com/NVIDIA/dllogger.git'
pip install 'openfold @ git+https://github.com/aqlaboratory/openfold.git@4b41059694619831a7db195b7e0988fc4ff3a307'
conda install -c conda-forge -yq mdtraj

# Graph tools (for binding editing)
pip install h5py
pip install torch_geometric==2.0 torch_scatter torch_sparse torch_cluster
pip install biopython

# Visualization and API tools
pip install matplotlib openai==0.28.0 accelerate

# Install ProteinDT package
pip install .
```

### Download data and checkpoints

ProteinDT provides datasets and pretrained checkpoints on HuggingFace:

```python
from huggingface_hub import snapshot_download

# Download datasets
snapshot_download(
    repo_id="chao1224/ProteinDT",
    repo_type="dataset",
    cache_dir='./data'
)

# Download model checkpoints
snapshot_download(
    repo_id="chao1224/ProteinDT",
    repo_type="model",
    cache_dir='./checkpoints'
)
```

Expected data layout:

```
./data/
└── SwissProtCLAP
    ├── protein_sequence.txt
    └── text_sequence.txt
```

**Sources:**
- [GitHub repository](https://github.com/chao1224/ProteinDT)
- [Nature Machine Intelligence paper](https://www.nature.com/articles/s42256-025-01011-z)
- [arXiv preprint](https://arxiv.org/abs/2302.04611)
- [Project page](https://chao1224.github.io/ProteinDT)
- [HuggingFace datasets and checkpoints](https://huggingface.co/chao1224/ProteinDT)

---

## Quickstart: Text-to-Protein Generation

### Option A: Use pretrained checkpoints (recommended)

Download the pretrained ProteinDT checkpoints from HuggingFace, then run inference directly.

```bash
export OUTPUT_DIR=./output/ProteinDT/hyper_01

# 1. Prepare text prompts
cd examples/downstream_Text2Protein
python step_01_text_retrieval.py

# 2. Generate protein sequences from text
python step_02_inference_ProteinDT.py \
  --decoder_distribution=T5Decoder \
  --score_network_type=T5Base \
  --num_workers=0 \
  --hidden_dim=16 \
  --batch_size=8 \
  --pretrained_folder="$OUTPUT_DIR" \
  --step_04_folder="$OUTPUT_DIR"/step_04_T5 \
  --num_repeat=16 \
  --use_facilitator \
  --AR_generation_mode=01 \
  --output_text_file_path="$OUTPUT_DIR"/step_04_T5/downstream_Text2Protein/step_02_inference.txt
```

**Key flags:**

| Flag | Meaning |
|------|---------|
| `--decoder_distribution` | `T5Decoder` or `MultinomialDiffusion` |
| `--score_network_type` | `T5Base`, `RNN`, or `BertBase` |
| `--num_repeat` | Number of sequences to generate per prompt |
| `--use_facilitator` | Use the trained text→latent facilitator |
| `--AR_generation_mode` | Autoregressive decoding strategy |

### Option B: Train from scratch

ProteinDT pretraining has 5 steps. Only do this if you have GPUs and want to adapt the model.

```bash
export OUTPUT_DIR=../output/ProteinDT/hyper_01

# Step 1: CLAP pretraining
python pretrain_step_01_CLAP.py \
  --protein_lr=1e-5 --protein_lr_scale=1 \
  --text_lr=1e-5 --text_lr_scale=1 \
  --protein_backbone_model=ProtBERT_BFD \
  --epochs=10 --batch_size=9 --num_workers=0 \
  --output_model_dir="$OUTPUT_DIR"

# Step 2: Frozen representations
python pretrain_step_02_empty_sequence.py \
  --protein_backbone_model=ProtBERT_BFD \
  --batch_size=16 --num_workers=0 \
  --pretrained_folder="$OUTPUT_DIR"

python pretrain_step_02_pairwise_representation.py \
  --protein_backbone_model=ProtBERT_BFD \
  --batch_size=16 --num_workers=0 \
  --pretrained_folder="$OUTPUT_DIR"

# Step 3: Facilitator (text → latent)
python pretrain_step_03_facilitator.py \
  --protein_lr=1e-5 --protein_lr_scale=1 \
  --text_lr=1e-5 --text_lr_scale=1 \
  --protein_backbone_model=ProtBERT_BFD \
  --epochs=10 --batch_size=9 --num_workers=0 \
  --pretrained_folder="$OUTPUT_DIR" \
  --output_model_folder="$OUTPUT_DIR"/step_03_Gaussian_10

# Step 4: Decoder (choose one)
python pretrain_step_04_decoder.py \
  --num_workers=0 --lr=1e-4 --epochs=50 \
  --decoder_distribution=T5Decoder --score_network_type=T5Base \
  --hidden_dim=16 \
  --pretrained_folder="$OUTPUT_DIR" \
  --output_folder="$OUTPUT_DIR"/step_04_T5

# Step 5: Auto-encoder for editing
python pretrain_step_05_AE.py \
  --num_workers=0 --lr=1e-4 --epochs=50 \
  --pretrained_folder="$OUTPUT_DIR" \
  --output_folder="$OUTPUT_DIR"/step_05
```

---

## Zero-Shot Text-Guided Protein Editing

ProteinDT can edit existing proteins toward a text-specified property without retraining.

### Structure / stability editing (latent optimization)

```bash
cd examples/downstream_Editing

python step_01_editing_latent_optimization.py \
  --num_workers=0 --batch_size=8 \
  --lambda_value=0.9 --num_repeat=16 --oracle_mode=text --temperature=2 \
  --editing_task=alpha --text_prompt_id=101 \
  --pretrained_folder="$OUTPUT_DIR" \
  --step_05_folder="$OUTPUT_DIR"/step_05_AE \
  --output_folder="$OUTPUT_DIR"/step_05_AE/downstream_Editing_latent_optimization/alpha_prompt_101 \
  --output_text_file_path="$OUTPUT_DIR"/step_05_AE/downstream_Editing_latent_optimization/alpha_prompt_101/step_01_editing.txt

# Evaluate edited structures
python step_01_evaluate_structure.py \
  --num_workers=0 --batch_size=8 --editing_task=alpha --text_prompt_id=101 \
  --output_folder="$OUTPUT_DIR"/step_05_AE/downstream_Editing_latent_optimization/alpha_prompt_101 \
  --output_text_file_path="$OUTPUT_DIR"/step_05_AE/downstream_Editing_latent_optimization/alpha_prompt_101/step_01_editing.txt
```

**Editing tasks:** `alpha`, `beta`, `Villin`, `Pin1`, `peptide_binding`

### Text-guided interpolation

```bash
python step_01_editing_latent_interpolation.py \
  --editing_task=alpha --text_prompt_id=101 \
  --decoder_distribution=T5Decoder --score_network_type=T5Base \
  --num_workers=0 --hidden_dim=16 --batch_size=2 \
  --theta=0.9 --num_repeat=16 --oracle_mode=text \
  --AR_generation_mode=01 --AR_condition_mode=expanded \
  --pretrained_folder="$OUTPUT_DIR" \
  --step_04_folder="$OUTPUT_DIR"/step_04_T5 \
  --output_folder=... \
  --output_text_file_path=.../step_01_editing.txt
```

---

## Protein Property Prediction (TAPE)

Use ProteinDT embeddings for downstream TAPE benchmarks:

```bash
python downstream_TAPE.py \
  --task_name=ss3 \
  --seed=3 \
  --learning_rate=3e-5 \
  --num_train_epochs=5 \
  --per_device_train_batch_size=2 \
  --gradient_accumulation_steps=8 \
  --warmup_ratio=0.08 \
  --pretrained_model=ProteinDT \
  --pretrained_folder="$OUTPUT_DIR" \
  --output_dir="$OUTPUT_DIR"/downstream_TAPE
```

Supported TAPE tasks: `ss3`, `ss8`, `remote_homology`, `fluorescence`, `stability`

---

## Pipeline Integration

ProteinDT can serve as a **Stage 1.5 / Stage 2** tool — it generates sequences from text, which then need structure prediction and filtering.

### Text → sequence → structure pipeline

| Stage | Tool | Purpose |
|-------|------|---------|
| 1.5 | **ProteinDT** | Generate sequence(s) from text prompt |
| 2 | *(optional)* ProteinMPNN | Re-design sequence if structure becomes available |
| 3 | ESMFold / OmegaFold / AlphaFold3 | Predict structure for generated sequences |
| 4 | Filtering | Rank by confidence and text relevance |

### Recommended pairings

- Quick text-to-structure screen → ProteinDT → ESMFold
- High-accuracy text-driven design → ProteinDT → AlphaFold3
- Commercial project → ProteinDT → Boltz-1 / Chai-1

---

## When to Use ProteinDT vs Other Text/NLP Tools

| Your Goal | Best Tool |
|-----------|-----------|
| Generate from GO terms / function keywords | ESM3 |
| Natural language + all-atom structure | Chroma |
| **Text → protein sequence only** | **ProteinDT** |
| Text-guided editing of existing proteins | **ProteinDT** |
| Text + structure joint generation | ProteinGenerator |
| MIT license required | **ProteinDT** |

---

## Writing Good Text Prompts

ProteinDT is trained on **UniProt free-text fields**, not imperative design instructions. For best results, write prompts in UniProt style:

**Good prompts:**
- `"Catalyzes the conversion of ATP to cAMP. Requires Mg(2+).`"
- `"DNA-binding protein that regulates transcription.`"
- `"Subunit of the 20S proteasome. Involved in protein degradation.`"

**Less effective prompts:**
- `"Design a protein that glows green.`" (too abstract)
- `"Make a binder for PD-L1.`" (needs structure context)

If your task is binder design or requires precise structural control, use RFdiffusion / BindCraft / RFdiffusion3 instead.

---

## Strengths and Limitations

**Strengths:**
- MIT license
- Direct text-to-sequence generation
- Zero-shot text-guided editing without retraining
- Strong protein-language alignment via ProteinCLAP
- Pretrained checkpoints available on HuggingFace

**Limitations:**
- Generates **sequences**, not structures directly (requires Stage 3 validation)
- Prompts work best in UniProt style, not free-form natural language
- Training from scratch is complex (5 steps, GPUs required)
- Less precise than structure-conditioned tools for scaffold/binder tasks

---

## Citation

Liu et al., "A Text-guided Protein Design Framework," *Nature Machine Intelligence*, 2025.

```bibtex
@article{liu2023text,
  title={A Text-guided Protein Design Framework},
  author={Liu, Shengchao and Li, Yanjing and Li, Zhuoxinran and Gitter, Anthony and Zhu, Yutao and Lu, Jiarui and Xu, Zhao and Nie, Weili and Ramanathan, Arvind and Xiao, Chaowei and Tang, Jian and Guo, Hongyu and Anandkumar, Anima},
  journal={arXiv preprint arXiv:2302.04611},
  year={2023}
}
```

---

## See Also

- `esm3-generative` — Multi-track programmable generation (GO terms / function)
- `chroma-backbone` — Natural language + all-atom structure generation
- `protein-generator` — Joint sequence + structure diffusion
- `sequence-design` — Structure-conditioned sequence design with ProteinMPNN
- `fast-screening` — Rapid validation with ESMFold / OmegaFold
- `pipeline-selection` — Choose the right workflow

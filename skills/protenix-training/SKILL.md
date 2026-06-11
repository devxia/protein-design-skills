---
name: protenix-training
description: Fine-tuning and training Protenix models — the only open-source AlphaFold3 reproduction with full training support
---

# Protenix Training & Fine-Tuning

## When to Use This Skill

- You want to **fine-tune** Protenix on your own protein structure data
- You need to **train from scratch** on a custom dataset
- You want to **adapt** Protenix for a specific protein family or domain
- You need **multi-GPU distributed training** setup
- You want to **evaluate** a trained model with PXMeter
- You need to **prepare training data** from existing structures

**Prerequisite:** Protenix must be installed. Read `protenix-validation` skill for installation.

## Training vs Inference

| Aspect | Inference | Training |
|--------|-----------|----------|
| Entry point | `protenix.predict` | `protenix.train` |
| Data needed | Sequences only | Structures + sequences |
| GPU memory | 16GB+ | 40GB+ (A100 recommended) |
| Time | Minutes to hours | Days to weeks |
| Output | Predicted structures | Trained model weights |

## Data Preparation

### Step 1: Collect Structures

Protenix training requires 3D structures. Sources:
- **PDB** (Protein Data Bank) — ~200K structures
- **AlphaFold DB** — ~200M predicted structures
- **Custom experimental data** — Cryo-EM, X-ray, NMR

### Step 2: Convert to Protenix Format

```python
from protenix.data import StructureDataset

# Convert PDB files to Protenix training format
dataset = StructureDataset.from_pdb_dir(
    pdb_dir="/path/to/pdbs/",
    output_dir="/path/to/training_data/",
    min_resolution=3.5,      # Filter by resolution (Angstrom)
    max_length=2048,         # Max sequence length
    include_ligands=True,    # Include small molecules
    include_nucleic=True,    # Include DNA/RNA
)

# Or from mmCIF files
dataset = StructureDataset.from_mmcif_dir(
    mmcif_dir="/path/to/mmcif/",
    output_dir="/path/to/training_data/",
)
```

### Step 3: Split Train/Validation/Test

```python
from protenix.data import split_dataset

split_dataset(
    data_dir="/path/to/training_data/",
    train_ratio=0.9,
    val_ratio=0.05,
    test_ratio=0.05,
    seed=42,
)
```

## Training Configuration

### Basic Fine-Tuning

```python
from protenix import ProtenixTrainer

trainer = ProtenixTrainer(
    # Model
    model_name="protenix-v2",           # Base model to fine-tune
    checkpoint_path=None,               # Resume from checkpoint (optional)
    
    # Data
    train_data="/path/to/training_data/train/",
    val_data="/path/to/training_data/val/",
    
    # Training hyperparameters
    learning_rate=1e-4,
    batch_size=1,                       # Per-device batch size
    gradient_accumulation_steps=4,      # Effective batch = 4
    max_epochs=10,
    warmup_steps=1000,
    
    # Optimizer
    optimizer="adamw",
    weight_decay=0.01,
    beta1=0.9,
    beta2=0.999,
    
    # Hardware
    precision="bf16",                   # bf16 or fp16 or fp32
    num_gpus=1,                         # Will use all available if None
)

# Start training
trainer.train()

# Save checkpoint
trainer.save_checkpoint("/path/to/checkpoints/protenix_finetuned.pt")
```

### Multi-GPU Distributed Training

```bash
# Using torchrun for distributed training
torchrun \
    --nnodes=1 \
    --nproc_per_node=8 \
    --master_port=29500 \
    -m protenix.train \
    --config train_config.yaml
```

**train_config.yaml:**
```yaml
model:
  name: protenix-v2
  checkpoint: null

data:
  train: /path/to/training_data/train/
  val: /path/to/training_data/val/
  batch_size: 1
  num_workers: 4

training:
  learning_rate: 1e-4
  max_epochs: 10
  warmup_steps: 1000
  gradient_accumulation_steps: 4
  
optimizer:
  name: adamw
  weight_decay: 0.01
  
hardware:
  precision: bf16
  num_gpus: 8
```

### Training from Scratch

```python
from protenix import ProtenixTrainer

trainer = ProtenixTrainer(
    model_name="protenix",              # Base architecture (no pretrained weights)
    train_data="/path/to/training_data/train/",
    val_data="/path/to/training_data/val/",
    learning_rate=1e-3,                 # Higher LR for from-scratch
    batch_size=1,
    gradient_accumulation_steps=8,
    max_epochs=100,                     # Much longer for from-scratch
    warmup_steps=10000,
)

trainer.train()
```

**Note:** Training from scratch requires massive compute (weeks on 8x A100) and is only recommended for research purposes.

## Fine-Tuning Strategies

### Strategy 1: Full Model Fine-Tuning

Fine-tune all model parameters. Best for large datasets (>10K structures).

```python
trainer = ProtenixTrainer(
    model_name="protenix-v2",
    train_data="...",
    val_data="...",
    learning_rate=1e-4,
    freeze_layers=None,                 # None = train all layers
)
```

### Strategy 2: Layer-wise Fine-Tuning

Freeze early layers, fine-tune later layers. Good for small datasets.

```python
trainer = ProtenixTrainer(
    model_name="protenix-v2",
    train_data="...",
    val_data="...",
    learning_rate=1e-4,
    freeze_layers=24,                   # Freeze first 24 layers
)
```

### Strategy 3: LoRA (Low-Rank Adaptation)

Add small trainable adapters instead of fine-tuning all parameters. Most efficient.

```python
trainer = ProtenixTrainer(
    model_name="protenix-v2",
    train_data="...",
    val_data="...",
    learning_rate=1e-3,
    use_lora=True,
    lora_rank=16,                       # Rank of LoRA matrices
    lora_alpha=32,                      # Scaling factor
    lora_dropout=0.1,
)
```

**Benefits of LoRA:**
- 99% fewer trainable parameters
- Faster training
- Smaller checkpoint files
- Less overfitting on small datasets

## Domain-Specific Fine-Tuning

### Antibody Fine-Tuning

```python
# Collect antibody-antigen complexes from SAbDab
# https://opig.stats.ox.ac.uk/webapps/newsabdab/sabdab/

trainer = ProtenixTrainer(
    model_name="protenix-v2",           # v2 has better antibody performance
    train_data="/path/to/antibody_data/train/",
    val_data="/path/to/antibody_data/val/",
    learning_rate=5e-5,                 # Lower LR for specialized domains
    max_epochs=20,
    use_lora=True,
    lora_rank=32,
)
```

### Membrane Protein Fine-Tuning

```python
trainer = ProtenixTrainer(
    model_name="protenix-v2",
    train_data="/path/to/membrane_data/train/",
    val_data="/path/to/membrane_data/val/",
    learning_rate=5e-5,
    max_epochs=15,
)
```

## Evaluation with PXMeter

After training, evaluate your model:

```python
from protenix import ProtenixModel
from pxmeter import PXMeter

# Load fine-tuned model
model = ProtenixModel.from_checkpoint("/path/to/checkpoints/protenix_finetuned.pt")

# Run evaluation
evaluator = PXMeter(
    model=model,
    test_data="/path/to/training_data/test/",
    metrics=["rmsd", "tm_score", "gdt_ts", "lddt"],
)

results = evaluator.evaluate()
print(f"Mean RMSD: {results['rmsd']:.2f} Å")
print(f"Mean TM-score: {results['tm_score']:.3f}")
```

## Training Monitoring

### TensorBoard

```python
trainer = ProtenixTrainer(
    ...,
    log_dir="/path/to/logs/",
    log_every_n_steps=100,
)
```

View logs:
```bash
tensorboard --logdir /path/to/logs/
```

### Key Metrics to Monitor

| Metric | Target | Action if Poor |
|--------|--------|---------------|
| Training loss | Decreasing | Check learning rate, data quality |
| Validation loss | Decreasing | Check overfitting |
| RMSD | <2 Å | Model is learning structure |
| TM-score | >0.8 | Model predictions are accurate |
| GDT-TS | >0.7 | Topology is correct |

## Tips

1. **Start with fine-tuning**, not from scratch. Pretrained weights contain important structural knowledge.
2. **Use LoRA** for small datasets (<1K structures). Use full fine-tuning for large datasets.
3. **Lower learning rate** (5e-5) for domain-specific fine-tuning vs general fine-tuning (1e-4).
4. **Monitor validation loss** closely. Stop if it starts increasing (overfitting).
5. **Use bf16 precision** for faster training with minimal accuracy loss.
6. **Gradient accumulation** simulates larger batch sizes when GPU memory is limited.
7. **Data quality matters more than quantity**. Clean, high-resolution structures train better than noisy large datasets.
8. **Include diverse structures** in training data. Don't just train on one protein family.

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Out of memory | Batch size too large | Reduce batch_size or use gradient accumulation |
| NaN loss | Learning rate too high | Reduce learning rate, add gradient clipping |
| Overfitting | Dataset too small | Use LoRA, add dropout, collect more data |
| Slow training | I/O bottleneck | Increase num_workers, use SSD for data |
| Poor validation | Data distribution mismatch | Ensure train/val/test splits are representative |

## Pipeline Integration

### Train → Validate → Use in Design Pipeline

```
Step 1: Prepare training data (PDB/mmCIF → Protenix format)
Step 2: Fine-tune Protenix on your data
Step 3: Evaluate with PXMeter
Step 4: Use fine-tuned model in design pipeline

Stage 1: RFdiffusion → Stage 2: ProteinMPNN
                              ↓
                  YOUR fine-tuned Protenix (validation)
                              ↓
                         Filtering
```

### Using Fine-Tuned Model for Validation

```python
from protenix import ProtenixModel

# Load your fine-tuned model instead of pretrained
model = ProtenixModel.from_checkpoint("/path/to/checkpoints/protenix_finetuned.pt")

# Use in validation pipeline
result = model.predict(sequences=[...])
```

## Hardware Requirements

| Configuration | GPUs | Memory per GPU | Time (fine-tune 10 epochs) |
|--------------|------|---------------|---------------------------|
| Minimum | 1x A100 | 40GB | ~3 days |
| Recommended | 4x A100 | 40GB | ~18 hours |
| Optimal | 8x A100 | 80GB | ~9 hours |

## References

- [Protenix GitHub](https://github.com/bytedance/Protenix)
- [Protenix Training Docs](https://github.com/bytedance/Protenix/tree/main/docs/training)
- [PXMeter GitHub](https://github.com/ByteDance/PXMeter)
- See `protenix-validation` skill for inference usage
- See `cross-validation` skill for comparing your trained model with other validators

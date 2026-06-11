---
name: protenix-validation
description: Biomolecular structure prediction with Protenix — ByteDance's open-source AlphaFold3 reproduction, first to outperform AF3 on benchmarks
---

# Alternative Stage 3: Protenix Structure Validation

> **Quick Entry**: Stage 3 alternative | training + inference scaling | Apache 2.0
>
> **Upstream**: `sequence-design` (ProteinMPNN/LigandMPNN/ESM-IF1) | **Downstream**: `filtering-ranking`

## When to Trigger

- User says "Protenix", "ByteDance", "Protenix-v1", "Protenix-v2"
- User wants open-source structure prediction with **training capability**
- User needs a **complete AF3 reproduction** with PyTorch framework
- User wants inference-time scaling for improved accuracy
- User needs a modular framework for biomolecular structure prediction
- User says "open source AlphaFold3 reproduction"

## Protenix Overview

[Protenix](https://github.com/bytedance/Protenix) is ByteDance's **fully open-source reproduction of AlphaFold3** for high-accuracy biomolecular structure prediction. Released under **Apache 2.0**, it supports training and inference for proteins, nucleic acids, small molecules, and their complexes.

### Key Differences from AlphaFold3

| Feature | AlphaFold3 | Protenix |
|---------|------------|----------|
| License | Non-commercial research only | **Apache 2.0 (fully open)** |
| Framework | JAX | **PyTorch** |
| Training | Not available | **Full training supported** |
| Inference scaling | Limited | **Log-linear improvements with samples** |
| Custom CUDA | No | **Yes (optimized kernels)** |
| Mini variant | No | **Protenix-Mini (fast)** |
| Binder design | No | **PXDesign (20-73% hit rates)** |
| Benchmarking | Limited | **PXMeter (6,000+ complexes)** |

**Key insight**: Protenix is the **most complete open-source AF3 reproduction**, offering not just inference but full training capabilities. Protenix-v1 was the first open-source model to **outperform AlphaFold3** on matched benchmarks.

## Versions

| Version | Release | Key Features |
|---------|---------|-------------|
| **Protenix** (initial) | 2024-2025 | First open-source AF3 reproduction |
| **Protenix-Mini** | July 2025 | Lightweight, few-step ODE sampling |
| **Protenix-v1** | Feb 2026 | **First to outperform AF3** on benchmarks |
| **Protenix-v2** | June 2026 | Major antibody-antigen improvements |

## Installation

```bash
# Clone repository
git clone https://github.com/bytedance/Protenix.git
cd Protenix

# Install dependencies
pip install -e .

# For Protenix-Mini (faster)
pip install protenix-mini
```

**Requirements:**
- CUDA-compatible GPU (recommended: A100/H100)
- PyTorch 2.0+
- BF16 support for efficient training

## Usage

### Inference

```python
from protenix import ProtenixModel

# Load model
model = ProtenixModel.from_pretrained("protenix-v1")

# Predict structure
result = model.predict(
    sequences=[
        {"protein": {"id": "A", "sequence": "MKTLLIL..."}},
        {"ligand": {"id": "L", "smiles": "CC(C)Cc1..."}},
    ],
    num_samples=1000,  # Inference-time scaling
)

# Save results
result.save_pdb("output.pdb")
```

### Inference-Time Scaling

Protenix supports **log-linear accuracy improvements** by sampling more candidates:

```python
# More samples = better accuracy (diminishing returns)
for num_samples in [5, 25, 100, 1000]:
    result = model.predict(sequences, num_samples=num_samples)
    print(f"Samples: {num_samples}, Confidence: {result.confidence:.3f}")
```

| Samples | Expected Improvement | Runtime |
|---------|---------------------|---------|
| 5 | Baseline | ~5 min |
| 25 | +2-3% | ~25 min |
| 100 | +4-5% | ~1.5 hr |
| 1000 | +6-8% | ~15 hr |

### Training (Protenix Unique Feature)

```python
from protenix import ProtenixTrainer

# Fine-tune on custom data
trainer = ProtenixTrainer(
    model_name="protenix-v1",
    train_data="custom_dataset/",
    learning_rate=1e-4,
)

trainer.train(epochs=10)
```

## Pipeline Integration

### Option 1: Protenix as AlphaFold3 Replacement
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN) → Protenix (validation)
                                                        ↓
                                        Stage 4 (Filtering)
```

### Option 2: Protenix with Inference Scaling
```
Stage 1 (RFdiffusion) → Stage 2 (ProteinMPNN)
                                ↓
                    Protenix with 1000 samples
                                ↓
                    Select top by confidence
```

### Option 3: PXDesign for Binder Design
```
Stage 0 (PDBFixer) → PXDesign (binder design)
                            ↓
                    Protenix (validate binder-target)
                            ↓
                    Filtering
```

**PXDesign**: ByteDance's protein binder design tool with reported 20-73% experimental hit rates.

## Comparison with Other Stage 3 Tools

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| Training capability | **Protenix** | Only tool with full training support |
| Inference scaling | **Protenix** | Log-linear improvements with samples |
| PyTorch ecosystem | **Protenix** | Native PyTorch (not JAX) |
| Commercial use (Apache) | Chai-1 | Also Apache 2.0 |
| Commercial use (MIT) | Boltz-1 | MIT license |
| Speed | ESMFold / OmegaFold | Faster but less accurate |
| Best accuracy | **Protenix-v1/v2** | Outperforms AF3 on benchmarks |
| Antibody-antigen | **Protenix-v2** | 9-13% improvement over v1 |
| Binder design | PXDesign + Protenix | Integrated design + validation |

## Ecosystem

| Component | Purpose | Link |
|-----------|---------|------|
| **Protenix-v1/v2** | Core prediction | `github.com/bytedance/Protenix` |
| **Protenix-Mini** | Fast variant | Included in repo |
| **PXMeter** | Benchmarking (6,000+ complexes) | `github.com/ByteDance/PXMeter` |
| **PXDesign** | Binder design | ByteDance internal |
| **Protenix-Dock** | Protein-ligand docking | Included in repo |

## Confidence Metrics

Protenix outputs standard confidence metrics:

| Metric | Description | Good Threshold |
|--------|-------------|----------------|
| pLDDT | Per-atom confidence | >70 |
| pTM | Topology confidence | >0.7 |
| ipTM | Interface confidence | >0.8 |

## Tips

- **Training**: Protenix is the only open-source tool that supports full training — great for research
- **Inference scaling**: Use 100-1000 samples for critical designs; 5-25 for screening
- **Protenix-Mini**: Use for quick prototyping when speed matters more than maximum accuracy
- **PyTorch**: Native PyTorch makes it easier to integrate with existing pipelines
- **PXMeter**: Use PXMeter for fair benchmarking against other methods
- **Antibody design**: Protenix-v2 excels at antibody-antigen complexes

## References

- [Protenix GitHub](https://github.com/bytedance/Protenix)
- [Protenix Paper](https://arxiv.org/abs/2512.24354)
- [PXMeter GitHub](https://github.com/ByteDance/PXMeter)
- [ByteDance AI Pharma](https://www.bytedance.com/)

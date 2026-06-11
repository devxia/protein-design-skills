---
name: aligninversepro-optimization
description: Inference-time optimization for protein diffusion models with AlignInversePro — optimize multiple reward functions during generation for better design quality
---

# Alternative: AlignInversePro Inference-Time Optimization

## When to Trigger

- User says "AlignInversePro", "inference-time optimization", "reward guidance"
- User wants to **improve design quality without retraining**
- User needs to **optimize multiple objectives** simultaneously (stability, pLDDT, scRMSD)
- User says "optimize my designs", "better quality", "refine predictions"
- User wants **controllable generation** with reward functions
- User is interested in **alignment** for protein generation

## AlignInversePro Overview

[AlignInversePro](https://github.com/masa-ue/AlignInversePro) is an **inference-time alignment framework for protein diffusion models** that optimizes multiple reward functions during the generation process. Unlike training-time methods that require expensive retraining, AlignInversePro improves design quality at inference by guiding the diffusion process toward desirable properties.

### Key Differences from Standard Generation

| Feature | Standard Diffusion | AlignInversePro |
|---------|-------------------|-----------------|
| Optimization | None | **Inference-time reward guidance** |
| Objectives | Single | **Multiple simultaneous** |
| Training required | No | **No (inference only)** |
| Applicability | Model-specific | **Works with any diffusion model** |
| Cost | Standard generation | **Slightly slower** |

**Key insight**: AlignInversePro is a **meta-tool** that can be applied ON TOP of existing tools (RFdiffusion, ProteinMPNN, etc.) to improve their output quality without any retraining.

## Installation

```bash
# Clone repository
git clone https://github.com/masa-ue/AlignInversePro.git
cd AlignInversePro

# Install dependencies
pip install -e .

# Requirements: PyTorch 2.0+, CUDA GPU
```

## Usage

### Basic Optimization (Single Reward)

```python
import torch
from aligninversepro import InferenceOptimizer

# Load your base diffusion model (e.g., RFdiffusion)
base_model = load_your_diffusion_model()

# Create optimizer with pLDDT reward
optimizer = InferenceOptimizer(
    base_model=base_model,
    reward_functions={"plddt": plddt_reward_function},
    optimization_steps=20,
)

# Generate with optimization
result = optimizer.generate(
    length=150,
    num_samples=10,
)

# Results are optimized for higher pLDDT
for i, design in enumerate(result):
    design.save_pdb(f"optimized_design_{i}.pdb")
```

### Multi-Objective Optimization

```python
# Optimize for multiple rewards simultaneously
optimizer = InferenceOptimizer(
    base_model=base_model,
    reward_functions={
        "plddt": plddt_reward_function,      # Structure confidence
        "stability": stability_reward,        # Thermodynamic stability
        "scRMSD": scRMSD_reward,             # Self-consistency
    },
    reward_weights={
        "plddt": 0.4,
        "stability": 0.35,
        "scRMSD": 0.25,
    },
    optimization_steps=20,
)

# Generate with multi-objective optimization
result = optimizer.generate(length=150, num_samples=10)
```

### Apply to Existing Pipeline

```python
# After RFdiffusion generates backbones
from aligninversepro import BackboneOptimizer

# Optimize each backbone
optimized_backbones = []
for backbone in rfdiffusion_backbones:
    opt_backbone = BackboneOptimizer.optimize(
        backbone=backbone,
        reward="plddt",
        steps=20,
    )
    optimized_backbones.append(opt_backbone)
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_model` | Model | — | Base diffusion/generative model |
| `reward_functions` | dict | — | Dictionary of reward functions |
| `reward_weights` | dict | Equal | Weights for each reward |
| `optimization_steps` | int | 20 | Number of optimization steps |
| `learning_rate` | float | 0.01 | Step size for optimization |

## Reward Functions

Common reward functions available:

| Reward | Description | Good For |
|--------|-------------|----------|
| `plddt` | Predicted structure confidence | Overall quality |
| `stability` | Thermodynamic stability | Fold stability |
| `scRMSD` | Self-consistency RMSD | Designability |
| `packing` | Sidechain packing quality | Sidechain quality |
| `hydrophobicity` | Surface hydrophobicity | Solubility |
| `interface` | Interface quality | Binder design |

## Pipeline Integration

### Option 1: Optimize After Generation
```
Stage 1: RFdiffusion (generate backbones)
    ↓
AlignInversePro (optimize backbones for pLDDT)
    ↓
Stage 2: ProteinMPNN (design sequences)
    ↓
Stage 3: AlphaFold3 (validate)
    ↓
Stage 4: Filtering
```

**Why this works:**
- Generate diverse backbones first
- Optimize best candidates for desired property
- Sequence design on optimized structures

### Option 2: Optimize Full Pipeline
```
Stage 1: RFdiffusion (generate backbones)
    ↓
Stage 2: ProteinMPNN (design sequences)
    ↓
Stage 3: AlphaFold3 (predict structures)
    ↓
AlignInversePro (optimize sequences for pLDDT)
    ↓
Re-validate with AlphaFold3
    ↓
Stage 4: Filtering
```

**Why this works:**
- Complete pipeline generates initial designs
- Optimization improves top candidates
- Re-validation confirms improvement

### Option 3: Multi-Objective Optimization
```
Stage 1: RFdiffusion (generate backbones)
    ↓
AlignInversePro (multi-objective: pLDDT + stability + scRMSD)
    ↓
Stage 2: ProteinMPNN (design sequences)
    ↓
Stage 3: AlphaFold3 (validate)
    ↓
Stage 4: Filtering with composite score
```

**Why this works:**
- Balance multiple quality metrics
- Avoid over-optimizing single property
- Get well-rounded designs

## Comparison with Other Methods

| Method | When to Use | Training Required |
|--------|-------------|-------------------|
| **AlignInversePro** | Inference-time improvement | No |
| Fine-tuning | Domain adaptation | Yes (expensive) |
| Re-training | Major architectural changes | Yes (very expensive) |
| Post-processing filtering | Remove bad designs | No |
| Multi-seed sampling | Ensemble approach | No |

## Tips

- **Optimization steps**: 10-30 steps typical. More steps = better but slower.
- **Reward weights**: Adjust weights based on your priority (e.g., 0.5 pLDDT, 0.3 stability, 0.2 scRMSD)
- **Learning rate**: Start with 0.01, reduce if optimization is unstable
- **Applicability**: Works with any diffusion model (RFdiffusion, Chroma, Genie 3, etc.)
- **Cost**: ~2-5× slower than standard generation but no training cost
- **Validation**: Always validate optimized designs — optimization can sometimes cause artifacts

## References

- [AlignInversePro GitHub](https://github.com/masa-ue/AlignInversePro)
- [Inference-Time Alignment Paper](https://arxiv.org/abs/2410.04327)
- [Reward-Guided Diffusion](https://arxiv.org/abs/2312.12506)

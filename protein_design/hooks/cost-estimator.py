#!/usr/bin/env python3
"""UserPromptSubmit hook: estimate computational cost for protein design workflows.

When users describe a design goal, this hook estimates GPU time, memory,
and cost for different pipeline options — helping them make informed decisions.
"""
import traceback
import json
import re
from typing import Any
import sys


COST_TABLE: dict[str, dict[str, Any]] = {
    "rfdiffusion": {
        "time_per_design": 2,  # minutes
        "gpu_memory_gb": 24,
        "setup_time": 30,  # minutes (first run)
    },
    "rfdiffusion_aa": {
        "time_per_design": 5,
        "gpu_memory_gb": 48,
        "setup_time": 60,
    },
    "proteinmpnn": {
        "time_per_design": 0.5,
        "gpu_memory_gb": 8,
        "setup_time": 5,
    },
    "alphafold3": {
        "time_per_design": 10,
        "gpu_memory_gb": 40,
        "setup_time": 120,
        "needs_databases": True,
        "db_size_tb": 2.6,
    },
    "omegafold": {
        "time_per_design": 0.2,
        "gpu_memory_gb": 12,
        "setup_time": 5,
        "needs_databases": False,
    },
    "esmfold": {
        "time_per_design": 0.05,
        "gpu_memory_gb": 8,
        "setup_time": 5,
        "needs_databases": False,
    },
    "boltz": {
        "time_per_design": 8,
        "gpu_memory_gb": 40,
        "setup_time": 30,
    },
    "chai1": {
        "time_per_design": 8,
        "gpu_memory_gb": 40,
        "setup_time": 30,
    },
    "protenix": {
        "time_per_design": 10,
        "gpu_memory_gb": 40,
        "setup_time": 60,
    },
    "openfold3": {
        "time_per_design": 10,
        "gpu_memory_gb": 40,
        "setup_time": 30,
    },
    "foldflow": {
        "time_per_design": 1,
        "gpu_memory_gb": 16,
        "setup_time": 15,
    },
    "chroma": {
        "time_per_design": 5,
        "gpu_memory_gb": 48,
        "setup_time": 60,
    },
    "diffpepbuilder": {
        "time_per_design": 15,
        "gpu_memory_gb": 48,
        "setup_time": 120,
        "multi_gpu": True,
    },
    "igdiff": {
        "time_per_design": 3,
        "gpu_memory_gb": 24,
        "setup_time": 30,
    },
    "evodiff": {
        "time_per_design": 0.5,
        "gpu_memory_gb": 16,
        "setup_time": 15,
    },
}


def _detect_pipeline(text: str) -> dict[str, Any]:
    """Detect pipeline components from user text."""
    text_lower = text.lower()
    result = {
        "num_designs": 10,
        "stage1": "rfdiffusion",
        "stage2": "proteinmpnn",
        "stage3": "alphafold3",
    }

    # Detect number of designs
    m = re.search(r'(\d+)\s*designs?', text_lower)
    if m:
        result["num_designs"] = int(m.group(1))

    # Detect Stage 1
    if "rfdiffusionaa" in text_lower or "rf diffusion all" in text_lower:
        result["stage1"] = "rfdiffusion_aa"
    elif "chroma" in text_lower:
        result["stage1"] = "chroma"
    elif "foldflow" in text_lower:
        result["stage1"] = "foldflow"
    elif "diffpepbuilder" in text_lower or "peptide" in text_lower:
        result["stage1"] = "diffpepbuilder"
    elif "igdiff" in text_lower or "antibody" in text_lower:
        result["stage1"] = "igdiff"
    elif "evodiff" in text_lower:
        result["stage1"] = "evodiff"
    elif "colabdesign" in text_lower or "afdesign" in text_lower:
        result["stage1"] = "colabdesign"

    # Detect Stage 2
    if "ligandmpnn" in text_lower:
        result["stage2"] = "proteinmpnn"  # Same cost profile
    elif "esm-if1" in text_lower or "esm if1" in text_lower:
        result["stage2"] = "proteinmpnn"  # Similar

    # Detect Stage 3
    if "omegafold" in text_lower:
        result["stage3"] = "omegafold"
    elif "esmfold" in text_lower:
        result["stage3"] = "esmfold"
    elif "boltz" in text_lower:
        result["stage3"] = "boltz"
    elif "chai" in text_lower:
        result["stage3"] = "chai1"
    elif "protenix" in text_lower:
        result["stage3"] = "protenix"
    elif "openfold" in text_lower:
        result["stage3"] = "openfold3"

    return result


def _estimate_cost(pipeline: dict[str, Any]) -> dict[str, Any]:
    """Estimate computational cost."""
    n = pipeline["num_designs"]
    s1 = COST_TABLE.get(pipeline["stage1"], COST_TABLE["rfdiffusion"])
    s2 = COST_TABLE.get(pipeline["stage2"], COST_TABLE["proteinmpnn"])
    s3 = COST_TABLE.get(pipeline["stage3"], COST_TABLE["alphafold3"])

    # Stage 2 typically processes all Stage 1 outputs
    stage2_multiplier = 2  # 2 sequences per backbone

    total_time = (
        s1["time_per_design"] * n +
        s2["time_per_design"] * n * stage2_multiplier +
        s3["time_per_design"] * n * stage2_multiplier
    )

    max_memory = max(s1["gpu_memory_gb"], s2["gpu_memory_gb"], s3["gpu_memory_gb"])

    setup_time = max(s1["setup_time"], s2["setup_time"], s3["setup_time"])

    needs_databases = s3.get("needs_databases", False)
    db_size = s3.get("db_size_tb", 0)

    # Cost on cloud GPU (A100 80GB at ~$2.5/hour)
    cloud_cost = (total_time / 60) * 2.5

    return {
        "total_time_min": total_time,
        "setup_time_min": setup_time,
        "max_gpu_memory_gb": max_memory,
        "needs_databases": needs_databases,
        "db_size_tb": db_size,
        "cloud_cost_usd": cloud_cost,
        "num_designs": n,
    }


def main() -> int:
    """Main entry point."""
    try:
        text = sys.stdin.read()
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    if not text.strip():
        return 0

    # Only activate for protein design prompts
    if not re.search(
        r"\b(protein|design|binder|scaffold|rfdiffusion|proteinmpnn|alphafold|pipeline|cost|time|gpu|resource)\b",
        text, re.IGNORECASE,
    ):
        return 0

    pipeline = _detect_pipeline(text)
    cost = _estimate_cost(pipeline)

    output = f"""[Cost Estimator] Pipeline: {pipeline['stage1']} → {pipeline['stage2']} → {pipeline['stage3']}

## Resource Estimate for {cost['num_designs']} Designs

| Resource | Estimate |
|----------|----------|
| **Total GPU time** | ~{cost['total_time_min']:.0f} minutes ({cost['total_time_min']/60:.1f} hours) |
| **Setup time** | ~{cost['setup_time_min']:.0f} minutes (first run only) |
| **Max GPU memory** | {cost['max_gpu_memory_gb']} GB |
| **Needs databases** | {'Yes (' + str(cost['db_size_tb']) + ' TB)' if cost['needs_databases'] else 'No'} |
| **Cloud cost (A100)** | ~${cost['cloud_cost_usd']:.2f} USD |

## Breakdown by Stage

| Stage | Tool | Time | Memory |
|-------|------|------|--------|
| Stage 1 | {pipeline['stage1']} | ~{cost['num_designs'] * COST_TABLE.get(pipeline['stage1'], COST_TABLE['rfdiffusion'])['time_per_design']:.0f} min | {COST_TABLE.get(pipeline['stage1'], COST_TABLE['rfdiffusion'])['gpu_memory_gb']} GB |
| Stage 2 | {pipeline['stage2']} | ~{cost['num_designs'] * 2 * COST_TABLE.get(pipeline['stage2'], COST_TABLE['proteinmpnn'])['time_per_design']:.0f} min | {COST_TABLE.get(pipeline['stage2'], COST_TABLE['proteinmpnn'])['gpu_memory_gb']} GB |
| Stage 3 | {pipeline['stage3']} | ~{cost['num_designs'] * 2 * COST_TABLE.get(pipeline['stage3'], COST_TABLE['alphafold3'])['time_per_design']:.0f} min | {COST_TABLE.get(pipeline['stage3'], COST_TABLE['alphafold3'])['gpu_memory_gb']} GB |

## Cost-Saving Alternatives

| Alternative | Savings | Trade-off |
|-------------|---------|-----------|
| Use OmegaFold instead of AlphaFold3 | **~80% faster Stage 3** | Slightly lower accuracy |
| Use ESMFold for pre-screen | **~99% faster Stage 3** | Good for initial screening |
| Use FoldFlow instead of RFdiffusion | **~50% faster Stage 1** | Max length ~300 residues |
| Reduce designs to 20 | **~50% total time** | Fewer candidates |
| Skip Stage 3 (design only) | **~70% total time** | No validation |

## Tips

- **Fastest pipeline**: FoldFlow → ProteinMPNN → ESMFold
- **Cheapest validation**: ESMFold (~$0.02/design) or OmegaFold (~$0.08/design)
- **Most accurate**: RFdiffusion → ProteinMPNN → AlphaFold3 (full MSA)
- **Database-free**: Use OmegaFold, ESMFold, or Boltz-1/Chai-1 (MSA server)
- **Batch overnight**: Submit all jobs before leaving; check results in morning
"""

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

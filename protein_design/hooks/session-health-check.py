#!/usr/bin/env python3
"""UserPromptSubmit hook: auto-run health checks on protein-related prompts.

When the session starts or user sends a protein-related message, this hook
silently checks environment health and injects the results into context.
"""
import traceback
import json
import re
import subprocess
from typing import Any
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from protein_design.utils import PROTEIN_DESIGN_PATTERN, get_hook_prompt, probe_gpus, read_hook_input


def _check_tools() -> dict[str, Any]:
    """Quick check for installed tools without heavy imports.

    Probes run concurrently: ten sequential 5s-timeout probes could take ~50s
    on slow machines, exceeding the 5s hook budget declared in hooks.json.
    """
    probes = [
        ("rfdiffusion", ["python", "-c", "import rfdiffusion"]),
        ("proteinmpnn", ["python", "-c", "import proteinmpnn"]),
        ("alphafold3", ["python", "-c", "import alphafold3"]),
        ("pdbfixer", ["python", "-c", "from pdbfixer import PDBFixer"]),
        ("esmfold", ["python", "-c", "import esm"]),
        ("omegafold", ["python", "-c", "import omegafold"]),
        ("boltz", ["python", "-c", "import boltz"]),
        ("chai1", ["python", "-c", "import chai_lab"]),
        ("protenix", ["python", "-c", "import protenix"]),
        ("openfold", ["python", "-c", "import openfold"]),
    ]

    def _probe(import_test: list[str]) -> bool:
        try:
            subprocess.run(import_test, capture_output=True, timeout=3, check=True)
            return True
        except Exception:
            return False

    tools: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(probes)) as pool:
        results = list(pool.map(lambda item: _probe(item[1]), probes))
    for (name, _), ok in zip(probes, results):
        tools[name] = "✓" if ok else "✗"
    return tools


def _check_gpu() -> dict[str, Any]:
    """Quick GPU check via the shared probe; timeout stays within the
    overall 5s hook budget declared in hooks.json."""
    gpus = probe_gpus(timeout=3.0)
    if gpus:
        return {"name": gpus[0]["name"], "free_mb": int(gpus[0]["free_mb"])}
    return {"name": "None", "free_mb": 0}


def _check_disk() -> dict[str, Any]:
    """Quick disk check."""
    try:
        import shutil
        disk = shutil.disk_usage("/tmp")
        return {"free_gb": round(disk.free / (1024**3), 1)}
    except Exception:
        return {"free_gb": 0}


def main() -> int:
    """Main entry point."""
    try:
        data = read_hook_input()
    except json.JSONDecodeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    user_prompt = get_hook_prompt(data)

    # Only activate for protein design keywords
    protein_keywords = re.compile(PROTEIN_DESIGN_PATTERN, re.IGNORECASE)

    if not protein_keywords.search(user_prompt):
        return 0

    # Run quick checks concurrently to stay within the 5s hook budget:
    # worst case is max(tools ~3s, GPU ~3s) rather than their sum.
    with ThreadPoolExecutor(max_workers=2) as pool:
        tools_future = pool.submit(_check_tools)
        gpu_future = pool.submit(_check_gpu)
        tools = tools_future.result()
        gpu = gpu_future.result()
    disk = _check_disk()

    # Build status string
    tools_str = " ".join(f"{k}:{v}" for k, v in tools.items())
    gpu_str = f"{gpu['name']} ({gpu['free_mb']}MB free)" if gpu["free_mb"] > 0 else "Not available"

    # Detect missing tools
    missing = [k for k, v in tools.items() if v == "✗"]
    missing_str = f" | Missing: {', '.join(missing)}" if missing else ""

    output = (
        f"[Session Health] Tools: {tools_str} | GPU: {gpu_str} | Disk: {disk['free_gb']}GB free{missing_str}"
    )

    # Add guidance for missing tools
    if missing:
        output += "\n\n**Missing tools — quick alternatives:**\n"
        alt_map = {
            "rfdiffusion": "Chroma (`pip install chroma-ai`) or FrameDiff",
            "proteinmpnn": "ESM-IF1 (`pip install fair-esm`) or LigandMPNN",
            "alphafold3": "ESMFold (`pip install fair-esm`) or OmegaFold (`pip install omegafold`) — no databases needed",
            "pdbfixer": "Run: `conda install -c conda-forge pdbfixer openmm`",
            "esmfold": "`pip install fair-esm` — MIT, CPU-compatible, no databases",
            "omegafold": "`pip install omegafold` — MIT, fast, no databases",
            "boltz": "`pip install boltz` — MIT, good for complexes",
            "chai1": "See chai-1 docs — Apache 2.0, single-seq mode",
            "protenix": "See protenix docs — MIT, training+inference scaling",
            "openfold": "`pip install openfold3` — Apache 2.0, AF3 parity",
        }
        for tool in missing:
            if tool in alt_map:
                output += f"  - **{tool}**: {alt_map[tool]}\n"
        output += "\nSee `install-guide` skill for full installation instructions.\n"

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""UserPromptSubmit hook: auto-run health checks on protein-related prompts.

When the session starts or user sends a protein-related message, this hook
silently checks environment health and injects the results into context —
eliminating the need for explicit health_check MCP calls.
"""

import json
import re
import subprocess
import sys
from typing import Any


def _check_tools() -> dict[str, Any]:
    """Quick check for installed tools without heavy imports."""
    tools = {}
    for name, import_test in [
        ("rfdiffusion", ["python", "-c", "import rfdiffusion"]),
        ("proteinmpnn", ["python", "-c", "import protein_mpnn_run"]),
        ("alphafold3", ["python", "-c", "import run_alphafold"]),
        ("pdbfixer", ["python", "-c", "from pdbfixer import PDBFixer"]),
    ]:
        try:
            subprocess.run(import_test, capture_output=True, timeout=5, check=True)
            tools[name] = "✓"
        except Exception:
            tools[name] = "✗"
    return tools


def _check_gpu() -> dict[str, Any]:
    """Quick GPU check."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        parts = [p.strip() for p in result.stdout.strip().split(",")]
        if len(parts) >= 2:
            return {"name": parts[0], "free_mb": int(float(parts[1]))}
    except Exception:
        pass
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
        user_prompt = sys.stdin.read()
    except Exception:
        user_prompt = ""

    # Only activate for protein design keywords
    protein_keywords = re.compile(
        r"\b(protein|pdb|binder|alphafold|rfdiffusion|proteinmpnn|design|"
        r"structure|sequence|residue|loop|scaffold|motif|oligomer|diffusion|"
        r"backbone|monomer|complex|interface|epitope|target|fold|prediction|"
        r"plddt|ptm|iptm|msa|validation|ranking|filter|chain)\b",
        re.IGNORECASE,
    )

    if not protein_keywords.search(user_prompt):
        return 0

    # Run quick checks
    tools = _check_tools()
    gpu = _check_gpu()
    disk = _check_disk()

    # Build status string
    tools_str = " ".join(f"{k}:{v}" for k, v in tools.items())
    gpu_str = f"{gpu['name']} ({gpu['free_mb']}MB free)" if gpu["free_mb"] > 0 else "Not available"

    # Detect missing tools
    missing = [k for k, v in tools.items() if v == "✗"]
    missing_str = f" | Missing: {', '.join(missing)}" if missing else ""

    output = (
        f"[环境状态] Tools: {tools_str} | GPU: {gpu_str} | Disk: {disk['free_gb']}GB free{missing_str}"
    )

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""UserPromptSubmit hook: inject protein design environment context.

When the user's message contains protein design keywords, this hook
returns a formatted environment status string that the model receives
in its context.

Works with any coding agent that supports hook context injection (Claude Code,
Kimi Code >= 0.6.0, Codex CLI).
"""

import subprocess
import sys
from typing import Any


def check_tool(name: str, command: list[str]) -> str:
    """Check if a tool is available."""
    try:
        subprocess.run(command, capture_output=True, timeout=5, check=True)
        return "✓"
    except Exception:
        return "✗"


def get_gpu_info() -> dict[str, Any]:
    """Get brief GPU info."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        parts = [p.strip() for p in result.stdout.strip().split(",")]
        if len(parts) >= 2:
            return {"name": parts[0], "free_mb": int(float(parts[1]))}
    except Exception:
        pass
    return {"name": "None", "free_mb": 0}


def main() -> int:
    """Main entry point. Reads prompt from stdin, prints context to stdout."""
    try:
        _ = sys.stdin.read()
    except Exception:
        pass

    gpu = get_gpu_info()
    tools = {
        "RFdiffusion": check_tool("rfdiffusion", ["python", "-c", "import rfdiffusion"]),
        "ProteinMPNN": check_tool("proteinmpnn", ["python", "-c", "import protein_mpnn_run"]),
        "AlphaFold3": check_tool("alphafold3", ["python", "-c", "import run_alphafold"]),
        "PDBFixer": check_tool("pdbfixer", ["python", "-c", "from pdbfixer import PDBFixer"]),
        "ESMFold": check_tool("esmfold", ["python", "-c", "import esm"]),
        "OmegaFold": check_tool("omegafold", ["python", "-c", "import omegafold"]),
        "Boltz": check_tool("boltz", ["python", "-c", "import boltz"]),
    }

    gpu_str = f"{gpu['name']} ({gpu['free_mb']}MB free)" if gpu["free_mb"] > 0 else "Not available"
    tools_str = " | ".join(f"{k} {v}" for k, v in tools.items())
    output_dir = "/tmp/protein-design"

    # Detect missing tools for guidance
    missing = [k for k, v in tools.items() if v == "✗"]
    missing_guidance = ""
    if missing:
        alt_map = {
            "RFdiffusion": "Chroma (`pip install chroma-ai`)",
            "ProteinMPNN": "ESM-IF1 (`pip install fair-esm`)",
            "AlphaFold3": "ESMFold (`pip install fair-esm`) or OmegaFold (`pip install omegafold`)",
            "PDBFixer": "`conda install -c conda-forge pdbfixer openmm`",
            "ESMFold": "`pip install fair-esm` — MIT, CPU-compatible",
            "OmegaFold": "`pip install omegafold` — MIT, fast",
            "Boltz": "`pip install boltz` — MIT, good for complexes",
        }
        missing_guidance = "\n**Missing tools — alternatives:**\n"
        for tool in missing:
            if tool in alt_map:
                missing_guidance += f"  - {tool}: {alt_map[tool]}\n"

    context = (
        f"[Session Health / 环境状态] "
        f"GPU: {gpu_str} | "
        f"Tools / 工具: {tools_str} | "
        f"Output / 输出目录: {output_dir}"
        f"{missing_guidance}"
    )

    print(context)
    return 0


if __name__ == "__main__":
    sys.exit(main())

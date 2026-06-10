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
    }

    gpu_str = f"{gpu['name']} ({gpu['free_mb']}MB free)" if gpu["free_mb"] > 0 else "Not available"
    tools_str = " | ".join(f"{k} {v}" for k, v in tools.items())
    output_dir = "/tmp/protein-design"

    context = (
        f"[蛋白质设计环境状态] "
        f"GPU: {gpu_str} | "
        f"工具: {tools_str} | "
        f"输出目录: {output_dir}"
    )

    print(context)
    return 0


if __name__ == "__main__":
    sys.exit(main())

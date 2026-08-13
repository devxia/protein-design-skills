#!/usr/bin/env python3
"""PostToolUse hook: analyze tool failures and suggest recovery strategies.

When a tool call fails, this hook intercepts the error and provides
context-aware recovery suggestions — helping users diagnose and fix
issues without manual debugging.
"""
import traceback
import json
import re
from typing import Any
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from protein_design.utils import extract_content_text, read_hook_input


def _parse_error(error_text: str) -> dict[str, Any]:
    """Parse error text to identify the failure type and root cause."""
    error_lower = error_text.lower()
    result: dict[str, Any] = {"type": "unknown", "message": error_text[:500]}

    # GPU / CUDA errors
    if any(kw in error_lower for kw in ["cuda", "gpu", "out of memory", "oom", "cudnn"]):
        result["type"] = "gpu_error"
        if "out of memory" in error_lower or "oom" in error_lower:
            result["subtype"] = "oom"
            result["message"] = "GPU out of memory"
        elif "cuda" in error_lower:
            result["subtype"] = "cuda"
            result["message"] = "CUDA error"
        return result

    # File not found errors
    if any(kw in error_lower for kw in ["file not found", "nosuchfile", "no such file"]):
        result["type"] = "file_not_found"
        # Try to extract filename
        match = re.search(r"['\"]?([^'\"\s]+\.(?:pdb|cif|json|fa|fasta|pt|ckpt))['\"]?", error_text, re.I)
        if match:
            result["missing_file"] = match.group(1)
        return result

    # Tool not installed
    if any(kw in error_lower for kw in ["not found", "not installed", "module not found", "importerror"]):
        result["type"] = "tool_not_found"
        for tool in ["rfdiffusion", "proteinmpnn", "alphafold", "pdbfixer"]:
            if tool in error_lower:
                result["missing_tool"] = tool
                break
        return result

    # Contig / parameter errors
    if any(kw in error_lower for kw in ["contig", "invalid", "argument", "parameter", "keyerror"]):
        result["type"] = "parameter_error"
        if "contig" in error_lower:
            result["subtype"] = "contig"
        return result

    # Timeout
    if any(kw in error_lower for kw in ["timeout", "timed out", "time out"]):
        result["type"] = "timeout"
        return result

    # MSA / Database errors
    if any(kw in error_lower for kw in ["msa", "database", "bfd", "uniref", "jackhmmer", "hhblits"]):
        result["type"] = "msa_error"
        return result

    # Conda / Environment errors
    if any(kw in error_lower for kw in ["conda", "environment", "module", "package"]):
        result["type"] = "environment_error"
        return result

    return result


def _build_recovery_strategy(error_info: dict[str, Any], tool_name: str) -> list[str]:
    """Build recovery strategies based on error type and tool."""
    strategies: list[str] = []
    error_type = error_info.get("type")
    subtype = error_info.get("subtype")

    if error_type == "gpu_error":
        if subtype == "oom":
            strategies = [
                "GPU out of memory. Solutions:",
                "  1. Reduce num_designs (e.g. from 50 to 10)",
                "  2. Lower diffuser_T (e.g. from 50 to 25)",
                "  3. Close other programs using the GPU",
                "  4. Use a shorter protein length",
            ]
        else:
            strategies = [
                "CUDA/GPU error. Solutions:",
                "  1. Check nvidia-smi to confirm the GPU is available",
                "  2. Check CUDA version compatibility with PyTorch",
                "  3. Try setting CUDA_VISIBLE_DEVICES=0",
                "  4. Restart the kernel/session",
            ]

    elif error_type == "file_not_found":
        missing = error_info.get("missing_file", "file")
        strategies = [
            f"File not found: {missing}",
            "  1. Check the file path (use an absolute path)",
            "  2. Confirm the file exists at the given location",
            f"  3. If it is an output file, ensure the directory exists: mkdir -p $(dirname {missing})",
            "  4. Check file permissions",
        ]

    elif error_type == "tool_not_found":
        missing_tool = error_info.get("missing_tool", "tool")
        alt_map = {
            "rfdiffusion": "Chroma (`pip install chroma-ai`) or FrameDiff",
            "proteinmpnn": "ESM-IF1 (`pip install fair-esm`) or LigandMPNN",
            "alphafold": "ESMFold (`pip install fair-esm`) or OmegaFold (`pip install omegafold`) — no databases needed",
            "pdbfixer": "Run: `conda install -c conda-forge pdbfixer openmm`",
        }
        alt = alt_map.get(missing_tool, "see the install-guide skill")
        strategies = [
            f"{missing_tool} not found or not installed",
            f"  Quick alternative: {alt}",
            f"  Set env var: {missing_tool.upper()}_PATH=/path/to/{missing_tool}",
            "  See the install-guide skill for full instructions",
        ]

    elif error_type == "parameter_error":
        if subtype == "contig":
            strategies = [
                "Contig parameter error. Check:",
                "  1. Syntax: [A1-50/0 10-20/A71-150]",
                "  2. Fixed regions need a chain prefix (e.g. A1-50)",
                "  3. Generated regions need no prefix (e.g. 10-20)",
                "  4. Use / to separate regions",
                "  5. Use 0 for a chain break (binder design)",
                "  6. Match residue numbers to the input PDB",
            ]
        else:
            strategies = [
                "Parameter error. Check:",
                "  1. All required params provided?",
                "  2. Correct param types (string/int/bool)?",
                "  3. See SKILL_INDEX.md for full params",
            ]

    elif error_type == "timeout":
        strategies = [
            "Job timed out. Solutions:",
            "  1. For AlphaFold3: set run_data_pipeline=false to skip MSA",
            "  2. Reduce num_designs or num_seeds",
            "  3. Use a shorter protein sequence",
            "  4. Check the GPU is working",
        ]

    elif error_type == "msa_error":
        strategies = [
            "MSA/Database error. Solutions:",
            "  1. Set run_data_pipeline=false to skip MSA (fast but less accurate)",
            "  2. Use ESMFold or OmegaFold instead (no databases needed)",
            "  3. Check the database directory exists and is complete (~2.6TB)",
            "  4. Check disk space",
        ]

    elif error_type == "environment_error":
        strategies = [
            "Environment/dependency error. Solutions:",
            "  1. Use the conda_env parameter to specify the correct conda environment",
            "  2. Use wrapper_script for custom environment setup",
            "  3. Check the conda environment contains the required packages",
            "  4. Reinstall the tool into the correct conda environment",
        ]

    else:
        strategies = [
            "Unknown error. Suggestions:",
            "  1. Inspect the full stderr log file",
            "  2. Check the input file format",
            "  3. Retry with simpler parameters",
            "  4. See the troubleshooting section of the docs",
        ]

    return strategies


def _extract_tool_name(data: dict[str, Any]) -> str:
    """Extract the tool name from hook input data."""
    # Try to find tool name from various locations in the data
    text = extract_content_text(data.get("result"))
    if text:
        try:
            result_json = json.loads(text)
            # Check for tool name in result
            if "tool_name" in result_json:
                return result_json["tool_name"]
            if "tool" in result_json:
                return result_json["tool"]
        except json.JSONDecodeError:
            pass

    # Check for error message
    error = data.get("error", "")
    if isinstance(error, str):
        for tool in ["rfdiffusion", "proteinmpnn", "alphafold", "pdbfixer", "filtering"]:
            if tool in error.lower():
                return tool

    return "unknown"


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

    # Only process failed tool calls
    result = data.get("result", {})
    if isinstance(result, dict) and result.get("isError"):
        error_text = extract_content_text(result)

        if not error_text:
            return 0

        tool_name = _extract_tool_name(data)
        error_info = _parse_error(error_text)
        strategies = _build_recovery_strategy(error_info, tool_name)

        output = f"""[Error Recovery] Tool: {tool_name} | Type: {error_info['type']}

{chr(10).join(strategies)}

Error summary: {error_info['message'][:200]}
"""
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())

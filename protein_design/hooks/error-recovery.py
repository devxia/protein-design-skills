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
from protein_design.utils import (
    extract_content_text,
    get_hook_error,
    get_hook_invoked_runner,
    get_hook_tool_name,
    get_hook_tool_response,
    hook_advisory_output,
    read_hook_input,
)


def _parse_error(error_text: str) -> dict[str, Any]:
    """Parse error text to identify the failure type and root cause."""
    error_lower = error_text.lower()
    result: dict[str, Any] = {"type": "unknown", "message": error_text[:500]}

    # GPU / CUDA errors ("oom" needs a word-boundary match so words like
    # "bedroom" do not trigger the OOM path)
    is_oom = "out of memory" in error_lower or re.search(r"\boom\b", error_lower) is not None
    if any(kw in error_lower for kw in ["cuda", "gpu", "cudnn"]) or is_oom:
        result["type"] = "gpu_error"
        if is_oom:
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
            "  1. For AlphaFold3: pass --no-msa to skip MSA",
            "  2. Reduce num_designs or num_seeds",
            "  3. Use a shorter protein sequence",
            "  4. Check the GPU is working",
        ]

    elif error_type == "msa_error":
        strategies = [
            "MSA/Database error. Solutions:",
            "  1. Pass --no-msa to skip MSA (fast but less accurate)",
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


def _find_response_tool_name(value: Any) -> str:
    """Find a tool name in nested response wrappers or JSON strings."""
    if isinstance(value, dict):
        for key in ("tool_name", "tool"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for key in ("tool_response", "result", "response", "output", "content"):
            if key in value:
                found = _find_response_tool_name(value[key])
                if found:
                    return found
    elif isinstance(value, list):
        for item in value:
            found = _find_response_tool_name(item)
            if found:
                return found
    elif isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return ""
        if isinstance(decoded, (dict, list)):
            return _find_response_tool_name(decoded)
    return ""


def _extract_tool_name(data: dict[str, Any], error_text: str = "") -> str:
    """Extract the authoritative or best-effort tool name from hook input."""
    tool_name = get_hook_tool_name(data)
    if tool_name:
        return tool_name

    # Older hosts sometimes included the tool name in the JSON response.
    tool_name = _find_response_tool_name(get_hook_tool_response(data))
    if tool_name:
        return tool_name

    for tool in ["rfdiffusion", "proteinmpnn", "alphafold", "pdbfixer", "filtering"]:
        if tool in error_text.lower():
            return tool

    return "unknown"


def _response_is_error(response: Any) -> bool:
    """Return whether a structured response or nested wrapper marks an error."""
    if isinstance(response, dict):
        if bool(response.get("isError")):
            return True
        return any(
            _response_is_error(response.get(key))
            for key in ("tool_response", "result", "response", "output", "content")
            if key in response
        )
    if isinstance(response, list):
        return any(_response_is_error(item) for item in response)
    if isinstance(response, str):
        try:
            decoded = json.loads(response)
        except (TypeError, ValueError):
            return False
        return _response_is_error(decoded) if isinstance(decoded, (dict, list)) else False
    return False


def _extract_error_text(value: Any) -> str:
    """Extract useful text from a response, unwrapping JSON strings."""
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return value
        if isinstance(decoded, (dict, list)):
            nested = _extract_error_text(decoded)
            return nested or value
        return value
    if isinstance(value, dict):
        for key in ("error", "message", "content", "tool_response", "result", "response", "output"):
            if key in value:
                nested = _extract_error_text(value[key])
                if nested:
                    return nested
    elif isinstance(value, list):
        for item in value:
            nested = _extract_error_text(item)
            if nested:
                return nested
    return extract_content_text(value)


def _get_error_text(data: dict[str, Any]) -> str:
    """Extract an error message from standard or legacy failure payloads."""
    error_value = get_hook_error(data)
    if error_value is not None:
        return _extract_error_text(error_value)

    response = get_hook_tool_response(data)
    if _response_is_error(response):
        return _extract_error_text(response)
    return ""


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

    # Only process failed tool calls. PostToolUseFailure payloads may contain
    # only a top-level error, while older PostToolUse payloads use result.
    if not isinstance(data, dict):
        return 0

    error_text = _get_error_text(data)
    if not error_text:
        return 0
    # Shell invocations are always resolved by the shared allowlist. Legacy
    # failure payloads may provide only an error response, so retain its
    # extracted tool label as an advisory-only compatibility fallback.
    tool_name = get_hook_invoked_runner(data) or _extract_tool_name(data, error_text)
    error_info = _parse_error(error_text)
    strategies = _build_recovery_strategy(error_info, tool_name)

    output = f"""[Error Recovery] Tool: {tool_name} | Type: {error_info['type']}

{chr(10).join(strategies)}

Error summary: {error_info['message'][:200]}
"""
    print(hook_advisory_output(output))

    return 0


if __name__ == "__main__":
    sys.exit(main())

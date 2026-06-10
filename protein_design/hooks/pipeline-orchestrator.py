#!/usr/bin/env python3
"""PostToolUse hook: auto-detect pipeline stage completions and suggest next steps.

When a protein design tool completes, this hook analyzes the result and
suggests the next pipeline stage automatically — reducing the need for
users to manually decide what to do next.

This hook reduces MCP usage by embedding pipeline orchestration logic
directly into the agent's context.
"""

import json
import os
import sys
from typing import Any


def _detect_next_stage(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Detect the next pipeline stage based on completed tool and result."""

    if tool_name == "pdbfixer":
        output_path = result.get("output_path", "")
        return {
            "next_stage": "Stage 1: Backbone Generation (RFdiffusion)",
            "suggestion": f"Preprocessing complete: {output_path}. Now run RFdiffusion to generate backbones.",
            "next_tool": "run_rfdiffusion",
            "tip": "Use the fixed PDB as input_pdb. Set contig based on your design goal.",
            "examples": [
                "Unconditional monomer: contig='[150-150]'",
                "Binder design: contig='[B1-100/0 100-100]' with hotspot_res",
                "Motif scaffolding: contig='[10-40/A163-181/10-40]'",
            ],
        }

    if tool_name == "rfdiffusion":
        structures = result.get("structures", [])
        num_designs = len(structures)
        return {
            "next_stage": "Stage 2: Sequence Design (ProteinMPNN)",
            "suggestion": f"Generated {num_designs} backbones. Now design sequences with ProteinMPNN.",
            "next_tool": "run_proteinmpnn",
            "tip": f"Design {min(8, num_designs * 2)} sequences total. Use sampling_temp='0.1' for reliable sequences.",
            "examples": [
                f"Process each PDB: pdb_path='{structures[0]}'" if structures else "Process each design_*.pdb",
                "For binder-target complexes: use pdb_path_chains='B' to fix target",
                "For diverse libraries: sampling_temp='0.1 0.2 0.3'",
            ],
        }

    if tool_name == "proteinmpnn":
        sequences = result.get("sequences", [])
        num_seqs = len(sequences)
        return {
            "next_stage": "Stage 3: Structure Validation (AlphaFold3)",
            "suggestion": f"Designed {num_seqs} sequences. Now validate with AlphaFold3.",
            "next_tool": "run_alphafold3",
            "tip": "Use convert_format to convert FASTA to AlphaFold3 JSON first.",
            "examples": [
                "Convert: convert_format(fasta → alphafold3_json)",
                "For quick screening: run_data_pipeline=false (skip MSA)",
                "For accuracy: run_data_pipeline=true (requires ~2.6TB DBs)",
            ],
        }

    if tool_name == "alphafold3":
        metrics = result.get("metrics", {})
        plddt = metrics.get("mean_plddt")
        iptm = metrics.get("iptm")
        ptm = metrics.get("ptm")

        has_good_results = False
        if plddt and plddt > 75:
            has_good_results = True
        if iptm and iptm > 0.7:
            has_good_results = True

        if has_good_results:
            return {
                "next_stage": "Stage 4: Filtering & Ranking",
                "suggestion": f"Validation complete. pLDDT={plddt}, ipTM={iptm}, pTM={ptm}. Now filter and rank.",
                "next_tool": "run_filtering",
                "tip": "Set criteria based on your design type.",
                "examples": [
                    "Binder filter: criteria={min_iptm: 0.8, min_plddt: 80}",
                    "Monomer filter: criteria={min_plddt: 80, min_ptm: 0.7}",
                    "Relaxed filter: criteria={min_plddt: 70, min_ptm: 0.5}",
                ],
            }
        else:
            return {
                "next_stage": "Stage 1/2: Regenerate",
                "suggestion": f"Quality metrics are low (pLDDT={plddt}, ipTM={iptm}). Consider regenerating.",
                "next_tool": "run_rfdiffusion or run_proteinmpnn",
                "tip": "Try: more designs, different contig, higher sampling_temp, or partial diffusion.",
                "examples": [
                    "Generate more backbones: num_designs=100",
                    "More diverse sequences: sampling_temp='0.3'",
                    "Try partial diffusion for local redesign",
                ],
            }

    if tool_name == "filtering":
        return {
            "next_stage": "Done or Iterate",
            "suggestion": "Filtering complete. Review top designs or iterate.",
            "next_tool": "analyze_alphafold3_results or run_alphafold3",
            "tip": "For top designs, validate with more seeds. For poor results, relax criteria or regenerate.",
            "examples": [
                "Top design: run_alphafold3 with num_seeds=5, num_samples=10",
                "Iterate: go back to Stage 1 with adjusted parameters",
            ],
        }

    return {
        "next_stage": "Unknown",
        "suggestion": f"Tool {tool_name} completed. Determine next step based on your pipeline.",
        "next_tool": "get_tool_info",
        "tip": "Check available tools with get_tool_info.",
        "examples": [],
    }


def _extract_tool_info(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract tool name and result from hook input data."""
    result = data.get("result") or {}
    if isinstance(result, dict):
        content = result.get("content", [{}])
        if content and isinstance(content, list):
            text = content[0].get("text", "")
            try:
                result_json = json.loads(text)
                # Try to find tool name from result
                tool_name = result_json.get("tool_name", "")
                if not tool_name and "structures" in result_json:
                    tool_name = "rfdiffusion"
                elif not tool_name and "sequences" in result_json:
                    tool_name = "proteinmpnn"
                elif not tool_name and "metrics" in result_json:
                    tool_name = "alphafold3"
                elif not tool_name and "output_path" in result_json:
                    tool_name = "pdbfixer"
                return tool_name, result_json
            except json.JSONDecodeError:
                pass
    return "", {}


def main() -> int:
    """Main entry point."""
    try:
        input_data = sys.stdin.read()
        data = json.loads(input_data) if input_data.strip() else {}
    except Exception:
        return 0

    # Only process successful tool completions
    result = data.get("result", {})
    if isinstance(result, dict) and result.get("isError"):
        return 0

    tool_name, tool_result = _extract_tool_info(data)
    if not tool_name:
        return 0

    # Only activate for protein design tools
    design_tools = {"pdbfixer", "rfdiffusion", "proteinmpnn", "alphafold3", "filtering"}
    if tool_name not in design_tools:
        return 0

    next_stage = _detect_next_stage(tool_name, tool_result)

    output = f"""[Pipeline Orchestrator] {tool_name} completed → {next_stage['next_stage']}

{next_stage['suggestion']}

Next tool: {next_stage['next_tool']}
Tip: {next_stage['tip']}
"""

    if next_stage.get("examples"):
        output += "\nExamples:\n"
        for ex in next_stage["examples"]:
            output += f"  • {ex}\n"

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

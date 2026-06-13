#!/usr/bin/env python3
"""PostToolUse hook: auto-detect pipeline stage completions and suggest next steps.

When a protein design tool completes, this hook analyzes the result and
suggests the next pipeline stage automatically — reducing the need for
users to manually decide what to do next.

This hook embeds pipeline orchestration logic directly into the agent's
context and provides standalone script commands for each stage transition.
"""
import traceback
import json
import os
from typing import Any
import sys
from pathlib import Path


def _get_scripts_dir() -> Path:
    """Get the scripts directory."""
    return Path(__file__).parent.parent.parent / "scripts"


def _build_script_cmd(script_name: str, args: list[str]) -> str:
    """Build a standalone script command."""
    scripts_dir = _get_scripts_dir()
    script_path = scripts_dir / script_name
    if script_path.exists():
        return f"python {script_path} {' '.join(args)}"
    return ""


def _detect_next_stage(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Detect the next pipeline stage based on completed tool and result."""
    scripts_dir = _get_scripts_dir()
    has_scripts = scripts_dir.exists()

    if tool_name == "pdbfixer":
        output_path = result.get("output_path", "")
        cmd = ""
        if has_scripts:
            cmd = _build_script_cmd("run_rfdiffusion.py", [
                f"--input-pdb {output_path}" if output_path else "",
                "--contig '[150-150]'",
                "--num-designs 50",
                "--verbose",
            ]).strip()

        return {
            "next_stage": "Stage 1: Backbone Generation (RFdiffusion)",
            "suggestion": f"Preprocessing complete: {output_path}. Now run RFdiffusion to generate backbones.",
            "script_cmd": cmd,
            "next_skill": "structure-generation",
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
        cmd = ""
        if has_scripts:
            cmd = _build_script_cmd("run_proteinmpnn.py", [
                "--pdb-path 'outputs/design_*.pdb'",
                "--out-folder outputs/sequences/",
                "--num-seq 8",
                "--verbose",
            ])

        return {
            "next_stage": "Stage 2: Sequence Design (ProteinMPNN)",
            "suggestion": f"Generated {num_designs} backbones. Now design sequences with ProteinMPNN.",
            "script_cmd": cmd,
            "next_skill": "sequence-design",
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

        # Build format conversion + validation commands
        convert_cmd = ""
        validate_cmd = ""
        if has_scripts:
            convert_cmd = _build_script_cmd("convert_format.py", [
                "--from fasta",
                "--to alphafold3_json",
                "--input outputs/sequences/seqs.fa",
                "--output af3_input.json",
                "--verbose",
            ])
            validate_cmd = _build_script_cmd("run_alphafold3.py", [
                "--json af3_input.json",
                "--output-dir outputs/af3/",
                "--verbose",
            ])

        return {
            "next_stage": "Stage 3: Structure Validation (AlphaFold3)",
            "suggestion": f"Designed {num_seqs} sequences. Now validate with AlphaFold3.",
            "script_cmds": [convert_cmd, validate_cmd] if convert_cmd else [],
            "next_skill": "structure-validation",
            "tip": "Use convert_format to convert FASTA to AlphaFold3 JSON first, then run AlphaFold3.",
            "examples": [
                "For quick screening: use ESMFold or OmegaFold (no DBs needed)",
                "For accuracy: run_data_pipeline=true (requires ~2.6TB DBs)",
                "For commercial use: Boltz-1 (MIT) or Chai-1 (Apache 2.0)",
            ],
        }

    if tool_name == "alphafold3":
        metrics = result.get("metrics", {})
        plddt = metrics.get("mean_plddt")
        iptm = metrics.get("iptm")
        ptm = metrics.get("ptm")

        filter_cmd = ""
        if has_scripts:
            filter_cmd = _build_script_cmd("run_filtering.py", [
                "--results-dir outputs/af3/",
                "--min-plddt 75",
                "--top-n 10",
                "--verbose",
            ])

        has_good_results = False
        if plddt and plddt > 75:
            has_good_results = True
        if iptm and iptm > 0.7:
            has_good_results = True

        if has_good_results:
            return {
                "next_stage": "Stage 4: Filtering & Ranking",
                "suggestion": f"Validation complete. pLDDT={plddt}, ipTM={iptm}, pTM={ptm}. Now filter and rank.",
                "script_cmd": filter_cmd,
                "next_skill": "filtering-ranking",
                "tip": "Set criteria based on your design type.",
                "examples": [
                    "Binder filter: min_iptm=0.8, min_plddt=80",
                    "Monomer filter: min_plddt=80, min_ptm=0.7",
                    "Relaxed filter: min_plddt=70, min_ptm=0.5",
                ],
            }
        else:
            return {
                "next_stage": "Stage 1/2: Regenerate or Alternative Validation",
                "suggestion": f"Quality metrics are low (pLDDT={plddt}, ipTM={iptm}). Consider regenerating or try alternative validators.",
                "script_cmd": "",
                "next_skill": "structure-generation or sequence-design or cross-validation",
                "tip": "Try: more designs, different contig, higher sampling_temp, partial diffusion, or validate with Boltz-1/Chai-1.",
                "examples": [
                    "Generate more backbones: num_designs=100",
                    "More diverse sequences: sampling_temp='0.3'",
                    "Try partial diffusion for local redesign",
                    "Cross-validate with Boltz-1 (MIT license, complexes)",
                    "Cross-validate with Chai-1 (Apache 2.0, single-seq mode)",
                    "Quick re-screen with ESMFold or OmegaFold",
                ],
            }

    if tool_name == "filtering":
        return {
            "next_stage": "Done or Iterate",
            "suggestion": "Filtering complete. Review top designs or iterate.",
            "script_cmd": "",
            "next_skill": "structure-validation or pipeline-selection",
            "tip": "For top designs, validate with more seeds. For poor results, relax criteria or regenerate.",
            "examples": [
                "Top design: run_alphafold3 with num_seeds=5, num_samples=10",
                "Validate with Boltz-1/Chai-1 for commercial-friendly licensing",
                "Quick re-screen: use ESMFold or OmegaFold for fast turnaround",
                "Iterate: go back to Stage 1 with adjusted parameters",
            ],
        }

    return {
        "next_stage": "Unknown",
        "suggestion": f"Tool {tool_name} completed. Determine next step based on your pipeline.",
        "script_cmd": "",
            "next_skill": "SKILL_INDEX.md",
        "tip": "Read SKILL_INDEX.md to find the right skill for your next step.",
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
    except json.JSONDecodeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

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
"""

    # Add standalone script command if available
    if next_stage.get("script_cmds"):
        output += "\n## Standalone Script Commands\n\n"
        for cmd in next_stage["script_cmds"]:
            if cmd:
                output += f"```bash\n{cmd}\n```\n\n"
    elif next_stage.get("script_cmd"):
        cmd = next_stage["script_cmd"]
        if cmd:
            output += f"""
## Standalone Script Command

```bash
{cmd}
```
"""

    output += f"""
Next Step: Read skill `{next_stage['next_skill']}`
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

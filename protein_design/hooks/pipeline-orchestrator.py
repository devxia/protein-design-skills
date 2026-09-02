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
from typing import Any, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from protein_design.utils import (
    extract_content_text, get_hook_invoked_runner, get_hook_tool_response,
    hook_advisory_output, read_hook_input,
)


def _get_scripts_dir() -> Path:
    """Get the scripts directory."""
    return Path(__file__).parent.parent.parent / "scripts"


def _build_script_cmd(script_name: str, args: list[str]) -> str:
    """Build a standalone script command (empty args are dropped)."""
    scripts_dir = _get_scripts_dir()
    script_path = scripts_dir / script_name
    if script_path.exists():
        return f"python {script_path} {' '.join(a for a in args if a)}"
    return ""


def _as_float(value: Any) -> Optional[float]:
    """Coerce a numeric response field without raising on malformed content."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _detect_next_stage(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Detect the next pipeline stage based on completed tool and result."""
    if not isinstance(result, dict):
        result = {}
    scripts_dir = _get_scripts_dir()
    has_scripts = scripts_dir.exists()

    if tool_name == "pdbfixer":
        output_path = result.get("output_path", "")
        if not isinstance(output_path, (str, int, float)):
            output_path = ""
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
        if not isinstance(structures, list):
            structures = []
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
        if not isinstance(sequences, list):
            sequences = []
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
                "For accuracy: omit --no-msa and provide AlphaFold3 databases (~2.6TB)",
                "For commercial use: Boltz-1 (MIT) or Chai-1 (Apache 2.0)",
            ],
        }

    if tool_name == "alphafold3":
        metrics = result.get("metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}
        plddt = _as_float(metrics.get("mean_plddt"))
        iptm = _as_float(metrics.get("iptm"))
        ptm = _as_float(metrics.get("ptm"))

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
                "Top design: run_alphafold3 with num_seeds=10",
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


def _decode_response(value: Any) -> Optional[dict[str, Any]]:
    """Decode direct, wrapped, or JSON-string responses safely."""
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return None
        return _decode_response(decoded) if isinstance(decoded, (dict, list)) else None

    if isinstance(value, dict):
        if value.get("isError"):
            return value
        recognized = {"status", "structures", "sequences", "metrics", "output_path", "tool_name", "tool"}
        if any(key in value for key in recognized):
            return value

        # Prefer actual response containers over generic text extraction, so
        # an outer wrapper containing JSON text is unwrapped before fallback.
        for key in ("tool_response", "result", "response", "output", "content"):
            if key not in value:
                continue
            nested = value[key]
            if nested is value:
                continue
            decoded = _decode_response(nested)
            if decoded is not None:
                return decoded

        text = extract_content_text(value)
        if text:
            try:
                decoded = json.loads(text)
            except (TypeError, ValueError):
                decoded = None
            if isinstance(decoded, (dict, list)):
                return _decode_response(decoded)
    elif isinstance(value, list):
        for nested in value:
            decoded = _decode_response(nested)
            if decoded is not None:
                return decoded
    return None


def _infer_tool_name(result: dict[str, Any]) -> str:
    """Infer a runner name from recognized result fields."""
    if isinstance(result.get("tool_name"), str) and result["tool_name"].strip():
        return result["tool_name"].strip()
    if isinstance(result.get("tool"), str) and result["tool"].strip():
        return result["tool"].strip()
    if isinstance(result.get("structures"), list):
        return "rfdiffusion"
    if isinstance(result.get("sequences"), list):
        return "proteinmpnn"
    if isinstance(result.get("metrics"), dict):
        return "alphafold3"
    if result.get("output_path"):
        return "pdbfixer"
    return ""


def _extract_tool_info(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract an allowlisted runner and safely decoded response."""
    result = _decode_response(get_hook_tool_response(data))
    runner = get_hook_invoked_runner(data) or ""
    tool_name = runner.removeprefix("run_")
    if not isinstance(result, dict):
        return tool_name, {}
    return tool_name, result


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

    # Only process dict payloads (non-dict JSON is ignored, not an error)
    if not isinstance(data, dict):
        return 0

    # Only process successful tool completions. Prefer the standard response
    # field while retaining legacy result compatibility.
    response = get_hook_tool_response(data)
    decoded_response = _decode_response(response)
    if isinstance(decoded_response, dict) and decoded_response.get("isError"):
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

    print(hook_advisory_output(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())

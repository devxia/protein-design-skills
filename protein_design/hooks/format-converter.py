#!/usr/bin/env python3
"""PostToolUse hook: auto-detect format conversion needs and provide commands.

When ProteinMPNN outputs FASTA that needs conversion for AlphaFold3/Boltz/Chai-1,
this hook provides the exact convert_format parameters or direct CLI commands.
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


def _decode_tool_response(value: Any) -> Optional[dict[str, Any]]:
    """Decode direct, wrapped, or JSON-string tool responses safely."""
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return None
        return _decode_tool_response(decoded) if isinstance(decoded, (dict, list)) else None

    if isinstance(value, dict):
        if value.get("isError"):
            return value
        if any(key in value for key in ("sequences", "fasta", "output_path")):
            return value

        text = extract_content_text(value)
        if text:
            try:
                decoded = json.loads(text)
            except (TypeError, ValueError):
                decoded = None
            if isinstance(decoded, (dict, list)):
                result = _decode_tool_response(decoded)
                if result is not None:
                    return result

        for key in ("tool_response", "result", "response", "output", "content"):
            nested = value.get(key)
            if nested is value:
                continue
            result = _decode_tool_response(nested)
            if result is not None:
                return result
    elif isinstance(value, list):
        for nested in value:
            result = _decode_tool_response(nested)
            if result is not None:
                return result
    return None


def _detect_conversion_need(data: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Detect if format conversion is needed based on tool output."""
    if not isinstance(data, dict):
        return None

    # Trigger only after the allowlisted sequence-design runner.
    if get_hook_invoked_runner(data) not in {"run_proteinmpnn", "run_ligandmpnn", "run_esm_if1"}:
        return None

    # Check if the standard tool_response (or legacy result) contains
    # sequences. The decoder accepts strings, content blocks, direct mappings,
    # and nested response wrappers without assuming a particular host schema.
    tool_result = _decode_tool_response(get_hook_tool_response(data))
    if not isinstance(tool_result, dict) or tool_result.get("isError"):
        return None

    if "sequences" in tool_result or "fasta" in str(tool_result).lower():
        input_path = tool_result.get("output_path", "outputs/sequences.fa")
        return {
            "from_format": "fasta",
            "to_format": "alphafold3_json",
            "input_path": input_path,
        }

    return None


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

    need = _detect_conversion_need(data)
    if not need:
        return 0

    output = f"""[Format Converter] ProteinMPNN output detected → Conversion needed

## Option 1: Standalone Script (Recommended)
```bash
python scripts/convert_format.py \\
    --from fasta \\
    --to alphafold3_json \\
    --input {need['input_path']} \\
    --output outputs/af3_input.json \\
    --verbose
```

## Option 2: Direct Python Script
```python
from Bio import SeqIO
import json

# Read FASTA
sequences = list(SeqIO.parse("{need['input_path']}", "fasta"))

# Convert to AlphaFold3 JSON
af3_input = {{
    "name": "design_validation",
    "sequences": []
}}

for seq in sequences:
    af3_input["sequences"].append({{
        "protein": {{
            "id": seq.id,
            "sequence": str(seq.seq)
        }}
    }})

with open("outputs/af3_input.json", "w") as f:
    json.dump(af3_input, f, indent=2)

print(f"Converted {{len(sequences)}} sequences")
```

## Option 3: Bash One-Liner
```bash
# For single sequence
echo '{{"name":"design","sequences":[{{"protein":{{"id":"A","sequence":"$(cat sequence.fa | grep -v ">")"}}}}]}}' > af3_input.json
```

## For Multi-Chain Complexes
Create the AlphaFold3 JSON input with one `protein` entry per receptor or target chain before running `scripts/run_alphafold3.py`.

## Alternative: Boltz/Chai-1/Protenix Input
These tools accept different formats:
- **Boltz-1**: YAML schema or FASTA with entity types
- **Chai-1**: FASTA with `>protein|name=<id>` or `>ligand|name=<id>` headers
- **Protenix**: YAML config or FASTA

See respective skills for format details.
"""

    print(hook_advisory_output(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())

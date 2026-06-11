#!/usr/bin/env python3
"""PostToolUse hook: auto-detect format conversion needs and provide commands.

When ProteinMPNN outputs FASTA that needs conversion for AlphaFold3/Boltz/Chai-1,
this hook provides the exact convert_format parameters or direct CLI commands.
"""

import json
import sys
from typing import Any


def _detect_conversion_need(data: dict[str, Any]) -> dict[str, Any] | None:
    """Detect if format conversion is needed based on tool output."""
    tool_name = data.get("tool", "")
    result = data.get("result") or {}

    # Only process proteinmpnn completions
    if "proteinmpnn" not in tool_name.lower() and "submit_job" not in tool_name.lower():
        return None

    # Check if result contains sequences (FASTA output)
    if isinstance(result, dict):
        content = result.get("content", [{}])
        if content and isinstance(content, list):
            text = content[0].get("text", "")
            try:
                tool_result = json.loads(text)
                if "sequences" in tool_result or "fasta" in str(tool_result).lower():
                    return {
                        "from_format": "fasta",
                        "to_format": "alphafold3_json",
                        "input_path": tool_result.get("output_path", "outputs/sequences.fa"),
                    }
            except (json.JSONDecodeError, IndexError):
                pass

    return None


def main() -> int:
    """Main entry point."""
    try:
        input_data = sys.stdin.read()
        data = json.loads(input_data) if input_data.strip() else {}
    except Exception:
        return 0

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
If your design includes a receptor/target, add `receptor_pdb` to the convert_format call.

## Alternative: Boltz/Chai-1/Protenix Input
These tools accept different formats:
- **Boltz-1**: YAML schema or FASTA with entity types
- **Chai-1**: FASTA with `|protein|` or `|ligand|` prefixes
- **Protenix**: YAML config or FASTA

See respective skills for format details.
"""

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""PreToolUse hook: provide direct execution alternatives.

When a user is about to use a protein design tool, this hook provides
the equivalent direct shell/Python command.

Priority order:
1. Standalone scripts (scripts/run_*.py) — preferred
2. Direct conda execution — fallback
"""

import json
import os
import sys
from pathlib import Path
from typing import Any


# Project root for finding standalone scripts
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# Standalone script mapping: tool_name -> script_name
STANDALONE_SCRIPTS = {
    "pdbfixer": "run_pdbfixer.py",
    "rfdiffusion": "run_rfdiffusion.py",
    "proteinmpnn": "run_proteinmpnn.py",
    "alphafold3": "run_alphafold3.py",
    "alphafold": "run_alphafold3.py",
    "boltz": "run_boltz.py",
    "boltz1": "run_boltz.py",
    "chai1": "run_chai1.py",
    "chai": "run_chai1.py",
    "omegafold": "run_omegafold.py",
    "esmfold": "run_esmfold.py",
    "filtering": "run_filtering.py",
    "convert_format": "convert_format.py",
}

# Direct execution commands for each tool (fallback)
EXECUTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "rfdiffusion": {
        "conda_env": "SE3nv",
        "base_cmd": "python scripts/run_inference.py",
        "params": {
            "output_prefix": "inference.output_prefix={value}",
            "num_designs": "inference.num_designs={value}",
            "input_pdb": "inference.input_pdb={value}",
            "contig": "contigmap.contigs=['{value}']",
            "hotspot_res": "ppi.hotspot_res=[{value}]",
            "symmetry": "symmetry.symmetry={value}",
            "diffuser_T": "diffuser.T={value}",
            "partial_T": "diffuser.partial_T={value}",
        },
    },
    "proteinmpnn": {
        "conda_env": "proteinmpnn",
        "base_cmd": "python protein_mpnn_run.py",
        "params": {
            "pdb_path": "--pdb_path {value}",
            "output_folder": "--out_folder {value}",
            "num_seq_per_target": "--num_seq_per_target {value}",
            "sampling_temp": "--sampling_temp {value}",
            "pdb_path_chains": "--pdb_path_chains {value}",
        },
    },
    "alphafold3": {
        "conda_env": "alphafold3",
        "base_cmd": "python run_alphafold.py",
        "params": {
            "json_path": "--json_path={value}",
            "output_dir": "--output_dir={value}",
            "model_dir": "--model_dir={value}",
            "db_dir": "--db_dir={value}",
            "num_seeds": "--num_seeds={value}",
        },
    },
    "pdbfixer": {
        "conda_env": "pdbfixer",
        "base_cmd": "python -m pdbfixer",
        "params": {
            "input_pdb": "{value}",
            "output_pdb": "--output={value}",
            "keep_chains": "--keep-chains={value}",
        },
    },
}


def _find_script(tool: str) -> Path | None:
    """Find standalone script for a tool."""
    script_name = STANDALONE_SCRIPTS.get(tool)
    if not script_name:
        return None
    script_path = SCRIPTS_DIR / script_name
    if script_path.exists():
        return script_path
    return None


def _build_script_command(tool: str, params: dict[str, Any]) -> str:
    """Build standalone script command for a tool."""
    script_path = _find_script(tool)
    if not script_path:
        return ""

    cmd_parts = ["python", str(script_path)]

    # Map params to script CLI args
    param_mapping = {
        "pdbfixer": {
            "input_pdb": "--input",
            "output_pdb": "--output",
            "keep_chains": "--keep-chains",
        },
        "rfdiffusion": {
            "input_pdb": "--input-pdb",
            "output_prefix": "--output-prefix",
            "num_designs": "--num-designs",
            "contig": "--contig",
            "hotspot_res": "--hotspot-res",
            "diffuser_T": "--diffuser-t",
        },
        "proteinmpnn": {
            "pdb_path": "--pdb-path",
            "output_folder": "--out-folder",
            "num_seq_per_target": "--num-seq",
            "sampling_temp": "--temp",
            "pdb_path_chains": "--chains",
        },
        "alphafold3": {
            "json_path": "--json",
            "output_dir": "--output-dir",
            "db_dir": "--db-dir",
            "num_seeds": "--num-seeds",
            "run_data_pipeline": "--no-msa",
        },
        "boltz": {
            "input_path": "--input",
            "output_dir": "--out-dir",
            "use_msa_server": None,
        },
        "chai1": {
            "input_path": "--input",
            "output_dir": "--output-dir",
            "use_msa_server": None,
        },
        "omegafold": {
            "fasta_path": "--input",
            "output_dir": "--output-dir",
        },
        "esmfold": {
            "fasta_path": "--input",
            "output_dir": "--output-dir",
        },
        "filtering": {
            "results_dir": "--results-dir",
            "min_plddt": "--min-plddt",
            "min_iptm": "--min-iptm",
            "top_n": "--top-n",
        },
        "convert_format": {
            "from_format": "--from",
            "to_format": "--to",
            "input_path": "--input",
            "output_path": "--output",
            "job_name": "--job-name",
        },
    }

    mapping = param_mapping.get(tool, {})

    for key, value in params.items():
        if key in mapping:
            arg_name = mapping[key]
            if arg_name is None:
                if value:
                    cmd_parts.append(f"--{key}")
                continue

            if isinstance(value, list):
                value_str = ",".join(str(v) for v in value)
            elif isinstance(value, bool):
                if key == "run_data_pipeline" and not value:
                    cmd_parts.append("--no-msa")
                continue
            else:
                value_str = str(value)

            cmd_parts.extend([arg_name, value_str])

    return " ".join(cmd_parts)


def _build_direct_command(tool: str, params: dict[str, Any]) -> str:
    """Build direct shell command for a tool (fallback)."""
    template = EXECUTION_TEMPLATES.get(tool)
    if not template:
        return ""

    cmd_parts = [f"conda run -n {template['conda_env']}", template["base_cmd"]]

    for key, value in params.items():
        if key in template["params"] and value is not None:
            fmt = template["params"][key]
            if isinstance(value, list):
                value_str = ",".join(str(v) for v in value)
            else:
                value_str = str(value)
            cmd_parts.append(fmt.format(value=value_str))

    return " ".join(cmd_parts)


def main() -> int:
    """Main entry point."""
    try:
        text = sys.stdin.read()
        data = json.loads(text) if text.strip() else {}
    except Exception:
        return 0

    tool = data.get("params", {}).get("tool", "")
    params = data.get("params", {}).get("params", {})

    # Check if standalone script is available (preferred)
    script_path = _find_script(tool)
    script_cmd = ""
    if script_path:
        script_cmd = _build_script_command(tool, params)

    # Build legacy direct command (fallback)
    direct_cmd = ""
    if tool in EXECUTION_TEMPLATES:
        direct_cmd = _build_direct_command(tool, params)

    if not script_cmd and not direct_cmd:
        return 0

    output_parts = [f"""[Execution Adapter] Tool execution detected for '{tool}'"""]

    # Option 1: Standalone script (preferred)
    if script_cmd:
        output_parts.append(f"""
## Standalone Script (Recommended)

```bash
{script_cmd} --verbose
```

**Benefits:**
- Direct CLI with --verbose output
- Auto-detects conda environments
- Logs to ~/.protein-design/history.jsonl
- Proper exit codes for scripting
""")

    # Option 2: Direct conda execution (fallback)
    if direct_cmd:
        output_parts.append(f"""
## Direct Conda Execution (Fallback)

```bash
{direct_cmd}
```

**Use when:** Standalone script is not available or you need custom Hydra overrides.
""")

    # Option 3: Background execution
    bg_cmd = script_cmd or direct_cmd
    if bg_cmd:
        output_parts.append(f"""
## Background Execution

```bash
nohup {bg_cmd} > logs/{tool}_$(date +%Y%m%d_%H%M%S).log 2>&1 &
echo $! > logs/{tool}.pid
```

**Monitor:**
```bash
tail -f logs/{tool}_*.log
ps -p $(cat logs/{tool}.pid)
```

**Cancel:**
```bash
kill $(cat logs/{tool}.pid)
```
""")

    output_parts.append("""
---
Tip: All standalone scripts are in the `scripts/` directory. Run with `--help` for full options.
""")

    print("\n".join(output_parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())

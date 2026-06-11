#!/usr/bin/env python3
"""
Standalone Protenix runner.

Usage: python scripts/run_protenix.py --input input.json --output-dir outputs/protenix/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = Protenix not installed / not found
    3 = Execution error
    4 = Invalid arguments
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def get_config():
    """Read protein-design config from YAML or return defaults."""
    config_paths = [
        Path.home() / ".protein-design" / "config.yaml",
        Path.home() / ".kimi-protein-design" / "config.yaml",
    ]
    config = {
        "output_dir": os.environ.get("PROTEIN_DESIGN_OUTPUT_DIR", "/tmp/protein-design"),
    }
    for path in config_paths:
        if path.exists():
            try:
                import yaml
                with open(path) as f:
                    file_config = yaml.safe_load(f) or {}
                config.update(file_config)
            except ImportError:
                pass
            break
    return config


def log_history(tool_name, params, runtime, success, output_dir):
    """Append execution record to history.jsonl for ETA estimation."""
    history_file = Path.home() / ".protein-design" / "history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "tool": tool_name,
        "params": params,
        "runtime": runtime,
        "success": success,
        "timestamp": datetime.now().isoformat(),
    }
    with open(history_file, "a") as f:
        f.write(json.dumps(record) + "\n")


def find_protenix():
    """Locate Protenix installation."""
    # 1. Try direct command
    try:
        result = subprocess.run(
            ["which", "protenix"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return "protenix"
    except FileNotFoundError:
        pass

    # 2. Conda environments
    conda_envs = ["protenix", "protein-design"]
    for env in conda_envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env, "protenix", "--help"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return f"conda run -n {env} protenix"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # 3. pip-installed in current env
    try:
        result = subprocess.run(
            ["python", "-m", "protenix", "--help"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "python -m protenix"
    except FileNotFoundError:
        pass

    # 4. Check if installed as package
    try:
        result = subprocess.run(
            ["python", "-c", "import protenix; print('ok')"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "python_api"
    except FileNotFoundError:
        pass

    return None


def run_protenix(input_file, out_dir, num_recycling=3, verbose=False):
    """Run Protenix prediction."""
    config = get_config()
    protenix_cmd = find_protenix()

    if not protenix_cmd:
        print("ERROR: Protenix not found. Install with: pip install protenix", file=sys.stderr)
        return 2

    if not Path(input_file).exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Build command
    if protenix_cmd == "python_api":
        # Use Python API wrapper
        script_content = f'''
import sys
import json
from pathlib import Path

# Try importing protenix
sys.path.insert(0, ".")
import protenix

input_file = Path("{input_file}")
out_dir = Path("{out_dir}")

with open(input_file) as f:
    data = json.load(f)

print(f"Running Protenix inference on {{input_file.name}}...")
# Protenix API entry point varies by version
# This attempts the most common pattern
try:
    from protenix.model.inference import inference
    result = inference(data, output_dir=str(out_dir), num_recycling={num_recycling})
    print(f"SUCCESS: Output saved to {{out_dir}}")
except Exception as e:
    print(f"ERROR: {{e}}")
    sys.exit(1)
'''
        script_path = out_path / "_protenix_run.py"
        with open(script_path, "w") as f:
            f.write(script_content)

        cmd = ["python", str(script_path)]
    elif protenix_cmd.startswith("conda run"):
        cmd = protenix_cmd.split() + ["predict", str(input_file), "--out_dir", str(out_dir)]
    elif protenix_cmd == "python -m protenix":
        cmd = ["python", "-m", "protenix", "predict", str(input_file), "--out_dir", str(out_dir)]
    else:
        cmd = [protenix_cmd, "predict", str(input_file), "--out_dir", str(out_dir)]

    if num_recycling != 3:
        cmd.extend(["--num_recycling", str(num_recycling)])

    if verbose:
        print(f"Running: {' '.join(cmd)}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200  # 2 hours max
        )
        runtime = time.time() - start_time

        if verbose and result.stdout:
            print(result.stdout[-2000:])

        if result.returncode != 0:
            print(f"ERROR: Protenix failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history("protenix", {"input": input_file}, runtime, False, config["output_dir"])
            return 3

        log_history("protenix", {"input": input_file}, runtime, True, config["output_dir"])

        if verbose:
            print(f"SUCCESS: Protenix completed in {runtime:.1f}s")
            print(f"Output: {out_dir}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: Protenix timed out (>2 hours)", file=sys.stderr)
        log_history("protenix", {"input": input_file}, 7200, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("protenix", {"input": input_file}, time.time() - start_time, False,
                    config["output_dir"])
        return 3
    finally:
        # Cleanup temp script
        temp_script = out_path / "_protenix_run.py"
        if temp_script.exists():
            temp_script.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Run Protenix — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic prediction
  python run_protenix.py --input input.json --output-dir outputs/protenix/

  # With custom recycling steps
  python run_protenix.py --input input.json --output-dir outputs/protenix/ --num-recycling 5

  # From FASTA (auto-convert to Protenix JSON)
  python run_protenix.py --input sequences.fa --output-dir outputs/protenix/ --from-fasta
        """
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input JSON or FASTA file")
    parser.add_argument("--output-dir", "-o", required=True,
                        help="Output directory")
    parser.add_argument("--num-recycling", type=int, default=3,
                        help="Number of recycling steps (default: 3)")
    parser.add_argument("--from-fasta", action="store_true",
                        help="Convert FASTA input to Protenix JSON format")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    input_file = args.input

    # Auto-convert FASTA to JSON if requested
    if args.from_fasta:
        from scripts.convert_format import sequence_to_alphafold3_json
        out_path = Path(args.output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        json_file = out_path / "protenix_input.json"
        sequence_to_alphafold3_json(
            args.input, str(json_file),
            job_name="protenix_run", seed=1
        )
        input_file = str(json_file)
        if args.verbose:
            print(f"Converted FASTA to JSON: {input_file}")

    return run_protenix(
        input_file=input_file,
        out_dir=args.output_dir,
        num_recycling=args.num_recycling,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Standalone ESMFold runner.

Usage: python scripts/run_esmfold.py --input sequences.fasta --output-dir outputs/esmfold/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = ESMFold not installed / not found
    3 = Execution error
    4 = Invalid arguments
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history

import argparse
import subprocess
import time


def find_esmfold():
    """Locate ESMFold installation."""
    # 1. Try pip-installed
    try:
        result = subprocess.run(
            ["python", "-c", "import esm; print(esm.__file__)"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "python_api"
    except FileNotFoundError:
        pass

    # 2. Try direct command
    try:
        result = subprocess.run(
            ["which", "esmfold"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return "esmfold"
    except FileNotFoundError:
        pass

    # 3. Conda environments
    conda_envs = ["esmfold", "esm", "protein-design"]
    for env in conda_envs:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", env, "python", "-c", "import esm; print('ok')"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return f"conda_api:{env}"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return None


def run_esmfold_api(input_file, output_dir, verbose=False):
    """Run ESMFold using Python API (most common installation)."""
    config = get_config("esmfold")

    if not Path(input_file).exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Read sequences
    sequences = []
    current_id = None
    current_seq = []

    with open(input_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                if current_id is not None:
                    sequences.append((current_id, "".join(current_seq)))
                current_id = line[1:].split()[0]
                current_seq = []
            elif line:
                current_seq.append(line)

    if current_id is not None:
        sequences.append((current_id, "".join(current_seq)))

    if verbose:
        print(f"Loaded {len(sequences)} sequence(s)")

    # Run ESMFold via Python script
    script_content = f'''
sys.path.insert(0, ".")
import torch
import esm

# Load model
model = esm.pretrained.esmfold_v1()
model = model.eval().cuda()

sequences = {sequences!r}
output_dir = Path("{output_dir}")

for seq_id, seq in sequences:
    if len(seq) > 2000:
        print(f"Warning: Sequence {{seq_id}} too long ({{len(seq)}} aa), truncating to 2000")
        seq = seq[:2000]

    print(f"Folding {{seq_id}} ({{len(seq)}} aa)...")
    with torch.no_grad():
        output = model.infer_pdb(seq)

    out_file = output_dir / f"{{seq_id}}.pdb"
    with open(out_file, "w") as f:
        f.write(output)
    print(f"  Saved: {{out_file}}")

print("Done!")
'''

    script_path = out_path / "_esmfold_run.py"
    with open(script_path, "w") as f:
        f.write(script_content)

    start_time = time.time()
    try:
        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=3600
        )
        runtime = time.time() - start_time

        if verbose and result.stdout:
            print(result.stdout)

        if result.returncode != 0:
            print(f"ERROR: ESMFold failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history("esmfold", {"input": input_file}, runtime, False, config["output_dir"])
            return 3

        log_history("esmfold", {"input": input_file}, runtime, True, config["output_dir"])

        if verbose:
            print(f"SUCCESS: ESMFold completed in {runtime:.1f}s")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: ESMFold timed out (>1 hour)", file=sys.stderr)
        log_history("esmfold", {"input": input_file}, 3600, False, config["output_dir"])
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history("esmfold", {"input": input_file}, time.time() - start_time, False,
                    config["output_dir"])
        return 3
    finally:
        # Cleanup temp script
        if script_path.exists():
            script_path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Run ESMFold — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic prediction
  python run_esmfold.py --input sequences.fasta --output-dir outputs/esmfold/

  # For very fast screening (single sequence)
  python run_esmfold.py --input single_seq.fa --output-dir outputs/esmfold/ --verbose
        """
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input FASTA file")
    parser.add_argument("--output-dir", "--out-dir", "-o", required=True,
                        help="Output directory")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return run_esmfold_api(
        input_file=args.input,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())

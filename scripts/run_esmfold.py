#!/usr/bin/env python3
"""
Standalone ESMFold runner.

Usage: python scripts/run_esmfold.py --input sequences.fasta --output-dir outputs/esmfold/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = ESMFold not installed / not found (argparse usage errors also exit 2)
    3 = Execution error
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history, read_fasta
from protein_design.conda_utils import probe_conda_envs

import argparse
import subprocess
import time


def _check_esm_installed() -> bool:
    """True when the ESMFold Python dependencies (torch, esm) are importable."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import torch, esm"],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def find_esmfold_python(config):
    """Return the Python interpreter prefix that can import torch and esm.

    Returns a list like ``["conda", "run", "-n", env, "python"]`` or
    ``[sys.executable]``, or ``None`` if ESMFold is not importable anywhere.
    """
    # 1. Configured path / environment variable: a Python interpreter with
    #    the esm dependencies importable.
    if config.get("esmfold_path"):
        path = Path(config["esmfold_path"])
        if path.exists():
            return [str(path)]

    # 2. Conda environment with the dependencies importable.
    env = probe_conda_envs(
        ["esmfold", "esm", "protein-design"],
        ["python", "-c", "import torch, esm"],
    )
    if env is not None:
        return ["conda", "run", "-n", env, "python"]

    # 3. Current interpreter can import the dependencies.
    if _check_esm_installed():
        return [sys.executable]

    return None


def run_esmfold_api(input_file, output_dir, verbose=False):
    """Run ESMFold using Python API (most common installation)."""
    config = get_config("esmfold")

    if not Path(input_file).exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    # Probe the dependency before doing any work so a missing install exits 2
    # (as documented) instead of surfacing as a generic execution failure.
    python_prefix = find_esmfold_python(config)
    if not python_prefix:
        print("ERROR: ESMFold is not installed (import torch, esm failed). "
              "Install from: https://github.com/facebookresearch/esm", file=sys.stderr)
        return 2

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Read sequences via the shared FASTA parser.
    sequences = read_fasta(input_file)

    if not sequences:
        print(f"ERROR: No sequences found in FASTA file: {input_file}", file=sys.stderr)
        return 1

    # ESMFold truncates sequences longer than 2000 aa below; surface that
    # destructive behaviour even when --verbose is off.
    for seq_id, seq in sequences:
        if len(seq) > 2000:
            print(f"NOTICE: Sequence {seq_id} is {len(seq)} aa and will be "
                  f"truncated to 2000 aa")

    if verbose:
        print(f"Loaded {len(sequences)} sequence(s)")

    # Run ESMFold via Python script
    script_content = f'''
import sys
from pathlib import Path

sys.path.insert(0, ".")
import torch
import esm

# Load model
model = esm.pretrained.esmfold_v1()
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.eval().to(device)

sequences = {sequences!r}
output_dir = Path(sys.argv[1])

for seq_id, seq in sequences:
    if len(seq) > 2000:
        print(f"Warning: Sequence {{seq_id}} too long ({{len(seq)}} aa), truncating to 2000")
        seq = seq[:2000]

    print(f"Folding {{seq_id}} ({{len(seq)}} aa)...")
    with torch.no_grad():
        output = model.infer_pdb(seq)

    out_file = output_dir / f"{{seq_id}}.pdb"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"  Saved: {{out_file}}")

print("Done!")
'''

    script_path = out_path / "_esmfold_run.py"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    start_time = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), str(out_path)],
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

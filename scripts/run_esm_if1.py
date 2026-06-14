#!/usr/bin/env python3
"""
Standalone ESM-IF1 inverse-folding runner.

Usage: python scripts/run_esm_if1.py --pdb-path structure.pdb --output-path outputs/esm_if1_seqs.fa [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = ESM-IF1 not installed / not found
    3 = Execution error
    4 = Invalid arguments

Upstream references:
    - https://github.com/facebookresearch/esm
    - ESM-IF1 paper: https://www.science.org/doi/10.1126/science.ade2574
    - CLI script: examples/inverse_folding/sample_sequences.py
    - Usage: python sample_sequences.py <pdbfile> --chain C --temperature 1 \
             --num-samples 3 --outpath output.fasta [--multichain-backbone]
    - The fair-esm pip package also exposes: python -m esm.inverse_folding.cli
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history

import argparse
import subprocess
import time


def find_esm_if1(config):
    """Locate ESM-IF1 installation."""
    # 1. Configured path / environment variable
    if config.get("esm_if1_path"):
        path = Path(config["esm_if1_path"])
        if path.exists():
            return str(path)

    # 2. Common ESM repo locations (sample_sequences.py is the canonical CLI)
    common_paths = [
        Path.home() / "esm" / "examples" / "inverse_folding" / "sample_sequences.py",
        Path.home() / "ESM" / "examples" / "inverse_folding" / "sample_sequences.py",
        Path.home() / "fair-esm" / "examples" / "inverse_folding" / "sample_sequences.py",
        Path("/opt/esm/examples/inverse_folding/sample_sequences.py"),
        Path("/usr/local/esm/examples/inverse_folding/sample_sequences.py"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    # 3. Conda environments: prefer the sample script; fall back to module CLI
    conda_envs = ["esm_if1", "esm", "protein-design"]
    for env in conda_envs:
        try:
            # Canonical upstream CLI: examples/inverse_folding/sample_sequences.py
            result = subprocess.run(
                ["conda", "run", "-n", env, "find", str(Path.home()), "-name", "sample_sequences.py",
                 "-path", "*/inverse_folding/*"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                script = result.stdout.strip().split("\n")[0]
                return f"conda run -n {env} python {script}"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        try:
            # Optional fair-esm module CLI (only if it actually exists)
            result = subprocess.run(
                ["conda", "run", "-n", env, "python", "-c",
                 "import esm.inverse_folding.cli; print('ok')"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return f"conda run -n {env} python -m esm.inverse_folding.cli"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # 4. Try pip-installed module CLI in the current interpreter
    try:
        result = subprocess.run(
            ["python", "-c", "import esm.inverse_folding.cli; print('ok')"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "python -m esm.inverse_folding.cli"
    except FileNotFoundError:
        pass

    return None


def run_esm_if1(pdb_path, output_path, chain=None, temperature=None,
                num_sequences=None, multichain_backbone=False, verbose=False):
    """Run ESM-IF1 sequence design with given parameters."""
    config = get_config("esm_if1")
    esm_if1_script = find_esm_if1(config)

    if not esm_if1_script:
        print(
            "ERROR: ESM-IF1 not found. Install from: "
            "https://github.com/facebookresearch/esm or run "
            "`pip install fair-esm`",
            file=sys.stderr,
        )
        return 2

    if not Path(pdb_path).exists():
        print(f"ERROR: Input file not found: {pdb_path}", file=sys.stderr)
        return 1

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build command
    if esm_if1_script.startswith("conda run"):
        cmd = esm_if1_script.split()
    elif esm_if1_script.startswith("python -m"):
        cmd = esm_if1_script.split()
    else:
        cmd = ["python", esm_if1_script]

    # The sample_sequences.py CLI takes the PDB file as a positional argument;
    # the pip module CLI uses --pdbfile.
    uses_pdbfile_flag = "-m" in cmd and "esm.inverse_folding.cli" in cmd
    if uses_pdbfile_flag:
        cmd.extend(["--pdbfile", pdb_path])
    else:
        cmd.append(pdb_path)

    if chain is not None:
        cmd.extend(["--chain", chain])
    if temperature is not None:
        cmd.extend(["--temperature", str(temperature)])
    if num_sequences is not None:
        cmd.extend(["--num-samples", str(num_sequences)])
    if multichain_backbone:
        cmd.append("--multichain-backbone")

    cmd.extend(["--outpath", output_path])

    if verbose:
        print(f"Running: {' '.join(cmd)}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes max
        )
        runtime = time.time() - start_time

        if verbose and result.stdout:
            print(result.stdout[-2000:])

        if result.returncode != 0:
            print(f"ERROR: ESM-IF1 failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history(
                "esm_if1",
                {"pdb_path": pdb_path, "output_path": output_path},
                runtime,
                False,
                config["output_dir"],
            )
            return 3

        if not out_path.exists():
            print("WARNING: Expected output file not found", file=sys.stderr)

        log_history(
            "esm_if1",
            {"pdb_path": pdb_path, "output_path": output_path},
            runtime,
            True,
            config["output_dir"],
        )

        if verbose:
            print(f"SUCCESS: ESM-IF1 completed in {runtime:.1f}s")
            print(f"Output: {output_path}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: ESM-IF1 timed out (>30 minutes)", file=sys.stderr)
        log_history(
            "esm_if1",
            {"pdb_path": pdb_path, "output_path": output_path},
            1800,
            False,
            config["output_dir"],
        )
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history(
            "esm_if1",
            {"pdb_path": pdb_path, "output_path": output_path},
            time.time() - start_time,
            False,
            config["output_dir"],
        )
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run ESM-IF1 inverse folding — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic sequence design
  python run_esm_if1.py --pdb-path structure.pdb --output-path outputs/esm_if1_seqs.fa

  # Design a specific chain with more sequences
  python run_esm_if1.py --pdb-path structure.pdb --chain A --num-sequences 8 \
      --temperature 1.0 --output-path outputs/esm_if1_seqs.fa

  # Condition on the whole complex backbone
  python run_esm_if1.py --pdb-path complex.pdb --chain A --multichain-backbone \
      --output-path outputs/esm_if1_seqs.fa
        """
    )
    parser.add_argument("--pdb-path", "-p", required=True,
                        help="Input PDB or mmCIF file")
    parser.add_argument("--output-path", "-o", required=True,
                        help="Output FASTA file path")
    parser.add_argument("--chain", "-c",
                        help="Chain ID to design")
    parser.add_argument("--temperature", "-t", type=float, default=1.0,
                        help="Sampling temperature (default: 1.0)")
    parser.add_argument("--num-sequences", "-n", type=int, default=1,
                        help="Number of sequences to sample (default: 1)")
    parser.add_argument("--multichain-backbone", action="store_true",
                        help="Condition on all chains in the complex")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return run_esm_if1(
        pdb_path=args.pdb_path,
        output_path=args.output_path,
        chain=args.chain,
        temperature=args.temperature,
        num_sequences=args.num_sequences,
        multichain_backbone=args.multichain_backbone,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())

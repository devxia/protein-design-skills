#!/usr/bin/env python3
"""
Standalone ColabFold runner.

Usage: python scripts/run_colabfold.py --input sequences.fasta --output-dir outputs/colabfold/ [options]

Exit codes:
    0 = Success
    1 = Input file not found
    2 = ColabFold not installed / not found
    3 = Execution error
    4 = Invalid arguments

Upstream references:
    - https://github.com/sokrypton/ColabFold
    - https://github.com/YoshitakaMo/localcolabfold (local install guide)
    - CLI entry point: colabfold_batch input.fasta output_dir [flags]
    - Common flags: --num-models, --num-recycle, --msa-mode, --model-type,
      --amber, --templates, --pair-mode, --random-seed, --max-msa
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.utils import get_config, log_history

import argparse
import subprocess
import time


def find_colabfold(config):
    """Locate ColabFold installation."""
    # 1. Configured path / environment variable
    if config.get("colabfold_path"):
        path = Path(config["colabfold_path"])
        if path.exists():
            return str(path)

    # 2. Direct command on PATH
    try:
        result = subprocess.run(
            ["which", "colabfold_batch"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass

    # 3. Common install locations
    common_paths = [
        Path.home() / "localcolabfold" / "localcolabfold" / "colabfold-conda" / "bin" / "colabfold_batch",
        Path.home() / "ColabFold" / "colabfold_batch",
        Path("/opt/ColabFold/colabfold_batch"),
        Path("/usr/local/ColabFold/colabfold_batch"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    # 4. Conda environments
    conda_envs = ["colabfold", "cf", "protein-design"]
    for env in conda_envs:
        try:
            # Check whether colabfold_batch is available in the env
            result = subprocess.run(
                ["conda", "run", "-n", env, "which", "colabfold_batch"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return f"conda run -n {env} colabfold_batch"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return None


def run_colabfold(input_file, output_dir, num_models=None, msa_mode=None,
                  recycle=None, model_type=None, amber=False, templates=False,
                  pair_mode=None, random_seed=None, max_msa=None, verbose=False):
    """Run ColabFold batch prediction with given parameters."""
    config = get_config("colabfold")
    colabfold_cmd = find_colabfold(config)

    if not colabfold_cmd:
        print(
            "ERROR: ColabFold not found. Install from: "
            "https://github.com/sokrypton/ColabFold or "
            "https://github.com/YoshitakaMo/localcolabfold",
            file=sys.stderr,
        )
        return 2

    if not Path(input_file).exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        return 1

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Build command
    if colabfold_cmd.startswith("conda run"):
        cmd = colabfold_cmd.split()
    else:
        cmd = [colabfold_cmd]

    cmd.extend([input_file, output_dir])

    if num_models is not None:
        cmd.extend(["--num-models", str(num_models)])
    if msa_mode is not None:
        cmd.extend(["--msa-mode", msa_mode])
    if recycle is not None:
        cmd.extend(["--num-recycle", str(recycle)])
    if model_type is not None:
        cmd.extend(["--model-type", model_type])
    if pair_mode is not None:
        cmd.extend(["--pair-mode", pair_mode])
    if random_seed is not None:
        cmd.extend(["--random-seed", str(random_seed)])
    if max_msa is not None:
        cmd.extend(["--max-msa", max_msa])
    if amber:
        cmd.append("--amber")
    if templates:
        cmd.append("--templates")

    if verbose:
        print(f"Running: {' '.join(cmd)}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour max
        )
        runtime = time.time() - start_time

        if verbose and result.stdout:
            print(result.stdout[-2000:])

        if result.returncode != 0:
            print(f"ERROR: ColabFold failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            log_history(
                "colabfold",
                {"input": input_file, "output_dir": output_dir},
                runtime,
                False,
                config["output_dir"],
            )
            return 3

        log_history(
            "colabfold",
            {"input": input_file, "output_dir": output_dir},
            runtime,
            True,
            config["output_dir"],
        )

        if verbose:
            print(f"SUCCESS: ColabFold completed in {runtime:.1f}s")
            print(f"Output: {output_dir}")

        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: ColabFold timed out (>1 hour)", file=sys.stderr)
        log_history(
            "colabfold",
            {"input": input_file, "output_dir": output_dir},
            3600,
            False,
            config["output_dir"],
        )
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_history(
            "colabfold",
            {"input": input_file, "output_dir": output_dir},
            time.time() - start_time,
            False,
            config["output_dir"],
        )
        return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run ColabFold — standalone execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic batch prediction
  python run_colabfold.py --input sequences.fasta --output-dir outputs/colabfold/

  # Fast single-sequence mode with fewer models
  python run_colabfold.py --input sequences.fasta --output-dir outputs/colabfold/ \
      --msa-mode single_sequence --num-models 1 --recycle 3

  # Multimer prediction with templates
  python run_colabfold.py --input complex.fasta --output-dir outputs/colabfold/ \
      --model-type AlphaFold2-multimer-v3 --templates --num-models 5
        """
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input FASTA file")
    parser.add_argument("--output-dir", "--out-dir", "-o", required=True,
                        help="Output directory")
    parser.add_argument("--num-models", "-n", type=int,
                        help="Number of AlphaFold2 models to run (1-5)")
    parser.add_argument("--msa-mode",
                        help="MSA mode: MMseqs2 (UniRef+Environmental), "
                             "MMseqs2 (UniRef only), single_sequence")
    parser.add_argument("--recycle", "-r", type=int,
                        help="Number of recycles (maps to --num-recycle)")
    parser.add_argument("--model-type",
                        help="Model type: auto, AlphaFold2-ptm, AlphaFold2-multimer, etc.")
    parser.add_argument("--pair-mode",
                        help="Pair mode: unpaired, paired, unpaired+paired")
    parser.add_argument("--random-seed", type=int,
                        help="Random seed")
    parser.add_argument("--max-msa",
                        help="Max MSA size, e.g. 512:1024")
    parser.add_argument("--amber", action="store_true",
                        help="Run Amber relaxation")
    parser.add_argument("--templates", action="store_true",
                        help="Use templates")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    return run_colabfold(
        input_file=args.input,
        output_dir=args.output_dir,
        num_models=args.num_models,
        msa_mode=args.msa_mode,
        recycle=args.recycle,
        model_type=args.model_type,
        amber=args.amber,
        templates=args.templates,
        pair_mode=args.pair_mode,
        random_seed=args.random_seed,
        max_msa=args.max_msa,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())

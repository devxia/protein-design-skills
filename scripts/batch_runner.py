#!/usr/bin/env python3
"""
Standalone batch pipeline runner.
Usage: python scripts/batch_runner.py --config pipeline.yaml
       python scripts/batch_runner.py --stage 1 --input target.pdb --contig "150-150"

Runs complete or partial protein design pipelines using standalone scripts.

Exit codes:
    0 = Pipeline completed successfully
    1 = Stage failed
    2 = Invalid config
    3 = Input not found
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def run_stage(stage_name: str, command: list[str], verbose: bool = False) -> bool:
    """Run a pipeline stage and return success status."""
    if verbose:
        print(f"\n{'=' * 60}")
        print(f"Stage: {stage_name}")
        print(f"Command: {' '.join(command)}")
        print(f"{'=' * 60}")

    start = time.time()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hours per stage
        )
        runtime = time.time() - start

        if result.returncode == 0:
            if verbose:
                print(f"✅ {stage_name} completed in {runtime:.1f}s")
            return True
        else:
            print(f"❌ {stage_name} failed (exit code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr[-2000:], file=sys.stderr)
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ {stage_name} timed out (>2 hours)", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ {stage_name} error: {e}", file=sys.stderr)
        return False


def run_pipeline_stages(stages: list[dict], verbose: bool = False) -> bool:
    """Run a sequence of pipeline stages."""
    for i, stage in enumerate(stages, 1):
        stage_name = stage.get("name", f"Stage {i}")
        command = stage.get("command", [])

        if not command:
            print(f"WARNING: No command for {stage_name}", file=sys.stderr)
            continue

        success = run_stage(stage_name, command, verbose)
        if not success:
            print(f"\n⏹️ Pipeline stopped at {stage_name}", file=sys.stderr)
            return False

    if verbose:
        print(f"\n{'=' * 60}")
        print("✅ All stages completed successfully!")
        print(f"{'=' * 60}")

    return True


def build_standard_pipeline(args) -> list[dict]:
    """Build standard 5-stage pipeline from CLI args."""
    stages = []
    scripts_dir = Path(__file__).parent

    # Stage 0: PDBFixer (if input PDB provided)
    if args.input_pdb and args.stage <= 0:
        stages.append({
            "name": "Stage 0: PDBFixer",
            "command": [
                "python", str(scripts_dir / "run_pdbfixer.py"),
                "--input", args.input_pdb,
                "--output", args.output_dir / "fixed.pdb",
                "--verbose",
            ],
        })

    # Stage 1: RFdiffusion (if backbone generation requested)
    if args.contig and args.stage <= 1:
        input_pdb = args.output_dir / "fixed.pdb" if args.input_pdb else None
        cmd = [
            "python", str(scripts_dir / "run_rfdiffusion.py"),
            "--contig", args.contig,
            "--num-designs", str(args.num_designs),
            "--output-prefix", str(args.output_dir / "design"),
            "--verbose",
        ]
        if input_pdb and input_pdb.exists():
            cmd.extend(["--input-pdb", str(input_pdb)])
        if args.hotspot_res:
            cmd.extend(["--hotspot-res", args.hotspot_res])

        stages.append({
            "name": "Stage 1: RFdiffusion",
            "command": cmd,
        })

    # Stage 2: ProteinMPNN (if sequence design requested)
    if args.stage <= 2:
        stages.append({
            "name": "Stage 2: ProteinMPNN",
            "command": [
                "python", str(scripts_dir / "run_proteinmpnn.py"),
                "--pdb-path", str(args.output_dir / "design_*.pdb"),
                "--out-folder", str(args.output_dir / "sequences"),
                "--num-seq", str(args.num_seq_per_target),
                "--verbose",
            ],
        })

    # Stage 3: Validation (if requested)
    if args.validator and args.stage <= 3:
        validator_scripts = {
            "alphafold3": "run_alphafold3.py",
            "boltz": "run_boltz.py",
            "chai1": "run_chai1.py",
            "omegafold": "run_omegafold.py",
            "esmfold": "run_esmfold.py",
            "protenix": "run_protenix.py",
            "openfold3": "run_openfold3.py",
        }
        script_name = validator_scripts.get(args.validator)
        if script_name:
            # First convert FASTA to appropriate format
            if args.validator == "alphafold3":
                stages.append({
                    "name": "Stage 3a: Format Conversion",
                    "command": [
                        "python", str(scripts_dir / "convert_format.py"),
                        "--from", "fasta",
                        "--to", "alphafold3_json",
                        "--input", str(args.output_dir / "sequences" / "seqs.fa"),
                        "--output", str(args.output_dir / "af3_input.json"),
                        "--verbose",
                    ],
                })
                stages.append({
                    "name": "Stage 3b: AlphaFold3",
                    "command": [
                        "python", str(scripts_dir / script_name),
                        "--json", str(args.output_dir / "af3_input.json"),
                        "--output-dir", str(args.output_dir / "validation"),
                        "--verbose",
                    ],
                })
            else:
                stages.append({
                    "name": f"Stage 3: {args.validator}",
                    "command": [
                        "python", str(scripts_dir / script_name),
                        "--input", str(args.output_dir / "sequences" / "seqs.fa"),
                        "--output-dir", str(args.output_dir / "validation"),
                        "--verbose",
                    ],
                })

    # Stage 4: Filtering (if validation was run)
    if args.stage <= 4 and (args.validator or args.stage <= 3):
        stages.append({
            "name": "Stage 4: Filtering",
            "command": [
                "python", str(scripts_dir / "run_filtering.py"),
                "--results-dir", str(args.output_dir / "validation"),
                "--min-plddt", str(args.min_plddt),
                "--top-n", str(args.top_n),
                "--verbose",
            ],
        })

    return stages


def load_pipeline_config(config_path: Path) -> list[dict]:
    """Load pipeline config from YAML or JSON file."""
    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except ImportError:
        with open(config_path) as f:
            config = json.load(f)
    except Exception as e:
        print(f"ERROR: Could not load config: {e}", file=sys.stderr)
        return []

    stages = config.get("stages", [])
    scripts_dir = Path(__file__).parent

    # Resolve script paths
    for stage in stages:
        cmd = stage.get("command", [])
        if cmd and cmd[0].startswith("scripts/"):
            cmd[0] = str(scripts_dir / cmd[0].replace("scripts/", ""))
            stage["command"] = cmd

    return stages


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run protein design pipeline using standalone scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline from config
  python batch_runner.py --config pipeline.yaml

  # Run complete standard pipeline
  python batch_runner.py --input-pdb target.pdb --contig "150-150" --validator omegafold

  # Run from Stage 2 (skip preprocessing + backbone generation)
  python batch_runner.py --stage 2 --validator alphafold3

  # Quick screening pipeline
  python batch_runner.py --contig "100-100" --validator esmfold --num-designs 100

  # Binder design pipeline
  python batch_runner.py --input-pdb target.pdb --contig "[B1-100/0 100-100]" \
    --hotspot-res A30,A33 --validator boltz
        """
    )

    # Config file option
    parser.add_argument("--config", "-c", type=Path,
                        help="Pipeline config file (YAML or JSON)")

    # Direct pipeline options
    parser.add_argument("--input-pdb", "-i", type=Path,
                        help="Input PDB file (triggers Stage 0)")
    parser.add_argument("--contig",
                        help="Contig for backbone generation (triggers Stage 1)")
    parser.add_argument("--hotspot-res",
                        help="Hotspot residues for binder design")
    parser.add_argument("--validator",
                        choices=["alphafold3", "boltz", "chai1", "omegafold", "esmfold", "protenix", "openfold3"],
                        help="Validation tool for Stage 3")
    parser.add_argument("--stage", type=int, default=0,
                        help="Start from stage N (0-4, default: 0 = full pipeline)")

    # Common parameters
    parser.add_argument("--output-dir", "-o", type=Path, default=Path("outputs/pipeline"),
                        help="Output directory (default: outputs/pipeline)")
    parser.add_argument("--num-designs", "-n", type=int, default=50,
                        help="Number of designs (default: 50)")
    parser.add_argument("--num-seq", type=int, default=8,
                        help="Sequences per target (default: 8)")
    parser.add_argument("--min-plddt", type=float, default=75.0,
                        help="Minimum pLDDT threshold (default: 75)")
    parser.add_argument("--top-n", type=int, default=10,
                        help="Top N designs to report (default: 10)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load stages
    if args.config:
        if not args.config.exists():
            print(f"ERROR: Config file not found: {args.config}", file=sys.stderr)
            return 3
        stages = load_pipeline_config(args.config)
    else:
        stages = build_standard_pipeline(args)

    if not stages:
        print("ERROR: No pipeline stages to run", file=sys.stderr)
        return 2

    if args.verbose:
        print(f"Pipeline: {len(stages)} stage(s)")
        print(f"Output: {args.output_dir}")

    # Run pipeline
    start_time = time.time()
    success = run_pipeline_stages(stages, verbose=args.verbose)
    total_time = time.time() - start_time

    if success:
        if args.verbose:
            print(f"\nTotal pipeline time: {total_time:.1f}s")
        return 0
    else:
        print(f"\nPipeline failed after {total_time:.1f}s", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

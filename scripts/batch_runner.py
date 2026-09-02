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
    3 = Config file not found
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protein_design.process_utils import run_process


def run_stage(stage_name: str, command: list[str], verbose: bool = False):
    """Run a pipeline stage and return success status."""
    if verbose:
        print(f"\n{'=' * 60}")
        print(f"Stage: {stage_name}")
        print(f"Command: {' '.join(command)}")
        print(f"{'=' * 60}")

    start = time.time()
    try:
        result = run_process(
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
            # A stage without a command is a misconfiguration (e.g. a
            # misspelled ``command:`` key). Treat it as a stage failure
            # (exit 1) instead of silently skipping and exiting 0.
            print(f"ERROR: No command for {stage_name}", file=sys.stderr)
            print(f"\n⏹️ Pipeline stopped at {stage_name}", file=sys.stderr)
            return False

        success = run_stage(stage_name, command, verbose)
        if not success:
            print(f"\n⏹️ Pipeline stopped at {stage_name}", file=sys.stderr)
            return False

    if verbose:
        print(f"\n{'=' * 60}")
        print("✅ All stages completed successfully!")
        print(f"{'=' * 60}")

    return True


def _concat_fasta_command(seq_dir: Path, out_fasta: Path) -> list[str]:
    """Build a command that concatenates all FASTA files in ``seq_dir``.

    The output file itself matches ``*.fa`` and, on pipeline re-runs, would
    otherwise be concatenated back into its own inputs (duplicate sequences),
    so it is explicitly excluded.
    """
    script = (
        "import glob, sys\n"
        "files = sorted(glob.glob(sys.argv[1] + '/*.fa')) + sorted(glob.glob(sys.argv[1] + '/*.fasta'))\n"
        "files = [p for p in files if p != sys.argv[2]]\n"
        "with open(sys.argv[2], 'w') as out:\n"
        "    for p in files:\n"
        "        with open(p) as f:\n"
        "            out.write(f.read())\n"
    )
    return [sys.executable, "-c", script, str(seq_dir), str(out_fasta)]


_SPLIT_CANDIDATES_SCRIPT = r'''
import hashlib
import json
import re
import sys
from pathlib import Path


def read_fasta(path):
    records = []
    current_id = None
    sequence = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_id is not None and sequence:
                    records.append((current_id, "".join(sequence)))
                current_id = line[1:].strip().split()[0] if line[1:].strip() else None
                sequence = []
            elif current_id is not None:
                sequence.append(line)
    if current_id is not None and sequence:
        records.append((current_id, "".join(sequence)))
    return records


def safe_name(value):
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return value or "candidate"


if len(sys.argv) != 4 or sys.argv[1] != "--split-candidates":
    raise SystemExit("usage: --split-candidates SEQUENCE_DIR CANDIDATE_DIR")

sequence_dir = Path(sys.argv[2])
candidate_dir = Path(sys.argv[3])
candidate_dir.mkdir(parents=True, exist_ok=True)
manifest = []
used_names = set()
ignored_names = {"all_sequences.fa", "all_sequences.fasta"}
max_candidate_basename = 120
short_hash_length = 12

for source in sorted(sequence_dir.rglob("*")):
    if not source.is_file() or source.suffix.lower() not in {".fa", ".fasta"}:
        continue
    if source.name.lower() in ignored_names:
        continue
    for record_index, (sequence_id, sequence) in enumerate(read_fasta(source), 1):
        base = safe_name(f"{source.stem}__{record_index}__{sequence_id}")
        if len(base) > max_candidate_basename:
            identity = "\0".join([
                source.relative_to(sequence_dir).as_posix(),
                str(record_index),
                sequence_id,
                sequence,
            ])
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:short_hash_length]
            base = f"{base[:max_candidate_basename - len(digest) - 2]}__{digest}"

        candidate_name = base
        suffix = 2
        while candidate_name in used_names:
            suffix_text = f"_{suffix}"
            candidate_name = f"{base[:max_candidate_basename - len(suffix_text)]}{suffix_text}"
            suffix += 1
        used_names.add(candidate_name)

        fasta_path = candidate_dir / f"{candidate_name}.fa"
        json_path = candidate_dir / f"{candidate_name}.json"
        fasta_path.write_text(f">{candidate_name}\n{sequence}\n", encoding="utf-8")
        json_path.write_text(json.dumps({
            "dialect": "alphafold3",
            "version": 1,
            "name": candidate_name,
            "sequences": [{"protein": {"id": "A", "sequence": sequence}}],
            "modelSeeds": [1],
        }, indent=2), encoding="utf-8")
        manifest.append({
            "name": candidate_name,
            "source": str(source),
            "sequence_id": sequence_id,
            "fasta": str(fasta_path),
            "json": str(json_path),
        })

manifest_path = candidate_dir / "manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
if not manifest:
    print(f"ERROR: No FASTA candidates found in {sequence_dir}", file=sys.stderr)
    raise SystemExit(1)
print(f"Prepared {len(manifest)} candidate(s) in {candidate_dir}")
'''.strip()


_VALIDATE_CANDIDATES_SCRIPT = r'''
import json
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 6 or sys.argv[1] != "--validate-candidates":
    raise SystemExit(
        "usage: --validate-candidates CANDIDATE_DIR VALIDATION_DIR VALIDATOR SCRIPTS_DIR"
    )

candidate_dir = Path(sys.argv[2])
validation_dir = Path(sys.argv[3])
validator = sys.argv[4]
scripts_dir = Path(sys.argv[5])
script_names = {
    "alphafold3": "run_alphafold3.py",
    "boltz": "run_boltz.py",
    "chai1": "run_chai1.py",
    "omegafold": "run_omegafold.py",
    "esmfold": "run_esmfold.py",
    "protenix": "run_protenix.py",
    "openfold3": "run_openfold3.py",
}
if validator not in script_names:
    print(f"ERROR: Unsupported validator: {validator}", file=sys.stderr)
    raise SystemExit(2)

manifest_path = candidate_dir / "manifest.json"
if not manifest_path.exists():
    print(f"ERROR: Candidate manifest not found: {manifest_path}", file=sys.stderr)
    raise SystemExit(1)
with manifest_path.open(encoding="utf-8") as handle:
    manifest = json.load(handle)
if not manifest:
    print("ERROR: Candidate manifest is empty", file=sys.stderr)
    raise SystemExit(1)

validation_dir.mkdir(parents=True, exist_ok=True)
validator_script = scripts_dir / script_names[validator]
for candidate in manifest:
    output_dir = validation_dir / candidate["name"]
    output_dir.mkdir(parents=True, exist_ok=True)
    if validator == "alphafold3":
        command = [
            sys.executable,
            str(validator_script),
            "--json",
            candidate["json"],
            "--output-dir",
            str(output_dir),
            "--verbose",
        ]
    else:
        command = [
            sys.executable,
            str(validator_script),
            "--input",
            candidate["fasta"],
            "--output-dir",
            str(output_dir),
            "--verbose",
        ]
    print(f"Validating candidate {candidate['name']}: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode != 0:
        print(f"ERROR: Candidate validation failed for {candidate['name']} "
              f"(exit code {result.returncode})", file=sys.stderr)
        if result.stderr:
            print(result.stderr[-2000:], file=sys.stderr)
        raise SystemExit(result.returncode or 1)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
'''.strip()


def build_standard_pipeline(args) -> list[dict]:
    """Build standard 5-stage pipeline from CLI args."""
    stages = []
    scripts_dir = Path(__file__).parent
    fixed_pdb = args.output_dir / "fixed.pdb"

    # Stage 0: PDBFixer (if input PDB provided).  Stage 1 below references this
    # future output directly; do not inspect its existence while building the
    # stage list because it is created by this preceding command at runtime.
    if args.input_pdb and args.stage <= 0:
        stages.append({
            "name": "Stage 0: PDBFixer",
            "command": [
                sys.executable, str(scripts_dir / "run_pdbfixer.py"),
                "--input", str(args.input_pdb),
                "--output", str(fixed_pdb),
                "--verbose",
            ],
        })

    # Stage 1: RFdiffusion (if backbone generation requested).  If Stage 0 was
    # built, run_pipeline_stages guarantees this path has been created before
    # this command runs.  For a pipeline started at Stage 1, it is the explicit
    # preprocessed input from the previous run.
    if args.contig and args.stage <= 1:
        cmd = [
            sys.executable, str(scripts_dir / "run_rfdiffusion.py"),
            "--contig", args.contig,
            "--num-designs", str(args.num_designs),
            "--output-prefix", str(args.output_dir / "design"),
            "--verbose",
        ]
        if args.input_pdb:
            cmd.extend(["--input-pdb", str(fixed_pdb), "--skip-preprocessing"])
        if args.hotspot_res:
            cmd.extend(["--hotspot-res", args.hotspot_res])

        stages.append({
            "name": "Stage 1: RFdiffusion",
            "command": cmd,
        })

    # Stage 2: ProteinMPNN (if sequence design requested).  The runner expands
    # this glob and invokes the official single-PDB interface once per target.
    if args.stage <= 2:
        stages.append({
            "name": "Stage 2: ProteinMPNN",
            "command": [
                sys.executable, str(scripts_dir / "run_proteinmpnn.py"),
                "--pdb-path", str(args.output_dir / "design_*.pdb"),
                "--out-folder", str(args.output_dir / "sequences"),
                "--num-seq", str(args.num_seq),
                "--verbose",
            ],
        })

    # Stage 3: Validation (if requested).  Each FASTA record becomes one
    # candidate FASTA and one single-chain AF3 JSON.  Validators are then run
    # one candidate per output directory, never as a multi-chain aggregate.
    if args.validator and args.stage <= 3:
        seq_dir = args.output_dir / "sequences"
        candidate_dir = args.output_dir / "validation_inputs"
        validation_dir = args.output_dir / "validation"
        stages.append({
            "name": "Stage 3a: Split candidates",
            "command": [
                sys.executable, "-c", _SPLIT_CANDIDATES_SCRIPT,
                "--split-candidates", str(seq_dir), str(candidate_dir),
            ],
        })
        validator_scripts = {
            "alphafold3": "run_alphafold3.py",
            "boltz": "run_boltz.py",
            "chai1": "run_chai1.py",
            "omegafold": "run_omegafold.py",
            "esmfold": "run_esmfold.py",
            "protenix": "run_protenix.py",
            "openfold3": "run_openfold3.py",
        }
        if args.validator in validator_scripts:
            stages.append({
                "name": f"Stage 3b: Candidate-wise {args.validator}",
                "command": [
                    sys.executable, "-c", _VALIDATE_CANDIDATES_SCRIPT,
                    "--validate-candidates", str(candidate_dir),
                    str(validation_dir), args.validator, str(scripts_dir),
                ],
            })

    # Stage 4: Filtering.  Keep this stage available when explicitly requested
    # even without a validator; run_filtering reports a missing results
    # directory (or empty results) with its normal, actionable error code.
    if args.stage <= 4:
        stages.append({
            "name": "Stage 4: Filtering",
            "command": [
                sys.executable, str(scripts_dir / "run_filtering.py"),
                "--results-dir", str(args.output_dir / "validation"),
                "--min-plddt", str(args.min_plddt),
                "--top-n", str(args.top_n),
                "--verbose",
            ],
        })

    return stages


def load_pipeline_config(config_path: Path) -> list[dict]:
    """Load pipeline config from YAML or JSON file.

    Any load failure — malformed YAML/JSON, a missing pyyaml fallback, or a
    non-mapping document — produces a readable error and an empty stage list
    (which the caller turns into the documented exit code), never a traceback.
    """
    try:
        import yaml
    except ImportError:
        yaml = None

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) if yaml is not None else json.load(f)
    except Exception as e:
        print(f"ERROR: Could not load config: {e}", file=sys.stderr)
        return []

    if not isinstance(config, dict):
        print(f"ERROR: Invalid config format in {config_path}: expected a mapping with a 'stages' list",
              file=sys.stderr)
        return []

    stages = config.get("stages", [])
    scripts_dir = Path(__file__).parent

    # Resolve script paths anywhere in each command.
    for stage in stages:
        cmd = stage.get("command", [])
        resolved = []
        for token in cmd:
            if isinstance(token, str) and token.startswith("scripts/"):
                resolved.append(str(scripts_dir / token[len("scripts/"):]))
            else:
                resolved.append(token)
        # A bare "python" launcher runs with the interpreter executing this
        # script, so PATH-less setups (e.g. python3-only macOS) still work.
        if resolved and resolved[0] == "python":
            resolved[0] = sys.executable
        stage["command"] = resolved

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
    parser.add_argument("--output-dir", "--out-dir", "-o", type=Path, default=Path("outputs/pipeline"),
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

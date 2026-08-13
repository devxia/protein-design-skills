## Review — `scripts/` (19 files)

### (a) Hard violations (break documented standards in AGENTS.md)

1. **`scripts/job_manager.py:275-280` — `submit` subcommand is unreachable, contradicting the documented usage in AGENTS.md** ("Job management: `python scripts/job_manager.py submit --name rfdiff -- python scripts/run_rfdiffusion.py ...`"). The main parser's `add_subparsers(dest="command")` (line 275) and the submit subparser's positional `submit_parser.add_argument("command", nargs=argparse.REMAINDER)` (line 280) share the same dest; argparse overwrites `args.command` with the remainder list, so `if args.command == "submit":` (line 327) is never true and submit falls through to `parser.print_help(); return 2`. The inner check `if not args.command or args.command[0] == "--"` shows the author expected the list at that point. Verify with: `python scripts/job_manager.py submit --name t -- echo hi`.

2. **`scripts/run_esmfold.py:38-53` — hand-rolled FASTA parser instead of shared util.** AGENTS.md code style: "Reuse `protein_design.utils` for config, FASTA I/O, …". The file imports only `get_config, log_history` and re-implements `read_fasta` inline (`for line in f: ... current_seq.append(line)`).

3. **`scripts/run_esmfold.py:10` — documented exit code never returned.** Docstring declares "2 = ESMFold not installed / not found", but grep confirms no `return 2` exists; a missing `esm` package surfaces as exit 3 via the embedded script's failure. AGENTS.md: "Scripts use explicit non-zero exit codes documented in their module docstrings."

4. **`scripts/summarize_outputs.py:2-3` — misplaced module docstring.** `from __future__ import annotations` precedes the docstring, so the module has no docstring at all; it also omits exit codes. AGENTS.md: "Module-level docstrings describe purpose, usage, and exit codes."

### (b) Judgement calls

- **Duplicated Code** — `run_boltz.py` and `run_chai1.py` are near-identical (`find_boltz`/`find_chai1` at lines 24-58 and the full `run_*` subprocess/timeout/log_history blocks). The same ~50-line try/except/log_history shape repeats across all 13 runners; a shared `_execute(cmd, tool, params, timeout)` helper in `conda_utils` would remove most of it. The repo endorses per-script standalone structure, so this is a call, not a violation.
- **Duplicated Code** — `summarize_outputs.py:35-40 _format_bar` vs `project_dashboard.py:32-38 progress_bar`, and `_quality_distribution` vs `quality_bucket` re-implement the same rendering/bucketing.
- **Correctness** — `run_filtering.py:105`: `d.get("plddt", 100) < min_plddt` defaults missing pLDDT to 100, so designs without a pLDDT always pass the pLDDT gate.
- **Correctness (side effect)** — `run_alphafold3.py:80-90 _set_model_seeds` rewrites the user's input JSON in place when `--num-seeds > 1`, silently mutating their file.
- **Correctness (injection-ish)** — `run_esmfold.py:75-78`: `output_dir` is interpolated into generated Python source (`output_dir = Path("{output_dir}")`); a path containing `"` breaks the generated script.
- **Correctness** — `batch_runner.py:209-216 load_pipeline_config`: if `yaml` is absent and `json.load` raises, the exception propagates (traceback) instead of the documented exit 2. Also docstring "3 = Input not found" is actually used for missing config file (line 307).
- **Fragile** — `run_rfdiffusion.py:104-113`, `run_esm_if1.py:60-68`, `run_ligandmpnn.py:58-66`: `conda run -n <env> find ~ -name run_inference.py` shells `find` inside a conda env and scans the entire home directory with a 10 s timeout — slow and environment-dependent.
- **Speculative Generality / dead params** — `convert_format.py`: `verbose` accepted but unused in `fasta_to_boltz_yaml`, `fasta_to_chai_fasta`, `csv_to_fasta`, `json_results_to_csv`; `fasta_to_chai_fasta` also has unused `i`.
- **Primitive Obsession** — `convert_format.py:30-46 fasta_to_boltz_yaml` builds YAML via string concatenation although `pyyaml` is a core dependency; raw sequence strings aren't escaped.
- **Consistency** — `project_dashboard.py --json` emits `{"dashboard_text": text}` (line 262), not the "machine-readable output" the help text promises; `list_jobs` (job_manager.py:139-160) ignores the `.exit` marker that `get_job_status` treats as authoritative, so zombie-PID jobs show inconsistent status. PID-reuse races in `os.kill(pid, 0)` checks are best-effort.

Good: no `shell=True` anywhere; all 13 runners use explicit timeouts, argparse epilogs, `get_config`/`log_history`/`conda_utils` consistently, and list-form subprocess args.

**Count: 4 hard violations, 11 judgement calls.**
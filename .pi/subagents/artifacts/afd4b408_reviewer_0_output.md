## Review

**Scope note:** I have no shell tool, so I could not run `git diff 77011ce...HEAD`/`git log`. I reviewed the current state of every file named in the remediation list (job_manager, quality-gate, utils escaping/keywords/read_hook_input, all 22 hooks, batch_runner, run_alphafold3, run_esmfold, convert_format, project_dashboard, install-hooks, hooks.json, docs en/zh, and the 11 new/updated test files). The supervisor should run `python -m py_compile scripts/*.py protein_design/hooks/*.py && python -m pytest tests/` to attest the suite.

**Correct (verified against AGENTS.md standards):**
- *Exit codes documented in docstrings*: batch_runner.py:9-13 documents 0–3 including the new `3 = Config file not found` (line 319). ✓
- *Escaping order is correct*: `_escape_powershell` (utils.py:309-325) doubles backticks first, then `"`, `$`, newlines — `\`$(...)` injection is closed. `_escape_applescript` (utils.py:296-306) escapes backslash before quote and flattens CR/LF. ✓
- *Fail-closed gate*: quality-gate.py:91-95 — `is_passing: evaluated > 0 and len(failed) == 0` with explicit `no_metrics_evaluated` FAIL branch. ✓
- *AF3 input immutability*: run_alphafold3.py:82-120 writes a `.seedsN.json` copy into the output dir; the input is never mutated. ✓
- *stdin migration complete*: zero inline `sys.stdin.read()`/`json.load(sys.stdin)` remain in hooks; all 21 stdin-consuming hooks import `read_hook_input`, guarded by `test_hooks_input_migration.py` (incl. a hook-count guard of 22). ✓
- *Keyword canonicalization*: `PROTEIN_DESIGN_KEYWORDS` (utils.py:402-409) matches hooks.json:5 exactly; parity test `test_keyword_pattern.py` prevents drift. ✓
- *YAML safety*: convert_format.py:48 uses `yaml.safe_dump` on a dict instead of f-string serialization. ✓
- *Installer cleanup safety*: install-hooks.py:452-457 deletes legacy files only via `_is_managed_legacy_hook` (canonical names or installer marker). ✓
- *Docs sync*: `--json` documented in both docs/en and docs/zh api-reference/scripts.md. ✓
- *Shared GPU probe*: `probe_gpus` distinguishes `None` (probe failure → fail-open) from `[]` (no GPU); gpu-check-hook.py:20-24 consumes it correctly. ✓

**Hard violations:** none confirmed.

**New bugs:**
- `job_manager.wait` timeout returns `-1` (job_manager.py:240); `sys.exit(-1)` → 255 on POSIX, an exit code not in the docstring's documented set (0/1/2). Standard: "Scripts use explicit non-zero exit codes documented in their module docstrings." If the diff touched `wait`, this is a hard violation; I could not diff to confirm introduction.
- job_manager.py:75-81: if the submitted command's executable is missing, the wrapper's `subprocess.run` raises `FileNotFoundError`; the exit-marker file is never written, so `get_job_status` falls back to PID liveness and reports "completed" with no exit code — and `wait_job` then defaults to exit 0 (line 234), reporting success for a job that never started. Medium-severity gap in the new launcher design.

**Judgement-call smells:**
- *Duplicated Code*: the exit-file/PID liveness block is near-identical in `get_job_status` (job_manager.py:124-138) and `list_jobs` (161-172); a shared `_resolve_status(metadata, exit_file)` helper would remove it.
- *Primitive Obsession / fragile heuristic*: quality-gate.py:69-76 `_detect_design_type` substring-matches `"binder"` over `str(result)`; any incidental "binder" string in the payload flips thresholds. Likely pre-existing, but worth noting.

**Counts:** 0 confirmed hard violations (1 candidate pending git confirmation), 2 new-bug findings, 2 smell notes, 10 verified-correct items.
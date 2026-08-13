## Review — remediation batch vs. spec #16 / tickets #17–#34

**Correct (verified in code, not commit messages):**
- #18 `job_manager.py:325` — REMAINDER gets its own `run_command` dest; leading `--` stripped (line 358); `list` consults `.exit` marker (lines 170–172); no dead branch remains; e2e test exists (`test_job_manager_cli.py`).
- #19 fail-closed both seams — `run_filtering.py:111-114` excludes missing-pLDDT designs and reports them (`missing_plddt_designs` in JSON); `quality-gate.py:99-103,146-150` returns `is_passing=False` with explicit "No evaluable metrics" reason.
- #20 `utils.py:295-326` — PowerShell escapes backtick/`$`/`"`/CR/LF; AppleScript flattens CR/LF; `_run_notifier` uses `text=True` (line 363).
- #21 `run_alphafold3.py:81-121` — seeds expanded into a new file in the output dir; original JSON never written.
- #22 `run_esmfold.py:26-52,58,78` — shared `read_fasta`, dependency probe → exit 2 with install URL, output dir via `sys.argv`.
- #23 `batch_runner.py:214-236,318-326` — missing config → 3, load failures → readable error, no traceback; docstring exit table matches.
- #24 — targeted probes in `run_rfdiffusion.py:112`, `run_esm_if1.py:61`, `run_ligandmpnn.py:45`; no home-wide find.
- #25/#26 — `convert_format.py:48` safe_dump; `project_dashboard.py:159-213` structured `--json` (stages, totals, distribution, `generated_at`); `summarize_outputs.py:1-20` docstring at top with exit codes.
- #27/#28 — all 22 hooks use `read_hook_input()` + `sys.path` bootstrap (22/22 matches); no `sys.stdin` parsing remains; `extract_content_text` guards notify/orchestrator/converter.
- #31/#32/#33/#34 — installer cleanup restricted via `_is_managed_legacy_hook`; manifest version/description tests exist and kimi description matches plugin.json; `_CONFIDENCE_METRIC_KEYS` single tuple used by both branches (`utils.py:208,249,255`); error-recovery has no Chinese strings; en/zh docs both updated (missing-metric semantics, submit syntax, `--json`).

**Partial / wrong against tickets:**
1. **#30 PARTIAL** — spec: "canonical pattern constant in utils, imported by re-matching UserPromptSubmit hooks". Only `session-health-check.py:87` and `tool-recommender.py:315` import `PROTEIN_DESIGN_PATTERN`. Three other re-matching hooks keep divergent inline copies: `parameter-generator.py:278-282`, `auto-parameter-tuner.py:196-199`, `cost-estimator.py:210-213` — their keyword sets disagree with the 30-keyword canonical set (e.g. tuner misses `motif`/`oligomer`/`pdb`), so hooks.json can fire a hook whose own gate then rejects the prompt. The parity test only guards hooks.json vs. utils, not these copies.
2. **#29 PARTIAL** — spec: "overall budget under the 5s hooks.json timeout". `session-health-check.py` runs 3s concurrent probes, then `_check_gpu()` → `probe_gpus()` with the default `timeout=5.0` (`utils.py:368`). A hanging `nvidia-smi` yields ~8s worst case, exceeding the 5s budget; the GPU probe timeout was not shrunk like the import probes.

**Notes:**
- #17 deviation: spec said conftest holds "repo-root sys.path insertion **and hook-module loader**"; the loader is in `tests/helpers.py`, conftest only does sys.path. Functionally equivalent.
- Scope creep: none. All 19 commits map to #17–#34 plus the supervisor-acknowledged #28 hardening (33b73b1).
- Trivial: duplicated comment `session-health-check.py:85-86`.
- ESMFold driver still interpolates sequence *data* into generated source (`{sequences!r}`); spec only required paths via argv — acceptable.

Counts: 2 partial implementations, 1 spec-letter deviation (non-blocking), 0 scope-creep items, 18 tickets fully verified.
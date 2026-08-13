## Review

**Correct**
- `install-hooks.py` implements the documented security rules faithfully: `_resolve_hook_script` (install-hooks.py:115-151) rejects shell metacharacters and enforces that resolved paths stay inside `protein_design/hooks/`, matching AGENTS.md "Hook path validation". `validate_plugin` re-verifies every command in `hooks/hooks.json` exists and resolves inside the allowed dir.
- All hook subprocess calls use argv lists (no `shell=True`), e.g. `gpu-check-hook.py:18-25`, `session-health-check.py:31` — consistent with "Scripts avoid shell=True and construct command lists explicitly".
- `hooks/hooks.json` (22 hooks) matches the documented counts/groupings, and every referenced script exists.
- `gpu-check-hook.py` documents and honours a fail-open contract (exit 0 allow / 2 block), catching `TimeoutExpired` and other errors.

**Hard violations**
1. **AGENTS.md: "Reuse `protein_design.utils` for … notifications, and hook input reading."** — `read_hook_input()` exists at `protein_design/utils.py:354` but is used by **zero** of the 22 hooks. Twenty hooks inline the identical stdin-read/JSON try-except block, e.g. `quality-gate.py:102-110`, `format-converter.py:44-52`, `design-comparator.py:16-17`, `job-monitor.py:28-29`. Only 5 hooks import utils at all (and only for `parse_confidence_json`/`send_notification`).

**Judgement calls**
2. **Duplicated Code** — the same nvidia-smi/disk-usage health check is re-implemented in `gpu-check-hook.py:15-55`, `session-health-check.py:38-62`, `protein-context-inject.py:28-33`, and `user-onboarding.py:86` (identical `nvidia-smi --query-gpu=...` string in 4 files).
3. **Correctness** — `session-health-check.py:16-35` runs 10 sequential `python -c "import …"` probes, each with `timeout=5` (worst case ~50 s), but `hooks/hooks.json` declares `timeout: 5` for this hook — it will be killed before finishing on slow environments.
4. **Correctness** — `quality-gate.py:83-95`: if extracted metrics match none of the design type's threshold keys (e.g. only `iptm` present for a "monomer" gated on plddt/ptm), `passed=[]`, `failed=[]` → `is_passing=True` and it prints "✅ PASS" vacuously — the gate passes without evaluating anything.
5. **Correctness/robustness** — `design-complete-notify.py:44` (`content[0].get("text","")`) sits outside the try block; a non-dict `content[0]` raises `AttributeError` that escapes `main`'s handlers → traceback/exit 1. Same shape at `pipeline-orchestrator.py:200` and `format-converter.py:26` (where the `IndexError` catch is in the wrong place — the `.get` happens before the try).
6. **Shotgun Surgery** — the protein-keyword regex is duplicated between `hooks/hooks.json` (UserPromptSubmit matcher) and inline copies in `session-health-check.py:76-80` and other UserPromptSubmit hooks; adding a keyword requires editing several files.
7. **Inconsistency** — `error-recovery.py:83-110` emits entirely Chinese messages ("GPU 内存不足。解决方案:") while every other hook emits English; the bilingual rule in AGENTS.md covers `docs/`, but mixed-language agent-facing output is a coherence issue.
8. **Over-broad deletion** — `_uninstall_codex` (install-hooks.py:445-449) unlinks every `*protein*.py` in `~/.codex/hooks/` during legacy cleanup; could delete unrelated user files. A marker-based match would be safer.

No blockers. Residual risk: hooks.json fires 9 UserPromptSubmit hooks per matching prompt (serial 5 s timeouts each) — intended behaviour, but worth monitoring.

Count: 1 hard violation, 7 judgement calls.
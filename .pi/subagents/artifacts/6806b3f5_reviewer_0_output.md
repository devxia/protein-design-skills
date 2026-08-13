## Review

### (a) Hard violations

1. **Incomplete PowerShell escaping → command injection** — `protein_design/utils.py:305-307`
   AGENTS.md standard: "`protein_design.utils.send_notification()` invokes platform-specific binaries (`osascript`, `notify-send`, PowerShell) **with escaped strings**". But `_escape_powershell` only escapes `"` and `\`:
   ```python
   return s.replace('"', '`"').replace("\\", "\\\\")
   ```
   In PowerShell double-quoted strings, `$` triggers subexpression/variable expansion, so a notification message containing `$(...)` (e.g. from a tool log) is **executed** inside `powershell -Command` (utils.py:332-334). Newlines and backticks are also unescaped. The AppleScript path (utils.py:301-302) similarly doesn't escape newlines. Escaping must cover `$`, backtick, and CR/LF.

### (b) Judgement calls

1. **Duplicated Code** — the identical 8-key metric tuple appears twice in `parse_confidence_json` (`utils.py:236-245` and `utils.py:251-260`). Extract one module-level constant; a future key addition must currently be made twice.

2. **Duplicated Code** — hook-module loader duplicated: `tests/test_plugin_manifests.py:16-24` (`_load_install_hooks_module`) and `tests/test_hooks_pure.py:8-15` (`_load_hook_module`) are the same shape; likewise `sys.path.insert(0, parents[1])` boilerplate repeats in 5 test files (`test_batch_runner.py`, `test_convert_format.py`, `test_job_manager.py`, `test_run_alphafold3.py`, `test_run_filtering.py`). A shared `tests/conftest.py` would hold both.

3. **Shotgun Surgery risk, no regression net** — version `"0.2.0"` lives in 6 files (`protein_design/__init__.py`, `plugin.json`, `kimi.plugin.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`). All are currently in sync, but `tests/test_plugin_manifests.py` asserts author consistency (`test_all_manifests_use_canonical_author`) while testing **no version consistency** — exactly the kind of drift the file exists to prevent.

4. **Duplicated Code / drift** — the description string is copy-pasted across four manifests; `kimi.plugin.json:3` has already drifted (lacks the "Agent-agnostic" prefix present in `plugin.json:4`, `.claude-plugin/plugin.json:3`, `.codex-plugin/plugin.json:3`). Cosmetic but shows the duplication is unguarded.

5. **Minor consistency** — AGENTS.md subprocess style says `capture_output=True, text=True`; `_run_notifier` (`utils.py:345`) omits `text=True`. Output is discarded, so impact is nil; flagged only as style drift.

### Verified clean
- Manifest placement rules from AGENTS.md hold: `.claude-plugin/plugin.json` has no `category`/`source`/`hooks`; marketplace has `source: "./"` + `category`; codex declares hooks. Versions all `0.2.0`. kimi.plugin.json hook count (22) and script list (19) match AGENTS.md.
- `ci.yml` matches the documented CI commands and Python matrix (3.10–3.12).
- `conda_utils.py` is well-documented and exception handling matches the documented 10s-probe design; tests cover the "conda missing" path.
- `tests/` follow consistent pytest style; smoke tests auto-discover scripts/hooks as documented.

1 hard violation, 5 judgement calls.
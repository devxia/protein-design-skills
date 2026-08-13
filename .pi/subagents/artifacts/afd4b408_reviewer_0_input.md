# Task for reviewer

You are a read-only reviewer for the repo at /Volumes/data/项目：VibeCoding/protein-design-skills . Do NOT edit files.
The change under review: `git diff 77011ce...HEAD` (19 commits, +2696/-405 across 71 files). Commit list: `git log 77011ce..HEAD --oneline`.
This diff is a remediation batch fixing 29 findings from a full-codebase review (GitHub issues #17-#34): job_manager submit fix, fail-closed quality gates, PowerShell/AppleScript escaping, AlphaFold3 input immutability, ESMFold conformance, batch_runner exit codes, tool-discovery probes, YAML serialization, dashboard --json, hook stdin migration to read_hook_input + sys.path bootstrap, shared GPU probe, keyword canonicalization, installer cleanup safety, manifest consistency tests, docs sync.

STANDARDS AXIS:
1. Read AGENTS.md (repo root) — the documented coding standards.
2. Review the diff (use git diff 77011ce...HEAD -- <paths> in slices; also read full files where context is needed).
3. Report: (a) HARD VIOLATIONS of documented standards — cite the rule (file + quote) and the offending hunk (file:line); (b) judgement-call smells from this baseline:
Smell baseline (Fowler, Refactoring ch.3). Two binding rules: (1) a documented repo standard always WINS over this baseline; (2) every smell is a labelled judgement call, never a hard violation. Skip anything tooling already enforces.
- Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, Refused Bequest — report any you spot, naming the smell and quoting the hunk.
4. Also flag concrete NEW bugs introduced by the diff (wrong exit codes, broken argparse, lost error handling, regressions vs the old behavior the diff replaced). Distinguish hard violations from judgement calls. Under 600 words. End with counts.

## Acceptance Contract
Acceptance level: attested
Completion is not accepted from prose alone. End with a structured acceptance report.

Criteria:
- criterion-1: Return concrete findings with file paths and severity when applicable

Required evidence: review-findings, residual-risks

Finish with a fenced JSON block tagged `acceptance-report` in this shape:
Use empty arrays when no items apply; array fields contain strings unless object entries are shown.
`criteriaSatisfied[].status` must be exactly one of: satisfied, not-satisfied, not-applicable.
`commandsRun[].result` must be exactly one of: passed, failed, not-run.
`manualNotes` and `notes` are optional strings; an empty string means no note and does not satisfy `manual-notes` evidence.
```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "specific proof"
    }
  ],
  "changedFiles": [
    "src/file.ts"
  ],
  "testsAddedOrUpdated": [
    "test/file.test.ts"
  ],
  "commandsRun": [
    {
      "command": "command",
      "result": "passed",
      "summary": "short result"
    }
  ],
  "validationOutput": [
    "validation output or concise summary"
  ],
  "residualRisks": [
    "none"
  ],
  "noStagedFiles": true,
  "diffSummary": "short description of the diff",
  "reviewFindings": [
    "blocker: file.ts:12 - issue found, or no blockers"
  ],
  "manualNotes": "anything else the parent should know"
}
```
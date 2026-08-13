# Task for reviewer

You are a read-only code reviewer for the repository at /Volumes/data/项目：VibeCoding/protein-design-skills . Do NOT edit any files. The user asked to review the ENTIRE codebase; your job is one assigned area. Review the current files directly using read/bash (rg, sed, wc) tools.

STEP 1 — Read the documented standards first:
- AGENTS.md (repo root): code style, security considerations, design decisions, testing rules. This is the primary documented standard.
- docs/AGENTS.md: docs maintenance rules (only relevant if your area touches docs/).
- tests/: existing pytest style (relevant when reviewing test files).

STEP 2 — Apply the standards plus this fixed smell baseline:
Smell baseline (Fowler, Refactoring ch.3). Two binding rules: (1) a documented repo standard always WINS over this baseline — where the repo endorses something the baseline would flag, suppress it; (2) every smell is a labelled judgement call, never a hard violation. Skip anything tooling already enforces.
- Mysterious Name — name doesn't reveal what it does/holds. -> rename.
- Duplicated Code — same logic shape in more than one place. -> extract shared shape.
- Feature Envy — method reaches into another object's data more than its own. -> move it.
- Data Clumps — same few fields/params travelling together. -> bundle into one type.
- Primitive Obsession — primitive/string standing in for a domain concept. -> small type.
- Repeated Switches — same if/switch cascade on the same type recurring. -> polymorphism or one shared map.
- Shotgun Surgery — one logical change forces scattered edits across many files. -> gather together.
- Divergent Change — one module edited for several unrelated reasons. -> split.
- Speculative Generality — abstraction/params/hooks added for needs that don't exist. -> delete/inline.
- Message Chains — long a.b().c().d() navigation. -> hide behind one method.
- Middle Man — function/class that mostly just delegates onward. -> cut it.
- Refused Bequest — subclass ignores/overrides most of what it inherits. -> composition.

STEP 3 — Report, per file where relevant:
(a) HARD VIOLATIONS: every place the code breaks a documented standard in AGENTS.md — cite the standard (file + the rule quoted) and quote the offending code with file:line.
(b) JUDGEMENT CALLS: any baseline smell you spot — name the smell and quote the code with file:line.
Also flag concrete correctness/security bugs you notice (e.g., shell injection, unhandled None, wrong exit codes) under (a) if they contradict a documented standard, otherwise under (b).
Rules: focus on real, verifiable issues; no nitpicks tooling would catch; do not suggest features; keep each finding to 1-3 lines. Under 700 words. End with a one-line count: N hard violations, M judgement calls.

YOUR AREA: scripts/ — all 19 *.py files (13 run_*.py tool runners + 6 utilities). Check consistency with the shared conventions (get_config/log_history/conda_utils usage, exit codes, timeouts, argparse epilog, no shell=True).

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
# sync-changelog

Generate and sync the project changelog from git commit history into `docs/en/release-notes/changelog.md` and `docs/zh/release-notes/changelog.md`.

## When To Use

- After a batch of meaningful changes lands on `main` and the maintainer wants to document them
- Before cutting a release tag
- When the user explicitly asks to "update changelog" or "sync release notes"

Do **not** run this for every single commit — only when there is a meaningful batch of changes worth documenting.

## Overview

Source of truth: `git log` on the `main` branch.

Targets:

| File | Role |
|------|------|
| `docs/en/release-notes/changelog.md` | English changelog; source of truth |
| `docs/zh/release-notes/changelog.md` | Chinese changelog; translated from English |

## Workflow

### Step 1: Find The Sync Range

Determine which commits are new since the last sync:

```bash
# Find the most recent version already in the English changelog
head -20 docs/en/release-notes/changelog.md

# Get commits since then
git log --oneline --reverse <last-synced-commit>..HEAD
```

If the changelog is empty (first sync), use all commits from the beginning of the project.

### Step 2: Classify Commits

Use conventional commit prefixes to classify each commit:

| Prefix | Category | Chinese |
|--------|----------|---------|
| `feat:` / `feat(` | Features | 新功能 |
| `fix:` / `fix(` / `hotfix:` | Bug Fixes | 修复 |
| `docs:` / `docs(` | Docs | 文档 |
| `refactor:` / `refactor(` / `chore:` / `ci:` / `test:` | Refactors | 重构 |
| `perf:` / `polish:` / `improve:` | Polish | 优化 |
| (anything else) | Other | 其他 |

For each commit:
- Keep only the subject line (first line)
- Strip the prefix (e.g., `fix: ` → remove)
- Strip PR references like `(#123)` at the end
- Strip commit hash references

### Step 3: Group By Version

If there are release tags (`git tag`), group commits under their nearest preceding tag.

If there are no tags, use date-based grouping or ask the user for a version number.

Example version heading:
```markdown
## 2024-06-01

### Features

- Add cross-conda-environment support for PDBFixer via `conda_env` parameter
- Add `receptor_pdb` support to `convert_format` for multi-chain AF3 JSON
- Add `analyze_alphafold3_results` tool for parsing AF3 output metrics

### Bug Fixes

- Fix missing `import time` in `alphafold.py` causing `submit_job` to crash
- Fix `run_filtering` ignoring top-level metric fields (plddt, iptm, ptm)
- Fix RFdiffusion contig double-bracketing when user provides brackets

### Refactors

- Improve editable-install detection in `check_all_tools`
```

### Step 4: Write English Changelog

Insert new version blocks at the top of `docs/en/release-notes/changelog.md`, after the header:

```markdown
# Changelog

This page documents the changes in each release of the Kimi Protein Design plugin.
```

Rules:
- Newest version first
- Omit empty sections
- Within each section, order by user impact (most impactful first)
- Keep entry text concise (one sentence per entry)

### Step 5: Translate to Chinese

Mirror the English changelog into `docs/zh/release-notes/changelog.md`:

- Preserve version headings (e.g., `## 2024-06-01`)
- Translate section headings:
  - `### Features` → `### 新功能`
  - `### Bug Fixes` → `### 修复`
  - `### Polish` → `### 优化`
  - `### Refactors` → `### 重构`
  - `### Docs` → `### 文档`
  - `### Other` → `### 其他`
- Translate entry body text
- Keep tool names, parameter names, code blocks, and file paths as-is
- Section order and entry counts must match English exactly

### Step 6: Verify

```bash
git diff docs/en/release-notes/changelog.md docs/zh/release-notes/changelog.md
```

Check:
- Version headings match
- Section sets and order match
- Entry counts per section match
- No empty sections

## Commit Message

```
docs(changelog): sync release notes for <version/date>
```

## Stop Signals

- No new commits since last sync
- Uncertain about version grouping (ask user)
- English and Chinese entry counts do not match after translation

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Including every single commit (including "wip", "tmp") | Filter out trivial commits; only document user-facing changes |
| Copying raw commit hashes into changelog | Strip them |
| Rewording commit messages without reason | Keep original meaning; only fix grammar |
| Leaving English text in Chinese changelog | Fully translate body text |
| Creating empty sections | Delete sections with no entries |
| Treating `docs:` commits as Features | Use `Docs` category |

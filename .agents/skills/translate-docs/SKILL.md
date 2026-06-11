---
name: translate-docs
description: Translate and sync bilingual documentation between docs/en/ and docs/zh/, and between README.md and README.zh.md, following source-of-truth rules and terminology table below.
---

# Translate Docs

## Overview

This repository maintains bilingual documentation under `docs/en/` and `docs/zh/` with mirrored directory structures. `README.md` and `README.zh.md` at the repository root are also managed as a mirrored pair. This skill synchronizes the two locales page by page after either side has been updated.

This skill is invoked by `gen-docs` (incremental updates) and may be invoked manually by users to keep documentation in sync.

## Prerequisites

If any of the following are missing, stop and report to the user before continuing:

- `docs/en/` and `docs/zh/` with mirrored directory structures.
- `README.md` and `README.zh.md` at the repository root.

## Source-of-truth rules

| Document | Source of truth |
|----------|-----------------|
| `docs/en/release-notes/changelog.md` | English → translate to Chinese |
| `docs/en/release-notes/breaking-changes.md` | English → translate to Chinese |
| All other `docs/en/*` ↔ `docs/zh/*` | Mirrored pairs — sync both ways |
| `README.md` ↔ `README.zh.md` | Mirrored pair — sync both ways |

When non-changelog pages change in either locale, sync the mirror in the same change. When the English changelog changes, sync the Chinese changelog.

## Terminology table (do not translate these terms)

| Term | Notes |
|------|-------|
| pLDDT | predicted Local Distance Difference Test |
| ipTM | interface predicted TM-score |
| pTM | predicted TM-score |
| RFdiffusion | tool name |
| ProteinMPNN | tool name |
| AlphaFold3 | tool name |
| AlphaFold3 Server | official server variant |
| PDBFixer | tool name |
| OpenMM | library name |
| Bio.PDB | Python module |
| FASTA | file format |
| PDB | file format |
| CIF / mmCIF | file format |
| JSON | file format |
| CSV | file format |
| MSA | Multiple Sequence Alignment |
| contig | RFdiffusion parameter term |
| motif | structural motif |
| scaffold | structural scaffold |
| binder | binding protein |
| oligomer | symmetric oligomer |
| monomer | single chain |
| sequence design | ProteinMPNN stage |
| backbone generation | RFdiffusion stage |
| structure validation | AlphaFold3 stage |
| structure prediction | general term |
| structure refinement | PDBFixer stage |
| filtering & ranking | quality filtering stage |
| ranking confidence | AlphaFold3 composite score |
| composite score | weighted score |
| conda | package manager |
| conda env | conda environment |
| pip | package installer |
| GitHub | platform name |
| coding agent | product category |
| Hooks | plugin hook system |
| CronCreate | scheduling feature (varies by agent) |
| Bash | tool name |
| GPU | Graphics Processing Unit |
| CUDA | NVIDIA compute platform |
| A100 / H100 / V100 | GPU model names |
| pLDDT > 80 | quality threshold notation |
| ipTM > 0.75 | quality threshold notation |
| pTM > 0.8 | quality threshold notation |
| clash | atomic clash |
| clash-free | no atomic clash |
| B-factor | temperature factor |
| chain ID | PDB chain identifier (e.g., `A`, `B`) |
| residue | amino acid residue |
| amino acid | monomer unit |

## Typography rules

### English docs
- H2+ headings: sentence case (e.g., "Quick start", "System requirements"). Proper nouns from the term table are excepted (e.g., "AlphaFold3 configuration").
- Use straight quotes (`"`), not curly quotes.
- Code blocks and inline code: use backticks. Do not translate code, command names, flag names, or file paths.

### Chinese docs
- Use full-width punctuation: `，。；：？！（）「」`.
- Add a space between Chinese characters and ASCII content (English words, numbers, inline code, links): `使用 ProteinMPNN` (not `使用ProteinMPNN`), `pLDDT > 80` (not `pLDDT>80`).
- Add a space between Chinese characters and Chinese punctuation only when the punctuation encloses ASCII content.
- Do not add spaces around em-dashes or en-dashes.
- For inline code mixed with Chinese, ensure spaces on both sides of the code span.
- Do not translate proper nouns listed in the term table.

## Workflow

### 1. Detect what needs syncing

- `git diff main..HEAD --stat docs/ README.md README.zh.md` — see which files changed.
- For each changed file under `docs/en/` or `docs/zh/`, locate its mirror in the other locale (same relative path).
- For `README.md` or `README.zh.md`, the mirror is the other README file.

### 2. Translate page by page, section by section

- Keep heading hierarchy, list structure, code blocks, callout blocks, and link targets identical between the two versions.
- Preserve the exact same structure: if the English version has a `## Quick start` followed by a code block and a bullet list, the Chinese version must have the same sections in the same order.
- When in doubt about a technical term, **read the actual code** to confirm behavior rather than guessing.

### 3. Apply terminology and typography rules

- Use the term table exactly. Do not invent translations or use synonyms.
- Apply English sentence-case rules for H2+ headings.
- Apply Chinese spacing and punctuation rules.
- Code blocks and identifiers stay as-is: do not translate code, command names, flag names, or file paths.

### 4. Verify

- `git diff docs/ README.md README.zh.md` — scan for terminology drift or punctuation regressions.
- Ensure all pages flagged by the diff are fully synced before finishing.
- This is a pure Markdown documentation set; there is no docs build step to run.

## README-specific rules

- The language switcher link at the top of each README must point to the other file:
  - `README.md`: `> **English** | [中文](./README.zh.md)`
  - `README.zh.md`: `> [English](./README.md) | 中文`
- Keep the project description (`## Features` / `## 功能特性`) and quick-start examples structurally identical.
- The "Documentation" table with links to `docs/` should have English column headers in `README.md` and Chinese column headers in `README.zh.md`, but link targets remain the same.

## Rules and conventions

- **Do not one-sided fixes**: if the changed locale has an unclear or incorrect statement, fix it there first; do not patch only the mirror.
- **Match style, not just words**: Chinese docs use a narrative instructional tone; preserve that tone in Chinese. English docs use concise, direct style; preserve that in English.
- **Code blocks and identifiers stay as-is**: do not translate code, command names, flag names, or file paths.
- **Finish all flagged pages**: if the diff shows multiple files changed, sync all of them before declaring the task complete.

## Common mistakes

- Rewriting only the mirror because a phrase feels awkward in the target language — fix the changed locale first, then sync.
- Letting English headings slip into Title Case (only sentence case is allowed for H2+).
- Forgetting to add spaces between Chinese characters and inline code or English words.
- Translating proper nouns listed in the term table (e.g., translating "RFdiffusion" as "RF扩散").
- Updating only one direction and leaving the other locale stale — always finish all pages flagged by the diff.
- Forgetting to sync `README.md` / `README.zh.md` when they are changed.

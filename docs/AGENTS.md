# Docs Maintenance Guide

This file tells AI agents how to maintain the `docs/` directory for the `protein-design-skills` project.

## Directory Structure

```
docs/
├── en/                          # English docs
│   ├── README.md               # Docs landing page
│   ├── guides/                 # User guides
│   ├── api-reference/          # Standalone scripts reference (manually maintained from scripts/)
│   └── release-notes/          # Changelog (source of truth)
├── zh/                          # Chinese docs
│   └── ... (mirror structure)
└── AGENTS.md                   # This file
```

## Source-of-truth rules

| Document | Source of truth |
|----------|-----------------|
| `docs/en/release-notes/changelog.md` | English → translate to Chinese |
| All other `docs/en/*` ↔ `docs/zh/*` | Mirrored pairs — sync both ways |
| `README.md` ↔ `README.zh.md` | Mirrored pair — sync both ways |

When non-changelog pages change in either locale, sync the mirror in the same change. When the English changelog changes, sync the Chinese changelog.

## Rules

1. **Sync both locales for non-changelog pages**. After either `docs/en/*` or `docs/zh/*` changes (except release-notes), update the mirror.
2. **Keep mirrored docs in sync** in terms of:
   - File structure and names
   - Section order and heading hierarchy
   - Entry counts in tables and lists
3. **Maintain `api-reference/scripts.md`** to reflect changes in `scripts/`:
   - Update parameter tables when script CLI arguments change
   - Keep usage examples current with script behavior
   - Maintain both English and Chinese versions
4. **Do not edit docs directly** without updating the source (code or README).
   - Guides should be extracted from `README.md` / `README.zh.md`
   - API reference should reflect the actual scripts in `scripts/`
5. **Changelog is managed by `sync-changelog` skill** — do not edit manually.

## Terminology table (do not translate)

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
| chain ID | PDB chain identifier |
| residue | amino acid residue |
| amino acid | monomer unit |

## Typography rules

### English docs
- H2+ headings: sentence case (e.g., "Quick start", "System requirements"). Proper nouns from the term table are excepted.
- Use straight quotes (`"`), not curly quotes.
- Do not translate code, command names, flag names, or file paths.

### Chinese docs
- Use full-width punctuation: `，。；：？！（）「」`.
- Add a space between Chinese characters and ASCII content (English words, numbers, inline code, links).
- Do not translate proper nouns listed in the term table.
- Do not translate code, command names, flag names, or file paths.

## README-specific rules

- `README.md`: `> **English** | [中文](./README.zh.md)`
- `README.zh.md`: `> [English](./README.md) | 中文`
- Keep Features / 功能特性 and quick-start examples structurally identical.

## Workflow When Code Changes

1. Run `gen-docs` skill to regenerate API reference and sync guides
2. Run `sync-changelog` skill if the change is user-facing
3. Run `translate-docs` skill to sync locales
4. Verify both English and Chinese docs are in sync
5. Commit with message: `docs: update docs for <description>`

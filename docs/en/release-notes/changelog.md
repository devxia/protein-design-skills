# Changelog

This page documents the changes in each release of the Kimi Protein Design plugin.

## 2026-06-04

### Bug fixes

- Fix `filtering.py` `_safe_float()` always returning `0.0` for `None` input, making fallback branches dead code — designs with missing metrics were incorrectly rejected instead of being skipped
- Fix `format_converter.py` duplicate `_make_chain_id()` definition and misplaced docstring in `sequence_to_alphafold3_json()`
- Fix command injection risk in `background-notify.py` and `design-complete-notify.py` — unescaped string interpolation into AppleScript and PowerShell commands
- Fix `design-complete-notify.py` falsy-zero check — `metrics.get("plddt")` skipped valid zero values instead of using `is not None`
- Fix `tool_registry.py` missing `KeyError` handling for `query_job`, `cancel_job`, `check_tool_status`, `configure_tool_path`, `configure_db_dir` — missing parameters caused unhandled `KeyError` instead of proper error responses
- Fix `alphafold.py` redundant `if wrapper_script` / `else` branch with identical code paths in `run_alphafold3()`
- Fix `server.py` deprecated `asyncio.get_event_loop()` → `asyncio.get_running_loop()` and add `UnicodeDecodeError` handling for stdin decoding
- Fix `progress_tracker.py` reading entire log file on every poll — now reads only last 8 KB; move `import re` to module level
- Fix `config.py` silent exception swallowing on malformed YAML — now logs warning; add graceful fallback when PyYAML not installed
- Fix `gpu-check-hook.py` potential `IndexError` on empty nvidia-smi stdout
- Fix `tool_installer.py` unprotected `import yaml` — now handles missing PyYAML gracefully
- Fix `system_info.py` overwriting warnings list when both missing-tools and no-GPU conditions trigger
- Fix incorrect `callable` type annotations in 6 files (should be `Callable[[int], None]`)
- Update `.gitignore` with common Python project entries (`.venv`, `.egg-info`, `.env`, `*.log`, etc.)

## 2026-06-03

### Bug fixes

- Fix `pdbfixer_tool.py` passing wrong keyword argument `env_name` instead of `conda_env` to `run_in_conda_with_logs`
- Fix `proteinmpnn.py` missing `str()` around `sampling_temp` parameter, causing `TypeError` when numeric values are passed to `subprocess.run`
- Fix `tool_installer.py` checking non-existent key `missing_db_reason` instead of `note`, so AlphaFold3 database-missing hint never triggered
- Fix file handle leak in `pdbfixer_tool.py` where `open()` was passed directly to `PDBFile.writeFile()` without `with` statement
- Fix race condition in `job_manager.py` by moving `job.future` assignment inside the lock and reading job state under lock in `cancel_job()`
- Fix `progress_tracker.py` allowing duplicate `start()` calls which leaked background threads
- Fix `tool_registry.py` thread-safety by adding a lock around `_ensure_tool_executors()` lazy-loading
- Fix `tool_registry.py` missing `get_gpu_status` from `TOOL_SCHEMAS` (tool was executable but not discoverable)
- Fix `filtering.py` type-safety by adding `_safe_float()` helper — previously string/None metric values caused `TypeError`
- Fix `format_converter.py` chain ID overflow beyond 'Z' (now generates AA, AB, ... for >26 chains)
- Fix `format_converter.py` unhandled `ValueError` when `seed` parameter is a non-numeric string
- Fix `alphafold.py` missing `encoding="utf-8"` on all `open()` calls
- Fix `server.py` not validating `params` type before calling `.get()`, causing `AttributeError` on malformed JSON-RPC requests
- Fix `design-complete-notify.py` crash when `result` is `null` in hook payload
- Fix `rfdiffusion.py` potential `Path("")` issue when `output_prefix` has no directory component
- Remove unused imports across 10+ files (`__future__.annotations`, `run_in_conda`, `run_in_conda_popen`, `field`, `tempfile`, `os`, `sys`, `json`, `JobManager`, `get_missing_tool_prompt`, `shutil`)

## 2025-06-01

### Features

- Initial commit of kimi-protein-design plugin with 5-stage protein design pipeline
- Add conda environment support for RFdiffusion, ProteinMPNN, and AlphaFold3
- Add file-based progress tracking with historical ETA estimation
- Add cross-conda-environment support for PDBFixer via `conda_env` parameter
- Add `receptor_pdb` support to `convert_format` for multi-chain AF3 JSON generation
- Add `analyze_alphafold3_results` tool for parsing AlphaFold3 output metrics without re-running
- Add editable-install detection in `check_all_tools` for pip-installed packages

### Bug fixes

- Address all plugin issues from first server run log analysis
- Fix missing `import time` in `alphafold.py` causing `submit_job` to crash
- Fix `run_filtering` ignoring top-level metric fields (plddt, iptm, ptm, has_clash)
- Fix RFdiffusion contig double-bracketing when user provides brackets in contig string

### Docs

- Reorder README sections and replace placeholder owner with devxia
- Add prominent "already installed?" tip before Prerequisites Installation steps
- Update README for wrapper_script, schema, and MSA behavior changes

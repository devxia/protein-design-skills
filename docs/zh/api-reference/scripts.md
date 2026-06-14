# API 参考 —— Standalone Scripts

本文档说明 `scripts/` 目录中所有 standalone scripts。这些脚本是蛋白质设计流程的**主要执行方式**。

---

## 脚本索引

| 脚本 | 阶段 | 目的 |
|------|------|------|
| `batch_runner.py` | — | Complete pipeline orchestration |
| `convert_format.py` | — | File format conversion |
| `job_manager.py` | — | Background job tracking |
| `project_dashboard.py` | — | Project-wide multi-stage dashboard |
| `run_alphafold3.py` | 3 | Structure validation (best accuracy) |
| `run_boltz.py` | 3 | Boltz-1 validation (MIT, complexes) |
| `run_chai1.py` | 3 | Chai-1 validation (Apache 2.0) |
| `run_colabfold.py` | 3 | ColabFold validation (MMseqs2 MSA) |
| `run_esm_if1.py` | 2 | ESM-IF1 inverse folding |
| `run_esmfold.py` | 3 | ESMFold validation (fastest) |
| `run_filtering.py` | 4 | Result filtering and ranking |
| `run_ligandmpnn.py` | 2 | LigandMPNN sequence design |
| `run_omegafold.py` | 3 | OmegaFold validation (fast, no DB) |
| `run_openfold3.py` | 3 | OpenFold3 validation (pip install) |
| `run_pdbfixer.py` | 0 | PDB preprocessing and repair |
| `run_proteinmpnn.py` | 2 | Sequence design |
| `run_protenix.py` | 3 | Protenix validation (training + inference) |
| `run_rfdiffusion.py` | 1 | Backbone generation |
| `summarize_outputs.py` | — | Progress summary + quality report |

---

## `batch_runner.py`

Run protein design pipeline using standalone scripts

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `config` | `--config / -c` | No | — | Path | Pipeline config file (YAML or JSON) |
| `input_pdb` | `--input-pdb / -i` | No | — | Path | Input PDB file (triggers Stage 0) |
| `contig` | `--contig` | No | — | string | Contig for backbone generation (triggers Stage 1) |
| `hotspot_res` | `--hotspot-res` | No | — | string | Hotspot residues for binder design |
| `validator` | `--validator` | No | — | enum | Validation tool for Stage 3 |
| `stage` | `--stage` | No | 0 | int | Start from stage N (0-4, default: 0 = full pipeline) |
| `output_dir` | `--output-dir / -o` | No | outputs/pipeline | Path | Output directory (default: outputs/pipeline) |
| `num_designs` | `--num-designs / -n` | No | 50 | int | Number of designs (default: 50) |
| `num_seq` | `--num-seq` | No | 8 | int | Sequences per target (default: 8) |
| `min_plddt` | `--min-plddt` | No | 75.0 | float | Minimum pLDDT threshold (default: 75) |
| `top_n` | `--top-n` | No | 10 | int | Top N designs to report (default: 10) |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `convert_format.py`

Convert between protein design file formats

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `from` | `--from / -f` | Yes | — | string | Source format: fasta, pdb, csv, json |
| `to` | `--to / -t` | Yes | — | string | Target format: alphafold3_json, boltz_yaml, chai_fasta, fasta, csv |
| `input` | `--input / -i` | Yes | — | string | Input file or directory |
| `output` | `--output / -o` | Yes | — | string | Output file |
| `job_name` | `--job-name` | No | design | string | Job name for AlphaFold3 JSON (default: design) |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `job_manager.py`

Lightweight job manager — process tracking

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `command` | `command` | No | — | enum | Command |

## `project_dashboard.py`

Project-wide pipeline dashboard

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `output_dir` | `--output-dir / -d` | No | outputs | string | Project output directory |
| `expected_backbones` | `--expected-backbones` | No | 0 | int | Expected backbone count |
| `expected_sequences` | `--expected-sequences` | No | 0 | int | Expected sequence count |
| `expected_validations` | `--expected-validations` | No | 0 | int | Expected validation count |
| `watch` | `--watch / -w` | No | false | flag | Refresh every 30 seconds |
| `json` | `--json` | No | false | flag | Output JSON instead of text |

## `run_alphafold3.py`

Run AlphaFold3 — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `json` | `--json / -j` | Yes | — | string | AlphaFold3 JSON input file |
| `output_dir` | `--output-dir / --out-dir / -o` | Yes | — | string | Output directory |
| `db_dir` | `--db-dir / -d` | No | — | string | Path to AlphaFold3 databases (~2.6TB) |
| `no_msa` | `--no-msa` | No | false | flag | Skip MSA search (faster, less accurate) |
| `num_seeds` | `--num-seeds` | No | 1 | int | Number of random seeds (default: 1) |
| `num_samples` | `--num-samples` | No | 1 | int | Samples per seed (default: 1) |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_boltz.py`

Run Boltz-1 — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `input` | `--input / -i` | Yes | — | string | Input YAML or FASTA file |
| `out_dir` | `--out-dir / --output-dir / -o` | Yes | — | string | Output directory |
| `no_msa` | `--no-msa` | No | false | flag | Skip MSA server (faster, less accurate) |
| `recycling_steps` | `--recycling-steps` | No | 3 | int | Number of recycling steps (default: 3) |
| `sampling_steps` | `--sampling-steps` | No | 200 | int | Diffusion sampling steps (default: 200) |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_chai1.py`

Run Chai-1 — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `input` | `--input / -i` | Yes | — | string | Input FASTA file |
| `output_dir` | `--output-dir / --out-dir / -o` | Yes | — | string | Output directory |
| `no_msa` | `--no-msa` | No | false | flag | Skip MSA server |
| `recycles` | `--recycles` | No | 3 | int | Number of trunk recycles (default: 3) |
| `timesteps` | `--timesteps` | No | 200 | int | Diffusion timesteps (default: 200) |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_colabfold.py`

Run ColabFold — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `input` | `--input / -i` | Yes | — | string | Input FASTA file |
| `output_dir` | `--output-dir / --out-dir / -o` | Yes | — | string | Output directory |
| `num_models` | `--num-models / -n` | No | — | int | Number of AlphaFold2 models to run (1-5) |
| `msa_mode` | `--msa-mode` | No | — | string | MSA mode: MMseqs2 (UniRef+Environmental), MMseqs2 (UniRef only), single_sequence |
| `recycle` | `--recycle / -r` | No | — | int | Number of recycles (maps to --num-recycle) |
| `model_type` | `--model-type` | No | — | string | Model type: auto, AlphaFold2-ptm, AlphaFold2-multimer, etc. |
| `pair_mode` | `--pair-mode` | No | — | string | Pair mode: unpaired, paired, unpaired+paired |
| `random_seed` | `--random-seed` | No | — | int | Random seed |
| `max_msa` | `--max-msa` | No | — | string | Max MSA size, e.g. 512:1024 |
| `amber` | `--amber` | No | false | flag | Run Amber relaxation |
| `templates` | `--templates` | No | false | flag | Use templates |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_esm_if1.py`

Run ESM-IF1 inverse folding — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `pdb_path` | `--pdb-path / -p` | Yes | — | string | Input PDB or mmCIF file |
| `output_path` | `--output-path / -o` | Yes | — | string | Output FASTA file path |
| `chain` | `--chain / -c` | No | — | string | Chain ID to design |
| `temperature` | `--temperature / -t` | No | 1.0 | float | Sampling temperature (default: 1.0) |
| `num_sequences` | `--num-sequences / -n` | No | 1 | int | Number of sequences to sample (default: 1) |
| `multichain_backbone` | `--multichain-backbone` | No | false | flag | Condition on all chains in the complex |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_esmfold.py`

Run ESMFold — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `input` | `--input / -i` | Yes | — | string | Input FASTA file |
| `output_dir` | `--output-dir / --out-dir / -o` | Yes | — | string | Output directory |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_filtering.py`

Filter and rank protein designs by validation metrics

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `results_dir` | `--results-dir / -d` | Yes | — | string | Directory containing validation results |
| `min_plddt` | `--min-plddt` | No | 70.0 | float | Minimum pLDDT threshold (default: 70) |
| `min_iptm` | `--min-iptm` | No | 0.6 | float | Minimum ipTM threshold (default: 0.6) |
| `min_ptm` | `--min-ptm` | No | 0.7 | float | Minimum pTM threshold (default: 0.7) |
| `max_pae` | `--max-pae` | No | 10.0 | float | Maximum PAE threshold (default: 10) |
| `top_n` | `--top-n` | No | — | int | Only show top N designs |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output with statistics |

## `run_ligandmpnn.py`

Run LigandMPNN — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `pdb_path` | `--pdb_path / -p` | Yes | — | string | Input PDB file |
| `out_folder` | `--out_folder / -o` | Yes | — | string | Output folder |
| `num_seq_per_target` | `--num_seq_per_target / --num-seq / --num-seq-per-target / -n` | No | 8 | int | Sequences per target (default: 8) |
| `sampling_temp` | `--sampling_temp / --sampling-temp / --temp / -t` | No | 0.1 | string | Sampling temperature (default: '0.1') |
| `model_type` | `--model_type` | No | — | string | Model variant: protein_mpnn, ligand_mpnn, soluble_mpnn, ... |
| `chains_to_design` | `--chains_to_design / --chains / -c` | No | — | string | Chains to redesign, e.g. A,B |
| `fixed_residues` | `--fixed_residues` | No | — | string | Residues to keep fixed, e.g. 'C1 C2 C3' |
| `redesigned_residues` | `--redesigned_residues` | No | — | string | Residues to redesign, e.g. 'A1 A2 A3' |
| `seed` | `--seed` | No | — | int | Random seed |
| `pack_side_chains` | `--pack_side_chains` | No | false | flag | Also pack side chains |
| `number_of_packs_per_design` | `--number_of_packs_per_design` | No | — | int | Number of side-chain packs per design |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_omegafold.py`

Run OmegaFold — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `input` | `--input / -i` | Yes | — | string | Input FASTA file |
| `output_dir` | `--output-dir / --out-dir / -o` | Yes | — | string | Output directory |
| `subbatch_size` | `--subbatch-size` | No | — | int | Subbatch size for memory control (lower = less memory) |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_openfold3.py`

Run OpenFold3 — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `input` | `--input / -i` | Yes | — | string | Input FASTA or JSON file |
| `output_dir` | `--output-dir / --out-dir / -o` | Yes | — | string | Output directory |
| `model_dir` | `--model-dir` | No | — | string | Path to OpenFold3 model weights directory |
| `db_dir` | `--db-dir` | No | — | string | Path to genetic databases directory |
| `num_recycling` | `--num-recycling` | No | 3 | int | Number of recycling steps (default: 3) |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_pdbfixer.py`

Run PDBFixer — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `input` | `--input / -i` | Yes | — | string | Input PDB file |
| `output` | `--output / -o` | Yes | — | string | Output fixed PDB file |
| `keep_chains` | `--keep-chains` | No | — | string | Comma-separated chain IDs to keep (e.g., A,B) |
| `add_atoms` | `--add-atoms` | No | heavy | enum | Which atoms to add (default: heavy) |
| `keep_heterogens` | `--keep-heterogens` | No | — | string | Heterogens to keep (e.g., water, all) |
| `ph` | `--ph` | No | 7.0 | float | pH for hydrogen addition (default: 7.0) |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_proteinmpnn.py`

Run ProteinMPNN — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `pdb_path` | `--pdb-path / -p` | Yes | — | string | Input PDB file or glob pattern |
| `out_folder` | `--out-folder / -o` | Yes | — | string | Output folder for sequences |
| `num_seq` | `--num-seq / --num-seq-per-target / -n` | No | 8 | int | Sequences per target (default: 8) |
| `temp` | `--temp / --sampling-temp / -t` | No | 0.1 | string | Sampling temperature (default: 0.1) |
| `chains` | `--chains / --pdb-path-chains / -c` | No | — | string | Chain IDs to design (comma-separated) |
| `fixed_positions` | `--fixed-positions` | No | — | string | Fixed positions (comma-separated indices) |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_protenix.py`

Run Protenix — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `input` | `--input / -i` | Yes | — | string | Input JSON or FASTA file |
| `output_dir` | `--output-dir / --out-dir / -o` | Yes | — | string | Output directory |
| `num_recycling` | `--num-recycling` | No | 3 | int | Number of recycling steps (default: 3) |
| `from_fasta` | `--from-fasta` | No | false | flag | Convert FASTA input to Protenix JSON format |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `run_rfdiffusion.py`

Run RFdiffusion — standalone execution

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `config` | `--config / -c` | No | — | string | Hydra config file |
| `output_prefix` | `--output-prefix / -o` | No | — | string | Output file prefix |
| `num_designs` | `--num-designs / -n` | No | 50 | int | Number of designs |
| `contig` | `--contig` | No | — | string | Contig string for generation |
| `hotspot_res` | `--hotspot-res` | No | — | string | Hotspot residues (comma-separated) |
| `diffuser_t` | `--diffuser-t / --diffuser-T` | No | 50 | int | Diffusion steps |
| `input_pdb` | `--input-pdb / -i` | No | — | string | Input PDB for conditional design |
| `verbose` | `--verbose / -v` | No | false | flag | Verbose output |

## `summarize_outputs.py`

Summarize protein design pipeline outputs.

### 参数

| 参数 | 标志 | 必需 | 默认值 | 类型 | 说明 |
|------|------|------|--------|------|------|
| `output_dir` | `--output-dir / -d` | Yes | — | Path | Directory containing pipeline outputs. |
| `expected_backbones` | `--expected-backbones` | No | 0 | int | Expected number of backbone PDB files for progress calculation. |
| `expected_sequences` | `--expected-sequences` | No | 0 | int | Expected number of sequence FASTA files for progress calculation. |
| `expected_validations` | `--expected-validations` | No | 0 | int | Expected number of validation jobs for progress calculation. |
| `watch` | `--watch / -w` | No | false | flag | Refresh summary repeatedly until interrupted. |
| `interval` | `--interval / -i` | No | 30 | int | Seconds between refreshes in watch mode (default: 30). |
| `json` | `--json / -j` | No | false | flag | Emit raw JSON instead of formatted text. |


---

## 退出码

大多数 standalone tool runners 使用以下退出码约定：

| 代码 | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 输入文件未找到 |
| 2 | 工具未安装 / 未找到 |
| 3 | 执行错误 |
| 4 | 无效参数 |

`run_filtering.py`、`batch_runner.py` 等工具脚本可能只使用其中部分退出码，或根据阶段赋予特定含义；具体代码请参见各脚本的模块 docstring。

---

## 配置优先级

脚本按以下优先级读取配置（从高到低）：

1. 命令行参数（最高优先级）
2. 环境变量（`RFDIFFUSION_PATH`、`PROTEINMPNN_PATH` 等）
3. `~/.protein-design/config.yaml`
4. `~/.kimi-protein-design/config.yaml`（旧版兼容）
5. 自动检测（常见路径、conda 环境）

## 历史记录

所有脚本将执行记录写入 `~/.protein-design/history.jsonl`，用于未来的 ETA 估算和进度跟踪。

# API 参考 —— Standalone Scripts

本文档说明 `scripts/` 目录中所有 standalone scripts。这些脚本是蛋白质设计流程的**主要执行方式**。

---

## 脚本索引

| 脚本 | 阶段 | 目的 |
|------|------|------|
| `run_pdbfixer.py` | 0 | PDB 预处理和修复 |
| `run_rfdiffusion.py` | 1 | 骨架生成 |
| `run_proteinmpnn.py` | 2 | 序列设计 |
| `run_alphafold3.py` | 3 | 结构验证（最佳精度） |
| `run_boltz.py` | 3 | Boltz-1 验证（MIT，复合物） |
| `run_chai1.py` | 3 | Chai-1 验证（Apache 2.0） |
| `run_omegafold.py` | 3 | OmegaFold 验证（快速，无需数据库） |
| `run_esmfold.py` | 3 | ESMFold 验证（最快） |
| `run_protenix.py` | 3 | Protenix 验证（训练 + 推理） |
| `run_openfold3.py` | 3 | OpenFold3 验证（pip 安装） |
| `run_filtering.py` | 4 | 结果过滤和排序 |
| `convert_format.py` | — | 文件格式转换 |
| `job_manager.py` | — | 后台任务跟踪 |
| `batch_runner.py` | — | 完整流程编排 |
| `summarize_outputs.py` | — | 进度汇总 + 质量报告 |
| `project_dashboard.py` | — | 项目级多阶段仪表盘 |

完整参数列表参见 [英文版 API 参考](https://github.com/devxia/protein-design-skills/blob/main/docs/en/api-reference/scripts.md)。

---

## `run_pdbfixer.py`

使用 PDBFixer 预处理 PDB/CIF 文件。在 RFdiffusion/ProteinMPNN 之前为必需步骤。修复非标准残基、移除杂原子、添加缺失的重原子。不添加氢原子或缺失的 loop。

```bash
python scripts/run_pdbfixer.py \
    --input target.pdb \
    --output target_fixed.pdb \
    [--keep-chains A B] \
    [--seed 42] \
    [--verbose]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--input` / `-i` | string | 是 | — | 输入 PDB/CIF 文件路径 |
| `--output` / `-o` | string | 否 | — | 输出 PDB 文件路径（省略则自动生成） |
| `--keep-chains` | string[] | 否 | — | 保留的链 ID，如 `A B` |
| `--seed` | integer | 否 | 42 | 随机种子 |
| `--verbose` / `-v` | flag | 否 | False | 详细输出 |

---

## `run_rfdiffusion.py`

运行 RFdiffusion 进行蛋白质骨架生成。支持无条件单体、motif scaffolding、binder 设计、对称寡聚体、部分扩散、inpainting、二级结构指定、fold conditioning、环化多肽和 potentials-guided 设计。

> 除非设置 `--skip-preprocessing`，输入 PDB 会自动通过 PDBFixer 预处理。

```bash
python scripts/run_rfdiffusion.py \
    --contig "150-150" \
    --num-designs 50 \
    --output-prefix outputs/design \
    [--input-pdb target.pdb] \
    [--verbose]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--output-prefix` | string | 是 | — | 输出路径前缀 |
| `--num-designs` / `-n` | integer | 否 | 10 | 生成设计数量 |
| `--input-pdb` | string | 否 | — | 输入 PDB 路径（motif/binder/部分扩散/inpainting 时必需） |
| `--contig` | string | 是 | — | Contig 字符串，如 `[150-150]` 或 `[B1-100/0 100-100]` |
| `--hotspot-res` | string[] | 否 | — | Binder 设计的热点残基，如 `A30 A33` |
| `--symmetry` | string | 否 | — | 对称模式：`c2`、`c3`、`c4`、`d2`、`d3`、`tetrahedral`、`octahedral`、`icosahedral` |
| `--diffuser-T` | integer | 否 | 50 | 扩散步数（越小越快） |
| `--ckpt-override-path` | string | 否 | — | 覆盖默认模型检查点 |
| `--skip-preprocessing` | flag | 否 | False | 跳过自动 PDBFixer 预处理 |
| `--cyclic` | flag | 否 | False | 设计大环环化多肽 |
| `--cyc-chains` | string | 否 | a | 环化的链（默认：`a`） |
| `--final-step` | integer | 否 | — | 提前停止扩散（更快，质量较低） |
| `--noise-scale-ca` | float | 否 | — | CA 坐标噪声尺度（越低多样性越低，质量越高） |
| `--noise-scale-frame` | float | 否 | — | Frame 噪声尺度 |
| `--verbose` / `-v` | flag | 否 | False | 详细输出 |

---

## `run_proteinmpnn.py`

运行 ProteinMPNN 进行氨基酸序列设计。支持直接 PDB 输入、固定位置、 tied 位置（对称性）、AA 偏置、PSSM 偏置和仅评分模式。

```bash
python scripts/run_proteinmpnn.py \
    --pdb-path design.pdb \
    --out-folder outputs/seqs/ \
    --num-seq 8 \
    [--sampling-temp 0.1] \
    [--verbose]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--pdb-path` / `-p` | string | 否 | — | 输入 PDB 文件路径（单 PDB 模式） |
| `--jsonl-path` | string | 否 | — | 解析后的 PDB jsonl 路径（多链批处理模式） |
| `--out-folder` / `-o` | string | 是 | — | 输出文件夹路径 |
| `--num-seq` / `-n` | integer | 否 | 8 | 每个目标的序列数 |
| `--sampling-temp` | string | 否 | 0.1 | 采样温度，如 `0.1` 或 `0.1 0.2 0.3` |
| `--model-name` | string | 否 | v_48_020 | 模型变体：`v_48_002`、`v_48_010`、`v_48_020`、`v_48_030` |
| `--score-only` | flag | 否 | False | 仅评分输入骨架-序列对，不生成新序列 |
| `--save-score` | flag | 否 | False | 保存分数到 .npz 文件 |
| `--save-probs` | flag | 否 | False | 保存预测概率到 .npz 文件 |
| `--conditional-probs-only` | flag | 否 | False | 输出每位置条件概率 |
| `--unconditional-probs-only` | flag | 否 | False | 输出无条件概率（类似 PSSM） |
| `--verbose` / `-v` | flag | 否 | False | 详细输出 |

---

## `run_alphafold3.py`

运行 AlphaFold3 进行结构预测和验证。接受 JSON 输入（ProteinMPNN FASTA 输出可先用 `convert_format.py` 转换）。

```bash
python scripts/run_alphafold3.py \
    --json af3_input.json \
    --output-dir outputs/af3/ \
    [--num-seeds 1] \
    [--num-samples 5] \
    [--verbose]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--json` / `-j` | string | 是 | — | 输入 JSON 文件路径 |
| `--output-dir` / `-o` | string | 是 | — | 输出目录 |
| `--num-seeds` | integer | 否 | 1 | 种子数 |
| `--num-samples` | integer | 否 | 5 | 每个种子的采样数 |
| `--run-data-pipeline` | flag | 否 | True | 运行 MSA 搜索（仅 CPU，较慢） |
| `--no-run-data-pipeline` | flag | 否 | — | 跳过 MSA 搜索 |
| `--save-embeddings` | flag | 否 | False | 保存结构嵌入 |
| `--save-distogram` | flag | 否 | False | 保存距离图预测 |
| `--verbose` / `-v` | flag | 否 | False | 详细输出 |

---

## 验证工具（阶段 3 替代方案）

### `run_boltz.py`

Boltz-1 —— MIT 许可证，支持复合物和共价修饰。

```bash
python scripts/run_boltz.py -i sequences.fasta -o outputs/boltz/
```

### `run_chai1.py`

Chai-1 —— Apache 2.0 许可证。

```bash
python scripts/run_chai1.py -i sequences.fasta -o outputs/chai1/
```

### `run_omegafold.py`

OmegaFold —— 快速，无需数据库。

```bash
python scripts/run_omegafold.py -i sequences.fasta -o outputs/omegafold/
```

### `run_esmfold.py`

ESMFold —— 超快速，适合大规模筛选。

```bash
python scripts/run_esmfold.py -i sequences.fasta -o outputs/esmfold/
```

---

## `run_filtering.py`

按置信度指标（pLDDT、ipTM、pTM、clashes）过滤和排序蛋白质设计。

```bash
python scripts/run_filtering.py \
    --results-dir outputs/af3/ \
    --min-plddt 75 \
    --top-n 10 \
    [--verbose]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--results-dir` / `-d` | string | 是 | — | 包含设计结果的目录 |
| `--min-plddt` | float | 否 | 70 | 最小 pLDDT 阈值 |
| `--min-iptm` | float | 否 | 0.6 | 最小 ipTM 阈值 |
| `--min-ptm` | float | 否 | 0.5 | 最小 pTM 阈值 |
| `--top-n` | integer | 否 | — | 过滤后保留前 N 个设计 |
| `--allow-clashes` | flag | 否 | False | 允许原子冲突的设计 |
| `--verbose` / `-v` | flag | 否 | False | 详细输出 |

---

## `convert_format.py`

蛋白质设计文件格式转换。

```bash
python scripts/convert_format.py \
    --from fasta --to alphafold3_json \
    --input seqs.fa \
    --output af3.json \
    [--receptor-pdb receptor.pdb] \
    [--receptor-chain A]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--from` | enum | 是 | — | 源格式：`fasta`、`pdb` |
| `--to` | enum | 是 | — | 目标格式：`alphafold3_json`、`validated_pdb` |
| `--input` / `-i` | string | 是 | — | 输入文件路径 |
| `--output` / `-o` | string | 否 | — | 输出文件路径 |
| `--receptor-pdb` | string | 否 | — | 多链 AF3 输入的可选受体 PDB |
| `--receptor-chain` | string | 否 | — | 受体 PDB 中提取的链 ID |

---

## `job_manager.py`

轻量级后台任务管理器，用于跟踪长时间运行的设计任务。

```bash
# 提交后台任务
python scripts/job_manager.py submit --name rfdiff -- \
    python scripts/run_rfdiffusion.py --contig "150-150" --num-designs 50

# 检查状态
python scripts/job_manager.py status <job_id>

# 查看日志
python scripts/job_manager.py tail <job_id> --lines 50

# 等待完成
python scripts/job_manager.py wait <job_id> --timeout 3600

# 列出所有任务
python scripts/job_manager.py list

# 取消任务
python scripts/job_manager.py cancel <job_id>
```

---

## `batch_runner.py`

用单个命令运行完整的蛋白质设计流程。

```bash
python scripts/batch_runner.py \
    --input-pdb target.pdb \
    --contig "[B1-100/0 100-100]" \
    --validator omegafold \
    --num-designs 50 \
    --verbose
```

或从配置文件：

```bash
python scripts/batch_runner.py --config pipeline.yaml
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | string | 否 | — | 流程配置 YAML 文件路径 |
| `--input-pdb` | string | 否 | — | 输入 PDB 文件路径 |
| `--contig` | string | 否 | — | RFdiffusion contig 字符串 |
| `--num-designs` | integer | 否 | 10 | 生成骨架数量 |
| `--num-seq` | integer | 否 | 8 | 每个骨架的序列数 |
| `--validator` | string | 否 | alphafold3 | 验证工具：`alphafold3`、`boltz`、`chai1`、`omegafold`、`esmfold` |
| `--min-plddt` | float | 否 | 70 | 过滤最小 pLDDT |
| `--output-dir` | string | 否 | — | 输出目录 |
| `--verbose` / `-v` | flag | 否 | False | 详细输出 |

---

## `summarize_outputs.py`

扫描输出目录并打印流程产物、进度条和验证质量指标的汇总。适用于定期检查进度。

### 用法

```bash
python scripts/summarize_outputs.py \
    --output-dir outputs/ \
    [--expected-backbones 50] \
    [--expected-sequences 200] \
    [--expected-validations 50] \
    [--watch] \
    [--interval 30] \
    [--json]
```

### 参数

| 参数 | 类型 | 必需 | 默认 | 说明 |
|-----------|------|----------|---------|-------------|
| `--output-dir` / `-d` | string | 是 | — | 要扫描的目录 |
| `--expected-backbones` | integer | 否 | 0 | 期望的 PDB 数量（用于进度条） |
| `--expected-sequences` | integer | 否 | 0 | 期望的 FASTA 数量（用于进度条） |
| `--expected-validations` | integer | 否 | 0 | 期望的验证数量（用于进度条） |
| `--watch` / `-w` | flag | 否 | False | 自动刷新，直到中断 |
| `--interval` / `-i` | integer | 否 | 30 | 刷新间隔（秒） |
| `--json` / `-j` | flag | 否 | False | 输出原始 JSON 而非格式化文本 |

### 输出汇总

- **产物计数**：PDB 骨架、FASTA 序列、confidence JSON 文件、mmCIF 结构
- **进度条**：相对于期望数量的完成百分比
- **质量分布**：按 pLDDT 分桶（优秀 ≥90、良好 80–90、可接受 70–80、较差 <70）
- **顶尖设计**：按 pLDDT 排序，显示 ipTM 和 pTM

---

## `project_dashboard.py`

项目级流程仪表盘。扫描输出目录中的所有阶段（预处理、骨架生成、序列设计、结构验证、过滤排序），打印包含产物计数、进度条、质量指标和下一步建议的汇总报告。

```bash
# 一次性仪表盘
python scripts/project_dashboard.py --output-dir outputs/

# 带预期数量的进度条
python scripts/project_dashboard.py --output-dir outputs/ \
    --expected-backbones 50 \
    --expected-sequences 400 \
    --expected-validations 50

# 实时刷新模式（每 30 秒）
python scripts/project_dashboard.py --output-dir outputs/ --watch
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--output-dir` / `-d` | string | 否 | `outputs` | 要扫描的根输出目录 |
| `--expected-backbones` | integer | 否 | 0 | 预期骨架数量（用于进度条） |
| `--expected-sequences` | integer | 否 | 0 | 预期序列数量（用于进度条） |
| `--expected-validations` | integer | 否 | 0 | 预期验证数量（用于进度条） |
| `--watch` / `-w` | flag | 否 | False | 每 30 秒刷新 |
| `--json` | flag | 否 | False | 输出 JSON 而不是文本 |

输出内容包括：
- 总体产物计数
- 每个阶段的进度条
- 平均 / 最佳 / 最差 pLDDT 和 ipTM
- 质量分布（优秀 / 良好 / 可接受 / 差）
- 基于已检测阶段的下一步建议

---

## 退出码

所有脚本使用以下退出码约定：

| 代码 | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 输入文件未找到 |
| 2 | 工具未安装 / 未找到 |
| 3 | 执行错误 |
| 4 | 无效参数 |

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

# API 参考 — 工具

本文档列出蛋白质设计插件提供的所有 MCP 工具。

## `get_tool_info`

获取所有可用工具的信息，包括参数和用法。

## `health_check`

检查蛋白质设计环境的健康状态：GPU、CUDA、conda、工具安装和磁盘空间。

## `submit_job`

提交蛋白质设计工具的异步任务。返回 task_id，可通过 query_job 轮询结果。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `tool` | enum(rfdiffusion, proteinmpnn, alphafold3, pdbfixer, filtering) | Yes | — | 要执行的工具名称 |
| `params` | object | Yes | — | 工具专属参数（详见 get_tool_info） |

## `query_job`

根据 task_id 查询已提交任务的状态和结果。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `task_id` | string | Yes | — | submit_job 返回的任务 ID |

## `cancel_job`

根据 task_id 取消正在运行或排队中的任务。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `task_id` | string | Yes | — | 要取消的任务 ID |

## `run_pdbfixer`

使用 PDBFixer 预处理 PDB/CIF 文件。在运行 RFdiffusion/ProteinMPNN 之前必须执行。修复非标准残基、移除异源分子、添加缺失的重原子。不会添加氢原子或缺失的 loop。支持通过 conda_env 跨 conda 环境执行。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `input_pdb` | string | Yes | — | 输入 PDB/CIF 文件路径 |
| `output_pdb` | string | No | — | 输出 PDB 文件路径（省略时自动生成） |
| `output_dir` | string | No | — | 未指定 output_pdb 时的输出目录 |
| `keep_chains` | array[string] | No | — | 要保留的 chain ID（如 ['A', 'B']）。省略时保留全部。 |
| `seed` | integer | No | 42 | 缺失原子重建的随机种子 |
| `conda_env` | string | No | — | PDBFixer 所在的 conda 环境名称。当 PDBFixer 不在当前环境中时使用。 |

## `run_rfdiffusion`

运行 RFdiffusion 进行蛋白质骨架生成。支持无条件单体、基序支架、结合物设计和对称寡聚体。输入 PDB 会自动用 PDBFixer 预处理，除非 skip_preprocessing=true。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `output_prefix` | string | Yes | — | 输出路径前缀 |
| `num_designs` | integer | No | 10 | 要生成的设计数量 |
| `input_pdb` | string | No | — | 输入 PDB 路径（基序/结合物/部分结构时需要） |
| `contig` | string | Yes | — | Contig 字符串，例如 '[150-150]' 或 '[B1-100/0 100-100]' |
| `hotspot_res` | array[string] | No | — | 结合物设计的热点残基，如 ['A30','A33'] |
| `symmetry` | string | No | — | 对称模式：c2、d2、tetrahedral 等 |
| `diffuser_T` | integer | No | 50 | 扩散时间步（越小越快） |
| `ckpt_override_path` | string | No | — | 覆盖默认模型检查点 |
| `skip_preprocessing` | boolean | No | False | 跳过自动 PDBFixer 预处理 |
| `keep_chains` | array[string] | No | — | 预处理时要保留的 chain |
| `conda_env` | string | No | — | RFdiffusion 的 conda 环境名称（如 'SE3nv'）。回退到配置或当前环境。 |
| `wrapper_script` | string | No | — | 运行 RFdiffusion 前设置环境（环境变量、conda 激活等）的 shell wrapper 脚本路径。覆盖 conda_env。 |

## `run_proteinmpnn`

在给定骨架 PDB 上运行 ProteinMPNN 进行氨基酸序列设计。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `pdb_path` | string | Yes | — | 输入 PDB 文件路径 |
| `output_folder` | string | Yes | — | 输出文件夹路径 |
| `num_seq_per_target` | integer | No | 8 | 每个目标的序列数量 |
| `sampling_temp` | string | No | 0.1 | 采样温度，如 '0.1' 或 '0.1 0.2 0.3' |
| `model_name` | string | No | v_48_020 | 模型变体 |
| `pdb_path_chains` | string | No | — | 要设计的 chain，如 'B' 表示仅设计结合物 |
| `fixed_positions_jsonl` | string | No | — | 固定位置 JSONL 文件路径 |
| `use_soluble_model` | boolean | No | False | 使用可溶性蛋白模型 |
| `seed` | integer | No | 37 | 随机种子 |
| `conda_env` | string | No | — | ProteinMPNN 的 conda 环境名称。回退到配置或当前环境。 |
| `wrapper_script` | string | No | — | 运行 ProteinMPNN 前设置环境的 shell wrapper 脚本路径。覆盖 conda_env。 |

## `run_alphafold3`

运行 AlphaFold3 进行结构预测和验证。接受 JSON 输入（ProteinMPNN 的 FASTA 输出可先用 convert_format 转换）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `json_path` | string | Yes | — | 输入 JSON 文件路径 |
| `model_dir` | string | No | — | AlphaFold3 模型参数目录 |
| `db_dir` | string | No | — | 遗传数据库目录 |
| `output_dir` | string | Yes | — | 输出目录 |
| `num_seeds` | integer | No | 1 | 种子数量 |
| `num_samples` | integer | No | 5 | 每个种子的样本数量 |
| `run_data_pipeline` | boolean | No | True | 运行 MSA 搜索（仅 CPU，较慢）。默认 true。仅在需要快速推理且使用预计算特征或无 MSA 模式时设为 false。 |
| `conda_env` | string | No | — | AlphaFold3 的 conda 环境名称。回退到配置或当前环境。 |
| `wrapper_script` | string | No | — | 运行 AlphaFold3 前设置环境（XLA_FLAGS、model_dir、db_dir、HMMER 路径等）的 shell wrapper 脚本路径（如 run_af3.sh）。覆盖 conda_env 和自动检测的 db_dir。 |

## `convert_format`

在蛋白质设计文件格式之间转换：ProteinMPNN FASTA 转 AlphaFold3 JSON（可选受体 PDB 用于多链复合物），或验证 PDB。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `from_format` | enum(fasta, pdb) | Yes | — | 源格式 |
| `to_format` | enum(alphafold3_json, validated_pdb) | Yes | — | 目标格式 |
| `input_path` | string | Yes | — | 输入文件路径 |
| `output_path` | string | No | — | 输出文件路径 |
| `job_name` | string | No | — | AF3 JSON 的任务名称 |
| `seed` | integer | No | 1 | AF3 JSON 的种子 |
| `receptor_pdb` | string | No | — | 受体 PDB 文件路径（可选）。提供时，受体序列会前置到设计序列中，用于多链 AlphaFold3 输入。 |
| `receptor_chain` | string | No | — | receptor_pdb 中要提取的 chain ID（可选）。省略时使用第一个可用 chain。 |

## `analyze_alphafold3_results`

解析并分析 AlphaFold3 预测结果目录。提取置信度指标（pLDDT、pTM、ipTM、每链 pLDDT、排名分数、冲突状态），无需重新运行预测。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `output_dir` | string | Yes | — | 要分析的 AlphaFold3 输出目录 |
| `job_name` | string | No | — | 输出文件使用的任务名称（可选）。省略时自动检测。 |

## `run_filtering`

根据 AlphaFold3 置信度指标（pLDDT、ipTM、pTM、冲突）过滤并排序蛋白质设计。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `designs` | array[object] | Yes | — | 包含指标的设计结果字典列表 |
| `criteria` | object | No | — |  |

## `check_batch_progress`

检查一批已提交任务的进度。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `task_ids` | array[string] | Yes | — | 要检查的任务 ID 列表 |

## `check_tool_status`

检查特定蛋白质设计工具是否已安装并可检测。返回安装状态、检测到的路径，以及缺失时的下载说明。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `tool_name` | enum(rfdiffusion, proteinmpnn, alphafold3, pdbfixer) | Yes | — | 要检查的工具名称 |

## `check_all_tools`

一次性检查所有蛋白质设计工具的安装状态。返回各工具状态摘要和总体就绪情况。

## `configure_tool_path`

配置工具安装路径并持久化到配置中。安装工具后使用此功能，以便插件能找到它。验证给定路径下是否存在预期文件。可选设置 conda 环境名称。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `tool_name` | enum(rfdiffusion, proteinmpnn, alphafold3) | Yes | — | 要配置的工具 |
| `path` | string | Yes | — | 工具根目录的绝对路径（如 /home/you/RFdiffusion） |
| `conda_env` | string | No | — | conda 环境名称（如 RFdiffusion 的 'SE3nv'）（可选） |

## `configure_db_dir`

配置 AlphaFold3 遗传数据库目录（如 ~/public_databases）。验证目录是否包含预期的数据库子目录。持久化到配置文件。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | string | Yes | — | 遗传数据库目录的绝对路径（如 /home/you/public_databases） |

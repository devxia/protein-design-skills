# API 参考 — 工具

本文档详细说明蛋白质设计插件提供的所有 MCP 工具。

## `get_tool_info`

获取所有可用工具的信息，包括参数和使用方法。

## `health_check`

检查蛋白质设计环境的健康状况：GPU、CUDA、conda、工具安装和磁盘空间。

## `get_gpu_status`

获取详细的 GPU 状态，包括可用性、显存和架构建议。

## `submit_job`

提交蛋白质设计工具的异步任务。返回 task_id，可通过 query_job 轮询结果。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `tool` | enum(rfdiffusion, proteinmpnn, alphafold3, pdbfixer, filtering) | 是 | — | 要执行的工具名称 |
| `params` | object | 是 | — | 工具专属参数（详见 get_tool_info） |

## `query_job`

根据 task_id 查询已提交任务的状态和结果。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `task_id` | string | 是 | — | submit_job 返回的任务 ID |

## `cancel_job`

根据 task_id 取消正在运行或排队中的任务。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `task_id` | string | 是 | — | 要取消的任务 ID |

## `run_pdbfixer`

使用 PDBFixer 预处理 PDB/CIF 文件。在运行 RFdiffusion/ProteinMPNN 之前必须执行。修复非标准残基、移除异源分子、添加缺失的重原子。不会添加氢原子或缺失的 loop。支持通过 conda_env 跨 conda 环境执行。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `input_pdb` | string | 是 | — | 输入 PDB/CIF 文件路径 |
| `output_pdb` | string | 否 | — | 输出 PDB 文件路径（省略时自动生成） |
| `output_dir` | string | 否 | — | 未指定 output_pdb 时的输出目录 |
| `keep_chains` | array[string] | 否 | — | 要保留的 chain ID（如 ['A', 'B']）。省略时保留全部。 |
| `seed` | integer | 否 | 42 | 缺失原子重建的随机种子 |
| `conda_env` | string | 否 | — | PDBFixer 所在的 conda 环境名称。当 PDBFixer 不在当前环境中时使用。 |

## `run_rfdiffusion`

运行 RFdiffusion 进行蛋白质骨架生成。支持无条件单体、基序支架、结合物设计、对称寡聚体、部分扩散、修复、二级结构指定、折叠条件约束、环肽和势能引导设计。输入 PDB 会自动用 PDBFixer 预处理，除非 skip_preprocessing=true。

### 基本参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `output_prefix` | string | 是 | — | 输出路径前缀 |
| `num_designs` | integer | 否 | 10 | 要生成的设计数量 |
| `input_pdb` | string | 否 | — | 输入 PDB 路径（基序/结合物/部分结构/修复时需要） |
| `contig` | string | 是 | — | Contig 字符串，例如 '[150-150]' 或 '[B1-100/0 100-100]' |
| `hotspot_res` | array[string] | 否 | — | 结合物设计的热点残基，如 ['A30','A33'] |
| `symmetry` | string | 否 | — | 对称模式：c2、c3、c4、d2、d3、tetrahedral、octahedral、icosahedral |
| `diffuser_T` | integer | 否 | 50 | 扩散时间步（越小越快）。部分扩散时使用 25。 |
| `ckpt_override_path` | string | 否 | — | 覆盖默认模型检查点。如 enzyme active sites 使用 models/ActiveSite_ckpt.pt。 |
| `skip_preprocessing` | boolean | 否 | False | 跳过自动 PDBFixer 预处理 |
| `keep_chains` | array[string] | 否 | — | 预处理时要保留的 chain |
| `conda_env` | string | 否 | — | RFdiffusion 的 conda 环境名称（如 'SE3nv'）。回退到配置或当前环境。 |
| `wrapper_script` | string | 否 | — | 运行 RFdiffusion 前设置环境（环境变量、conda 激活等）的 shell wrapper 脚本路径。覆盖 conda_env。 |

### 高级参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `partial_T` | integer | 否 | — | 部分扩散：先加噪 N 步然后去噪（如 10）。值越低越保守。 |
| `provide_seq` | string | 否 | — | 部分扩散期间保持序列固定。格式：'[172-205]' 或 '[172-177,200-205]' |
| `inpaint_seq` | string | 否 | — | 掩码残基的序列身份。格式：'[A163-168/A170-171]' |
| `inpaint_str` | string | 否 | — | 掩码 3D 结构但保持序列。格式：'[B165-178]' |
| `inpaint_str_helix` | string | 否 | — | 将掩码残基指定为 alpha-螺旋。格式：'[A51-60]' |
| `inpaint_str_strand` | string | 否 | — | 将掩码残基指定为 beta-折叠。格式：'[A61-70]' |
| `inpaint_str_loop` | string | 否 | — | 将掩码残基指定为环区。格式：'[A71-80]' |
| `scaffoldguided` | boolean | 否 | False | 通过二级结构 + 块邻接启用折叠条件约束 |
| `scaffold_dir` | string | 否 | — | 包含支架 ss/adj 文件的目录（scaffoldguided=true 时需要） |
| `cyclic` | boolean | 否 | False | 设计大环肽 |
| `cyc_chains` | string | 否 | a | 要环化的链（默认：'a'） |
| `potentials` | array[string] | 否 | — | 引导势能。如 ['type:monomer_ROG,weight:1.0'] 或 ['type:interface_ncontacts,binderlen:100,weight:1.0'] |

### 模型检查点（自动选择）

| 检查点 | 自动选择条件 |
|--------|-------------|
| `Base_ckpt.pt` | 默认（无特殊标志） |
| `Complex_base_ckpt.pt` | 设置了 `hotspot_res` |
| `Complex_Fold_base_ckpt.pt` | `scaffoldguided=True` |
| `InpaintSeq_ckpt.pt` | 设置了 `inpaint_seq` 或 `provide_seq` 或 `inpaint_str` |
| `ActiveSite_ckpt.pt` | 仅手动覆盖（非常小的基序） |

## `run_proteinmpnn`

运行 ProteinMPNN 进行氨基酸序列设计。支持直接 PDB 输入、JSONL 多链工作流、固定位置、绑定位置（对称性）、氨基酸偏置、PSSM 偏置和仅评分模式。

### 基本参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `pdb_path` | string | 否 | — | 输入 PDB 文件路径（单 PDB 模式）。使用 pdb_path 或 jsonl_path 之一。 |
| `jsonl_path` | string | 否 | — | 解析后的 PDB jsonl 格式路径（多链批处理模式）。使用 helper_scripts/parse_multiple_chains.py 准备。 |
| `output_folder` | string | 是 | — | 输出文件夹路径 |
| `num_seq_per_target` | integer | 否 | 8 | 每个目标的序列数量 |
| `sampling_temp` | string | 否 | 0.1 | 采样温度，如 '0.1' 或 '0.1 0.2 0.3' |
| `model_name` | string | 否 | v_48_020 | 模型变体：v_48_002, v_48_010, v_48_020, v_48_030 |
| `pdb_path_chains` | string | 否 | — | 单 PDB 模式要设计的链，如 'B' 表示仅设计结合物 |
| `fixed_positions_jsonl` | string | 否 | — | 固定位置 JSONL 文件路径 |
| `use_soluble_model` | boolean | 否 | False | 使用可溶性蛋白模型 |
| `seed` | integer | 否 | 37 | 随机种子（0=随机） |
| `conda_env` | string | 否 | — | ProteinMPNN 的 conda 环境名称。回退到配置或当前环境。 |
| `wrapper_script` | string | 否 | — | 运行 ProteinMPNN 前设置环境的 shell wrapper 脚本路径。覆盖 conda_env。 |

### 高级参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `chain_id_jsonl` | string | 否 | — | 链分配 JSONL 路径（jsonl_path 模式）。使用 helper_scripts/assign_fixed_chains.py 准备。 |
| `tied_positions_jsonl` | string | 否 | — | 绑定（对称）位置 JSONL 路径。使用 helper_scripts/make_tied_positions_dict.py 准备。 |
| `bias_AA_jsonl` | string | 否 | — | 全局氨基酸偏置 JSONL 路径。使用 helper_scripts/make_bias_AA.py 准备。 |
| `bias_by_res_jsonl` | string | 否 | — | 每个位置氨基酸偏置 JSONL 路径 |
| `pssm_jsonl` | string | 否 | — | PSSM 偏置 JSONL 路径 |
| `pssm_multi` | number | 否 | 0.0 | PSSM 权重 [0.0, 1.0] |
| `omit_AAs` | string | 否 | X | 排除的氨基酸，如 'AC' 排除 Ala 和 Cys |
| `backbone_noise` | number | 否 | 0.0 | 骨架原子上的高斯噪声标准差（Å） |
| `save_score` | boolean | 否 | False | 保存分数到 .npz 文件 |
| `save_probs` | boolean | 否 | False | 保存预测概率到 .npz 文件 |
| `score_only` | boolean | 否 | False | 仅评分输入的骨架-序列对，不生成新序列 |
| `path_to_fasta` | string | 否 | — | 要评分的 FASTA 序列（score_only=true 时需要） |
| `ca_only` | boolean | 否 | False | 对 CA-only 结构使用 CA-only 模型 |
| `batch_size` | integer | 否 | 1 | 批大小（更大的 GPU 可以增加） |
| `path_to_model_weights` | string | 否 | — | 自定义模型权重文件夹路径 |

## `run_alphafold3`

运行 AlphaFold3 进行结构预测和验证。接受 JSON 输入（ProteinMPNN 的 FASTA 输出可先用 convert_format 转换）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `json_path` | string | 是 | — | 输入 JSON 文件路径 |
| `model_dir` | string | 否 | — | AlphaFold3 模型参数目录 |
| `db_dir` | string | 否 | — | 遗传数据库目录 |
| `output_dir` | string | 是 | — | 输出目录 |
| `num_seeds` | integer | 否 | 1 | 种子数量 |
| `num_samples` | integer | 否 | 5 | 每个种子的样本数量 |
| `run_data_pipeline` | boolean | 否 | True | 运行 MSA 搜索（仅 CPU，较慢）。默认 true。仅在需要快速推理且使用预计算特征或无 MSA 模式时设为 false。 |
| `save_embeddings` | boolean | 否 | False | 保存结构嵌入以供下游分析 |
| `save_distogram` | boolean | 否 | False | 保存距离图预测 |
| `conda_env` | string | 否 | — | AlphaFold3 的 conda 环境名称。回退到配置或当前环境。 |
| `wrapper_script` | string | 否 | — | 运行 AlphaFold3 前设置环境（XLA_FLAGS、model_dir、db_dir、HMMER 路径等）的 shell wrapper 脚本路径（如 run_af3.sh）。覆盖 conda_env 和自动检测的 db_dir。 |

## `convert_format`

在蛋白质设计文件格式之间转换：ProteinMPNN FASTA 转 AlphaFold3 JSON（可选受体 PDB 用于多链复合物），或验证 PDB。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `from_format` | enum(fasta, pdb) | 是 | — | 源格式 |
| `to_format` | enum(alphafold3_json, validated_pdb) | 是 | — | 目标格式 |
| `input_path` | string | 是 | — | 输入文件路径 |
| `output_path` | string | 否 | — | 输出文件路径 |
| `job_name` | string | 否 | — | AF3 JSON 的任务名称 |
| `seed` | integer | 否 | 1 | AF3 JSON 的种子 |
| `receptor_pdb` | string | 否 | — | 受体 PDB 文件路径（可选）。提供时，受体序列会前置到设计序列中，用于多链 AlphaFold3 输入。 |
| `receptor_chain` | string | 否 | — | receptor_pdb 中要提取的 chain ID（可选）。省略时使用第一个可用 chain。 |

## `analyze_alphafold3_results`

解析并分析 AlphaFold3 预测结果目录。提取置信度指标（pLDDT、pTM、ipTM、每链 pLDDT、排名分数、冲突状态），无需重新运行预测。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `output_dir` | string | 是 | — | 要分析的 AlphaFold3 输出目录 |
| `job_name` | string | 否 | — | 输出文件使用的任务名称（可选）。省略时自动检测。 |

## `run_filtering`

根据 AlphaFold3 置信度指标（pLDDT、ipTM、pTM、冲突）过滤并排序蛋白质设计。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `designs` | array[object] | 是 | — | 包含指标的设计结果字典列表 |
| `criteria` | object | 否 | — | 过滤条件对象 |

### 条件对象

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `min_plddt` | number | 70 | 最小 pLDDT 阈值 |
| `min_iptm` | number | 0.6 | 最小 ipTM 阈值 |
| `min_ptm` | number | 0.5 | 最小 pTM 阈值 |
| `allow_clashes` | boolean | False | 允许原子冲突的设计 |

## `check_batch_progress`

检查一批已提交任务的进度。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `task_ids` | array[string] | 是 | — | 要检查的任务 ID 列表 |

## `check_tool_status`

检查特定蛋白质设计工具是否已安装并可检测。返回安装状态、检测到的路径，以及缺失时的下载说明。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `tool_name` | enum(rfdiffusion, proteinmpnn, alphafold3, pdbfixer) | 是 | — | 要检查的工具名称 |

## `check_all_tools`

一次性检查所有蛋白质设计工具的安装状态。返回各工具状态摘要和总体就绪情况。

## `configure_tool_path`

配置工具安装路径并持久化到配置中。安装工具后使用此功能，以便插件能找到它。验证给定路径下是否存在预期文件。可选设置 conda 环境名称。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `tool_name` | enum(rfdiffusion, proteinmpnn, alphafold3) | 是 | — | 要配置的工具 |
| `path` | string | 是 | — | 工具根目录的绝对路径（如 /home/you/RFdiffusion） |
| `conda_env` | string | 否 | — | conda 环境名称（如 RFdiffusion 的 'SE3nv'）（可选） |

## `configure_db_dir`

配置 AlphaFold3 遗传数据库目录（如 ~/public_databases）。验证目录是否包含预期的数据库子目录。持久化到配置文件。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | string | 是 | — | 遗传数据库目录的绝对路径（如 /home/you/public_databases） |

# 🧬 Kimi Protein Design

> [English](./README.md) | 中文

一个用于端到端蛋白质设计工作流的 [Kimi Code](https://github.com/MoonshotAI/Kimi-Code) 插件。通过自然语言对话，即可生成蛋白质骨架、设计序列、验证结构并排序结果。

## 功能特性

- **Stage 0 — 结构预处理**：使用 PDBFixer 自动修复 PDB（非标准残基、异质原子、缺失原子）
- **Stage 1 — 骨架生成**：RFdiffusion 用于单体、结合物、基序支架及对称寡聚体
- **Stage 2 — 序列设计**：ProteinMPNN 用于氨基酸序列分配
- **Stage 3 — 结构验证**：AlphaFold3 用于置信度评分（pLDDT、ipTM、pTM）
- **Stage 4 — 过滤与排序**：自动质量过滤及综合评分
- **异步任务管理**：提交长时间运行的任务并轮询结果
- **批量验证**：CronCreate 支持大规模 AlphaFold3 筛选
- **Hooks (0.6.0+)**：上下文注入、GPU 安全检查及桌面通知


## ⚠️ 重要提示：Plugin ≠ Tools

本插件**不捆绑** RFdiffusion、ProteinMPNN、AlphaFold3 或 PDBFixer。这些是大型机器学习模型（多 GB），必须单独安装。插件提供**编排层**（MCP Server + Skills），通过子进程调用这些工具。


## 安装

### 从 GitHub 安装（推荐）

```
/plugins install https://github.com/devxia/kimi-protein-design
```

### 从本地目录安装

```
/plugins install /path/to/kimi-protein-design
```

### 激活插件

安装后，启动**新会话**使插件生效：

```
/new
```

> ⚠️ **重要**：插件更改仅适用于新会话。已有会话保持其初始插件快照。


## 环境要求

- Kimi Code >= 0.6.0
- Python >= 3.9
- 显存 >= 16GB 的 CUDA 显卡（推荐）
- Conda（miniconda 或 anaconda）
- 单独安装：RFdiffusion、ProteinMPNN、AlphaFold3、PDBFixer + OpenMM


## 前置条件安装

> 💡 **已经安装了这些工具？**
>
> 如果你已经安装了 RFdiffusion、ProteinMPNN、AlphaFold3 或 PDBFixer，无需重新安装。直接告诉 Agent：
> - 每个工具的位置（例如："RFdiffusion 在 `~/software/RFdiffusion`"）
> - 每个工具运行在哪个 conda 环境中（例如："RFdiffusion 使用 conda 环境 `SE3nv`"）
>
> 插件会自动探测常见安装位置并请你确认。你也可以随时运行 `check_all_tools` 查看已检测到的工具。

### 第 1 步：创建 Conda 环境

```bash
conda create -n protein-design python=3.10
conda activate protein-design
```

### 第 2 步：安装 PDBFixer + OpenMM（Stage 0）

PDBFixer 是唯一的 Python API 依赖；其余均通过子进程调用。

```bash
conda install -c conda-forge pdbfixer openmm>=8.2
```

验证：
```bash
python -c "from pdbfixer import PDBFixer; print('PDBFixer OK')"
```

### 第 3 步：安装 RFdiffusion（Stage 1）

```bash
# 克隆仓库
cd ~/software  # 或你偏好的目录
git clone https://github.com/RosettaCommons/RFdiffusion.git
cd RFdiffusion

# 创建独立的 conda 环境（推荐）
conda env create -f env/SE3nv.yml
conda activate SE3nv

# 安装 RFdiffusion 包
pip install -e .

# 下载模型权重（~2GB）
mkdir -p models
# 按官方说明操作：https://github.com/RosettaCommons/RFdiffusion
# 通常需要从 Zenodo 或 HuggingFace 下载
```

插件按以下顺序查找 `RFdiffusion/scripts/run_inference.py`：
1. `$RFDIFFUSION_PATH/scripts/run_inference.py`（环境变量）
2. `./RFdiffusion/scripts/run_inference.py`
3. `~/RFdiffusion/scripts/run_inference.py`
4. `/opt/RFdiffusion/scripts/run_inference.py`

### 第 4 步：安装 ProteinMPNN（Stage 2）

```bash
cd ~/software
git clone https://github.com/dauparas/ProteinMPNN.git
```

无需额外 pip 安装 —— 直接作为脚本运行。

插件按以下顺序查找 `ProteinMPNN/protein_mpnn_run.py`：
1. `$PROTEINMPNN_PATH/protein_mpnn_run.py`（环境变量）
2. `./ProteinMPNN/protein_mpnn_run.py`
3. `~/ProteinMPNN/protein_mpnn_run.py`
4. `/opt/ProteinMPNN/protein_mpnn_run.py`

### 第 5 步：安装 AlphaFold3（Stage 3）

AlphaFold3 是最复杂的依赖。有两种安装方式：

#### 方案 A：Docker（推荐，最简单）

```bash
cd ~/software
git clone https://github.com/google-deepmind/alphafold3.git
cd alphafold3

# 构建 Docker 镜像
docker build -t alphafold3 -f docker/Dockerfile .

# 下载模型参数（~1.6GB）和数据库（总计 ~2.6TB）
# 参考：https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md
```

> **注意：** 当前插件代码使用本地 Python 执行（`python run_alphafold.py`）。如需 Docker 模式，需要修改 `mcp_server/tools/alphafold.py` 以将命令包装在 `docker run` 中。请参阅该文件中的注释以获取指导。

#### 方案 B：本地安装

```bash
cd ~/software
git clone https://github.com/google-deepmind/alphafold3.git
cd alphafold3

# 安装依赖
pip install -r requirements.txt

# 下载模型参数到 ~/models
# 下载基因数据库到 ~/public_databases
# 参考：https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md
```

插件按以下顺序查找 `alphafold3/run_alphafold.py`：
1. `$ALPHAFOLD_PATH/run_alphafold.py`（环境变量）
2. `./alphafold3/run_alphafold.py`
3. `~/alphafold3/run_alphafold.py`
4. `/opt/alphafold3/run_alphafold.py`

### 第 6 步：告诉插件工具的安装位置

安装完工具后，必须告知插件它们的位置。

**方案 A：环境变量**（临时，仅当前 shell 有效）

```bash
export RFDIFFUSION_PATH="$HOME/software/RFdiffusion"
export PROTEINMPNN_PATH="$HOME/software/ProteinMPNN"
export ALPHAFOLD_PATH="$HOME/software/alphafold3"
export PROTEIN_DESIGN_OUTPUT_DIR="/tmp/protein-design"
```

添加到 `~/.bashrc` 或 `~/.zshrc` 可永久生效。

**方案 B：配置文件**（持久化，推荐）

```bash
mkdir -p ~/.kimi-protein-design
cat > ~/.kimi-protein-design/config.yaml << 'EOF'
output_dir: /tmp/protein-design
max_jobs: 4
timeout: 3600
rfdiffusion_path: /Users/YOURNAME/software/RFdiffusion
proteinmpnn_path: /Users/YOURNAME/software/ProteinMPNN
alphafold_path: /Users/YOURNAME/software/alphafold3
rfdiffusion_conda_env: SE3nv
proteinmpnn_conda_env: null
alphafold_conda_env: null
EOF
```

将 `/Users/YOURNAME` 替换为你的实际主目录路径。

**Conda 环境**：如果每个工具安装在独立的 conda 环境中，在上述配置中设置环境名。插件会自动用 `conda run -n <env>` 包装命令。如果工具在当前环境中，保持为 `null` 即可。

**方案 C：符号链接**（如果不想使用配置文件，最简单的方式）

```bash
ln -s ~/software/RFdiffusion ./RFdiffusion
ln -s ~/software/ProteinMPNN ./ProteinMPNN
ln -s ~/software/alphafold3 ./alphafold3
```

将这些符号链接放在 Kimi Code 启动 MCP 服务器的同一目录中（即插件根目录）。

### 第 7 步：验证安装

安装插件后（`/plugins install ...` + `/new`），运行：

```
/mcp
```

你应该能看到 `protein` 服务器已连接。然后测试：

```
Call get_tool_info
Call health_check
```

`health_check` 会报告 RFdiffusion、ProteinMPNN 和 AlphaFold3 是否可检测到。


## 卸载

### `/plugins install` 实际安装的内容

运行 `/plugins install` 时，Kimi Code 会将插件仓库下载到其内部插件目录（`~/.kimi-code/plugins/...`）并注册：

| 组件 | 说明 | 位置 |
|-----------|-----------|----------|
| **清单** | `kimi.plugin.json` | 插件目录内 |
| **Skills** | `skills/` 下的 7 个 Markdown 文件 | 插件目录内 |
| **MCP Server** | `mcp_server/` 下的 Python 源码 | 插件目录内 |
| **MCP 注册** | Stdio 服务器配置 | Kimi Code 内部状态 |
| **会话启动** | 自动加载 skill 绑定 | Kimi Code 内部状态 |

**重要**：插件**不会**安装 RFdiffusion、ProteinMPNN、AlphaFold3 或 PDBFixer。这些是你单独安装的外部工具。

### 插件级卸载

```
/plugins remove kimi-protein-design
```

这会移除：
- ✅ 插件源码（`~/.kimi-code/plugins/.../kimi-protein-design/`）
- ✅ MCP 服务器注册（protein 服务器不再启动）
- ✅ Skills 索引和会话启动绑定

这**不会**移除：
- ❌ `~/.kimi-protein-design/config.yaml`（你的路径配置）
- ❌ `~/.kimi-code/hooks/` 中的 Hooks（如果你运行过 `install-hooks.py`）
- ❌ `~/.kimi-code/config.toml` 中的 Hooks 条目
- ❌ `/tmp/protein-design/` 中的输出文件
- ❌ 外部工具（RFdiffusion、ProteinMPNN、AlphaFold3、数据库）

### 完全清理（移除所有内容）

要彻底清除所有痕迹：

```bash
# 1. 卸载插件（在 Kimi Code 中）
# /plugins remove kimi-protein-design

# 2. 删除插件配置
rm -rf ~/.kimi-protein-design/

# 3. 删除 hooks（如果已安装）
rm -f ~/.kimi-code/hooks/protein-context-inject.py
rm -f ~/.kimi-code/hooks/gpu-check-hook.py
rm -f ~/.kimi-code/hooks/design-complete-notify.py
rm -f ~/.kimi-code/hooks/background-notify.py

# 4. 编辑 ~/.kimi-code/config.toml 并移除该插件的 [[hooks]] 部分

# 5. 删除历史输出（可选）
rm -rf /tmp/protein-design/

# 6. 外部工具（可选，体积很大）
rm -rf ~/software/RFdiffusion
rm -rf ~/software/ProteinMPNN
rm -rf ~/software/alphafold3
rm -rf ~/public_databases
```

### 清理检查清单

| 组件 | `remove` 命令 | 需要手动清理？ |
|-----------|-----------------|----------------------|
| 插件源码 | ✅ 自动 | 否 |
| MCP 注册 | ✅ 自动 | 否 |
| `~/.kimi-protein-design/config.yaml` | ❌ 否 | `rm -rf ~/.kimi-protein-design/` |
| Hooks 脚本 | ❌ 否 | `rm ~/.kimi-code/hooks/*.py` |
| Hooks config.toml 条目 | ❌ 否 | 编辑 `~/.kimi-code/config.toml` |
| 输出文件 | ❌ 否 | `rm -rf /tmp/protein-design/` |
| 外部工具 | ❌ 否 | `rm -rf ~/software/...` |


## 快速开始

### 示例 1：设计一个 150 个氨基酸的单体

```
User: Generate a 150 amino acid protein backbone
→ Plugin auto-runs RFdiffusion with contig [150-150]
```

### 示例 2：为 PD-L1 设计结合物

```
User: Design a binder targeting PD-L1
→ Stage 0: PDBFixer preprocesses target.pdb
→ Stage 1: RFdiffusion generates binder backbones
→ Stage 2: ProteinMPNN designs binder sequences
→ Stage 3: AlphaFold3 validates structures
→ Stage 4: Filter by ipTM > 0.8 and pLDDT > 80
```


## 架构

```
kimi-protein-design/
├── kimi.plugin.json              # Plugin manifest
├── skills/                       # Workflow guidance
│   ├── protein-design-context/   # Session-start context
│   ├── structure-preprocessing/  # Stage 0: PDBFixer
│   ├── structure-generation/     # Stage 1: RFdiffusion
│   ├── sequence-design/          # Stage 2: ProteinMPNN
│   ├── structure-validation/     # Stage 3: AlphaFold3
│   ├── filtering-ranking/        # Stage 4: Filtering
│   └── full-pipeline/            # End-to-end orchestration
├── mcp_server/                   # MCP Server (stdio JSON-RPC)
│   ├── server.py                 # Main entry
│   ├── tools/                    # Tool implementations
│   │   ├── job_manager.py        # Async task management
│   │   ├── pdbfixer_tool.py      # PDB preprocessing
│   │   ├── rfdiffusion.py        # Backbone generation
│   │   ├── proteinmpnn.py        # Sequence design
│   │   ├── alphafold.py          # Structure validation
│   │   ├── format_converter.py   # FASTA ↔ JSON conversion
│   │   ├── filtering.py          # Quality filtering
│   │   └── system_info.py        # Environment checks
│   ├── utils/                    # Utilities
│   │   ├── config.py             # Configuration
│   │   └── gpu_utils.py          # GPU detection
│   └── hooks/                    # Recommended hooks
│       ├── install-hooks.py      # One-click installer
│       ├── protein-context-inject.py
│       ├── gpu-check-hook.py
│       ├── design-complete-notify.py
│       └── background-notify.py
└── README.md
```


## MCP 工具

| 工具 | 说明 |
|------|-------------|
| `get_tool_info` | 列出所有工具及其参数 |
| `health_check` | 检查 GPU、CUDA、conda、磁盘空间 |
| `submit_job` | 提交异步计算任务 |
| `query_job` | 按 task_id 轮询任务状态 |
| `cancel_job` | 取消正在运行的任务 |
| `run_pdbfixer` | 预处理 PDB/CIF（Stage 0 必需） |
| `run_rfdiffusion` | 生成蛋白质骨架 |
| `run_proteinmpnn` | 设计氨基酸序列 |
| `run_alphafold3` | 预测并验证结构 |
| `convert_format` | 将 FASTA 转换为 AlphaFold3 JSON |
| `run_filtering` | 按指标过滤和排序 |
| `check_batch_progress` | 同时检查多个任务 |


## 配置

环境变量：

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `PROTEIN_DESIGN_OUTPUT_DIR` | `/tmp/protein-design` | 输出目录 |
| `PROTEIN_DESIGN_MAX_JOBS` | `4` | 最大并发任务数 |
| `PROTEIN_DESIGN_TIMEOUT` | `3600` | 任务超时时间（秒） |
| `RFDIFFUSION_PATH` | auto-detect | RFdiffusion 安装路径 |
| `PROTEINMPNN_PATH` | auto-detect | ProteinMPNN 安装路径 |
| `ALPHAFOLD_PATH` | auto-detect | AlphaFold3 安装路径 |

配置文件：`~/.kimi-protein-design/config.yaml`

```yaml
output_dir: /tmp/protein-design
max_jobs: 4
timeout: 3600
rfdiffusion_path: /opt/RFdiffusion
proteinmpnn_path: /opt/ProteinMPNN
alphafold_path: /opt/alphafold3
```


## Hooks（强烈推荐）

Kimi Code 0.6.0+ 支持 hooks，用于增强蛋白质设计工作流。

### 安装 Hooks

```bash
python mcp_server/hooks/install-hooks.py
```

这会安装：
- **UserPromptSubmit** — 自动将 GPU/工具状态注入模型上下文
- **PreToolUse** — 如果 GPU/磁盘不足，阻止 submit_job
- **PostToolUse** — 任务完成时桌面通知
- **Notification** — 后台任务完成/失败时提醒

然后重启 Kimi Code：`/new`

### 手动 Hook 配置

添加到 `~/.kimi-code/config.toml`：

```toml
[[hooks]]
event = "UserPromptSubmit"
matcher = "(?i)(protein|pdb|binder|alphafold|rfdiffusion|proteinmpnn|design|structure|sequence|residue|loop|scaffold)"
command = "python ~/.kimi-code/hooks/protein-context-inject.py"
timeout = 3

[[hooks]]
event = "PreToolUse"
matcher = "mcp__.*__submit_job"
command = "python ~/.kimi-code/hooks/gpu-check-hook.py"
timeout = 5

[[hooks]]
event = "PostToolUse"
matcher = "mcp__.*__query_job"
command = "python ~/.kimi-code/hooks/design-complete-notify.py"
timeout = 5

[[hooks]]
event = "Notification"
matcher = "task\\.completed|task\\.failed|task\\.killed"
command = "python ~/.kimi-code/hooks/background-notify.py"
timeout = 5
```


## 使用 CronCreate 进行批量验证

对于大规模筛选（>10 个设计），使用 CronCreate 代替阻塞式轮询：

1. 提交所有 AlphaFold3 验证任务（异步）
2. 创建定期检查：
   ```
   CronCreate(cron="*/10 * * * *", prompt="Check AF3 batch progress for task_ids [X,Y,Z]. Report completed count and pLDDT>80 pass rate.")
   ```
3. 会话被释放，可执行其他工作
4. 完成后，取消定时器：
   ```
   CronDelete(id="<id>")
   ```


## 质量阈值

| 指标 | 可接受 | 良好 | 优秀 |
|--------|-----------|------|-----------|
| pLDDT | >70 | >80 | >90 |
| ipTM | >0.6 | >0.8 | >0.9 |
| pTM | >0.5 | >0.7 | >0.9 |


## 故障排除

| 问题 | 解决方案 |
|-------|----------|
| 插件未加载 | 安装后运行 `/new` |
| `run_pdbfixer` 未找到 | `conda install -c conda-forge pdbfixer openmm` |
| RFdiffusion 未找到 | 设置 `RFDIFFUSION_PATH` 环境变量 |
| GPU 显存不足 | 减小 `num_designs` 或 `diffuser_T` |
| AlphaFold3 MSA 超时 | 重新运行时设置 `run_data_pipeline=false` |
| Hooks 未生效 | 验证 `~/.kimi-code/config.toml` 语法，然后 `/new` |


## 许可证

MIT


## 致谢

- RFdiffusion — [Watson et al., 2023](https://www.nature.com/articles/s41586-023-06415-8)
- ProteinMPNN — [Dauparas et al., 2022](https://www.science.org/doi/10.1126/science.add2187)
- AlphaFold3 — [Abramson et al., 2024](https://www.nature.com/articles/s41586-024-07487-w)
- PDBFixer — OpenMM project

---
title: 安装指南
source: README.zh.md
---

# 安装指南

> **重要：** 本插件**不附带** RFdiffusion、ProteinMPNN、AlphaFold3 或 PDBFixer。这些都是大型机器学习模型（多 GB），必须单独安装。插件提供的是**编排层**——skills、hooks 和 standalone scripts——用于引导智能体完成设计流程。

## 架构概览

本插件采用 **skills + hooks + scripts** 架构：

- **Skills** (`skills/`) —— 79 个 Markdown 格式的工作流指南，告诉智能体如何使用每个工具
- **Hooks** (`protein_design/hooks/`) —— 24 个自动化脚本，用于上下文注入、GPU 检查、进度跟踪和通知
- **Standalone Scripts** (`scripts/`) —— 16 个直接 CLI 脚本，用于工具执行

本插件适用于任何能读取 skills 并运行 Python 脚本的编程智能体。

## 选择你的智能体

| 智能体 | 配置方式 |
|--------|----------|
| **Claude Code** | `claude plugin marketplace add devxia/protein-design-skills`，然后 `claude plugin install protein-design-skills@protein-design-skills` |
| **Codex CLI** | `codex plugin marketplace add devxia/protein-design-skills`，然后 `codex plugin install protein-design-skills` |
| **Kimi Code** | `/plugins install https://github.com/devxia/protein-design-skills` |

手动安装时，按智能体安装 hooks：

```bash
# Claude Code
python protein_design/hooks/install-hooks.py claude

# Codex CLI
python protein_design/hooks/install-hooks.py codex

# 所有智能体
python protein_design/hooks/install-hooks.py
```

你也可以为 Claude Code 和 Codex CLI 安装项目级本地 hooks：

```bash
python protein_design/hooks/install-hooks.py --local claude codex
```

## 安装插件

```bash
git clone https://github.com/devxia/protein-design-skills.git
cd protein-design-skills
pip install -r requirements.txt
```

### 安装 hooks（推荐）

Hooks 提供自动上下文注入、GPU 安全检查以及桌面通知：

```bash
# 适用于 Claude Code
python protein_design/hooks/install-hooks.py claude

# 适用于 Codex CLI
python protein_design/hooks/install-hooks.py codex

# 适用于所有智能体
python protein_design/hooks/install-hooks.py
```

Hooks 按智能体安装，可自定义。参见 `protein_design/hooks/install-hooks.py --help` 了解选项。

### Kimi Code

从 GitHub 安装：
```
/plugins install https://github.com/devxia/protein-design-skills
```

从本地目录安装：
```
/plugins install /path/to/protein-design-skills
```

安装后，启动**新会话**：
```
/new
```

> 插件变更仅对新会话生效。

## 系统要求

- Python >= 3.9
- CUDA GPU，显存 >= 16GB（推荐）
- Conda（miniconda 或 anaconda）
- 单独安装：RFdiffusion、ProteinMPNN、AlphaFold3、PDBFixer + OpenMM

## 安装外部工具

> **已有这些工具？** 只需告诉 Agent 每个工具的位置和使用的 conda 环境。插件会自动检测常见安装位置。

### 步骤 1：创建 Conda 环境

```bash
conda create -n protein-design python=3.10
conda activate protein-design
```

### 步骤 2：安装 PDBFixer + OpenMM

```bash
conda install -c conda-forge pdbfixer openmm>=8.2
```

验证：`python -c "from pdbfixer import PDBFixer; print('PDBFixer OK')"`

### 步骤 3：安装 RFdiffusion

```bash
cd ~/software
git clone https://github.com/RosettaCommons/RFdiffusion.git
cd RFdiffusion
conda env create -f env/SE3nv.yml
conda activate SE3nv
pip install -e .
```

按官方说明下载模型权重（~2GB）。

### 步骤 4：安装 ProteinMPNN

```bash
cd ~/software
git clone https://github.com/dauparas/ProteinMPNN.git
```

无需 pip 安装，直接作为脚本运行。

### 步骤 5：安装 AlphaFold3

**方案 A：Docker（推荐）**

```bash
git clone https://github.com/google-deepmind/alphafold3.git
cd alphafold3
docker build -t alphafold3 -f docker/Dockerfile .
```

**方案 B：本地安装**

```bash
git clone https://github.com/google-deepmind/alphafold3.git
cd alphafold3
pip install -r requirements.txt
```

下载模型参数（~1.6GB）：访问 https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md 申请访问权限。

下载遗传数据库（~2.6TB）：参见 AlphaFold3 文档中的数据库设置说明。

**方案 C：无数据库验证器（最简单）**

如果没有 2.6TB 空间存放数据库，可以使用以下替代方案：

| 工具 | 安装命令 | GPU | 数据库 | 速度 |
|------|---------|-----|--------|------|
| ESMFold | `pip install fair-esm` | 可选 | 无 | ~2秒/序列 |
| OmegaFold | `pip install omegafold` | 需要 | 无 | ~5秒/序列 |
| Boltz-1 | `pip install boltz` | 需要 | 无 | ~10秒/序列 |
| Chai-1 | 参见 chai-1 文档 | 需要 | 无 | ~10秒/序列 |

### 可选：安装额外的验证工具

| 工具 | 许可证 | 最佳场景 |
|------|--------|----------|
| Boltz-1 | MIT | 复合物、共价修饰 |
| Chai-1 | Apache 2.0 | 约束条件、许可证灵活性 |
| OmegaFold | MIT | 快速、无需数据库 |
| ESMFold | MIT | 超快速筛选、CPU 兼容 |

## 配置工具路径

**方法 A：环境变量**

```bash
export RFDIFFUSION_PATH="$HOME/software/RFdiffusion"
export PROTEINMPNN_PATH="$HOME/software/ProteinMPNN"
export ALPHAFOLD_PATH="$HOME/software/alphafold3"
export PROTEIN_DESIGN_OUTPUT_DIR="/tmp/protein-design"
```

**方法 B：配置文件（推荐）**

```yaml
# ~/.protein-design/config.yaml
output_dir: /tmp/protein-design
max_jobs: 4
timeout: 3600
rfdiffusion_path: /Users/YOURNAME/software/RFdiffusion
proteinmpnn_path: /Users/YOURNAME/software/ProteinMPNN
alphafold_path: /Users/YOURNAME/software/alphafold3
rfdiffusion_conda_env: SE3nv
proteinmpnn_conda_env: null
alphafold_conda_env: null
```

> **旧路径兼容**：`~/.kimi-protein-design/config.yaml` 也受支持。

**方法 C：符号链接**

```bash
ln -s ~/software/RFdiffusion ./RFdiffusion
ln -s ~/software/ProteinMPNN ./ProteinMPNN
ln -s ~/software/alphafold3 ./alphafold3
```

## 验证安装

安装 hooks 和外部工具后，验证一切正常：

```bash
# 检查 skill 发现
ls skills/

# 测试 standalone script 执行
python scripts/run_pdbfixer.py --help

# 检查工具检测
python protein_design/hooks/session-health-check.py
```

`session-health-check` hook 会报告已安装的工具、检测到的路径，并为缺失的工具提供安装指南。

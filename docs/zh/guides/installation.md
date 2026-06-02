---
title: 安装指南
source: README.zh.md
---

# 安装指南

> ⚠️ **重要**：本插件**不附带** RFdiffusion、ProteinMPNN、AlphaFold3 或 PDBFixer。这些都是大型机器学习模型（多 GB），必须单独安装。插件提供的是**编排层**，通过子进程调用这些工具。

## 安装插件

### 从 GitHub 安装（推荐）

```
/plugins install https://github.com/devxia/kimi-protein-design
```

### 从本地目录安装

```
/plugins install /path/to/kimi-protein-design
```

### 激活

安装后，启动**新会话**：

```
/new
```

> 插件变更仅对新会话生效。

## 系统要求

- Kimi Code >= 0.6.0
- Python >= 3.9
- CUDA GPU，显存 >= 16GB（推荐）
- Conda（miniconda 或 anaconda）
- 单独安装：RFdiffusion、ProteinMPNN、AlphaFold3、PDBFixer + OpenMM

## 安装外部工具

> 💡 **已有这些工具？** 只需告诉 Agent 每个工具的位置和使用的 conda 环境。插件会自动检测常见安装位置。

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

下载模型参数（~1.6GB）和遗传数据库（~2.6TB）。

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
# ~/.kimi-protein-design/config.yaml
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

**方法 C：符号链接**

```bash
ln -s ~/software/RFdiffusion ./RFdiffusion
ln -s ~/software/ProteinMPNN ./ProteinMPNN
ln -s ~/software/alphafold3 ./alphafold3
```

## 验证安装

```
/mcp
```

应显示 `protein` 服务器已连接。然后测试：

```
Call get_tool_info
Call health_check
```

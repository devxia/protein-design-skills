# 🧬 蛋白质设计技能插件

> [English](./README.md) | 中文

一个用于端到端蛋白质设计工作流的通用插件，支持多种编程智能体（Claude Code、Codex CLI、Kimi Code 等）。编排 RFdiffusion、ProteinMPNN、AlphaFold3、Boltz-1、Chai-1 等 15+ 工具，完成从骨架生成到结构验证的完整流程。

## 架构

本插件采用**三层架构** — 无需服务器：

| 层 | 说明 | 数量 | 位置 |
|----|------|------|------|
| **Skills** | 面向 LLM 的 Markdown 知识 | 76 | `skills/` |
| **Hooks** | 自动化脚本 | 22 | `protein_design/hooks/` |
| **Scripts** | 独立执行脚本 | 19 | `scripts/` |

**工作原理：** Skills 教导智能体 → Hooks 自动触发 → Scripts 直接运行工具。

## 功能特性

- **Stage 0 — 结构预处理**：使用 PDBFixer 自动修复 PDB
- **Stage 1 — 骨架生成**：RFdiffusion、Chroma、FoldFlow、DiffPepBuilder、RFpeptides 等
- **Stage 2 — 序列设计**：ProteinMPNN、LigandMPNN、ESM-IF1、EvoDiff
- **Stage 3 — 结构验证**：AlphaFold3、Boltz-1、Chai-1、OmegaFold、ESMFold、Protenix、OpenFold3
- **Stage 4 — 过滤与排序**：质量指标、交叉验证共识、评分优先筛选
- **76 个技能**：覆盖 30+ 设计流水线，从快速筛选到完整验证
- **22 个钩子**：上下文注入、GPU 安全检查、工具推荐、流水线编排、错误恢复
- **19 个独立脚本**：所有流水线阶段的直接命令行执行

## 15+ 设计流水线

| 流水线 | 阶段 1 | 阶段 2 | 阶段 3 | 适用场景 |
|--------|--------|--------|--------|----------|
| **标准** | RFdiffusion | ProteinMPNN | AlphaFold3 | 通用用途 |
| **快速筛选** | RFdiffusion | ProteinMPNN | ESMFold/OmegaFold | 无需数据库 |
| **配体感知** | RFdiffusionAA | LigandMPNN | AlphaFold3 | 小分子、辅因子 |
| **肽段** | DiffPepBuilder | 内置 | AlphaFold3 | 8-30aa 肽段 |
| **大环肽** | RFpeptides | ProteinMPNN | AlphaFold3/Boltz-1 | 12-18aa 环肽 |
| **交叉验证** | RFdiffusion | ProteinMPNN | Boltz-1 + Chai-1 + OmegaFold | 最稳健的排名 |
| **评分优先** | RFdiffusion | ProteinMPNN (score_only) | AlphaFold3 | 预筛选以节省计算 |
| **Chroma** | Chroma（联合） | — | AlphaFold3 | 全原子、自然语言 |
| **ColabDesign** | AfDesign | AfDesign | AlphaFold3 | 无本地 GPU |
| **集成** | RFdiffusion | ProteinMPNN + ESM-IF1 | AlphaFold3 | 最大多样性 |
| **FoldFlow** | FoldFlow | ProteinMPNN | AlphaFold3 | 快速流匹配 |
| **OpenFold3** | RFdiffusion | ProteinMPNN | OpenFold3 | pip 安装，AF3 等效 |
| **Protenix** | RFdiffusion | ProteinMPNN | Protenix | 训练 + 推理扩展 |
| **抗体** | IgDiff/RFdiffusion | AbMPNN/ProteinMPNN | AlphaFold3 | 抗体、纳米抗体 |
| **酶** | RFdiffusionAA | LigandMPNN | AlphaFold3 | 活性位点、催化 |

## 快速开始

### 前置条件

- Python >= 3.9
- 显存 >= 8GB 的 CUDA 显卡（推荐 16GB+）
- Conda（miniconda 或 anaconda）
- 单独安装：RFdiffusion、ProteinMPNN、AlphaFold3、PDBFixer + OpenMM

### 插件市场安装（推荐）

**Claude Code：**
```bash
claude plugin marketplace add devxia/protein-design-skills
claude plugin install protein-design-skills@protein-design-skills
```

**Codex CLI：**
```bash
codex plugin marketplace add devxia/protein-design-skills
codex plugin install protein-design-skills
```

**Kimi Code：**
```bash
/plugins install https://github.com/devxia/protein-design-skills
/new
```

### 手动安装

```bash
# 克隆插件
git clone https://github.com/devxia/protein-design-skills.git
cd protein-design-skills

# 安装 Python 依赖
pip install -r requirements.txt
```

### 安装钩子（按你的智能体选择）

```bash
# 自动检测所有已安装的智能体
python protein_design/hooks/install-hooks.py

# 或指定安装到特定智能体
python protein_design/hooks/install-hooks.py claude    # Claude Code
python protein_design/hooks/install-hooks.py codex     # Codex CLI
python protein_design/hooks/install-hooks.py kimi      # Kimi Code

# 同时安装到多个智能体
python protein_design/hooks/install-hooks.py claude codex

# 验证插件清单
python protein_design/hooks/install-hooks.py --validate
```

**安装内容说明：**
- **Claude Code**: 钩子注册到 `~/.claude/settings.json`（或使用 `--local` 注册到 `.claude/settings.json`）
- **Codex CLI**: 钩子写入 `~/.codex/hooks.json`（或使用 `--local` 写入 `.codex/hooks.json`）
- **Kimi Code**: 钩子注册到 `~/.kimi-code/config.toml`

**项目级本地安装（不写全局配置）：**
```bash
python protein_design/hooks/install-hooks.py --local claude codex
```

### 验证安装

```bash
# 检查钩子是否注册成功（以 Claude Code 为例）
cat ~/.claude/settings.json | grep -A 5 "protein"

# 应该看到类似以下的钩子条目：
# "UserPromptSubmit": [..., "session-health-check.py", ...]
```

### 安装第三方工具

你不需要安装所有工具 — 根据你的需求选择即可：

| 工具 | 用途 | 安装难度 | 无 GPU 可用替代 |
|------|------|---------|----------------|
| PDBFixer | 结构修复（Stage 0） | ⭐ 简单 | — |
| RFdiffusion | 骨架生成（Stage 1） | ⭐⭐ 中等 | Chroma、FoldFlow |
| ProteinMPNN | 序列设计（Stage 2） | ⭐ 简单 | ESM-IF1、LigandMPNN |
| AlphaFold3 | 结构验证（Stage 3） | ⭐⭐⭐ 复杂 | ESMFold、OmegaFold（无需数据库） |

**没有 GPU？** 使用 ESMFold 或 OmegaFold 进行快速验证，它们可以在 CPU 上运行。

**没有 2.6TB 数据库？** 使用 `--run-data-pipeline false` 跳过 AlphaFold3 的 MSA 搜索，或使用 ESMFold/OmegaFold。

> 📚 详细安装步骤：[docs/zh/guides/installation.md](./docs/zh/guides/installation.md)

### 开始设计

```bash
# 1. 生成 10 个 150 残基的骨架
python scripts/run_rfdiffusion.py --contig "150-150" --num-designs 10 --verbose

# 2. 为每个骨架设计 8 条序列
python scripts/run_proteinmpnn.py --pdb-path "outputs/design_*.pdb" --out-folder outputs/seqs/ --num-seq 8 --verbose

# 3. 用 OmegaFold 验证（无需数据库）
python scripts/run_omegafold.py --input outputs/seqs/seqs.fa --output-dir outputs/validation/ --verbose

# 4. 过滤优质设计
python scripts/run_filtering.py --results-dir outputs/validation/ --min-plddt 75 --top-n 5 --verbose
```

### 通过对话完成设计

直接告诉智能体你想做什么：

```
User: 为 PD-L1 设计一个结合物
→ Stage 0: PDBFixer 预处理 target.pdb
→ Stage 1: RFdiffusion 生成结合物骨架（20 个）
→ Stage 2: ProteinMPNN 设计序列（每个 8 条）
→ Stage 3: AlphaFold3 验证结构
→ Stage 4: 按 ipTM > 0.8 和 pLDDT > 80 过滤
```

### 批量流水线

```bash
# 创建流水线配置
cat > pipeline.yaml << 'EOF'
stages:
  - name: "Stage 0: PDBFixer"
    command: [python, scripts/run_pdbfixer.py, --input, target.pdb, --output, outputs/fixed.pdb]
  - name: "Stage 1: RFdiffusion"
    command: [python, scripts/run_rfdiffusion.py, --input-pdb, outputs/fixed.pdb, --contig, "[150-150]", --num-designs, "50"]
  - name: "Stage 2: ProteinMPNN"
    command: [python, scripts/run_proteinmpnn.py, --pdb-path, "outputs/design_*.pdb", --out-folder, outputs/seqs/, --num-seq, "8"]
  - name: "Stage 3: OmegaFold"
    command: [python, scripts/run_omegafold.py, --input, outputs/seqs/seqs.fa, --output-dir, outputs/validation/]
  - name: "Stage 4: Filtering"
    command: [python, scripts/run_filtering.py, --results-dir, outputs/validation/, --min-plddt, "75", --top-n, "10"]
EOF

# 一键运行整个流水线
python scripts/batch_runner.py --config pipeline.yaml
```

### 验证安装成功

```bash
# 测试钩子执行（应打印欢迎消息）
echo "design a protein" | python protein_design/hooks/user-onboarding.py

# 测试工具检测（应列出已安装/缺失的工具）
echo "protein design" | python protein_design/hooks/session-health-check.py

# 测试脚本执行（应显示帮助信息）
python scripts/run_rfdiffusion.py --help
```

## 钩子功能（安装后自动生效）

安装钩子后，你的智能体会自动获得以下能力：

| 钩子 | 触发时机 | 功能 |
|------|---------|------|
| **user-onboarding** | 首次蛋白质提示 | 欢迎消息 + 工具状态 + 快速开始指南 |
| **session-health-check** | 蛋白质相关提示 | 检查已安装工具，为缺失工具推荐替代方案 |
| **tool-recommender** | 设计请求 | 根据场景推荐脚本和参数 |
| **error-recovery** | 工具执行失败 | 建议修复方案、替代工具、安装命令 |
| **progress-reporter** | 长时间任务 | ETA 估计、文件计数、进度更新 |
| **pipeline-orchestrator** | 阶段完成 | 自动检测下一步，建议后续操作 |
| **quality-gate** | 验证结果 | 基于阈值的通过/失败判定 |
| **design-report** | 过滤完成 | 自动生成汇总报告和排名 |
| **gpu-check-hook** | GPU 任务前 | 检查显存，不足时发出警告 |

无需手动配置 — 钩子会在你讨论蛋白质设计时自动触发。

## 支持的智能体

| 智能体 | 配置位置 | 钩子格式 | 状态 |
|--------|---------|---------|------|
| **Claude Code** | `~/.claude/settings.json`（或使用 `--local` 时 `.claude/settings.json`） | JSON | ✅ 完全支持 |
| **Codex CLI** | `~/.codex/hooks.json`（或使用 `--local` 时 `.codex/hooks.json`） | JSON | ✅ 完全支持 |
| **Kimi Code** | `~/.kimi-code/config.toml` | TOML | ✅ 完全支持 |

所有智能体都获得相同的 22 个钩子和 76 个技能。插件会自动检测已安装的智能体。

## 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| GPU | NVIDIA 8GB 显存 | NVIDIA A100/V100 16GB+ |
| CPU | 8 核 | 16+ 核 |
| 内存 | 32GB | 64GB+ |
| 磁盘 | 100GB | 3TB（含数据库） |
| 系统 | Linux | Linux (Ubuntu 20.04+) |
| Python | 3.9 | 3.10+ |

> **注意：** 本插件不附带 ML 模型，它提供的是编排层（skills + hooks + scripts），用于调用你已安装的工具。

## 配置

```bash
# 设置工具路径
export RFDIFFUSION_PATH="~/RFdiffusion"
export PROTEINMPNN_PATH="~/ProteinMPNN"
export ALPHAFOLD_PATH="~/alphafold3"

# 或使用配置文件
cat ~/.protein-design/config.yaml
```

## 进度追踪

```bash
# 单次汇总
python scripts/summarize_outputs.py --output-dir outputs/

# 实时监控（每 30 秒刷新）
python scripts/summarize_outputs.py --output-dir outputs/ --watch

# 项目级仪表盘
python scripts/project_dashboard.py --output-dir outputs/ \
  --expected-backbones 50 \
  --expected-sequences 400 \
  --expected-validations 50
```

## 文档

| 文档 | 说明 |
|------|------|
| [Skills 索引](./skills/SKILL_INDEX.md) | 所有 76 个技能及导航 |
| [安装指南](./docs/zh/guides/installation.md) | 分步工具安装和配置 |
| [快速开始](./docs/zh/guides/quickstart.md) | 从零到第一个设计 |
| [流程架构](./docs/zh/guides/pipeline.md) | 5 阶段设计流程 |
| [API 参考 —— Scripts](./docs/zh/api-reference/scripts.md) | 所有 standalone scripts 及参数 |
| [故障排除](./docs/zh/guides/troubleshooting.md) | 常见问题及解决方案 |
| [变更记录](./docs/zh/release-notes/changelog.md) | 发布说明 |

## 质量阈值

| 指标 | 可接受 | 良好 | 优秀 |
|------|--------|------|------|
| pLDDT | >70 | >80 | >90 |
| ipTM | >0.6 | >0.8 | >0.9 |
| pTM | >0.5 | >0.7 | >0.9 |

## 安装故障排除

### 钩子没有触发？

```bash
# 检查钩子是否注册成功
cat ~/.claude/settings.json | grep protein  # Claude Code
cat ~/.codex/hooks.json | grep protein   # Codex CLI

# 重新安装钩子（强制覆盖）
python protein_design/hooks/install-hooks.py claude --force

# 列出所有已安装的钩子
python protein_design/hooks/install-hooks.py --list
```

### "Module not found" 错误？

```bash
# 确保在插件目录中
cd protein-design-skills

# 安装依赖
pip install -r requirements.txt
```

### 智能体未被检测到？

```bash
# 手动为你的智能体安装
python protein_design/hooks/install-hooks.py claude
python protein_design/hooks/install-hooks.py codex
python protein_design/hooks/install-hooks.py kimi
```

### 检查钩子安装状态

```bash
# 列出每个智能体的已安装钩子
python protein_design/hooks/install-hooks.py --list

# 或手动检查
ls -la ~/.claude/hooks/     # Claude Code
ls -la ~/.codex/hooks/      # Codex CLI
ls -la ~/.kimi-code/hooks/  # Kimi Code
```

## 插件结构

本项目支持多个编码智能体，每个智能体有专用的 manifest 文件：

| 文件 | 用途 | 使用者 |
|------|------|--------|
| `.claude-plugin/plugin.json` | Claude Code 插件 manifest | Claude Code |
| `.claude-plugin/marketplace.json` | Claude 市场注册 | `claude plugin marketplace add` |
| `.codex-plugin/plugin.json` | Codex CLI 插件 manifest | Codex CLI |
| `plugin.json` | 根目录元数据 | npm、GitHub、通用工具 |
| `kimi.plugin.json` | Kimi Code 插件 manifest | Kimi Code |
| `.agents/plugins/marketplace.json` | 多智能体市场索引 | `.agents` 插件加载器 |
| `hooks/hooks.json` | 权威钩子定义 | `install-hooks.py`、Claude Code 插件加载器 |

`.claude-plugin/plugin.json` 遵循 [Claude Code plugin-structure 规范](https://docs.anthropic.com/en/docs/claude-code/plugins)。钩子也可通过 `protein_design/hooks/install-hooks.py` 安装，适用于不使用标准钩子加载器的智能体。

## 许可证

MIT

## 致谢

- RFdiffusion — [Watson et al., 2023](https://www.nature.com/articles/s41586-023-06415-8)
- ProteinMPNN — [Dauparas et al., 2022](https://www.science.org/doi/10.1126/science.add2187)
- AlphaFold3 — [Abramson et al., 2024](https://www.nature.com/articles/s41586-024-07487-w)
- Boltz-1 — [Wöhlke et al.](https://github.com/jwohlwend/boltz)
- Chai-1 — [Chai Discovery](https://github.com/chaidiscovery/chai1)
- Protenix — [ByteDance](https://github.com/bytedance/Protenix)
- PDBFixer — OpenMM project

# 🧬 Protein Design MCP

> [English](./README.md) | 中文

一个用于端到端蛋白质设计工作流的通用插件，支持多种编程智能体（Claude Code、Codex CLI、Kimi Code 等）。通过自然语言对话，即可生成蛋白质骨架、设计序列、验证结构并排序结果。

## 功能特性

- **Stage 0 — 结构预处理**：使用 PDBFixer 自动修复 PDB
- **Stage 1 — 骨架生成**：RFdiffusion 用于单体、结合物、基序支架及对称寡聚体
- **Stage 2 — 序列设计**：ProteinMPNN 用于氨基酸序列分配
- **Stage 3 — 结构验证**：AlphaFold3 用于置信度评分（pLDDT、ipTM、pTM）
- **Stage 4 — 过滤与排序**：自动质量过滤及综合评分
- **异步任务管理**：提交长时间运行的任务并轮询结果
- **批量验证**：支持大规模 AlphaFold3 筛选的定时调度
- **Hooks (0.6.0+)**：上下文注入、GPU 安全检查及桌面通知


> **注意：** 本插件不捆绑 RFdiffusion、ProteinMPNN、AlphaFold3 或 PDBFixer。这些是大型机器学习模型（多 GB），必须单独安装。插件提供编排层（MCP Server + Skills），通过子进程调用这些工具。


## 安装

### 前置条件

本插件可与任何支持 MCP 的编程智能体配合使用（Claude Code、Codex CLI、Kimi Code 等）。

### 方式一：Claude Code

```bash
# 克隆插件
git clone https://github.com/devxia/protein-design-mcp.git
cd protein-design-mcp

# 安装依赖
pip install -r requirements.txt

# 项目根目录的 .mcp.json 会自动配置 MCP 服务器。
```

### 方式二：Kimi Code

```
/plugins install https://github.com/devxia/protein-design-mcp
/new
```

### 方式三：其他 MCP 智能体

将以下内容添加到智能体的 MCP 配置中：

```json
{
  "mcpServers": {
    "protein-design-mcp": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/protein-design-mcp",
      "env": {
        "PYTHONPATH": "/path/to/protein-design-mcp",
        "PROTEIN_DESIGN_OUTPUT_DIR": "/tmp/protein-design",
        "PROTEIN_DESIGN_MAX_JOBS": "4"
      }
    }
  }
}
```

### 环境要求

- Python >= 3.9
- 显存 >= 16GB 的 CUDA 显卡（推荐）
- Conda（miniconda 或 anaconda）
- 单独安装：RFdiffusion、ProteinMPNN、AlphaFold3、PDBFixer + OpenMM

> 📚 **各工具的详细安装步骤**：[docs/zh/guides/installation.md](./docs/zh/guides/installation.md)


## 通过与 Agent 对话完成设置

配置插件最简单的方式就是**直接和 Agent 对话**。

**已经安装了这些工具？** 直接告诉 Agent：
- 每个工具的位置（例如："RFdiffusion 在 `~/software/RFdiffusion`"）
- 每个工具运行在哪个 conda 环境中（例如："RFdiffusion 使用 conda 环境 `SE3nv`"）

插件会自动探测常见安装位置并请你确认。你也可以随时运行 `check_all_tools` 查看已检测到的工具。

**偏好手动配置？** 你可以通过以下方式设置路径：
- 环境变量（`RFDIFFUSION_PATH`、`PROTEINMPNN_PATH`、`ALPHAFOLD_PATH`）
- 配置文件（`~/.protein-design/config.yaml`）
- 插件根目录中的符号链接

> 📚 详见 [docs/zh/guides/installation.md](./docs/zh/guides/installation.md) 中的详细配置说明。


## 快速开始

### 示例 1：设计一个 150 个氨基酸的单体

```
User: 生成一个 150 个氨基酸的蛋白质骨架
→ 插件自动运行 RFdiffusion，contig 为 [150-150]
```

### 示例 2：为 PD-L1 设计结合物

```
User: 为 PD-L1 设计一个结合物
→ Stage 0: PDBFixer 预处理 target.pdb
→ Stage 1: RFdiffusion 生成结合物骨架
→ Stage 2: ProteinMPNN 设计结合物序列
→ Stage 3: AlphaFold3 验证结构
→ Stage 4: 按 ipTM > 0.8 和 pLDDT > 80 过滤
```

流程默认值：10 个骨架 → 每个 8 条序列 → 每个 5 次预测。可通过自然语言调整（例如："生成 50 个骨架"、"用 3 个种子验证"）。


## 文档

| 文档 | 说明 |
|----------|-------------|
| [安装指南](./docs/zh/guides/installation.md) | 分步工具安装和配置 |
| [快速开始](./docs/zh/guides/quickstart.md) | 流程默认值和示例工作流 |
| [流程架构](./docs/zh/guides/pipeline.md) | 5 阶段设计流程和项目结构 |
| [API 参考](./docs/zh/api-reference/tools.md) | 所有 MCP 工具及其参数 |
| [故障排除](./docs/zh/guides/troubleshooting.md) | 常见问题及解决方案 |
| [变更记录](./docs/zh/release-notes/changelog.md) | 发布说明 |


## 质量阈值

| 指标 | 可接受 | 良好 | 优秀 |
|--------|-----------|------|-----------|
| pLDDT | >70 | >80 | >90 |
| ipTM | >0.6 | >0.8 | >0.9 |
| pTM | >0.5 | >0.7 | >0.9 |


## 许可证

MIT


## 致谢

- RFdiffusion — [Watson et al., 2023](https://www.nature.com/articles/s41586-023-06415-8)
- ProteinMPNN — [Dauparas et al., 2022](https://www.science.org/doi/10.1126/science.add2187)
- AlphaFold3 — [Abramson et al., 2024](https://www.nature.com/articles/s41586-024-07487-w)
- PDBFixer — OpenMM project

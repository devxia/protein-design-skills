---
title: 流程架构
source: README.zh.md
---

# 流程架构

## 项目结构

```
protein-design-skills/
├── kimi.plugin.json              # 插件清单（Kimi Code）
├── skills/                       # 工作流指南（79 skills）
│   ├── protein-design-context/   # 会话启动上下文
│   ├── structure-preprocessing/  # 阶段 0：PDBFixer
│   ├── structure-generation/     # 阶段 1：RFdiffusion + 替代方案
│   ├── sequence-design/          # 阶段 2：ProteinMPNN + 替代方案
│   ├── structure-validation/     # 阶段 3：AlphaFold3 + 替代方案
│   ├── filtering-ranking/        # 阶段 4：过滤与排序
│   ├── full-pipeline/            # 端到端编排
│   ├── pipeline-selection/       # 从 30+ 设计流程中选择
│   └── ...                       # 更多专项 skills
├── protein_design/
│   └── hooks/                    # 自动化脚本（24 hooks）
│       ├── install-hooks.py      # 一键安装器
│       ├── protein-context-inject.py
│       ├── gpu-check-hook.py
│       ├── session-health-check.py
│       ├── job-monitor.py
│       ├── progress-reporter.py
│       ├── execution-adapter.py
│       ├── pipeline-orchestrator.py
│       └── ...
├── scripts/                      # 独立执行脚本
│   ├── run_pdbfixer.py           # 阶段 0
│   ├── run_rfdiffusion.py        # 阶段 1
│   ├── run_proteinmpnn.py        # 阶段 2
│   ├── run_alphafold3.py         # 阶段 3
│   ├── run_boltz.py              # 阶段 3（替代方案）
│   ├── run_chai1.py              # 阶段 3（替代方案）
│   ├── run_omegafold.py          # 阶段 3（替代方案）
│   ├── run_esmfold.py            # 阶段 3（替代方案）
│   ├── run_filtering.py          # 阶段 4
│   ├── convert_format.py         # 格式转换
│   ├── job_manager.py            # 后台任务
│   └── batch_runner.py           # 流程编排
└── README.md
```

## 设计流程（5 个阶段）

| 阶段 | 目的 | 主要工具 | 默认输出 |
|------|------|---------|---------|
| 0 | 预处理 | PDBFixer | 修复后的 PDB |
| 1 | 骨架生成 | RFdiffusion | 10 个骨架 |
| 2 | 序列设计 | ProteinMPNN | 每个骨架 8 条序列 |
| 3 | 结构验证 | AlphaFold3 | 每个设计 5 个预测 |
| 4 | 过滤与排序 | Filtering | 按质量分数排序 |

## 执行流程

```
用户请求
    |
    v
Skill 选择（protein-design-context / pipeline-selection）
    |
    v
Hook: protein-context-inject.py（自动注入相关 skill 上下文）
    |
    v
Hook: gpu-check-hook.py（验证 GPU 可用性）
    |
    v
Standalone Script 执行（scripts/run_*.py）
    |
    v
Hook: progress-reporter.py（跟踪进度，估算 ETA）
    |
    v
Hook: design-complete-notify.py（完成时桌面通知）
    |
    v
结果 + 下一步 Skill 推荐
```

## 选择流程

使用 `skills/pipeline-selection/SKILL.md` 从 15+ 设计流程中选择：

| 流程 | 阶段 1 | 阶段 2 | 阶段 3 | 最佳场景 |
|------|--------|--------|--------|----------|
| Standard | RFdiffusion | ProteinMPNN | AlphaFold3 | 通用目的 |
| Fast Screen | RFdiffusion | ProteinMPNN | ESMFold | 大型库（100+） |
| Two-Stage | RFdiffusion | ProteinMPNN | ESMFold → AlphaFold3 | 速度与精度平衡 |
| Peptide | RFdiffusion | ProteinMPNN | AlphaFold3 | 多肽结合物 |
| Macrocycle | RFpeptides | ProteinMPNN | AlphaFold3 | 环化多肽 |
| Enzyme | RFdiffusion (ActiveSite) | ProteinMPNN | AlphaFold3 | 酶设计 |
| Antibody | RFdiffusion / IgDiff | ProteinMPNN | AlphaFold3 | 抗体设计 |
| Complex | RFdiffusion (Complex) | ProteinMPNN | Boltz-1 | 多链复合物 |
| Inverse | BCDesign / AlignInversePro | — | — | 逆折叠优化 |
| Co-design | MultiFlow | MultiFlow | AlphaFold3 | 联合结构-序列设计 |

## Hooks 参考

| Hook | 触发时机 | 目的 |
|------|----------|------|
| `install-hooks.py` | 手动 | 为选定的智能体安装 hooks |
| `protein-context-inject.py` | 蛋白质相关提示 | 自动注入相关 skill 上下文 |
| `gpu-check-hook.py` | GPU 密集型任务前 | 验证 GPU 可用性和显存 |
| `session-health-check.py` | 手动 / 会话启动 | 检查工具安装状态 |
| `job-monitor.py` | 任务提交后 | 监控后台任务 |
| `progress-reporter.py` | 长时间任务中 | 解析日志，估算 ETA |
| `execution-adapter.py` | 脚本执行时 | 路由到正确的脚本和参数 |
| `pipeline-orchestrator.py` | 多阶段请求 | 自动链接各阶段 |
| `design-complete-notify.py` | 任务完成 | 桌面通知 |
| `background-notify.py` | 后台任务完成 | 异步任务通知 |
| `auto-parameter-tuner.py` | 参数调优 | 建议最优参数 |
| `design-comparator.py` | 结果比较 | 比较多个设计 |
| `cost-estimator.py` | 执行前 | 估算 GPU 时间和成本 |
| `quality-gate.py` | 验证后 | 自动质量检查 |
| `error-recovery.py` | 失败时 | 建议恢复操作 |
| `batch-orchestrator.py` | 批处理任务 | 管理批量提交 |
| `format-converter.py` | 格式转换 | 文件格式互转 |
| `tool-recommender.py` | 工具选择 | 为任务推荐工具 |
| `alternative-tool-recommender.py` | 工具未找到 | 建议替代工具 |
| `design-report.py` | 流程完成后 | 生成总结报告 |

## 架构

执行流程：**Skills → Hooks → Standalone Scripts**。

---
title: 流程架构
source: README.zh.md
---

# 流程架构

## 项目结构

```
protein-design-skills/
├── kimi.plugin.json              # 插件清单（Kimi Code）
├── skills/                       # 工作流指导
│   ├── protein-design-context/   # 会话启动上下文
│   ├── structure-preprocessing/  # Stage 0: PDBFixer
│   ├── structure-generation/     # Stage 1: RFdiffusion
│   ├── sequence-design/          # Stage 2: ProteinMPNN
│   ├── structure-validation/     # Stage 3: AlphaFold3
│   ├── filtering-ranking/        # Stage 4: 过滤排序
│   └── full-pipeline/            # 端到端编排
├── protein_design/                   # MCP 服务器（stdio JSON-RPC）
│   ├── server.py                 # 主入口
│   ├── tools/                    # 工具实现
│   │   ├── tool_registry.py      # 工具 schema 与分发
│   │   ├── job_manager.py        # 异步任务管理
│   │   ├── pdbfixer_tool.py      # PDB 预处理
│   │   ├── rfdiffusion.py        # 骨架生成
│   │   ├── proteinmpnn.py        # 序列设计
│   │   ├── alphafold.py          # 结构验证
│   │   ├── format_converter.py   # FASTA ↔ JSON 转换
│   │   ├── filtering.py          # 质量过滤
│   │   ├── tool_installer.py     # 工具路径配置
│   │   └── system_info.py        # 环境检查
│   ├── utils/                    # 工具类
│   │   ├── config.py             # 配置
│   │   ├── conda_utils.py        # 跨 conda 执行
│   │   ├── gpu_utils.py          # GPU 检测
│   │   └── progress_tracker.py   # 基于文件的进度与 ETA
│   └── hooks/                    # 推荐 hooks
│       ├── install-hooks.py      # 一键安装
│       ├── protein-context-inject.py
│       ├── gpu-check-hook.py
│       ├── design-complete-notify.py
│       └── background-notify.py
└── README.md
```

## 设计流程（5 个阶段）

| 阶段 | 目的 | 工具 | 默认输出 |
|-------|---------|------|---------------|
| 0 | 预处理 | PDBFixer | 修复后的 PDB |
| 1 | 骨架生成 | RFdiffusion | 10 个骨架 |
| 2 | 序列设计 | ProteinMPNN | 每个骨架 8 条序列 |
| 3 | 结构验证 | AlphaFold3 | 每个设计 5 个预测 |
| 4 | 过滤排序 | 质量过滤 | 按质量分数排序 |

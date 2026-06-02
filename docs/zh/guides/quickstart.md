---
title: 快速开始
source: README.zh.md
---

# 快速开始

## 流程默认值

| 阶段 | 工具 | 默认输出 | 参数 |
|-------|------|---------------|-----------|
| 1 — 骨架生成 | RFdiffusion | **10** 个骨架 | `num_designs` |
| 2 — 序列设计 | ProteinMPNN | 每个骨架 **8** 条序列 | `num_seq_per_target` |
| 3 — 结构验证 | AlphaFold3 | **5** 个预测（1 种子 × 5 样本） | `num_seeds` × `num_samples` |

**完整流程默认**：10 个骨架 × 8 条序列 × 5 次预测 = 最多 **400** 个 AlphaFold3 结果。

可以通过自然语言调整数量：

```
User: "生成 50 个骨架"
→ num_designs = 50

User: "每个骨架设计 16 条序列"
→ num_seq_per_target = 16

User: "用 3 个种子验证"
→ num_seeds = 3
```

## 示例 1：设计 150 残基单体

```
User: 生成一个 150 个氨基酸的蛋白质骨架
→ 插件自动运行 RFdiffusion，contig 为 [150-150]
```

## 示例 2：为 PD-L1 设计结合物

```
User: 为 PD-L1 设计一个结合物
→ Stage 0: PDBFixer 预处理 target.pdb
→ Stage 1: RFdiffusion 生成结合物骨架
→ Stage 2: ProteinMPNN 设计结合物序列
→ Stage 3: AlphaFold3 验证结构
→ Stage 4: 按 ipTM > 0.8 和 pLDDT > 80 过滤
```

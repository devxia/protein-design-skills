# 变更记录

本页记录 Kimi Protein Design 插件每个版本的变更内容。

## 2025-06-01

### 新功能

- kimi-protein-design 插件初始提交，包含 5 阶段蛋白质设计流程
- 为 RFdiffusion、ProteinMPNN 和 AlphaFold3 添加 conda 环境支持
- 添加基于文件的进度跟踪和历史 ETA 估计
- 为 PDBFixer 添加跨 conda 环境支持（通过 `conda_env` 参数）
- 为 `convert_format` 添加 `receptor_pdb` 支持，用于多链 AF3 JSON 生成
- 添加 `analyze_alphafold3_results` 工具，无需重新运行即可解析 AlphaFold3 输出指标
- 在 `check_all_tools` 中添加 editable install 检测，支持 pip 安装的包

### 修复

- 修复首次服务器运行日志分析中发现的所有插件问题
- 修复 `alphafold.py` 缺少 `import time` 导致 `submit_job` 崩溃的问题
- 修复 `run_filtering` 忽略顶层指标字段（plddt、iptm、ptm、has_clash）的问题
- 修复当用户在 contig 字符串中提供方括号时 RFdiffusion 出现双括号的问题

### 文档

- 重新排序 README 章节并将占位符所有者替换为 devxia
- 在 Prerequisites Installation 步骤前添加醒目的 "already installed?" 提示
- 更新 README，说明 wrapper_script、schema 和 MSA 行为变更

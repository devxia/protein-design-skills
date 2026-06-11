# 变更记录

本页记录 Protein Design Skills 插件每个版本的变更内容。

## 2026-06-11

### 重大变更

- **MCP（Model Context Protocol）已彻底移除。** 本插件不再使用或支持 MCP。所有执行现在通过 **skills + hooks + standalone scripts** 进行。
- 删除 `protein_design/server.py` —— 异步 stdio JSON-RPC 服务器已移除。
- 删除 `protein_design/tools/` 目录 —— 所有 11 个 MCP tool 实现文件已删除（`tool_registry.py`、`job_manager.py`、`pdbfixer_tool.py`、`rfdiffusion.py`、`proteinmpnn.py`、`alphafold.py`、`format_converter.py`、`filtering.py`、`tool_installer.py`、`system_info.py`）。
- 删除 `protein_design/utils/` 目录 —— 所有 4 个工具文件已删除（`config.py`、`conda_utils.py`、`gpu_utils.py`、`progress_tracker.py`）。
- 重写 `plugin.json` —— 移除 `mcpServers` 配置。
- 重写 `kimi.plugin.json` —— 改为 skills-first 指令，MCP 已弃用。
- 重写 `protein_design/__init__.py` —— 纯插件元数据，无服务器导入。

### 新功能

- **新增 5 个 skills**（共 54 个）：
  - `rfpeptides-macrocycle` —— RFpeptides 大环环化多肽设计流程
  - `cross-validation` —— 多验证器共识排序（AlphaFold3 + Boltz-1 + Chai-1）
  - `score-first-screening` —— ProteinMPNN `score_only` 预筛选策略
  - `protenix-training` —— Protenix 微调和训练指南
  - `quickstart-guide` —— 新用户 10 分钟快速上手指南
- **扩充 4 个现有 skills**，添加从 GitHub 源码发现的参数：
  - `la-proteina-backbone` —— 新增 7 种 LD 模型、3 种 AE 模型、Hydra 配置系统、模型选择指南
  - `framedipt-inpainting` —— 新增 Hydra 配置、TCR CDR3 用例、评估指标、cg2all 转换
  - `alphaflow-ensemble` —— 新增 8 种模型变体、ESMFlow、MSA 生成、ensemble 分析脚本
  - `rfdpoly-multipolymer` —— 新增 Apptainer 详细用法、两种权重变体、多聚合物 contig 语法
- **重写入口 skills**，提升可发现性：
  - `protein-design-context` —— 现提供显式 Main Entrance，含 10 种场景快速匹配表
  - `pipeline-selection` —— 新增 Immediate Match 快速参考表
- **更新 hooks**：`install-hooks.py` 现支持所有智能体的 `--mcp-free` 标志。生成 `.mcp-free.json` 模板。
- **重写文档**，从 MCP 中心架构改为 skills-first 架构：
  - `docs/en/guides/installation.md` —— 移除 MCP 配置，添加 hooks 安装
  - `docs/en/guides/pipeline.md` —— 更新架构图，添加 hook 参考表
  - `docs/en/api-reference/scripts.md` —— 替换 tools.md，改为 standalone scripts 参考
  - `docs/en/README.md` —— 从「MCP Documentation」重命名为「Skills Documentation」

### 架构

- **主要执行方式**：`scripts/` 中的 standalone scripts（12 个脚本）
- **指导层**：`skills/` 中的 skills（54 个）
- **自动化层**：`protein_design/hooks/` 中的 hooks（22 个）
- **已弃用**：所有 MCP 基础设施（本版本中已移除）

## 2026-06-04

### 修复

- 修复 `filtering.py` `_safe_float()` 对 `None` 输入始终返回 `0.0`，导致回退分支为死代码——缺少指标的设计被错误拒绝而非跳过
- 修复 `format_converter.py` `sequence_to_alphafold3_json()` 中重复定义 `_make_chain_id()` 和文档字符串错位的问题
- 修复 `background-notify.py` 和 `design-complete-notify.py` 中的命令注入风险——未转义的字符串直接插入 AppleScript 和 PowerShell 命令
- 修复 `design-complete-notify.py` 零值误判——`metrics.get("plddt")` 跳过了有效的零值，改为使用 `is not None`
- 修复 `tool_registry.py` 中 `query_job`、`cancel_job`、`check_tool_status`、`configure_tool_path`、`configure_db_dir` 缺少 `KeyError` 处理——缺少参数时抛出未处理的 `KeyError` 而非返回错误响应
- 修复 `alphafold.py` `run_alphafold3()` 中 `if wrapper_script` / `else` 分支代码完全相同的问题
- 修复 `server.py` 已弃用的 `asyncio.get_event_loop()` → `asyncio.get_running_loop()`，并为 stdin 解码添加 `UnicodeDecodeError` 处理
- 修复 `progress_tracker.py` 每次轮询读取整个日志文件——现仅读取最后 8 KB；将 `import re` 移至模块级
- 修复 `config.py` 对格式错误的 YAML 静默吞掉异常——现记录警告；添加 PyYAML 缺失时的优雅降级
- 修复 `gpu-check-hook.py` nvidia-smi 输出为空时的潜在 `IndexError`
- 修复 `tool_installer.py` 未保护的 `import yaml`——现处理 PyYAML 缺失的情况
- 修复 `system_info.py` 当同时触发缺少工具和无 GPU 条件时覆盖警告列表的问题
- 修复 6 个文件中错误的 `callable` 类型注解（应为 `Callable[[int], None]`）
- 更新 `.gitignore`，添加常见 Python 项目条目（`.venv`、`.egg-info`、`.env`、`*.log` 等）

## 2026-06-03

### 修复

- 修复 `pdbfixer_tool.py` 向 `run_in_conda_with_logs` 传递错误关键字参数 `env_name`（应为 `conda_env`）的问题
- 修复 `proteinmpnn.py` 缺少 `str()` 包裹 `sampling_temp` 参数，导致传入数值时 `subprocess.run` 抛出 `TypeError`
- 修复 `tool_installer.py` 检查不存在的键 `missing_db_reason`（应为 `note`），导致 AlphaFold3 数据库缺失提示永不触发
- 修复 `pdbfixer_tool.py` 文件句柄泄漏：`open()` 直接传给 `PDBFile.writeFile()` 而没有使用 `with` 语句
- 修复 `job_manager.py` 竞态条件：将 `job.future` 赋值移入锁内，`cancel_job()` 中在锁下读取任务状态
- 修复 `progress_tracker.py` 允许重复调用 `start()` 导致后台线程泄漏
- 修复 `tool_registry.py` 线程安全问题：为 `_ensure_tool_executors()` 懒加载添加锁
- 修复 `tool_registry.py` `TOOL_SCHEMAS` 中缺少 `get_gpu_status`（该工具可执行但不可发现）
- 修复 `filtering.py` 类型安全问题：新增 `_safe_float()` 辅助函数，避免字符串/None 指标值导致 `TypeError`
- 修复 `format_converter.py` chain ID 超出 'Z' 后溢出（超过 26 条链时现在生成 AA、AB…）
- 修复 `format_converter.py` `seed` 参数为非数字字符串时未处理 `ValueError`
- 修复 `alphafold.py` 所有 `open()` 调用缺少 `encoding="utf-8"`
- 修复 `server.py` 未校验 `params` 类型就直接调用 `.get()`，导致畸形 JSON-RPC 请求时 `AttributeError`
- 修复 `design-complete-notify.py` 当 hook payload 中 `result` 为 `null` 时崩溃
- 修复 `rfdiffusion.py` 当 `output_prefix` 不含目录部分时可能出现的 `Path("")` 问题
- 清理 10+ 个文件中的未使用导入（`__future__.annotations`、`run_in_conda`、`run_in_conda_popen`、`field`、`tempfile`、`os`、`sys`、`json`、`JobManager`、`get_missing_tool_prompt`、`shutil`）

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
- 在安装前置条件步骤前添加醒目的「已安装？」提示
- 更新 README，说明 wrapper_script、schema 和 MSA 行为变更

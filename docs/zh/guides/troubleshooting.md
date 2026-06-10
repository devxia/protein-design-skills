---
title: 故障排除
source: README.zh.md
---

# 故障排除

## 常见问题

| 问题 | 解决方案 |
|-------|----------|
| 插件未加载 | 安装后运行 `/new` |
| `run_pdbfixer` 未找到 | `conda install -c conda-forge pdbfixer openmm`，或使用 `conda_env` 参数在另一环境中执行 |
| RFdiffusion 未找到 | 设置 `RFDIFFUSION_PATH` 环境变量 |
| GPU 显存不足 | 减小 `num_designs` 或 `diffuser_T` |
| AlphaFold3 MSA 超时 | 默认运行完整 MSA。设置 `run_data_pipeline=false` 可跳过（更快，精度稍低） |
| 工具在其他环境中未找到 | `check_all_tools` 现在会自动扫描常见 conda 环境 + editable install |
| 验证结合物需要受体 | 使用 `convert_format` 的 `receptor_pdb` 参数生成多链 AF3 JSON |
| Hooks 未生效 | 验证智能体的 hook 配置语法，然后重启会话 |

## 跨 Conda 环境执行

如果工具安装在不同 conda 环境中，无需全部安装到一个环境：

- **`run_pdbfixer`**：使用 `conda_env="BindCraft"` 在目标环境中运行 PDBFixer
- **`run_rfdiffusion` / `run_proteinmpnn` / `run_alphafold3`**：使用 `conda_env` 或 `wrapper_script` 指定目标环境

插件会自动检测跨常见 conda 环境和 editable install 的工具。

## 多链复合物验证

对于结合物/多肽设计验证，AlphaFold3 需要将受体和设计的肽段放在同一个 JSON 中：

```python
convert_format(
    from_format="fasta",
    to_format="alphafold3_json",
    input_path="/path/to/proteinmpnn_out.fasta",
    receptor_pdb="/path/to/receptor_fixed.pdb",
    receptor_chain="A",
    job_name="binder_validation"
)
```

AlphaFold3 完成后，无需重新运行即可分析结果：

```python
analyze_alphafold3_results(
    output_dir="/path/to/af3_output",
    job_name="binder_validation"
)
# 返回：每链 pLDDT、ipTM、pTM、排名分数、冲突状态、最佳结构
```

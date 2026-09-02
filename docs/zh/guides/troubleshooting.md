---
title: 故障排除
source: README.zh.md
---

# 故障排除

## 常见问题

| 问题 | 解决方案 |
|-------|----------|
| 插件未加载 | 安装后运行 `/new` |
| `run_pdbfixer` 未找到 | 运行 `conda install -c conda-forge pdbfixer openmm`，然后再次执行脚本 |
| RFdiffusion 未找到 | 设置 `RFDIFFUSION_PATH` 或配置 `rfdiffusion_path` |
| GPU 显存不足 | 减小 `num_designs` 或 `diffuser_T` |
| AlphaFold3 MSA 超时 | 使用 `--no-msa` 重新运行，以获得更快但精度较低的验证 |
| 在其他 conda env 中未找到工具 | 运行器会自动探测常见 conda env；若未发现，请配置 `<tool>_path` 或 `<tool>_wrapper_script` |
| 验证 binder 需要受体 | 创建包含所有所需 chain 的 AlphaFold3 JSON 输入，然后运行 `scripts/run_alphafold3.py --json input.json --output-dir outputs/af3/` |
| Hooks 未生效 | 验证智能体的 hook 配置语法，然后重启会话 |

## 跨 conda env 执行

工具可以安装在不同的 conda env 中；运行器会自动探测常见环境，并在找到受支持的安装时使用 `conda run`。如果工具需要自定义激活，请在 `~/.protein-design/config.yaml` 中设置其配置路径或 `<tool>_wrapper_script`。不要传入 `conda_env` CLI 参数：standalone runners 不提供该参数。

## 多链复合物验证

对于 binder 或 peptide 验证，请创建包含受体和设计肽 chain 的 AlphaFold3 JSON 输入，然后运行：

```bash
python scripts/run_alphafold3.py --json binder_input.json --output-dir outputs/af3/
```

使用过滤阶段检查生成的 confidence JSON 文件：

```bash
python scripts/run_filtering.py --results-dir outputs/af3/ --min-plddt 75
```

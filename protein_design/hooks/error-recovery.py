#!/usr/bin/env python3
"""PostToolUse hook: analyze tool failures and suggest recovery strategies.

When a tool call fails, this hook intercepts the error and provides
context-aware recovery suggestions — helping users diagnose and fix
issues without manual debugging.
"""
import traceback
import json
import re
from typing import Any
import sys


def _parse_error(error_text: str) -> dict[str, Any]:
    """Parse error text to identify the failure type and root cause."""
    error_lower = error_text.lower()
    result: dict[str, Any] = {"type": "unknown", "message": error_text[:500]}

    # GPU / CUDA errors
    if any(kw in error_lower for kw in ["cuda", "gpu", "out of memory", "oom", "cudnn"]):
        result["type"] = "gpu_error"
        if "out of memory" in error_lower or "oom" in error_lower:
            result["subtype"] = "oom"
            result["message"] = "GPU out of memory"
        elif "cuda" in error_lower:
            result["subtype"] = "cuda"
            result["message"] = "CUDA error"
        return result

    # File not found errors
    if any(kw in error_lower for kw in ["file not found", "nosuchfile", "no such file"]):
        result["type"] = "file_not_found"
        # Try to extract filename
        match = re.search(r"['\"]?([^'\"\s]+\.(?:pdb|cif|json|fa|fasta|pt|ckpt))['\"]?", error_text, re.I)
        if match:
            result["missing_file"] = match.group(1)
        return result

    # Tool not installed
    if any(kw in error_lower for kw in ["not found", "not installed", "module not found", "importerror"]):
        result["type"] = "tool_not_found"
        for tool in ["rfdiffusion", "proteinmpnn", "alphafold", "pdbfixer"]:
            if tool in error_lower:
                result["missing_tool"] = tool
                break
        return result

    # Contig / parameter errors
    if any(kw in error_lower for kw in ["contig", "invalid", "argument", "parameter", "keyerror"]):
        result["type"] = "parameter_error"
        if "contig" in error_lower:
            result["subtype"] = "contig"
        return result

    # Timeout
    if any(kw in error_lower for kw in ["timeout", "timed out", "time out"]):
        result["type"] = "timeout"
        return result

    # MSA / Database errors
    if any(kw in error_lower for kw in ["msa", "database", "bfd", "uniref", "jackhmmer", "hhblits"]):
        result["type"] = "msa_error"
        return result

    # Conda / Environment errors
    if any(kw in error_lower for kw in ["conda", "environment", "module", "package"]):
        result["type"] = "environment_error"
        return result

    return result


def _build_recovery_strategy(error_info: dict[str, Any], tool_name: str) -> list[str]:
    """Build recovery strategies based on error type and tool."""
    strategies: list[str] = []
    error_type = error_info.get("type")
    subtype = error_info.get("subtype")

    if error_type == "gpu_error":
        if subtype == "oom":
            strategies = [
                "GPU 内存不足。解决方案:",
                "  1. 减少 num_designs（例如从 50 降到 10）",
                "  2. 降低 diffuser_T（例如从 50 降到 25）",
                "  3. 关闭其他使用 GPU 的程序",
                "  4. 使用更小的蛋白质长度",
            ]
        else:
            strategies = [
                "CUDA/GPU 错误。解决方案:",
                "  1. 检查 nvidia-smi 确认 GPU 可用",
                "  2. 检查 CUDA 版本与 PyTorch 兼容性",
                "  3. 尝试设置 CUDA_VISIBLE_DEVICES=0",
                "  4. 重启 kernel/session",
            ]

    elif error_type == "file_not_found":
        missing = error_info.get("missing_file", "文件")
        strategies = [
            f"找不到文件: {missing}",
            "  1. 检查文件路径是否正确（使用绝对路径）",
            "  2. 确认文件存在于指定位置",
            f"  3. 如果是输出文件，确保目录存在: mkdir -p $(dirname {missing})",
            "  4. 检查文件权限",
        ]

    elif error_type == "tool_not_found":
        missing_tool = error_info.get("missing_tool", "工具")
        alt_map = {
            "rfdiffusion": "Chroma (`pip install chroma-ai`) 或 FrameDiff",
            "proteinmpnn": "ESM-IF1 (`pip install fair-esm`) 或 LigandMPNN",
            "alphafold": "ESMFold (`pip install fair-esm`) 或 OmegaFold (`pip install omegafold`) — 无需数据库",
            "pdbfixer": "运行: `conda install -c conda-forge pdbfixer openmm`",
        }
        alt = alt_map.get(missing_tool, "参考 install-guide 技能")
        strategies = [
            f"{missing_tool} 未安装或未找到 / {missing_tool} not found or not installed",
            f"  快速替代方案 / Quick alternative: {alt}",
            f"  设置环境变量 / Set env var: {missing_tool.upper()}_PATH=/path/to/{missing_tool}",
            "  参考安装指南 / See install-guide skill for full instructions",
        ]

    elif error_type == "parameter_error":
        if subtype == "contig":
            strategies = [
                "Contig 参数错误 / Contig parameter error。检查 / Check:",
                "  1. 语法格式 / Syntax: [A1-50/0 10-20/A71-150]",
                "  2. 固定区域必须使用链ID前缀 / Fixed regions need chain prefix (如 A1-50)",
                "  3. 生成区域不需要前缀 / Generated regions no prefix (如 10-20)",
                "  4. 使用 / 分隔不同区域 / Use / to separate regions",
                "  5. 使用 0 表示链断裂 / Use 0 for chain break (binder设计)",
                "  6. 确保残基编号与输入 PDB 匹配 / Match residue numbers to input PDB",
            ]
        else:
            strategies = [
                "参数错误 / Parameter error。检查 / Check:",
                "  1. 所有必需参数是否已提供 / All required params provided?",
                "  2. 参数类型是否正确 / Correct param types (string/int/bool)?",
                "  3. 参考 SKILL_INDEX.md 查看完整参数 / See SKILL_INDEX.md for full params",
            ]

    elif error_type == "timeout":
        strategies = [
            "作业超时。解决方案:",
            "  1. 对于 AlphaFold3: 设置 run_data_pipeline=false 跳过 MSA",
            "  2. 减少 num_designs 或 num_samples",
            "  3. 使用更短的蛋白质序列",
            "  4. 检查 GPU 是否正常工作",
        ]

    elif error_type == "msa_error":
        strategies = [
            "MSA/数据库错误 / MSA/Database error。解决方案 / Solutions:",
            "  1. 设置 run_data_pipeline=false 跳过 MSA / Skip MSA (fast but less accurate)",
            "  2. 使用 ESMFold 或 OmegaFold 替代（无需数据库）/ Use ESMFold or OmegaFold (no DB needed)",
            "  3. 检查数据库目录是否存在且完整 (~2.6TB) / Check DB dir exists and complete",
            "  4. 检查磁盘空间是否充足 / Check disk space",
        ]

    elif error_type == "environment_error":
        strategies = [
            "环境/依赖错误。解决方案:",
            "  1. 使用 conda_env 参数指定正确的 conda 环境",
            "  2. 使用 wrapper_script 自定义环境设置",
            "  3. 检查 conda 环境是否包含所需包",
            "  4. 重新安装工具到正确的 conda 环境",
        ]

    else:
        strategies = [
            "未知错误。建议:",
            "  1. 查看完整的 stderr 日志文件",
            "  2. 检查输入文件格式是否正确",
            "  3. 尝试简化参数后重试",
            "  4. 参考文档中的故障排除部分",
        ]

    return strategies


def _extract_tool_name(data: dict[str, Any]) -> str:
    """Extract the tool name from hook input data."""
    # Try to find tool name from various locations in the data
    result = data.get("result", {})
    if isinstance(result, dict):
        content = result.get("content", [{}])
        if content and isinstance(content, list):
            text = content[0].get("text", "")
            try:
                result_json = json.loads(text)
                # Check for tool name in result
                if "tool_name" in result_json:
                    return result_json["tool_name"]
                if "tool" in result_json:
                    return result_json["tool"]
            except json.JSONDecodeError:
                pass

    # Check for error message
    error = data.get("error", "")
    if isinstance(error, str):
        for tool in ["rfdiffusion", "proteinmpnn", "alphafold", "pdbfixer", "filtering"]:
            if tool in error.lower():
                return tool

    return "unknown"


def main() -> int:
    """Main entry point."""
    try:
        input_data = sys.stdin.read()
        data = json.loads(input_data) if input_data.strip() else {}
    except json.JSONDecodeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1

    # Only process failed tool calls
    result = data.get("result", {})
    if isinstance(result, dict) and result.get("isError"):
        error_text = ""
        content = result.get("content", [{}])
        if content and isinstance(content, list):
            error_text = content[0].get("text", "")

        if not error_text:
            return 0

        tool_name = _extract_tool_name(data)
        error_info = _parse_error(error_text)
        strategies = _build_recovery_strategy(error_info, tool_name)

        output = f"""[Error Recovery / 错误恢复建议] Tool / 工具: {tool_name} | Type / 类型: {error_info['type']}

{chr(10).join(strategies)}

Error summary / 原始错误摘要: {error_info['message'][:200]}
"""
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())

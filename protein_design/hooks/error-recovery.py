#!/usr/bin/env python3
"""PostToolUse hook: analyze tool failures and suggest recovery strategies.

When a tool call fails, this hook intercepts the error and provides
context-aware recovery suggestions — reducing the need for the user
to manually debug or make additional MCP calls.

This hook reduces MCP usage by embedding error-handling knowledge directly
into the agent's context.
"""

import json
import re
import sys
from typing import Any


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
        strategies = [
            f"{missing_tool} 未安装或未找到。",
            "  1. 使用 check_tool_status 检查安装状态",
            "  2. 使用 configure_tool_path 配置工具路径",
            f"  3. 设置环境变量: {missing_tool.upper()}_PATH",
            "  4. 参考安装指南安装缺失的工具",
        ]

    elif error_type == "parameter_error":
        if subtype == "contig":
            strategies = [
                "Contig 参数错误。检查:",
                "  1. 语法格式: [A1-50/0 10-20/A71-150]",
                "  2. 固定区域必须使用链ID前缀 (如 A1-50)",
                "  3. 生成区域不需要前缀 (如 10-20)",
                "  4. 使用 / 分隔不同区域",
                "  5. 使用 0 表示链断裂（binder设计）",
                "  6. 确保残基编号与输入 PDB 匹配",
            ]
        else:
            strategies = [
                "参数错误。检查:",
                "  1. 所有必需参数是否已提供",
                "  2. 参数类型是否正确（字符串/整数/布尔值）",
                "  3. 使用 get_tool_info 查看完整参数列表",
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
            "MSA/数据库错误。解决方案:",
            "  1. 设置 run_data_pipeline=false 跳过 MSA（快速但不精确）",
            "  2. 使用 configure_db_dir 配置正确的数据库路径",
            "  3. 检查数据库目录是否存在且完整 (~2.6TB)",
            "  4. 检查磁盘空间是否充足",
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
    except Exception:
        return 0

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

        output = f"""[错误恢复建议] 工具: {tool_name} | 错误类型: {error_info['type']}

{chr(10).join(strategies)}

原始错误摘要: {error_info['message'][:200]}
"""
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())

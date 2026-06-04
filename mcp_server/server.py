"""MCP Server main entry point for Kimi Protein Design.

Implements a stdio-based JSON-RPC 2.0 server. Supports:
  - initialize
  - tools/list
  - tools/call

Uses asyncio for non-blocking I/O while running compute-heavy tool calls
in a thread pool via job_manager.
"""

import asyncio
import json
import logging
import sys
from typing import Any

from mcp_server.tools.tool_registry import get_tool_info, execute_tool

# Configure logging to stderr so stdout stays clean for JSON-RPC
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

SERVER_NAME = "kimi-protein-design"
SERVER_VERSION = "0.1.0"


class JSONRPCError(Exception):
    """Custom exception for JSON-RPC errors."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


def _make_response(id_: Any, result: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 success response."""
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _make_error_response(id_: Any, error: JSONRPCError) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error response."""
    err_body: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.data is not None:
        err_body["data"] = error.data
    return {"jsonrpc": "2.0", "id": id_, "error": err_body}


def _make_generic_error(id_: Any, code: int, message: str) -> dict[str, Any]:
    """Build a generic JSON-RPC error response."""
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


async def _handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Process a single JSON-RPC request.

    Args:
        request: Parsed JSON-RPC request dict.

    Returns:
        JSON-RPC response dict.
    """
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    logger.debug("Handling method: %s", method)

    if method == "initialize":
        return _make_response(
            req_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        )

    if method == "tools/list":
        info = get_tool_info()
        return _make_response(
            req_id,
            {
                "tools": info["tools"],
            },
        )

    if method == "tools/call":
        if not isinstance(params, dict):
            return _make_generic_error(req_id, -32602, "Invalid params: expected object")
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return _make_generic_error(req_id, -32602, "Missing tool name")

        try:
            result = execute_tool(tool_name, arguments)
            return _make_response(req_id, {"content": [{"type": "text", "text": json.dumps(result)}]})
        except JSONRPCError as exc:
            return _make_error_response(req_id, exc)
        except Exception as exc:
            logger.exception("Tool execution failed: %s", tool_name)
            return _make_generic_error(req_id, -32603, f"Tool execution error: {str(exc)}")

    return _make_generic_error(req_id, -32601, f"Method not found: {method}")


async def _process_line(line: str) -> None:
    """Parse and handle a single JSON-RPC message line.

    Args:
        line: Raw JSON string from stdin.
    """
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        response = _make_generic_error(None, -32700, f"Parse error: {exc}")
        _write_response(response)
        return

    if not isinstance(request, dict):
        response = _make_generic_error(None, -32600, "Invalid Request")
        _write_response(response)
        return

    response = await _handle_request(request)
    _write_response(response)


def _write_response(response: dict[str, Any]) -> None:
    """Write a JSON-RPC response to stdout with proper formatting.

    Args:
        response: JSON-RPC response dict.
    """
    json_str = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(json_str + "\n")
    sys.stdout.flush()


async def main() -> None:
    """Main event loop: read JSON-RPC requests from stdin, write responses to stdout."""
    logger.info("%s MCP Server v%s starting...", SERVER_NAME, SERVER_VERSION)

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        try:
            line = await reader.readline()
        except asyncio.CancelledError:
            break

        if not line:
            break

        try:
            text = line.decode("utf-8").strip()
        except UnicodeDecodeError:
            logger.warning("Received non-UTF-8 data on stdin, skipping line")
            continue
        if not text:
            continue

        await _process_line(text)

    logger.info("%s MCP Server shutting down.", SERVER_NAME)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(0)

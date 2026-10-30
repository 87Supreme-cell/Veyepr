"""Read-only Model Context Protocol projection for The Firm execution log.

The MCP process exposes evidence summaries to an LLM client. It cannot record
authoritative events, grant access, modify policy, select filesystem paths, or
write exports. The host-owned ``firm`` adapter performs those actions outside
the model process.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping, TextIO

from .sentinel import SentinelPolicy, load_json

PROTOCOL_VERSION = "2024-11-05"


def tool_definitions() -> list[dict[str, object]]:
    """Return only read-only MCP tools."""
    empty_object = {"type": "object", "additionalProperties": False}
    return [
        {
            "name": "veyepr_execution_log_summary",
            "description": (
                "Return a content-free summary and integrity digest for the host-configured execution log. "
                "This tool cannot change the log or request access."
            ),
            "inputSchema": empty_object,
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "veyepr_policy_boundary",
            "description": (
                "Return the host-configured review-only policy boundary. "
                "This tool cannot alter policy or authorize an action."
            ),
            "inputSchema": empty_object,
            "annotations": {"readOnlyHint": True},
        },
    ]


def dispatch(
    request: Mapping[str, Any], *, log_path: Path, policy_path: Path
) -> dict[str, object] | None:
    """Handle a small, read-only subset of the stdio MCP JSON-RPC protocol."""
    request_id = request.get("id")
    method = request.get("method")
    if not isinstance(method, str):
        return _error(request_id, -32600, "request method must be a string")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "veyepr-the-firm", "version": "0.1.0"},
            },
        )
    if method == "tools/list":
        return _result(request_id, {"tools": tool_definitions()})
    if method == "tools/call":
        return _call_tool(request_id, request.get("params"), log_path=log_path, policy_path=policy_path)
    return _error(request_id, -32601, f"unsupported read-only method: {method}")


def serve(input_stream: TextIO, output_stream: TextIO, *, log_path: Path, policy_path: Path) -> None:
    """Run the line-delimited stdio JSON-RPC loop used by local MCP clients."""
    for raw_line in input_stream:
        if not raw_line.strip():
            continue
        try:
            request = json.loads(raw_line)
        except json.JSONDecodeError:
            response = _error(None, -32700, "invalid JSON")
        else:
            response = (
                dispatch(request, log_path=log_path, policy_path=policy_path)
                if isinstance(request, Mapping)
                else _error(None, -32600, "request must be an object")
            )
        if response is not None:
            output_stream.write(json.dumps(response, separators=(",", ":")) + "\n")
            output_stream.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True, help="Host-configured Markdown or text export to summarize.")
    parser.add_argument(
        "--policy", type=Path, default=Path("policy/mock-sentinel-policy.json"), help="Host-configured policy path."
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    serve(sys.stdin, sys.stdout, log_path=args.log, policy_path=args.policy)


def _call_tool(
    request_id: object, params: object, *, log_path: Path, policy_path: Path
) -> dict[str, object]:
    if not isinstance(params, Mapping) or set(params) - {"name", "arguments"}:
        return _error(request_id, -32602, "tool call parameters are invalid")
    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(name, str) or not isinstance(arguments, Mapping) or arguments:
        return _error(request_id, -32602, "read-only tools accept no arguments")
    try:
        if name == "veyepr_execution_log_summary":
            result = _log_summary(log_path)
        elif name == "veyepr_policy_boundary":
            policy = SentinelPolicy.from_record(load_json(policy_path))
            result = {
                "policy_id": policy.policy_id,
                "policy_version": policy.policy_version,
                "response_mode": policy.response_mode,
                "retention_mode": policy.retention_mode,
                "model_authority": "none",
                "model_cannot": [
                    "grant access",
                    "change policy",
                    "write or erase an export",
                    "choose the log path",
                    "declare an action authoritative",
                ],
            }
        else:
            return _error(request_id, -32602, f"unknown read-only tool: {name}")
    except (OSError, ValueError) as error:
        return _result(
            request_id,
            {"content": [{"type": "text", "text": json.dumps({"error": str(error)})}], "isError": True},
        )
    return _result(
        request_id,
        {"content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}], "isError": False},
    )


def _log_summary(log_path: Path) -> dict[str, object]:
    content = log_path.read_bytes()
    if b"\x00" in content:
        raise ValueError("execution log must be a text export")
    text = content.decode("utf-8")
    return {
        "log_name": log_path.name,
        "byte_count": len(content),
        "sha256": sha256(content).hexdigest(),
        "entry_count": text.count("entry_digest=") or text.count("- Entry digest:"),
        "review_required_count": text.count("decision=review_required")
        or text.count("Decision: `review_required`"),
        "log_writer": "host_controlled_adapter",
        "model_authority": "none",
    }


def _result(request_id: object, result: Mapping[str, Any]) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": dict(result)}


def _error(request_id: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


if __name__ == "__main__":
    main()

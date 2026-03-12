from __future__ import annotations

import json
from typing import Any, Protocol

from .lifecycle import (
    McpLifecycleState,
    build_jsonrpc_success_response,
    dispatch_lifecycle_method,
)
from .tool_schemas import McpToolSchema, serialize_mcp_tool_schema


class McpRpcRuntime(Protocol):
    settings: Any

    def registered_tools(self) -> tuple[str, ...]: ...
    def registered_resources(self) -> tuple[str, ...]: ...
    def tool_schema(self, tool_name: str) -> McpToolSchema: ...
    def dispatch_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any: ...
    def dispatch_resource(self, uri: str) -> Any: ...


LIFECYCLE_METHODS = frozenset(
    {
        "initialize",
        "initialized",
        "notifications/initialized",
        "ping",
        "shutdown",
    }
)


def ensure_lifecycle_state(runtime: McpRpcRuntime) -> McpLifecycleState:
    lifecycle_state = getattr(runtime, "_mcp_lifecycle_state", None)
    if lifecycle_state is None:
        lifecycle_state = McpLifecycleState()
        setattr(runtime, "_mcp_lifecycle_state", lifecycle_state)
    return lifecycle_state


def handle_mcp_rpc_request(
    runtime: McpRpcRuntime,
    req: dict[str, Any],
) -> dict[str, Any] | None:
    method = req.get("method")
    params = req.get("params") or {}
    req_id = req.get("id")

    lifecycle_result = _dispatch_lifecycle_request(runtime, method, params)
    if method in LIFECYCLE_METHODS:
        if req_id is None or lifecycle_result is None:
            return None
        return build_jsonrpc_success_response(req_id, lifecycle_result)

    result = dispatch_rpc_method(
        runtime,
        method=method,
        params=params,
    )

    if req_id is None:
        return None

    return build_jsonrpc_success_response(req_id, result)


def dispatch_rpc_method(
    runtime: McpRpcRuntime,
    *,
    method: Any,
    params: Any,
) -> dict[str, Any]:
    if method == "exit":
        raise SystemExit(0)
    if method == "tools/list":
        return _build_tools_list_result(runtime)
    if method == "tools/call":
        return _build_tools_call_result(runtime, params)
    if method == "resources/list":
        return _build_resources_list_result(runtime)
    if method == "resources/read":
        return _build_resources_read_result(runtime, params)

    raise ValueError(f"Unknown method: {method}")


def _dispatch_lifecycle_request(
    runtime: McpRpcRuntime,
    method: Any,
    params: Any,
) -> dict[str, Any] | None:
    lifecycle_state = ensure_lifecycle_state(runtime)
    return dispatch_lifecycle_method(
        runtime,
        lifecycle_state,
        method if isinstance(method, str) else None,
        params if isinstance(params, dict) else None,
    )


def _build_tools_list_result(runtime: McpRpcRuntime) -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": tool_name,
                "description": f"{tool_name} tool",
                "inputSchema": serialize_mcp_tool_schema(
                    runtime.tool_schema(tool_name)
                ),
            }
            for tool_name in runtime.registered_tools()
        ]
    }


def _build_tools_call_result(
    runtime: McpRpcRuntime,
    params: Any,
) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ValueError("tools/call requires 'params' (object)")

    name = params.get("name")
    arguments = params.get("arguments") or {}

    if not isinstance(name, str) or not name.strip():
        raise ValueError("tools/call requires 'name' (string)")
    if not isinstance(arguments, dict):
        raise ValueError("tools/call requires 'arguments' (object)")

    response = runtime.dispatch_tool(name.strip(), arguments)
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(response.payload, ensure_ascii=False),
            }
        ]
    }


def _build_resources_list_result(runtime: McpRpcRuntime) -> dict[str, Any]:
    return {
        "resources": [
            {
                "uri": resource_uri,
                "name": resource_uri,
                "description": f"{resource_uri} resource",
            }
            for resource_uri in runtime.registered_resources()
        ]
    }


def _build_resources_read_result(
    runtime: McpRpcRuntime,
    params: Any,
) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ValueError("resources/read requires 'params' (object)")

    uri = params.get("uri")
    if not isinstance(uri, str) or not uri.strip():
        raise ValueError("resources/read requires 'uri' (string)")

    normalized_uri = uri.strip()
    response = runtime.dispatch_resource(normalized_uri)
    return {
        "contents": [
            {
                "uri": normalized_uri,
                "mimeType": "application/json",
                "text": json.dumps(response.payload, ensure_ascii=False),
            }
        ]
    }


__all__ = [
    "LIFECYCLE_METHODS",
    "McpRpcRuntime",
    "dispatch_rpc_method",
    "ensure_lifecycle_state",
    "handle_mcp_rpc_request",
]

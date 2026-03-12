from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from typing import Any, Protocol

from .lifecycle import McpLifecycleState
from .resource_handlers import (
    parse_workflow_detail_resource_uri,
    parse_workspace_resume_resource_uri,
)
from .rpc import handle_mcp_rpc_request
from .tool_schemas import DEFAULT_EMPTY_MCP_TOOL_SCHEMA, McpToolSchema

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StdioTransportIntrospection:
    transport: str
    routes: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()


def _lookup_server_symbol(name: str) -> type[Any]:
    from .. import server as server_module

    return getattr(server_module, name)


McpToolHandler = Any
McpResourceHandler = Any


class StdioRuntimeProtocol(Protocol):
    settings: Any
    _tool_handlers: dict[str, McpToolHandler]
    _resource_handlers: dict[str, McpResourceHandler]
    _tool_schemas: dict[str, McpToolSchema]

    def registered_tools(self) -> tuple[str, ...]: ...
    def registered_resources(self) -> tuple[str, ...]: ...


class StdioRuntimeAdapter:
    """
    stdio transport adapter for MCP-style request dispatch.

    This remains intentionally lightweight. Its responsibilities are:
    - keep stdio transport lifecycle state
    - register tool/resource handlers and schemas
    - expose transport introspection
    - delegate tool/resource dispatch to helper functions
    """

    def __init__(
        self,
        settings: Any,
        tool_handlers: dict[str, McpToolHandler] | None = None,
        resource_handlers: dict[str, McpResourceHandler] | None = None,
        tool_schemas: dict[str, McpToolSchema] | None = None,
    ) -> None:
        self.settings = settings
        self._started = False
        self._tool_handlers: dict[str, McpToolHandler] = tool_handlers or {}
        self._resource_handlers: dict[str, McpResourceHandler] = resource_handlers or {}
        self._tool_schemas: dict[str, McpToolSchema] = tool_schemas or {}
        self._mcp_lifecycle_state = McpLifecycleState()

    def register_tool_handler(
        self,
        tool_name: str,
        handler: McpToolHandler,
        schema: McpToolSchema | None = None,
    ) -> None:
        self._tool_handlers[tool_name] = handler
        if schema is not None:
            self._tool_schemas[tool_name] = schema

    def register_resource_handler(
        self,
        resource_pattern: str,
        handler: McpResourceHandler,
    ) -> None:
        self._resource_handlers[resource_pattern] = handler

    def registered_tools(self) -> tuple[str, ...]:
        return tuple(sorted(self._tool_handlers.keys()))

    def registered_resources(self) -> tuple[str, ...]:
        return tuple(sorted(self._resource_handlers.keys()))

    def tool_schema(self, tool_name: str) -> McpToolSchema:
        return self._tool_schemas.get(tool_name, DEFAULT_EMPTY_MCP_TOOL_SCHEMA)

    def introspect(self) -> StdioTransportIntrospection:
        return StdioTransportIntrospection(
            transport="stdio",
            tools=self.registered_tools(),
            resources=self.registered_resources(),
        )

    def dispatch_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        return dispatch_mcp_tool(self, tool_name, arguments).response

    def dispatch_resource(self, uri: str) -> Any:
        return dispatch_mcp_resource(self, uri).response

    def start(self) -> None:
        logger.info(
            "stdio runtime adapter starting",
            extra={
                "transport": "stdio",
                "registered_tools": list(self.registered_tools()),
                "registered_resources": list(self.registered_resources()),
            },
        )
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return

        logger.info(
            "stdio runtime adapter stopping",
            extra={
                "transport": "stdio",
                "registered_tools": list(self.registered_tools()),
                "registered_resources": list(self.registered_resources()),
            },
        )
        self._started = False


@dataclass(slots=True)
class StdioRpcServer:
    runtime: StdioRuntimeAdapter

    def handle_request(self, req: dict[str, Any]) -> dict[str, Any] | None:
        return handle_mcp_rpc_request(self.runtime, req)

    def run(self) -> None:
        for line in sys.stdin:
            raw_line = line.strip()
            if not raw_line:
                continue

            req_id: Any = None
            try:
                parsed = json.loads(raw_line)
                if not isinstance(parsed, dict):
                    raise ValueError("Request must be a JSON object")

                req_id = parsed.get("id")
                response = self.handle_request(parsed)
                if response is not None:
                    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
            except SystemExit:
                raise
            except Exception as exc:
                if req_id is None:
                    continue

                error_response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": str(exc),
                    },
                }
                sys.stdout.write(json.dumps(error_response, ensure_ascii=False) + "\n")
                sys.stdout.flush()


def dispatch_mcp_tool(
    runtime: StdioRuntimeAdapter,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    handler = runtime._tool_handlers.get(tool_name)
    if handler is None:
        response = _lookup_server_symbol("McpToolResponse")(
            payload={
                "error": {
                    "code": "tool_not_found",
                    "message": (
                        f"no MCP tool handler is registered for tool '{tool_name}'"
                    ),
                }
            }
        )
        return _lookup_server_symbol("RuntimeDispatchResult")(
            transport="stdio",
            target=tool_name,
            status="tool_not_found",
            response=response,
        )

    response = handler(arguments)
    error_payload = response.payload.get("error")
    return _lookup_server_symbol("RuntimeDispatchResult")(
        transport="stdio",
        target=tool_name,
        status="error" if error_payload is not None else "ok",
        response=response,
    )


def dispatch_mcp_resource(
    runtime: StdioRuntimeAdapter,
    uri: str,
) -> Any:
    for resource_pattern, handler in runtime._resource_handlers.items():
        if resource_pattern == "workspace://{workspace_id}/resume":
            if parse_workspace_resume_resource_uri(uri) is not None:
                response = handler(uri)
                status = "ok" if response.status_code < 400 else "error"
                return _lookup_server_symbol("RuntimeDispatchResult")(
                    transport="stdio",
                    target=uri,
                    status=status,
                    response=response,
                )

        elif (
            resource_pattern
            == "workspace://{workspace_id}/workflow/{workflow_instance_id}"
        ):
            if parse_workflow_detail_resource_uri(uri) is not None:
                response = handler(uri)
                status = "ok" if response.status_code < 400 else "error"
                return _lookup_server_symbol("RuntimeDispatchResult")(
                    transport="stdio",
                    target=uri,
                    status=status,
                    response=response,
                )

    response = _lookup_server_symbol("McpResourceResponse")(
        status_code=404,
        payload={
            "error": {
                "code": "resource_not_found",
                "message": (
                    f"no MCP resource handler is registered for resource '{uri}'"
                ),
            }
        },
        headers={"content-type": "application/json"},
    )
    return _lookup_server_symbol("RuntimeDispatchResult")(
        transport="stdio",
        target=uri,
        status="resource_not_found",
        response=response,
    )


__all__ = [
    "McpResourceHandler",
    "McpToolHandler",
    "StdioRpcServer",
    "StdioRuntimeAdapter",
    "StdioRuntimeProtocol",
    "StdioTransportIntrospection",
    "dispatch_mcp_resource",
    "dispatch_mcp_tool",
]

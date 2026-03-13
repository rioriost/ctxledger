from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from ..config import AppSettings
from ..mcp.resource_handlers import (
    build_workflow_detail_resource_handler,
    build_workspace_resume_resource_handler,
    parse_workflow_detail_resource_uri,
    parse_workspace_resume_resource_uri,
)
from ..mcp.tool_handlers import (
    build_mcp_error_response,
    build_memory_get_context_tool_handler,
    build_memory_remember_episode_tool_handler,
    build_memory_search_tool_handler,
    build_projection_failures_ignore_tool_handler,
    build_projection_failures_resolve_tool_handler,
    build_resume_workflow_tool_handler,
    build_workflow_checkpoint_tool_handler,
    build_workflow_complete_tool_handler,
    build_workflow_start_tool_handler,
    build_workspace_register_tool_handler,
)
from ..mcp.tool_schemas import (
    DEFAULT_EMPTY_MCP_TOOL_SCHEMA,
    MEMORY_GET_CONTEXT_TOOL_SCHEMA,
    MEMORY_REMEMBER_EPISODE_TOOL_SCHEMA,
    MEMORY_SEARCH_TOOL_SCHEMA,
    PROJECTION_FAILURES_IGNORE_TOOL_SCHEMA,
    PROJECTION_FAILURES_RESOLVE_TOOL_SCHEMA,
    WORKFLOW_CHECKPOINT_TOOL_SCHEMA,
    WORKFLOW_COMPLETE_TOOL_SCHEMA,
    WORKFLOW_RESUME_TOOL_SCHEMA,
    WORKFLOW_START_TOOL_SCHEMA,
    WORKSPACE_REGISTER_TOOL_SCHEMA,
    McpToolSchema,
)
from ..memory.service import MemoryService
from .http_handlers import (
    build_closed_projection_failures_http_handler,
    build_mcp_http_handler,
    build_projection_failures_ignore_http_handler,
    build_projection_failures_resolve_http_handler,
    build_runtime_introspection_http_handler,
    build_runtime_routes_http_handler,
    build_runtime_tools_http_handler,
    build_workflow_resume_http_handler,
)
from .introspection import RuntimeIntrospection
from .protocols import HttpHandlerFactoryServer

if TYPE_CHECKING:
    from ..server import CtxLedgerServer
    from .protocols import HttpRuntimeAdapterProtocol
    from .types import (
        McpHttpResponse,
        McpResourceResponse,
        McpToolResponse,
        WorkflowResumeResponse,
    )

logger = logging.getLogger(__name__)

WorkflowHttpHandler = Any


class HttpRuntimeAdapter:
    """
    HTTP runtime adapter responsible for HTTP handler registration, MCP tool and
    resource dispatch, runtime introspection, and lifecycle logging.
    """

    def __init__(
        self,
        settings: AppSettings,
        server: CtxLedgerServer | None = None,
        handlers: dict[str, WorkflowHttpHandler] | None = None,
    ) -> None:
        self.settings = settings
        self._started = False
        self._handlers: dict[str, WorkflowHttpHandler] = handlers or {}
        self._server: CtxLedgerServer | None = server

    def register_handler(self, route_name: str, handler: WorkflowHttpHandler) -> None:
        self._handlers[route_name] = handler

    def handler(self, route_name: str) -> WorkflowHttpHandler | None:
        return self._handlers.get(route_name)

    def require_handler(self, route_name: str) -> WorkflowHttpHandler:
        handler = self.handler(route_name)
        if handler is None:
            raise KeyError(route_name)
        return handler

    def introspection_endpoints(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers.keys()))

    def registered_tools(self) -> tuple[str, ...]:
        return (
            "memory_get_context",
            "memory_remember_episode",
            "memory_search",
            "projection_failures_ignore",
            "projection_failures_resolve",
            "workflow_checkpoint",
            "workflow_complete",
            "workflow_resume",
            "workflow_start",
            "workspace_register",
        )

    def tool_schema(self, tool_name: str) -> McpToolSchema:
        tool_schemas = {
            "memory_get_context": MEMORY_GET_CONTEXT_TOOL_SCHEMA,
            "memory_remember_episode": MEMORY_REMEMBER_EPISODE_TOOL_SCHEMA,
            "memory_search": MEMORY_SEARCH_TOOL_SCHEMA,
            "projection_failures_ignore": PROJECTION_FAILURES_IGNORE_TOOL_SCHEMA,
            "projection_failures_resolve": PROJECTION_FAILURES_RESOLVE_TOOL_SCHEMA,
            "workflow_checkpoint": WORKFLOW_CHECKPOINT_TOOL_SCHEMA,
            "workflow_complete": WORKFLOW_COMPLETE_TOOL_SCHEMA,
            "workflow_resume": WORKFLOW_RESUME_TOOL_SCHEMA,
            "workflow_start": WORKFLOW_START_TOOL_SCHEMA,
            "workspace_register": WORKSPACE_REGISTER_TOOL_SCHEMA,
        }
        return tool_schemas.get(tool_name, DEFAULT_EMPTY_MCP_TOOL_SCHEMA)

    def registered_resources(self) -> tuple[str, ...]:
        return (
            "workspace://{workspace_id}/resume",
            "workspace://{workspace_id}/workflow/{workflow_instance_id}",
        )

    def dispatch_resource(self, uri: str) -> McpResourceResponse:
        workspace_resume_handler = build_workspace_resume_resource_handler(self._server)
        workflow_detail_handler = build_workflow_detail_resource_handler(self._server)

        if parse_workflow_detail_resource_uri(uri) is not None:
            return workflow_detail_handler(uri)
        if parse_workspace_resume_resource_uri(uri) is not None:
            return workspace_resume_handler(uri)

        from .types import McpResourceResponse

        return McpResourceResponse(
            status_code=404,
            payload={
                "error": {
                    "code": "resource_not_found",
                    "message": f"unknown MCP resource '{uri}'",
                }
            },
            headers={"content-type": "application/json"},
        )

    def dispatch_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> McpToolResponse:
        tool_handlers = {
            "memory_get_context": build_memory_get_context_tool_handler(
                MemoryService()
            ),
            "memory_remember_episode": build_memory_remember_episode_tool_handler(
                MemoryService()
            ),
            "memory_search": build_memory_search_tool_handler(MemoryService()),
            "projection_failures_ignore": build_projection_failures_ignore_tool_handler(
                self._server
            ),
            "projection_failures_resolve": build_projection_failures_resolve_tool_handler(
                self._server
            ),
            "workflow_checkpoint": build_workflow_checkpoint_tool_handler(self._server),
            "workflow_complete": build_workflow_complete_tool_handler(self._server),
            "workflow_resume": build_resume_workflow_tool_handler(self._server),
            "workflow_start": build_workflow_start_tool_handler(self._server),
            "workspace_register": build_workspace_register_tool_handler(self._server),
        }
        handler = tool_handlers.get(tool_name)
        if handler is None:
            return build_mcp_error_response(
                code="tool_not_found",
                message=f"unknown MCP tool '{tool_name}'",
            )
        return handler(arguments)

    def introspect(self) -> RuntimeIntrospection:
        return RuntimeIntrospection(
            transport="http",
            routes=self.introspection_endpoints(),
            tools=self.registered_tools(),
            resources=self.registered_resources(),
        )

    def dispatch(
        self,
        route_name: str,
        path: str,
        body: str | None = None,
    ) -> WorkflowResumeResponse | McpHttpResponse:
        from .types import WorkflowResumeResponse

        handler = self.handler(route_name)
        if handler is None:
            return WorkflowResumeResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "route_not_found",
                        "message": f"no HTTP handler is registered for route '{route_name}'",
                    }
                },
                headers={"content-type": "application/json"},
            )

        if route_name == "mcp_rpc":
            return handler(path, body)

        return handler(path)

    def start(self) -> None:
        logger.info(
            "HTTP runtime adapter starting",
            extra={
                "transport": "http",
                "host": self.settings.http.host,
                "port": self.settings.http.port,
                "path": self.settings.http.path,
                "mcp_url": self.settings.http.mcp_url,
                "introspection_endpoints": list(self.introspection_endpoints()),
            },
        )
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return

        logger.info(
            "HTTP runtime adapter stopping",
            extra={
                "transport": "http",
                "host": self.settings.http.host,
                "port": self.settings.http.port,
                "introspection_endpoints": list(self.introspection_endpoints()),
            },
        )
        self._started = False


def register_http_runtime_handlers(
    runtime: HttpRuntimeAdapterProtocol,
    server: HttpHandlerFactoryServer,
) -> HttpRuntimeAdapterProtocol:
    mcp_runtime = runtime
    debug_settings = getattr(server.settings, "debug", None)
    debug_http_endpoints_enabled = (
        True if debug_settings is None else getattr(debug_settings, "enabled", True)
    )

    runtime.register_handler(
        "mcp_rpc",
        build_mcp_http_handler(mcp_runtime, server),
    )

    if debug_http_endpoints_enabled:
        runtime.register_handler(
            "runtime_introspection",
            build_runtime_introspection_http_handler(server),
        )
        runtime.register_handler(
            "runtime_routes",
            build_runtime_routes_http_handler(server),
        )
        runtime.register_handler(
            "runtime_tools",
            build_runtime_tools_http_handler(server),
        )

    runtime.register_handler(
        "workflow_resume",
        build_workflow_resume_http_handler(server),
    )
    runtime.register_handler(
        "workflow_closed_projection_failures",
        build_closed_projection_failures_http_handler(server),
    )
    runtime.register_handler(
        "projection_failures_ignore",
        build_projection_failures_ignore_http_handler(server),
    )
    runtime.register_handler(
        "projection_failures_resolve",
        build_projection_failures_resolve_http_handler(server),
    )
    return runtime


def build_http_runtime_adapter(
    server: HttpHandlerFactoryServer,
) -> HttpRuntimeAdapterProtocol:
    runtime = HttpRuntimeAdapter(server.settings, server=server)
    return register_http_runtime_handlers(runtime, server)


__all__ = [
    "HttpRuntimeAdapter",
    "build_http_runtime_adapter",
    "register_http_runtime_handlers",
]

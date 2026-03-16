from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from ..mcp.rpc import handle_mcp_rpc_request
from ..mcp.streamable_http import (
    StreamableHttpRequest,
    build_streamable_http_endpoint,
)

_WORKFLOW_RESUME_ROUTE = "workflow-resume"
_DEBUG_RUNTIME_ROUTE = "debug/runtime"
_DEBUG_ROUTES_ROUTE = "debug/routes"
_DEBUG_TOOLS_ROUTE = "debug/tools"

if TYPE_CHECKING:
    from uuid import UUID

    from .protocols import HttpHandlerFactoryServer, McpRuntimeProtocol
    from .types import (
        McpHttpResponse,
        RuntimeIntrospectionResponse,
        WorkflowResumeResponse,
    )


def parse_required_uuid_argument(
    arguments: dict[str, Any],
    field_name: str,
) -> UUID | McpToolResponse:
    from uuid import UUID

    from ..mcp.tool_handlers import build_mcp_error_response

    raw_value = arguments.get(field_name)
    if not isinstance(raw_value, str) or not raw_value.strip():
        return build_mcp_error_response(
            code="invalid_request",
            message=f"{field_name} must be a non-empty string",
            details={"field": field_name},
        )

    try:
        return UUID(raw_value)
    except ValueError:
        return build_mcp_error_response(
            code="invalid_request",
            message=f"{field_name} must be a valid UUID",
            details={"field": field_name},
        )


def parse_workflow_resume_request_path(path: str):
    parts = _parse_request_path_parts(path)
    if parts is None or len(parts) != 2 or parts[0] != _WORKFLOW_RESUME_ROUTE:
        return None

    return _parse_uuid_value(parts[1])


def build_workflow_resume_http_handler(
    server: HttpHandlerFactoryServer,
):
    from .server_responses import build_workflow_resume_response
    from .types import WorkflowResumeResponse

    def _handler(path: str) -> WorkflowResumeResponse:
        workflow_instance_id = parse_workflow_resume_request_path(path)
        if workflow_instance_id is None:
            return _build_http_error_response(
                WorkflowResumeResponse,
                status_code=404,
                code="not_found",
                message=(
                    "workflow resume endpoint requires "
                    "/workflow-resume/{workflow_instance_id}"
                ),
            )

        return build_workflow_resume_response(server, workflow_instance_id)

    return _handler


def build_runtime_introspection_http_handler(
    server: HttpHandlerFactoryServer,
):
    from .server_responses import build_runtime_introspection_response
    from .types import RuntimeIntrospectionResponse

    def _handler(path: str) -> RuntimeIntrospectionResponse:
        if _normalize_debug_path(path) != _DEBUG_RUNTIME_ROUTE:
            return _build_http_error_response(
                RuntimeIntrospectionResponse,
                status_code=404,
                code="not_found",
                message="runtime introspection endpoint requires /debug/runtime",
            )

        return build_runtime_introspection_response(server)

    return _handler


def build_runtime_routes_http_handler(
    server: HttpHandlerFactoryServer,
):
    from .server_responses import build_runtime_routes_response
    from .types import RuntimeIntrospectionResponse

    def _handler(path: str) -> RuntimeIntrospectionResponse:
        if _normalize_debug_path(path) != _DEBUG_ROUTES_ROUTE:
            return _build_http_error_response(
                RuntimeIntrospectionResponse,
                status_code=404,
                code="not_found",
                message="runtime routes endpoint requires /debug/routes",
            )

        return build_runtime_routes_response(server)

    return _handler


def build_runtime_tools_http_handler(
    server: HttpHandlerFactoryServer,
):
    from .server_responses import build_runtime_tools_response
    from .types import RuntimeIntrospectionResponse

    def _handler(path: str) -> RuntimeIntrospectionResponse:
        if _normalize_debug_path(path) != _DEBUG_TOOLS_ROUTE:
            return _build_http_error_response(
                RuntimeIntrospectionResponse,
                status_code=404,
                code="not_found",
                message="runtime tools endpoint requires /debug/tools",
            )

        return build_runtime_tools_response(server)

    return _handler


def build_mcp_http_handler(
    runtime: McpRuntimeProtocol,
    server: HttpHandlerFactoryServer,
):
    from .types import McpHttpResponse

    class _StreamableHttpRuntimeAdapter:
        def handle_rpc_request(
            self,
            request: dict[str, Any],
        ) -> dict[str, Any] | None:
            return handle_mcp_rpc_request(runtime, request)

    endpoint = build_streamable_http_endpoint(
        _StreamableHttpRuntimeAdapter(),
        mcp_path=server.settings.http.path,
    )

    def _handler(path: str, body: str | None = None) -> McpHttpResponse:
        response = endpoint.handle(
            StreamableHttpRequest(
                path=path,
                body=body,
            )
        )
        return McpHttpResponse(
            status_code=response.status_code,
            payload=response.payload,
            headers=response.headers,
        )

    return _handler


def _build_http_error_response(
    response_type: type[Any],
    *,
    status_code: int,
    code: str,
    message: str,
) -> Any:
    return response_type(
        status_code=status_code,
        payload={
            "error": {
                "code": code,
                "message": message,
            }
        },
        headers={"content-type": "application/json"},
    )


def _build_http_validation_error_response(
    response_type: type[Any],
    error_response: McpToolResponse,
) -> Any:
    return response_type(
        status_code=400,
        payload={"error": error_response.payload["error"]},
        headers={"content-type": "application/json"},
    )


def _parse_request_path_parts(path: str) -> list[str] | None:
    normalized_path = path.strip()
    if not normalized_path:
        return None

    path_without_query = normalized_path.split("?", 1)[0]
    trimmed = path_without_query.strip("/")
    if not trimmed:
        return None

    return trimmed.split("/")


def _normalize_debug_path(path: str) -> str | None:
    parts = _parse_request_path_parts(path)
    if parts is None:
        return None
    return "/".join(parts)


def _parse_uuid_value(value: str):
    from uuid import UUID

    try:
        return UUID(value)
    except ValueError:
        return None


__all__ = [
    "build_mcp_http_handler",
    "build_runtime_introspection_http_handler",
    "build_runtime_routes_http_handler",
    "build_runtime_tools_http_handler",
    "build_workflow_resume_http_handler",
    "parse_required_uuid_argument",
    "parse_workflow_resume_request_path",
]

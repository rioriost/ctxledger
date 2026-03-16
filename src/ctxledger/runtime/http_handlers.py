from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from ..mcp.rpc import handle_mcp_rpc_request
from ..mcp.streamable_http import (
    StreamableHttpRequest,
    build_streamable_http_endpoint,
)

_WORKFLOW_RESUME_ROUTE = "workflow-resume"
_CLOSED_PROJECTION_FAILURES_ROUTE = "closed-projection-failures"
_DEBUG_RUNTIME_ROUTE = "debug/runtime"
_DEBUG_ROUTES_ROUTE = "debug/routes"
_DEBUG_TOOLS_ROUTE = "debug/tools"
_PROJECTION_FAILURES_IGNORE_ROUTE = "projection_failures_ignore"
_PROJECTION_FAILURES_RESOLVE_ROUTE = "projection_failures_resolve"

if TYPE_CHECKING:
    from uuid import UUID

    from ..workflow.service import ProjectionArtifactType
    from .protocols import HttpHandlerFactoryServer, McpRuntimeProtocol
    from .types import (
        McpHttpResponse,
        McpToolResponse,
        ProjectionFailureActionResponse,
        ProjectionFailureHistoryResponse,
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


def parse_optional_projection_type_argument(
    arguments: dict[str, Any],
) -> ProjectionArtifactType | None | McpToolResponse:
    from ..mcp.tool_handlers import build_mcp_error_response

    raw_value = arguments.get("projection_type")
    if raw_value is None:
        return None
    if not isinstance(raw_value, str) or not raw_value.strip():
        return build_mcp_error_response(
            code="invalid_request",
            message="projection_type must be a non-empty string when provided",
            details={"field": "projection_type"},
        )

    from ..workflow.service import ProjectionArtifactType

    try:
        return ProjectionArtifactType(raw_value.strip())
    except ValueError:
        allowed_values = [
            projection_type.value for projection_type in ProjectionArtifactType
        ]
        return build_mcp_error_response(
            code="invalid_request",
            message="projection_type must be a supported projection artifact type",
            details={
                "field": "projection_type",
                "allowed_values": allowed_values,
            },
        )


def parse_workflow_resume_request_path(path: str):
    parts = _parse_request_path_parts(path)
    if parts is None or len(parts) != 2 or parts[0] != _WORKFLOW_RESUME_ROUTE:
        return None

    return _parse_uuid_value(parts[1])


def parse_closed_projection_failures_request_path(path: str):
    parts = _parse_request_path_parts(path)
    if (
        parts is None
        or len(parts) != 3
        or parts[0] != _WORKFLOW_RESUME_ROUTE
        or parts[2] != _CLOSED_PROJECTION_FAILURES_ROUTE
    ):
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


def build_closed_projection_failures_http_handler(
    server: HttpHandlerFactoryServer,
):
    from .server_responses import build_closed_projection_failures_response
    from .types import ProjectionFailureHistoryResponse

    def _handler(path: str) -> ProjectionFailureHistoryResponse:
        workflow_instance_id = parse_closed_projection_failures_request_path(path)
        if workflow_instance_id is None:
            return _build_http_error_response(
                ProjectionFailureHistoryResponse,
                status_code=404,
                code="not_found",
                message=(
                    "closed projection failures endpoint requires "
                    "/workflow-resume/{workflow_instance_id}"
                    "/closed-projection-failures"
                ),
            )

        return build_closed_projection_failures_response(server, workflow_instance_id)

    return _handler


def build_projection_failures_ignore_http_handler(
    server: HttpHandlerFactoryServer,
):
    from .server_responses import build_projection_failures_ignore_response
    from .types import McpToolResponse, ProjectionFailureActionResponse

    def _handler(path: str) -> ProjectionFailureActionResponse:
        parsed_arguments = _parse_projection_failure_request(
            path,
            expected_route=_PROJECTION_FAILURES_IGNORE_ROUTE,
            not_found_message=(
                "projection failure ignore endpoint requires "
                "/projection_failures_ignore"
            ),
        )
        if isinstance(parsed_arguments, ProjectionFailureActionResponse):
            return parsed_arguments

        workspace_id, workflow_instance_id, projection_type = parsed_arguments
        return build_projection_failures_ignore_response(
            server,
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=projection_type,
        )

    return _handler


def build_projection_failures_resolve_http_handler(
    server: HttpHandlerFactoryServer,
):
    from .server_responses import build_projection_failures_resolve_response
    from .types import McpToolResponse, ProjectionFailureActionResponse

    def _handler(path: str) -> ProjectionFailureActionResponse:
        parsed_arguments = _parse_projection_failure_request(
            path,
            expected_route=_PROJECTION_FAILURES_RESOLVE_ROUTE,
            not_found_message=(
                "projection failure resolve endpoint requires "
                "/projection_failures_resolve"
            ),
        )
        if isinstance(parsed_arguments, ProjectionFailureActionResponse):
            return parsed_arguments

        workspace_id, workflow_instance_id, projection_type = parsed_arguments
        return build_projection_failures_resolve_response(
            server,
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=projection_type,
        )

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


def _parse_query_arguments(query: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(query).items() if values}


def _parse_projection_failure_request(
    path: str,
    *,
    expected_route: str,
    not_found_message: str,
) -> tuple[UUID, UUID, ProjectionArtifactType | None] | ProjectionFailureActionResponse:
    from .types import McpToolResponse, ProjectionFailureActionResponse

    parsed = urlparse(path)
    normalized_path = parsed.path.strip("/")
    if normalized_path != expected_route:
        return _build_http_error_response(
            ProjectionFailureActionResponse,
            status_code=404,
            code="not_found",
            message=not_found_message,
        )

    arguments = _parse_query_arguments(parsed.query)

    workspace_id = parse_required_uuid_argument(arguments, "workspace_id")
    if isinstance(workspace_id, McpToolResponse):
        return _build_http_validation_error_response(
            ProjectionFailureActionResponse,
            workspace_id,
        )

    workflow_instance_id = parse_required_uuid_argument(
        arguments,
        "workflow_instance_id",
    )
    if isinstance(workflow_instance_id, McpToolResponse):
        return _build_http_validation_error_response(
            ProjectionFailureActionResponse,
            workflow_instance_id,
        )

    projection_type = parse_optional_projection_type_argument(arguments)
    if isinstance(projection_type, McpToolResponse):
        return _build_http_validation_error_response(
            ProjectionFailureActionResponse,
            projection_type,
        )

    return workspace_id, workflow_instance_id, projection_type


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
    "build_closed_projection_failures_http_handler",
    "build_mcp_http_handler",
    "build_projection_failures_ignore_http_handler",
    "build_projection_failures_resolve_http_handler",
    "build_runtime_introspection_http_handler",
    "build_runtime_routes_http_handler",
    "build_runtime_tools_http_handler",
    "build_workflow_resume_http_handler",
    "parse_closed_projection_failures_request_path",
    "parse_optional_projection_type_argument",
    "parse_required_uuid_argument",
    "parse_workflow_resume_request_path",
]

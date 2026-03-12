from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from ..mcp.rpc import handle_mcp_rpc_request
from ..mcp.streamable_http import (
    StreamableHttpRequest,
    StreamableHttpResponse,
    build_streamable_http_endpoint,
)

if TYPE_CHECKING:
    from uuid import UUID

    from ..server import CtxLedgerServer, McpRuntimeProtocol, ProjectionArtifactType
    from .types import (
        McpHttpResponse,
        McpToolResponse,
        ProjectionFailureActionResponse,
        ProjectionFailureHistoryResponse,
        RuntimeIntrospectionResponse,
        WorkflowResumeResponse,
    )


def extract_bearer_token(path: str) -> str | None:
    normalized_path = path.strip()
    if not normalized_path:
        return None

    parsed = urlparse(normalized_path)
    authorization_values = parse_qs(parsed.query).get("authorization", [])
    if not authorization_values:
        return None

    authorization = authorization_values[0].strip()
    if not authorization:
        return None

    scheme, separator, token = authorization.partition(" ")
    if separator == "" or scheme.lower() != "bearer":
        return None

    token = token.strip()
    return token or None


def build_http_auth_error_response(message: str) -> WorkflowResumeResponse:
    from .types import WorkflowResumeResponse

    return WorkflowResumeResponse(
        status_code=401,
        payload={
            "error": {
                "code": "authentication_error",
                "message": message,
            }
        },
        headers={
            "content-type": "application/json",
            "www-authenticate": 'Bearer realm="ctxledger"',
        },
    )


def require_http_bearer_auth(
    server: CtxLedgerServer,
    path: str,
) -> WorkflowResumeResponse | None:
    if not server.settings.auth.is_enabled:
        return None

    expected_token = server.settings.auth.bearer_token
    if expected_token is None:
        return build_http_auth_error_response("bearer token is not configured")

    presented_token = extract_bearer_token(path)
    if presented_token is None:
        return build_http_auth_error_response("missing bearer token")

    if presented_token != expected_token:
        return build_http_auth_error_response("invalid bearer token")

    return None


def parse_required_uuid_argument(
    arguments: dict[str, Any],
    field_name: str,
) -> UUID | McpToolResponse:
    from uuid import UUID

    from ..server import build_mcp_error_response

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
    from ..server import build_mcp_error_response

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
    from uuid import UUID

    normalized_path = path.strip()
    if not normalized_path:
        return None

    path_without_query = normalized_path.split("?", 1)[0]
    trimmed = path_without_query.strip("/")
    if not trimmed:
        return None

    parts = trimmed.split("/")
    if len(parts) != 2 or parts[0] != "workflow-resume":
        return None

    try:
        return UUID(parts[1])
    except ValueError:
        return None


def parse_closed_projection_failures_request_path(path: str):
    from uuid import UUID

    normalized_path = path.strip()
    if not normalized_path:
        return None

    path_without_query = normalized_path.split("?", 1)[0]
    trimmed = path_without_query.strip("/")
    if not trimmed:
        return None

    parts = trimmed.split("/")
    if (
        len(parts) != 3
        or parts[0] != "workflow-resume"
        or parts[2] != "closed-projection-failures"
    ):
        return None

    try:
        return UUID(parts[1])
    except ValueError:
        return None


def build_workflow_resume_http_handler(
    server: CtxLedgerServer,
):
    from .server_responses import build_workflow_resume_response
    from .types import WorkflowResumeResponse

    def _handler(path: str) -> WorkflowResumeResponse:
        auth_error = require_http_bearer_auth(server, path)
        if auth_error is not None:
            return auth_error

        workflow_instance_id = parse_workflow_resume_request_path(path)
        if workflow_instance_id is None:
            return WorkflowResumeResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": (
                            "workflow resume endpoint requires "
                            "/workflow-resume/{workflow_instance_id}"
                        ),
                    }
                },
                headers={"content-type": "application/json"},
            )

        return build_workflow_resume_response(server, workflow_instance_id)

    return _handler


def build_closed_projection_failures_http_handler(
    server: CtxLedgerServer,
):
    from .server_responses import build_closed_projection_failures_response
    from .types import ProjectionFailureHistoryResponse

    def _handler(path: str) -> ProjectionFailureHistoryResponse:
        auth_error = require_http_bearer_auth(server, path)
        if auth_error is not None:
            return ProjectionFailureHistoryResponse(
                status_code=auth_error.status_code,
                payload=auth_error.payload,
                headers=auth_error.headers,
            )

        workflow_instance_id = parse_closed_projection_failures_request_path(path)
        if workflow_instance_id is None:
            return ProjectionFailureHistoryResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": (
                            "closed projection failures endpoint requires "
                            "/workflow-resume/{workflow_instance_id}"
                            "/closed-projection-failures"
                        ),
                    }
                },
                headers={"content-type": "application/json"},
            )

        return build_closed_projection_failures_response(server, workflow_instance_id)

    return _handler


def build_projection_failures_ignore_http_handler(
    server: CtxLedgerServer,
):
    from .server_responses import build_projection_failures_ignore_response
    from .types import McpToolResponse, ProjectionFailureActionResponse

    def _handler(path: str) -> ProjectionFailureActionResponse:
        auth_error = require_http_bearer_auth(server, path)
        if auth_error is not None:
            return ProjectionFailureActionResponse(
                status_code=auth_error.status_code,
                payload=auth_error.payload,
                headers=auth_error.headers,
            )

        parsed = urlparse(path)
        normalized_path = parsed.path.strip("/")
        if normalized_path != "projection_failures_ignore":
            return ProjectionFailureActionResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": (
                            "projection failure ignore endpoint requires "
                            "/projection_failures_ignore"
                        ),
                    }
                },
                headers={"content-type": "application/json"},
            )

        arguments = {
            key: values[0] for key, values in parse_qs(parsed.query).items() if values
        }

        workspace_id = parse_required_uuid_argument(arguments, "workspace_id")
        if isinstance(workspace_id, McpToolResponse):
            return ProjectionFailureActionResponse(
                status_code=400,
                payload={"error": workspace_id.payload["error"]},
                headers={"content-type": "application/json"},
            )

        workflow_instance_id = parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, McpToolResponse):
            return ProjectionFailureActionResponse(
                status_code=400,
                payload={"error": workflow_instance_id.payload["error"]},
                headers={"content-type": "application/json"},
            )

        projection_type = parse_optional_projection_type_argument(arguments)
        if isinstance(projection_type, McpToolResponse):
            return ProjectionFailureActionResponse(
                status_code=400,
                payload={"error": projection_type.payload["error"]},
                headers={"content-type": "application/json"},
            )

        return build_projection_failures_ignore_response(
            server,
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=projection_type,
        )

    return _handler


def build_projection_failures_resolve_http_handler(
    server: CtxLedgerServer,
):
    from .server_responses import build_projection_failures_resolve_response
    from .types import McpToolResponse, ProjectionFailureActionResponse

    def _handler(path: str) -> ProjectionFailureActionResponse:
        auth_error = require_http_bearer_auth(server, path)
        if auth_error is not None:
            return ProjectionFailureActionResponse(
                status_code=auth_error.status_code,
                payload=auth_error.payload,
                headers=auth_error.headers,
            )

        parsed = urlparse(path)
        normalized_path = parsed.path.strip("/")
        if normalized_path != "projection_failures_resolve":
            return ProjectionFailureActionResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": (
                            "projection failure resolve endpoint requires "
                            "/projection_failures_resolve"
                        ),
                    }
                },
                headers={"content-type": "application/json"},
            )

        arguments = {
            key: values[0] for key, values in parse_qs(parsed.query).items() if values
        }

        workspace_id = parse_required_uuid_argument(arguments, "workspace_id")
        if isinstance(workspace_id, McpToolResponse):
            return ProjectionFailureActionResponse(
                status_code=400,
                payload={"error": workspace_id.payload["error"]},
                headers={"content-type": "application/json"},
            )

        workflow_instance_id = parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, McpToolResponse):
            return ProjectionFailureActionResponse(
                status_code=400,
                payload={"error": workflow_instance_id.payload["error"]},
                headers={"content-type": "application/json"},
            )

        projection_type = parse_optional_projection_type_argument(arguments)
        if isinstance(projection_type, McpToolResponse):
            return ProjectionFailureActionResponse(
                status_code=400,
                payload={"error": projection_type.payload["error"]},
                headers={"content-type": "application/json"},
            )

        return build_projection_failures_resolve_response(
            server,
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=projection_type,
        )

    return _handler


def build_runtime_introspection_http_handler(
    server: CtxLedgerServer,
):
    from .server_responses import build_runtime_introspection_response
    from .types import RuntimeIntrospectionResponse

    def _handler(path: str) -> RuntimeIntrospectionResponse:
        auth_error = require_http_bearer_auth(server, path)
        if auth_error is not None:
            return RuntimeIntrospectionResponse(
                status_code=auth_error.status_code,
                payload=auth_error.payload,
                headers=auth_error.headers,
            )

        normalized_path = path.strip()
        path_without_query = normalized_path.split("?", 1)[0].strip("/")
        if path_without_query != "debug/runtime":
            return RuntimeIntrospectionResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": (
                            "runtime introspection endpoint requires /debug/runtime"
                        ),
                    }
                },
                headers={"content-type": "application/json"},
            )

        return build_runtime_introspection_response(server)

    return _handler


def build_runtime_routes_http_handler(
    server: CtxLedgerServer,
):
    from .server_responses import build_runtime_routes_response
    from .types import RuntimeIntrospectionResponse

    def _handler(path: str) -> RuntimeIntrospectionResponse:
        auth_error = require_http_bearer_auth(server, path)
        if auth_error is not None:
            return RuntimeIntrospectionResponse(
                status_code=auth_error.status_code,
                payload=auth_error.payload,
                headers=auth_error.headers,
            )

        normalized_path = path.strip()
        path_without_query = normalized_path.split("?", 1)[0].strip("/")
        if path_without_query != "debug/routes":
            return RuntimeIntrospectionResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": "runtime routes endpoint requires /debug/routes",
                    }
                },
                headers={"content-type": "application/json"},
            )

        return build_runtime_routes_response(server)

    return _handler


def build_runtime_tools_http_handler(
    server: CtxLedgerServer,
):
    from .server_responses import build_runtime_tools_response
    from .types import RuntimeIntrospectionResponse

    def _handler(path: str) -> RuntimeIntrospectionResponse:
        auth_error = require_http_bearer_auth(server, path)
        if auth_error is not None:
            return RuntimeIntrospectionResponse(
                status_code=auth_error.status_code,
                payload=auth_error.payload,
                headers=auth_error.headers,
            )

        normalized_path = path.strip()
        path_without_query = normalized_path.split("?", 1)[0].strip("/")
        if path_without_query != "debug/tools":
            return RuntimeIntrospectionResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": "runtime tools endpoint requires /debug/tools",
                    }
                },
                headers={"content-type": "application/json"},
            )

        return build_runtime_tools_response(server)

    return _handler


def build_mcp_http_handler(
    runtime: McpRuntimeProtocol,
    server: CtxLedgerServer,
):
    from .types import McpHttpResponse

    def _validate_auth(path: str) -> StreamableHttpResponse | None:
        auth_error = require_http_bearer_auth(server, path)
        if auth_error is None:
            return None
        return StreamableHttpResponse(
            status_code=auth_error.status_code,
            payload=auth_error.payload,
            headers=auth_error.headers,
        )

    class _StreamableHttpRuntimeAdapter:
        def handle_rpc_request(
            self,
            request: dict[str, Any],
        ) -> dict[str, Any] | None:
            return handle_mcp_rpc_request(runtime, request)

    endpoint = build_streamable_http_endpoint(
        _StreamableHttpRuntimeAdapter(),
        mcp_path=server.settings.http.path,
        auth_validator=_validate_auth,
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


__all__ = [
    "build_closed_projection_failures_http_handler",
    "build_http_auth_error_response",
    "build_mcp_http_handler",
    "build_projection_failures_ignore_http_handler",
    "build_projection_failures_resolve_http_handler",
    "build_runtime_introspection_http_handler",
    "build_runtime_routes_http_handler",
    "build_runtime_tools_http_handler",
    "build_workflow_resume_http_handler",
    "extract_bearer_token",
    "parse_closed_projection_failures_request_path",
    "parse_optional_projection_type_argument",
    "parse_required_uuid_argument",
    "parse_workflow_resume_request_path",
    "require_http_bearer_auth",
]

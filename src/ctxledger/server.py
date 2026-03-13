from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from .config import AppSettings
from .mcp.resource_handlers import (
    build_workflow_detail_resource_handler,
    build_workspace_resume_resource_handler,
    parse_workflow_detail_resource_uri,
    parse_workspace_resume_resource_uri,
)
from .mcp.tool_handlers import (
    build_mcp_error_response,
    build_mcp_success_response,
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
from .mcp.tool_schemas import (
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
from .memory.service import MemoryService
from .runtime.composite import CompositeRuntimeAdapter
from .runtime.database_health import (
    DefaultDatabaseHealthChecker,
    build_database_health_checker,
)
from .runtime.errors import ServerBootstrapError
from .runtime.http_handlers import (
    build_closed_projection_failures_http_handler as extracted_build_closed_projection_failures_http_handler,
)
from .runtime.http_handlers import (
    build_http_auth_error_response,
    extract_bearer_token,
    parse_optional_projection_type_argument,
    parse_required_uuid_argument,
    require_http_bearer_auth,
)
from .runtime.http_handlers import (
    build_mcp_http_handler as extracted_build_mcp_http_handler,
)
from .runtime.http_handlers import (
    build_projection_failures_ignore_http_handler as extracted_build_projection_failures_ignore_http_handler,
)
from .runtime.http_handlers import (
    build_projection_failures_resolve_http_handler as extracted_build_projection_failures_resolve_http_handler,
)
from .runtime.http_handlers import (
    build_runtime_introspection_http_handler as extracted_build_runtime_introspection_http_handler,
)
from .runtime.http_handlers import (
    build_runtime_routes_http_handler as extracted_build_runtime_routes_http_handler,
)
from .runtime.http_handlers import (
    build_runtime_tools_http_handler as extracted_build_runtime_tools_http_handler,
)
from .runtime.http_handlers import (
    build_workflow_resume_http_handler as extracted_build_workflow_resume_http_handler,
)
from .runtime.http_handlers import (
    parse_closed_projection_failures_request_path as extracted_parse_closed_projection_failures_request_path,
)
from .runtime.http_handlers import (
    parse_workflow_resume_request_path as extracted_parse_workflow_resume_request_path,
)
from .runtime.http_runtime import (
    build_http_runtime_adapter as extracted_build_http_runtime_adapter,
)
from .runtime.introspection import (
    RuntimeIntrospection,
    collect_runtime_introspection,
)
from .runtime.protocols import (
    DatabaseHealthChecker,
    HttpRuntimeAdapterProtocol,
    McpRuntimeProtocol,
    ServerRuntime,
    WorkflowServiceFactory,
)
from .runtime.serializers import (
    serialize_closed_projection_failures_history,
    serialize_stub_response,
    serialize_workflow_resume,
)
from .runtime.server_factory import (
    build_workflow_service_factory as extracted_build_workflow_service_factory,
)
from .runtime.server_factory import (
    create_server as extracted_create_server,
)
from .runtime.server_responses import (
    build_closed_projection_failures_response as extracted_build_closed_projection_failures_response,
)
from .runtime.server_responses import (
    build_projection_failures_ignore_response as extracted_build_projection_failures_ignore_response,
)
from .runtime.server_responses import (
    build_projection_failures_resolve_response as extracted_build_projection_failures_resolve_response,
)
from .runtime.server_responses import (
    build_runtime_introspection_response as extracted_build_runtime_introspection_response,
)
from .runtime.server_responses import (
    build_runtime_routes_response as extracted_build_runtime_routes_response,
)
from .runtime.server_responses import (
    build_runtime_tools_response as extracted_build_runtime_tools_response,
)
from .runtime.server_responses import (
    build_workflow_detail_resource_response as extracted_build_workflow_detail_resource_response,
)
from .runtime.server_responses import (
    build_workflow_resume_response as extracted_build_workflow_resume_response,
)
from .runtime.server_responses import (
    build_workspace_resume_resource_response as extracted_build_workspace_resume_resource_response,
)
from .runtime.status import (
    build_health_status,
    build_readiness_status,
)
from .runtime.types import (
    HealthStatus,
    McpHttpResponse,
    McpResourceResponse,
    McpToolResponse,
    ProjectionFailureActionResponse,
    ProjectionFailureHistoryResponse,
    ReadinessStatus,
    RuntimeDispatchResult,
    RuntimeIntrospectionResponse,
    WorkflowResumeResponse,
)
from .workflow.service import (
    ProjectionArtifactType,
    ResumeWorkflowInput,
    WorkflowResume,
    WorkflowService,
)

logger = logging.getLogger(__name__)

WorkflowHttpHandler = Any
McpToolHandler = Any
McpResourceHandler = Any
McpHttpHandler = Any


class HttpRuntimeAdapter:
    """
    Placeholder HTTP runtime adapter.

    This class establishes the lifecycle and logging contract for the future
    MCP Streamable HTTP implementation.
    """

    def __init__(
        self,
        settings: AppSettings,
        handlers: dict[str, WorkflowHttpHandler] | None = None,
    ) -> None:
        self.settings = settings
        self._started = False
        self._handlers: dict[str, WorkflowHttpHandler] = handlers or {}
        self._server: CtxLedgerServer | None = None

    def register_handler(self, route_name: str, handler: WorkflowHttpHandler) -> None:
        self._handlers[route_name] = handler

    def registered_routes(self) -> tuple[str, ...]:
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
            routes=self.registered_routes(),
            tools=self.registered_tools(),
            resources=self.registered_resources(),
        )

    def dispatch(
        self,
        route_name: str,
        path: str,
        body: str | None = None,
    ) -> WorkflowResumeResponse | McpHttpResponse:
        return dispatch_http_request(self, route_name, path, body).response

    def start(self) -> None:
        logger.info(
            "HTTP runtime adapter starting",
            extra={
                "transport": "http",
                "host": self.settings.http.host,
                "port": self.settings.http.port,
                "path": self.settings.http.path,
                "mcp_url": self.settings.http.mcp_url,
                "registered_routes": list(self.registered_routes()),
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
                "registered_routes": list(self.registered_routes()),
            },
        )
        self._started = False


class CtxLedgerServer:
    """
    Application bootstrap and operational status surface for ctxledger.

    Responsibilities:
    - validate startup configuration
    - initialize runtime dependencies
    - expose liveness and readiness checks
    - provide a lifecycle boundary for the HTTP runtime adapter
    """

    def __init__(
        self,
        settings: AppSettings,
        db_health_checker: DatabaseHealthChecker | None = None,
        runtime: ServerRuntime | None = None,
        workflow_service_factory: WorkflowServiceFactory | None = None,
    ) -> None:
        self.settings = settings
        self.db_health_checker = db_health_checker or build_database_health_checker(
            settings.database.url
        )
        self.runtime = runtime
        self.workflow_service_factory = workflow_service_factory
        self.workflow_service: WorkflowService | None = None
        self._started = False

    def get_workflow_resume(self, workflow_instance_id: UUID) -> WorkflowResume:
        if self.workflow_service is None:
            raise ServerBootstrapError("workflow service is not initialized")
        return self.workflow_service.resume_workflow(
            ResumeWorkflowInput(workflow_instance_id=workflow_instance_id)
        )

    def build_workflow_resume_response(
        self,
        workflow_instance_id: UUID,
    ) -> WorkflowResumeResponse:
        return extracted_build_workflow_resume_response(self, workflow_instance_id)

    def build_closed_projection_failures_response(
        self,
        workflow_instance_id: UUID,
    ) -> ProjectionFailureHistoryResponse:
        return extracted_build_closed_projection_failures_response(
            self,
            workflow_instance_id,
        )

    def build_projection_failures_ignore_response(
        self,
        *,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> ProjectionFailureActionResponse:
        return extracted_build_projection_failures_ignore_response(
            self,
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=projection_type,
        )

    def build_projection_failures_resolve_response(
        self,
        *,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> ProjectionFailureActionResponse:
        return extracted_build_projection_failures_resolve_response(
            self,
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=projection_type,
        )

    def build_runtime_introspection_response(self) -> RuntimeIntrospectionResponse:
        return extracted_build_runtime_introspection_response(self)

    def build_runtime_routes_response(self) -> RuntimeIntrospectionResponse:
        return extracted_build_runtime_routes_response(self)

    def build_runtime_tools_response(self) -> RuntimeIntrospectionResponse:
        return extracted_build_runtime_tools_response(self)

    def build_workspace_resume_resource_response(
        self,
        workspace_id: UUID,
    ) -> McpResourceResponse:
        return build_workspace_resume_resource_response(self, workspace_id)

    def build_workflow_detail_resource_response(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
    ) -> McpResourceResponse:
        return build_workflow_detail_resource_response(
            self,
            workspace_id,
            workflow_instance_id,
        )

    def validate_configuration(self) -> None:
        self.settings.validate()

    def configure_logging(self) -> None:
        level_name = self.settings.logging.level.value.upper()
        level = getattr(logging, level_name, logging.INFO)

        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            force=True,
        )

    def startup(self) -> None:
        self.configure_logging()
        logger.info(
            "ctxledger startup initiated",
            extra={
                "app_name": self.settings.app_name,
                "app_version": self.settings.app_version,
                "environment": self.settings.environment,
            },
        )

        self.validate_configuration()
        self.db_health_checker.ping()

        if not self.db_health_checker.schema_ready():
            raise ServerBootstrapError("database schema is not ready")

        if self.workflow_service_factory is not None:
            self.workflow_service = self.workflow_service_factory()

        if self.runtime is not None:
            self.runtime.start()

        self._started = True

        logger.info(
            "ctxledger startup complete",
            extra={
                "http_enabled": self.settings.http.enabled,
                "host": self.settings.http.host,
                "port": self.settings.http.port,
                "mcp_url": self.settings.http.mcp_url,
                "workflow_service_initialized": self.workflow_service is not None,
                "runtime": serialize_runtime_introspection_collection(
                    collect_runtime_introspection(self.runtime)
                ),
            },
        )

    def shutdown(self) -> None:
        logger.info("ctxledger shutdown initiated")

        if self.runtime is not None and self._started:
            self.runtime.stop()

        self.workflow_service = None
        self._started = False
        logger.info("ctxledger shutdown complete")

    def health(self) -> HealthStatus:
        return build_health_status(self)

    def readiness(self) -> ReadinessStatus:
        return build_readiness_status(self)


def _extract_bearer_token(path: str) -> str | None:
    return extract_bearer_token(path)


def _http_auth_error_response(message: str) -> WorkflowResumeResponse:
    return build_http_auth_error_response(message)


def _require_http_bearer_auth(
    server: CtxLedgerServer,
    path: str,
) -> WorkflowResumeResponse | None:
    return require_http_bearer_auth(server, path)


def dispatch_http_request(
    runtime: HttpRuntimeAdapter,
    route_name: str,
    path: str,
    body: str | None = None,
) -> RuntimeDispatchResult:
    handler = runtime._handlers.get(route_name)
    if handler is None:
        response = WorkflowResumeResponse(
            status_code=404,
            payload={
                "error": {
                    "code": "route_not_found",
                    "message": f"no HTTP handler is registered for route '{route_name}'",
                }
            },
            headers={"content-type": "application/json"},
        )
        return RuntimeDispatchResult(
            transport="http",
            target=route_name,
            status="route_not_found",
            response=response,
        )

    if route_name == "mcp_rpc":
        response = handler(path, body)
    else:
        response = handler(path)
    return RuntimeDispatchResult(
        transport="http",
        target=route_name,
        status="ok" if response.status_code < 400 else "error",
        response=response,
    )


def build_workflow_resume_response(
    server: CtxLedgerServer,
    workflow_instance_id: UUID,
) -> WorkflowResumeResponse:
    return extracted_build_workflow_resume_response(server, workflow_instance_id)


def build_closed_projection_failures_response(
    server: CtxLedgerServer,
    workflow_instance_id: UUID,
) -> ProjectionFailureHistoryResponse:
    return extracted_build_closed_projection_failures_response(
        server,
        workflow_instance_id,
    )


def build_projection_failures_ignore_response(
    server: CtxLedgerServer,
    *,
    workspace_id: UUID,
    workflow_instance_id: UUID,
    projection_type: ProjectionArtifactType | None = None,
) -> ProjectionFailureActionResponse:
    return extracted_build_projection_failures_ignore_response(
        server,
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=projection_type,
    )


def build_projection_failures_resolve_response(
    server: CtxLedgerServer,
    *,
    workspace_id: UUID,
    workflow_instance_id: UUID,
    projection_type: ProjectionArtifactType | None = None,
) -> ProjectionFailureActionResponse:
    return extracted_build_projection_failures_resolve_response(
        server,
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=projection_type,
    )


def build_runtime_introspection_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    return extracted_build_runtime_introspection_response(server)


def build_runtime_routes_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    return extracted_build_runtime_routes_response(server)


def build_runtime_tools_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    return extracted_build_runtime_tools_response(server)


def build_workspace_resume_resource_response(
    server: CtxLedgerServer,
    workspace_id: UUID,
) -> McpResourceResponse:
    return extracted_build_workspace_resume_resource_response(server, workspace_id)


def build_workflow_detail_resource_response(
    server: CtxLedgerServer,
    workspace_id: UUID,
    workflow_instance_id: UUID,
) -> McpResourceResponse:
    return extracted_build_workflow_detail_resource_response(
        server,
        workspace_id,
        workflow_instance_id,
    )


def _parse_required_uuid_argument(
    arguments: dict[str, Any],
    field_name: str,
) -> UUID | McpToolResponse:
    return parse_required_uuid_argument(arguments, field_name)


def _parse_optional_projection_type_argument(
    arguments: dict[str, Any],
) -> ProjectionArtifactType | None | McpToolResponse:
    return parse_optional_projection_type_argument(arguments)


def parse_workflow_resume_request_path(path: str) -> UUID | None:
    return extracted_parse_workflow_resume_request_path(path)


def build_workflow_resume_http_handler(
    server: CtxLedgerServer,
):
    return extracted_build_workflow_resume_http_handler(server)


def parse_closed_projection_failures_request_path(path: str) -> UUID | None:
    return extracted_parse_closed_projection_failures_request_path(path)


def build_closed_projection_failures_http_handler(
    server: CtxLedgerServer,
):
    return extracted_build_closed_projection_failures_http_handler(server)


def build_projection_failures_ignore_http_handler(
    server: CtxLedgerServer,
):
    return extracted_build_projection_failures_ignore_http_handler(server)


def build_projection_failures_resolve_http_handler(
    server: CtxLedgerServer,
):
    return extracted_build_projection_failures_resolve_http_handler(server)


def build_runtime_introspection_http_handler(
    server: CtxLedgerServer,
):
    return extracted_build_runtime_introspection_http_handler(server)


def build_runtime_routes_http_handler(
    server: CtxLedgerServer,
):
    return extracted_build_runtime_routes_http_handler(server)


def build_runtime_tools_http_handler(
    server: CtxLedgerServer,
):
    return extracted_build_runtime_tools_http_handler(server)


def build_mcp_http_handler(
    runtime: McpRuntimeProtocol,
    server: CtxLedgerServer,
):
    return extracted_build_mcp_http_handler(runtime, server)


def build_http_runtime_adapter(server: CtxLedgerServer) -> HttpRuntimeAdapter:
    runtime = extracted_build_http_runtime_adapter(server)
    runtime._server = server
    return runtime


def build_workflow_service_factory(
    settings: AppSettings,
) -> WorkflowServiceFactory | None:
    return extracted_build_workflow_service_factory(settings)


def create_runtime(
    settings: AppSettings,
    server: CtxLedgerServer | None = None,
) -> ServerRuntime | None:
    if not settings.http.enabled:
        return None

    if server is not None:
        return build_http_runtime_adapter(server)

    return HttpRuntimeAdapter(settings)


def _print_runtime_summary(server: CtxLedgerServer) -> None:
    from .runtime.orchestration import print_runtime_summary

    print_runtime_summary(server)


def create_server(
    settings: AppSettings,
    db_health_checker: DatabaseHealthChecker | None = None,
    runtime: ServerRuntime | None = None,
    workflow_service_factory: WorkflowServiceFactory | None = None,
) -> CtxLedgerServer:
    return extracted_create_server(
        settings,
        server_class=CtxLedgerServer,
        create_runtime=create_runtime,
        build_database_health_checker=build_database_health_checker,
        db_health_checker=db_health_checker,
        runtime=runtime,
        workflow_service_factory=workflow_service_factory,
    )


def run_server(
    *,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> int:
    from .runtime.orchestration import run_server as extracted_run_server

    return extracted_run_server(
        transport=transport,
        host=host,
        port=port,
    )


__all__ = [
    "CompositeRuntimeAdapter",
    "CtxLedgerServer",
    "DatabaseHealthChecker",
    "DefaultDatabaseHealthChecker",
    "HealthStatus",
    "HttpRuntimeAdapter",
    "HttpRuntimeAdapterProtocol",
    "McpToolResponse",
    "ProjectionFailureHistoryResponse",
    "ReadinessStatus",
    "RuntimeDispatchResult",
    "RuntimeIntrospection",
    "RuntimeIntrospectionResponse",
    "ServerBootstrapError",
    "ServerRuntime",
    "WorkflowResumeResponse",
    "WorkflowServiceFactory",
    "build_closed_projection_failures_http_handler",
    "build_closed_projection_failures_response",
    "build_http_runtime_adapter",
    "build_mcp_error_response",
    "build_mcp_success_response",
    "build_projection_failures_ignore_http_handler",
    "build_projection_failures_ignore_response",
    "build_projection_failures_resolve_http_handler",
    "build_projection_failures_resolve_response",
    "build_memory_get_context_tool_handler",
    "build_runtime_introspection_http_handler",
    "build_runtime_introspection_response",
    "build_runtime_routes_http_handler",
    "build_runtime_routes_response",
    "build_runtime_tools_http_handler",
    "build_runtime_tools_response",
    "build_memory_remember_episode_tool_handler",
    "build_memory_search_tool_handler",
    "build_projection_failures_ignore_tool_handler",
    "build_projection_failures_resolve_tool_handler",
    "build_resume_workflow_tool_handler",
    "build_workspace_resume_resource_handler",
    "build_workspace_resume_resource_response",
    "build_workflow_detail_resource_handler",
    "build_workflow_detail_resource_response",
    "build_workspace_register_tool_handler",
    "build_workflow_checkpoint_tool_handler",
    "build_workflow_complete_tool_handler",
    "build_workflow_start_tool_handler",
    "collect_runtime_introspection",
    "_print_runtime_summary",
    "build_workflow_resume_http_handler",
    "build_workflow_resume_response",
    "build_workflow_service_factory",
    "create_runtime",
    "create_server",
    "dispatch_http_request",
    "parse_closed_projection_failures_request_path",
    "parse_workspace_resume_resource_uri",
    "parse_workflow_detail_resource_uri",
    "parse_workflow_resume_request_path",
    "run_server",
    "serialize_closed_projection_failures_history",
    "serialize_runtime_introspection",
    "serialize_runtime_introspection_collection",
    "serialize_stub_response",
    "serialize_workflow_resume",
]


def serialize_runtime_introspection(introspection: RuntimeIntrospection):
    from .runtime.serializers import serialize_runtime_introspection as extracted

    return extracted(introspection)


def serialize_runtime_introspection_collection(
    introspections: tuple[RuntimeIntrospection, ...],
):
    from .runtime.serializers import (
        serialize_runtime_introspection_collection as extracted,
    )

    return extracted(introspections)

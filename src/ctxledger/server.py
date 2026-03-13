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
    build_http_auth_error_response,
    extract_bearer_token,
    parse_optional_projection_type_argument,
    parse_required_uuid_argument,
    require_http_bearer_auth,
)
from .runtime.http_runtime import (
    HttpRuntimeAdapter,
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
    serialize_runtime_introspection_collection,
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
    build_workflow_resume_response as extracted_build_workflow_resume_response,
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
        from .runtime.server_responses import (
            build_workspace_resume_resource_response,
        )

        return build_workspace_resume_resource_response(self, workspace_id)

    def build_workflow_detail_resource_response(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
    ) -> McpResourceResponse:
        from .runtime.server_responses import (
            build_workflow_detail_resource_response,
        )

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


def build_http_runtime_adapter(server: CtxLedgerServer) -> HttpRuntimeAdapter:
    return extracted_build_http_runtime_adapter(server)


def build_workflow_service_factory(
    settings: AppSettings,
) -> WorkflowServiceFactory | None:
    return extracted_build_workflow_service_factory(settings)


def create_runtime(
    settings: AppSettings,
    server: CtxLedgerServer | None = None,
) -> ServerRuntime | None:
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
    "RuntimeIntrospection",
    "RuntimeIntrospectionResponse",
    "ServerBootstrapError",
    "ServerRuntime",
    "WorkflowResumeResponse",
    "WorkflowServiceFactory",
    "build_http_runtime_adapter",
    "build_mcp_error_response",
    "build_mcp_success_response",
    "build_memory_get_context_tool_handler",
    "build_memory_remember_episode_tool_handler",
    "build_memory_search_tool_handler",
    "build_projection_failures_ignore_tool_handler",
    "build_projection_failures_resolve_tool_handler",
    "build_resume_workflow_tool_handler",
    "build_workspace_resume_resource_handler",
    "build_workflow_detail_resource_handler",
    "build_workspace_register_tool_handler",
    "build_workflow_checkpoint_tool_handler",
    "build_workflow_complete_tool_handler",
    "build_workflow_start_tool_handler",
    "collect_runtime_introspection",
    "_print_runtime_summary",
    "build_workflow_service_factory",
    "create_runtime",
    "create_server",
    "parse_workspace_resume_resource_uri",
    "parse_workflow_detail_resource_uri",
    "run_server",
    "serialize_closed_projection_failures_history",
    "serialize_stub_response",
    "serialize_workflow_resume",
]

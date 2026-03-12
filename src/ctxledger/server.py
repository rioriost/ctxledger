from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from .config import AppSettings
from .memory.service import StubResponse
from .workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    ProjectionArtifactType,
    RegisterWorkspaceInput,
    ResumeWorkflowInput,
    StartWorkflowInput,
    VerifyStatus,
    WorkflowError,
    WorkflowInstanceStatus,
    WorkflowResume,
    WorkflowService,
)

logger = logging.getLogger(__name__)


class SettingsProtocol(Protocol):
    database_url: str | None
    host: str
    port: int
    enable_http: bool
    enable_stdio: bool
    auth_bearer_token: str | None
    log_level: str


class DatabaseHealthChecker(Protocol):
    def ping(self) -> None: ...
    def schema_ready(self) -> bool: ...


class ServerRuntime(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


class WorkflowServiceFactory(Protocol):
    def __call__(self) -> WorkflowService: ...


@dataclass(slots=True)
class HealthStatus:
    ok: bool
    status: str
    details: dict[str, Any]


@dataclass(slots=True)
class ReadinessStatus:
    ready: bool
    status: str
    details: dict[str, Any]


@dataclass(slots=True)
class WorkflowResumeResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass(slots=True)
class ProjectionFailureHistoryResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass(slots=True)
class ProjectionFailureActionResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass(slots=True)
class RuntimeIntrospectionResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass(slots=True)
class McpResourceResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass(slots=True)
class McpToolResponse:
    payload: dict[str, Any]


@dataclass(slots=True)
class RuntimeDispatchResult:
    transport: str
    target: str
    status: str
    response: WorkflowResumeResponse | McpToolResponse | McpResourceResponse


class McpRuntimeProtocol(Protocol):
    settings: AppSettings

    def registered_tools(self) -> tuple[str, ...]: ...
    def registered_resources(self) -> tuple[str, ...]: ...
    def tool_schema(self, tool_name: str) -> McpToolSchema: ...
    def dispatch_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> McpToolResponse: ...
    def dispatch_resource(self, uri: str) -> McpResourceResponse: ...


from .mcp.lifecycle import McpLifecycleState
from .mcp.resource_handlers import (
    build_workflow_detail_resource_handler,
    build_workflow_detail_resource_response,
    build_workspace_resume_resource_handler,
    build_workspace_resume_resource_response,
    parse_workflow_detail_resource_uri,
    parse_workspace_resume_resource_uri,
)
from .mcp.stdio import (
    StdioRpcServer,
    StdioRuntimeAdapter,
    dispatch_mcp_resource,
    dispatch_mcp_tool,
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
    serialize_mcp_tool_schema,
)
from .runtime.composite import CompositeRuntimeAdapter
from .runtime.database_health import (
    DefaultDatabaseHealthChecker,
    PostgresDatabaseHealthChecker,
    build_database_health_checker,
)
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
from .runtime.introspection import (
    RuntimeIntrospection,
    collect_runtime_introspection,
    serialize_runtime_introspection,
    serialize_runtime_introspection_collection,
)
from .runtime.orchestration import (
    build_stdio_runtime_adapter,
    run_server,
)
from .runtime.orchestration import (
    create_runtime as create_runtime_orchestration,
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

WorkflowHttpHandler = Any
McpToolHandler = Any
McpResourceHandler = Any
McpHttpHandler = Any


@dataclass(slots=True)
class McpHttpResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


class ServerBootstrapError(RuntimeError):
    pass


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

    def register_handler(self, route_name: str, handler: WorkflowHttpHandler) -> None:
        self._handlers[route_name] = handler

    def registered_routes(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers.keys()))

    def introspect(self) -> RuntimeIntrospection:
        return RuntimeIntrospection(
            transport="http",
            routes=self.registered_routes(),
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
    - provide a lifecycle boundary for HTTP/stdio adapters
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
        return extracted_build_workspace_resume_resource_response(self, workspace_id)

    def build_workflow_detail_resource_response(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
    ) -> McpResourceResponse:
        return extracted_build_workflow_detail_resource_response(
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
                "stdio_enabled": self.settings.stdio.enabled,
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
        runtime_introspection = collect_runtime_introspection(self.runtime)
        return HealthStatus(
            ok=True,
            status="ok",
            details={
                "service": self.settings.app_name,
                "version": self.settings.app_version,
                "started": self._started,
                "workflow_service_initialized": self.workflow_service is not None,
                "runtime": serialize_runtime_introspection_collection(
                    runtime_introspection
                ),
            },
        )

    def readiness(self) -> ReadinessStatus:
        runtime_introspection = collect_runtime_introspection(self.runtime)
        details: dict[str, Any] = {
            "service": self.settings.app_name,
            "version": self.settings.app_version,
            "started": self._started,
            "database_configured": bool(self.settings.database.url),
            "http_enabled": self.settings.http.enabled,
            "stdio_enabled": self.settings.stdio.enabled,
            "workflow_service_initialized": self.workflow_service is not None,
            "runtime": serialize_runtime_introspection_collection(
                runtime_introspection
            ),
        }

        if not self._started:
            return ReadinessStatus(
                ready=False,
                status="not_started",
                details=details,
            )

        try:
            self.db_health_checker.ping()
            details["database_reachable"] = True
        except Exception as exc:
            details["database_reachable"] = False
            details["error"] = str(exc)
            return ReadinessStatus(
                ready=False,
                status="database_unavailable",
                details=details,
            )

        try:
            schema_ready = self.db_health_checker.schema_ready()
            details["schema_ready"] = schema_ready
        except Exception as exc:
            details["schema_ready"] = False
            details["error"] = str(exc)
            return ReadinessStatus(
                ready=False,
                status="schema_check_failed",
                details=details,
            )

        if not details["schema_ready"]:
            return ReadinessStatus(
                ready=False,
                status="schema_not_ready",
                details=details,
            )

        return ReadinessStatus(
            ready=True,
            status="ready",
            details=details,
        )


def serialize_workflow_resume(resume: WorkflowResume) -> dict[str, Any]:
    return {
        "workspace": {
            "workspace_id": str(resume.workspace.workspace_id),
            "repo_url": resume.workspace.repo_url,
            "canonical_path": resume.workspace.canonical_path,
            "default_branch": resume.workspace.default_branch,
            "metadata": resume.workspace.metadata,
        },
        "workflow": {
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "workspace_id": str(resume.workflow_instance.workspace_id),
            "ticket_id": resume.workflow_instance.ticket_id,
            "status": resume.workflow_instance.status.value,
            "metadata": resume.workflow_instance.metadata,
        },
        "attempt": (
            {
                "attempt_id": str(resume.attempt.attempt_id),
                "workflow_instance_id": str(resume.attempt.workflow_instance_id),
                "attempt_number": resume.attempt.attempt_number,
                "status": resume.attempt.status.value,
                "failure_reason": resume.attempt.failure_reason,
                "verify_status": (
                    resume.attempt.verify_status.value
                    if resume.attempt.verify_status is not None
                    else None
                ),
                "started_at": resume.attempt.started_at.isoformat(),
                "finished_at": (
                    resume.attempt.finished_at.isoformat()
                    if resume.attempt.finished_at is not None
                    else None
                ),
            }
            if resume.attempt is not None
            else None
        ),
        "latest_checkpoint": (
            {
                "checkpoint_id": str(resume.latest_checkpoint.checkpoint_id),
                "workflow_instance_id": str(
                    resume.latest_checkpoint.workflow_instance_id
                ),
                "attempt_id": str(resume.latest_checkpoint.attempt_id),
                "step_name": resume.latest_checkpoint.step_name,
                "summary": resume.latest_checkpoint.summary,
                "checkpoint_json": resume.latest_checkpoint.checkpoint_json,
                "created_at": resume.latest_checkpoint.created_at.isoformat(),
            }
            if resume.latest_checkpoint is not None
            else None
        ),
        "latest_verify_report": (
            {
                "verify_id": str(resume.latest_verify_report.verify_id),
                "attempt_id": str(resume.latest_verify_report.attempt_id),
                "status": resume.latest_verify_report.status.value,
                "report_json": resume.latest_verify_report.report_json,
                "created_at": resume.latest_verify_report.created_at.isoformat(),
            }
            if resume.latest_verify_report is not None
            else None
        ),
        "projections": [
            {
                "projection_type": projection.projection_type.value,
                "status": projection.status.value,
                "target_path": projection.target_path,
                "last_successful_write_at": (
                    projection.last_successful_write_at.isoformat()
                    if projection.last_successful_write_at is not None
                    else None
                ),
                "last_canonical_update_at": (
                    projection.last_canonical_update_at.isoformat()
                    if projection.last_canonical_update_at is not None
                    else None
                ),
                "open_failure_count": projection.open_failure_count,
            }
            for projection in resume.projections
        ],
        "resumable_status": resume.resumable_status.value,
        "next_hint": resume.next_hint,
        "warnings": [
            {
                "code": warning.code,
                "message": warning.message,
                "details": warning.details,
            }
            for warning in resume.warnings
        ],
        "closed_projection_failures": [
            {
                "projection_type": failure.projection_type.value,
                "target_path": failure.target_path,
                "attempt_id": (
                    str(failure.attempt_id) if failure.attempt_id is not None else None
                ),
                "error_code": failure.error_code,
                "error_message": failure.error_message,
                "occurred_at": (
                    failure.occurred_at.isoformat()
                    if failure.occurred_at is not None
                    else None
                ),
                "resolved_at": (
                    failure.resolved_at.isoformat()
                    if failure.resolved_at is not None
                    else None
                ),
                "open_failure_count": failure.open_failure_count,
                "retry_count": failure.retry_count,
                "status": failure.status,
            }
            for failure in getattr(resume, "closed_projection_failures", ())
        ],
    }


def serialize_closed_projection_failures_history(
    workflow_instance_id: UUID,
    closed_projection_failures: tuple[Any, ...] | list[Any],
) -> dict[str, Any]:
    return {
        "workflow_instance_id": str(workflow_instance_id),
        "closed_projection_failures": [
            {
                "projection_type": failure.projection_type.value,
                "target_path": failure.target_path,
                "attempt_id": (
                    str(failure.attempt_id) if failure.attempt_id is not None else None
                ),
                "error_code": failure.error_code,
                "error_message": failure.error_message,
                "occurred_at": (
                    failure.occurred_at.isoformat()
                    if failure.occurred_at is not None
                    else None
                ),
                "resolved_at": (
                    failure.resolved_at.isoformat()
                    if failure.resolved_at is not None
                    else None
                ),
                "open_failure_count": failure.open_failure_count,
                "retry_count": failure.retry_count,
                "status": failure.status,
            }
            for failure in closed_projection_failures
        ],
    }


def serialize_stub_response(response: StubResponse) -> dict[str, Any]:
    return {
        "feature": response.feature.value,
        "implemented": response.implemented,
        "message": response.message,
        "status": response.status,
        "available_in_version": response.available_in_version,
        "timestamp": response.timestamp.isoformat(),
        "details": response.details,
    }


def serialize_runtime_introspection(
    introspection: RuntimeIntrospection,
) -> dict[str, Any]:
    return {
        "transport": introspection.transport,
        "routes": list(introspection.routes),
        "tools": list(introspection.tools),
        "resources": list(introspection.resources),
    }


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
    return server.build_workflow_resume_response(workflow_instance_id)


def build_closed_projection_failures_response(
    server: CtxLedgerServer,
    workflow_instance_id: UUID,
) -> ProjectionFailureHistoryResponse:
    return server.build_closed_projection_failures_response(workflow_instance_id)


def build_projection_failures_ignore_response(
    server: CtxLedgerServer,
    *,
    workspace_id: UUID,
    workflow_instance_id: UUID,
    projection_type: ProjectionArtifactType | None = None,
) -> ProjectionFailureActionResponse:
    return server.build_projection_failures_ignore_response(
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
    return server.build_projection_failures_resolve_response(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=projection_type,
    )


def build_runtime_introspection_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    return server.build_runtime_introspection_response()


def build_runtime_routes_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    return server.build_runtime_routes_response()


def build_runtime_tools_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    return server.build_runtime_tools_response()


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
    from .runtime.http_runtime import (
        build_http_runtime_adapter as _build_http_runtime_adapter,
    )

    return _build_http_runtime_adapter(server)


def build_workflow_service_factory(
    settings: AppSettings,
) -> WorkflowServiceFactory | None:
    return extracted_build_workflow_service_factory(settings)


def create_runtime(
    settings: AppSettings,
    server: CtxLedgerServer | None = None,
) -> ServerRuntime | None:
    if server is None:
        return create_runtime_orchestration(
            settings,
            server,
            http_runtime_builder=lambda _: HttpRuntimeAdapter(settings),
        )
    return create_runtime_orchestration(
        settings,
        server,
        http_runtime_builder=build_http_runtime_adapter,
    )


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


__all__ = [
    "CompositeRuntimeAdapter",
    "CtxLedgerServer",
    "DatabaseHealthChecker",
    "DefaultDatabaseHealthChecker",
    "HealthStatus",
    "HttpRuntimeAdapter",
    "McpToolResponse",
    "ProjectionFailureHistoryResponse",
    "ReadinessStatus",
    "RuntimeDispatchResult",
    "RuntimeIntrospection",
    "RuntimeIntrospectionResponse",
    "ServerBootstrapError",
    "ServerRuntime",
    "StdioRpcServer",
    "StdioRuntimeAdapter",
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
    "build_stdio_runtime_adapter",
    "collect_runtime_introspection",
    "_print_runtime_summary",
    "build_workflow_resume_http_handler",
    "build_workflow_resume_response",
    "build_workflow_service_factory",
    "create_runtime",
    "create_server",
    "dispatch_http_request",
    "dispatch_mcp_resource",
    "dispatch_mcp_tool",
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

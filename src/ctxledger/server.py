from __future__ import annotations

import json
import logging
import signal
import sys
from dataclasses import dataclass
from types import FrameType
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from .config import AppSettings, TransportMode, get_settings
from .db.postgres import PostgresConfig, build_postgres_uow_factory
from .memory.service import MemoryService, StubResponse
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
from .mcp.rpc import handle_mcp_rpc_request
from .mcp.stdio import (
    StdioRpcServer,
    StdioRuntimeAdapter,
    build_stdio_runtime,
    dispatch_mcp_resource,
    dispatch_mcp_tool,
    find_stdio_runtime,
    run_stdio_runtime_if_present,
)
from .mcp.stdio import (
    build_stdio_runtime_adapter as build_extracted_stdio_runtime_adapter,
)
from .mcp.streamable_http import (
    StreamableHttpRequest,
    StreamableHttpResponse,
    build_streamable_http_endpoint,
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


@dataclass(slots=True)
class RuntimeIntrospection:
    transport: str
    routes: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()


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


class DefaultDatabaseHealthChecker:
    """
    Lightweight placeholder health checker.

    This implementation intentionally avoids a hard dependency on a specific
    PostgreSQL driver in the initial runtime bootstrap. It validates that a DB
    URL is configured and treats schema readiness as a deploy-time guarantee.

    When a PostgreSQL driver is available, use `build_database_health_checker()`
    to get a real health checker instead of instantiating this class directly.
    """

    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url

    def ping(self) -> None:
        if not self._database_url:
            raise ServerBootstrapError("database_url is not configured")

    def schema_ready(self) -> bool:
        return bool(self._database_url)


class PostgresDatabaseHealthChecker:
    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url

    def _connect_timeout_seconds(self) -> int:
        if not self._database_url:
            return 5

        parsed = urlparse(self._database_url)
        query = parse_qs(parsed.query)
        raw_timeout = query.get("connect_timeout", [None])[0]
        if raw_timeout is None:
            return 5

        try:
            timeout = int(raw_timeout)
        except ValueError:
            return 5

        return timeout if timeout > 0 else 5

    def _connect(self) -> Any:
        if not self._database_url:
            raise ServerBootstrapError("database_url is not configured")

        try:
            import psycopg
        except ImportError as exc:
            raise ServerBootstrapError(
                "PostgreSQL health checker requires psycopg to be installed"
            ) from exc

        return psycopg.connect(
            self._database_url,
            connect_timeout=self._connect_timeout_seconds(),
        )

    def ping(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

    def schema_ready(self) -> bool:
        required_tables = (
            "workspaces",
            "workflow_instances",
            "workflow_attempts",
            "workflow_checkpoints",
            "verify_reports",
            "projection_states",
        )

        query = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = %s
        )
        """

        with self._connect() as connection:
            with connection.cursor() as cursor:
                for table_name in required_tables:
                    cursor.execute(query, (table_name,))
                    row = cursor.fetchone()
                    if row is None or row[0] is not True:
                        return False

        return True


def build_database_health_checker(database_url: str | None) -> DatabaseHealthChecker:
    if not database_url:
        return DefaultDatabaseHealthChecker(database_url)

    try:
        import psycopg  # noqa: F401
    except ImportError:
        return DefaultDatabaseHealthChecker(database_url)

    return PostgresDatabaseHealthChecker(database_url)


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


class CompositeRuntimeAdapter:
    """
    Aggregates multiple runtime adapters behind a single lifecycle boundary.
    """

    def __init__(self, runtimes: list[ServerRuntime]) -> None:
        self._runtimes = runtimes
        self._started = False

    def start(self) -> None:
        started: list[ServerRuntime] = []
        try:
            for runtime in self._runtimes:
                runtime.start()
                started.append(runtime)
            self._started = True
        except Exception:
            for runtime in reversed(started):
                try:
                    runtime.stop()
                except Exception:
                    logger.exception("Failed to stop partially started runtime")
            raise

    def stop(self) -> None:
        if not self._started:
            return

        for runtime in reversed(self._runtimes):
            try:
                runtime.stop()
            except Exception:
                logger.exception("Runtime shutdown failed")

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
        try:
            resume = self.get_workflow_resume(workflow_instance_id)
        except ServerBootstrapError as exc:
            return WorkflowResumeResponse(
                status_code=503,
                payload={
                    "error": {
                        "code": "server_not_ready",
                        "message": str(exc),
                    }
                },
                headers={"content-type": "application/json"},
            )

        return WorkflowResumeResponse(
            status_code=200,
            payload=serialize_workflow_resume(resume),
            headers={"content-type": "application/json"},
        )

    def build_closed_projection_failures_response(
        self,
        workflow_instance_id: UUID,
    ) -> ProjectionFailureHistoryResponse:
        try:
            resume = self.get_workflow_resume(workflow_instance_id)
        except ServerBootstrapError as exc:
            return ProjectionFailureHistoryResponse(
                status_code=503,
                payload={
                    "error": {
                        "code": "server_not_ready",
                        "message": str(exc),
                    }
                },
                headers={"content-type": "application/json"},
            )

        return ProjectionFailureHistoryResponse(
            status_code=200,
            payload=serialize_closed_projection_failures_history(
                workflow_instance_id,
                getattr(resume, "closed_projection_failures", ()),
            ),
            headers={"content-type": "application/json"},
        )

    def build_projection_failures_ignore_response(
        self,
        *,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> ProjectionFailureActionResponse:
        if self.workflow_service is None:
            return ProjectionFailureActionResponse(
                status_code=503,
                payload={
                    "error": {
                        "code": "server_not_ready",
                        "message": "workflow service is not initialized",
                    }
                },
                headers={"content-type": "application/json"},
            )

        try:
            updated_failure_count = (
                self.workflow_service.ignore_resume_projection_failures(
                    workspace_id=workspace_id,
                    workflow_instance_id=workflow_instance_id,
                    projection_type=projection_type,
                )
            )
        except Exception as exc:
            message = str(exc) or "failed to ignore projection failures"
            lowered = message.lower()
            if "not found" in lowered:
                status_code = 404
                code = "not_found"
            elif "does not belong to workspace" in lowered or "mismatch" in lowered:
                status_code = 400
                code = "invalid_request"
            else:
                status_code = 500
                code = "server_error"
            return ProjectionFailureActionResponse(
                status_code=status_code,
                payload={
                    "error": {
                        "code": code,
                        "message": message,
                    }
                },
                headers={"content-type": "application/json"},
            )

        return ProjectionFailureActionResponse(
            status_code=200,
            payload={
                "workspace_id": str(workspace_id),
                "workflow_instance_id": str(workflow_instance_id),
                "projection_type": (
                    projection_type.value if projection_type is not None else None
                ),
                "updated_failure_count": updated_failure_count,
                "status": "ignored",
            },
            headers={"content-type": "application/json"},
        )

    def build_projection_failures_resolve_response(
        self,
        *,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> ProjectionFailureActionResponse:
        if self.workflow_service is None:
            return ProjectionFailureActionResponse(
                status_code=503,
                payload={
                    "error": {
                        "code": "server_not_ready",
                        "message": "workflow service is not initialized",
                    }
                },
                headers={"content-type": "application/json"},
            )

        try:
            updated_failure_count = (
                self.workflow_service.resolve_resume_projection_failures(
                    workspace_id=workspace_id,
                    workflow_instance_id=workflow_instance_id,
                    projection_type=projection_type,
                )
            )
        except Exception as exc:
            message = str(exc) or "failed to resolve projection failures"
            lowered = message.lower()
            if "not found" in lowered:
                status_code = 404
                code = "not_found"
            elif "does not belong to workspace" in lowered or "mismatch" in lowered:
                status_code = 400
                code = "invalid_request"
            else:
                status_code = 500
                code = "server_error"
            return ProjectionFailureActionResponse(
                status_code=status_code,
                payload={
                    "error": {
                        "code": code,
                        "message": message,
                    }
                },
                headers={"content-type": "application/json"},
            )

        return ProjectionFailureActionResponse(
            status_code=200,
            payload={
                "workspace_id": str(workspace_id),
                "workflow_instance_id": str(workflow_instance_id),
                "projection_type": (
                    projection_type.value if projection_type is not None else None
                ),
                "updated_failure_count": updated_failure_count,
                "status": "resolved",
            },
            headers={"content-type": "application/json"},
        )

    def build_runtime_introspection_response(self) -> RuntimeIntrospectionResponse:
        introspections = collect_runtime_introspection(self.runtime)
        return RuntimeIntrospectionResponse(
            status_code=200,
            payload={
                "runtime": serialize_runtime_introspection_collection(introspections),
            },
            headers={"content-type": "application/json"},
        )

    def build_runtime_routes_response(self) -> RuntimeIntrospectionResponse:
        introspections = collect_runtime_introspection(self.runtime)
        return RuntimeIntrospectionResponse(
            status_code=200,
            payload={
                "routes": [
                    {
                        "transport": introspection.transport,
                        "routes": list(introspection.routes),
                    }
                    for introspection in introspections
                    if introspection.routes
                ],
            },
            headers={"content-type": "application/json"},
        )

    def build_runtime_tools_response(self) -> RuntimeIntrospectionResponse:
        introspections = collect_runtime_introspection(self.runtime)
        return RuntimeIntrospectionResponse(
            status_code=200,
            payload={
                "tools": [
                    {
                        "transport": introspection.transport,
                        "tools": list(introspection.tools),
                    }
                    for introspection in introspections
                    if introspection.tools
                ],
            },
            headers={"content-type": "application/json"},
        )

    def build_workspace_resume_resource_response(
        self,
        workspace_id: UUID,
    ) -> McpResourceResponse:
        if self.workflow_service is None:
            return McpResourceResponse(
                status_code=503,
                payload={
                    "error": {
                        "code": "server_not_ready",
                        "message": "workflow service is not initialized",
                    }
                },
                headers={"content-type": "application/json"},
            )

        if hasattr(self.workflow_service, "_uow_factory"):
            with self.workflow_service._uow_factory() as uow:
                workspace = uow.workspaces.get_by_id(workspace_id)
                if workspace is None:
                    return McpResourceResponse(
                        status_code=404,
                        payload={
                            "error": {
                                "code": "not_found",
                                "message": f"workspace '{workspace_id}' was not found",
                            }
                        },
                        headers={"content-type": "application/json"},
                    )

                running_workflow = uow.workflow_instances.get_running_by_workspace_id(
                    workspace_id
                )
                selected_workflow = running_workflow
                if selected_workflow is None:
                    selected_workflow = (
                        uow.workflow_instances.get_latest_by_workspace_id(workspace_id)
                    )

            if selected_workflow is None:
                return McpResourceResponse(
                    status_code=404,
                    payload={
                        "error": {
                            "code": "not_found",
                            "message": (
                                f"no workflow is available for workspace '{workspace_id}'"
                            ),
                        }
                    },
                    headers={"content-type": "application/json"},
                )

            workflow_response = self.build_workflow_resume_response(
                selected_workflow.workflow_instance_id
            )
        else:
            workflow_response = self.build_workflow_resume_response(
                getattr(self.workflow_service.resume_result.workspace, "workspace_id")
            )
            if workflow_response.status_code == 200:
                response_workspace_id = workflow_response.payload.get(
                    "workspace", {}
                ).get("workspace_id")
                if response_workspace_id != str(workspace_id):
                    return McpResourceResponse(
                        status_code=404,
                        payload={
                            "error": {
                                "code": "not_found",
                                "message": f"workspace '{workspace_id}' was not found",
                            }
                        },
                        headers={"content-type": "application/json"},
                    )
        if workflow_response.status_code != 200:
            return McpResourceResponse(
                status_code=workflow_response.status_code,
                payload=workflow_response.payload,
                headers=workflow_response.headers,
            )

        return McpResourceResponse(
            status_code=200,
            payload={
                "uri": f"workspace://{workspace_id}/resume",
                "resource": workflow_response.payload,
            },
            headers={"content-type": "application/json"},
        )

    def build_workflow_detail_resource_response(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
    ) -> McpResourceResponse:
        if self.workflow_service is None:
            return McpResourceResponse(
                status_code=503,
                payload={
                    "error": {
                        "code": "server_not_ready",
                        "message": "workflow service is not initialized",
                    }
                },
                headers={"content-type": "application/json"},
            )

        if hasattr(self.workflow_service, "_uow_factory"):
            with self.workflow_service._uow_factory() as uow:
                workflow = uow.workflow_instances.get_by_id(workflow_instance_id)
                if workflow is None:
                    return McpResourceResponse(
                        status_code=404,
                        payload={
                            "error": {
                                "code": "not_found",
                                "message": (
                                    f"workflow '{workflow_instance_id}' was not found"
                                ),
                            }
                        },
                        headers={"content-type": "application/json"},
                    )
                if workflow.workspace_id != workspace_id:
                    return McpResourceResponse(
                        status_code=400,
                        payload={
                            "error": {
                                "code": "invalid_request",
                                "message": (
                                    "workflow instance does not belong to workspace"
                                ),
                            }
                        },
                        headers={"content-type": "application/json"},
                    )
        else:
            resume = self.workflow_service.resume_result
            if resume.workflow_instance.workflow_instance_id != workflow_instance_id:
                return McpResourceResponse(
                    status_code=404,
                    payload={
                        "error": {
                            "code": "not_found",
                            "message": (
                                f"workflow '{workflow_instance_id}' was not found"
                            ),
                        }
                    },
                    headers={"content-type": "application/json"},
                )
            if resume.workflow_instance.workspace_id != workspace_id:
                return McpResourceResponse(
                    status_code=400,
                    payload={
                        "error": {
                            "code": "invalid_request",
                            "message": "workflow instance does not belong to workspace",
                        }
                    },
                    headers={"content-type": "application/json"},
                )

        workflow_response = self.build_workflow_resume_response(workflow_instance_id)
        if workflow_response.status_code != 200:
            return McpResourceResponse(
                status_code=workflow_response.status_code,
                payload=workflow_response.payload,
                headers=workflow_response.headers,
            )

        return McpResourceResponse(
            status_code=200,
            payload={
                "uri": f"workspace://{workspace_id}/workflow/{workflow_instance_id}",
                "resource": workflow_response.payload,
            },
            headers={"content-type": "application/json"},
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


def _http_auth_error_response(message: str) -> WorkflowResumeResponse:
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


def _require_http_bearer_auth(
    server: CtxLedgerServer,
    path: str,
) -> WorkflowResumeResponse | None:
    if not server.settings.auth.is_enabled:
        return None

    expected_token = server.settings.auth.bearer_token
    if expected_token is None:
        return _http_auth_error_response("bearer token is not configured")

    presented_token = _extract_bearer_token(path)
    if presented_token is None:
        return _http_auth_error_response("missing bearer token")

    if presented_token != expected_token:
        return _http_auth_error_response("invalid bearer token")

    return None


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


def _parse_optional_projection_type_argument(
    arguments: dict[str, Any],
) -> ProjectionArtifactType | None | McpToolResponse:
    raw_value = arguments.get("projection_type")
    if raw_value is None:
        return None
    if not isinstance(raw_value, str) or not raw_value.strip():
        return build_mcp_error_response(
            code="invalid_request",
            message="projection_type must be a non-empty string when provided",
            details={"field": "projection_type"},
        )

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


def parse_workflow_resume_request_path(path: str) -> UUID | None:
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


def build_workflow_resume_http_handler(
    server: CtxLedgerServer,
):
    def _handler(path: str) -> WorkflowResumeResponse:
        auth_error = _require_http_bearer_auth(server, path)
        if auth_error is not None:
            return auth_error

        workflow_instance_id = parse_workflow_resume_request_path(path)
        if workflow_instance_id is None:
            return WorkflowResumeResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": "workflow resume endpoint requires /workflow-resume/{workflow_instance_id}",
                    }
                },
                headers={"content-type": "application/json"},
            )

        return build_workflow_resume_response(server, workflow_instance_id)

    return _handler


def parse_closed_projection_failures_request_path(path: str) -> UUID | None:
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


def build_closed_projection_failures_http_handler(
    server: CtxLedgerServer,
):
    def _handler(path: str) -> ProjectionFailureHistoryResponse:
        auth_error = _require_http_bearer_auth(server, path)
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
                        "message": "closed projection failures endpoint requires /workflow-resume/{workflow_instance_id}/closed-projection-failures",
                    }
                },
                headers={"content-type": "application/json"},
            )

        return build_closed_projection_failures_response(server, workflow_instance_id)

    return _handler


def build_projection_failures_ignore_http_handler(
    server: CtxLedgerServer,
):
    def _handler(path: str) -> ProjectionFailureActionResponse:
        auth_error = _require_http_bearer_auth(server, path)
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
                        "message": "projection failure ignore endpoint requires /projection_failures_ignore",
                    }
                },
                headers={"content-type": "application/json"},
            )

        arguments = {
            key: values[0] for key, values in parse_qs(parsed.query).items() if values
        }

        workspace_id = _parse_required_uuid_argument(arguments, "workspace_id")
        if isinstance(workspace_id, McpToolResponse):
            return ProjectionFailureActionResponse(
                status_code=400,
                payload={"error": workspace_id.payload["error"]},
                headers={"content-type": "application/json"},
            )

        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, McpToolResponse):
            return ProjectionFailureActionResponse(
                status_code=400,
                payload={"error": workflow_instance_id.payload["error"]},
                headers={"content-type": "application/json"},
            )

        projection_type = _parse_optional_projection_type_argument(arguments)
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
    def _handler(path: str) -> ProjectionFailureActionResponse:
        auth_error = _require_http_bearer_auth(server, path)
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
                        "message": "projection failure resolve endpoint requires /projection_failures_resolve",
                    }
                },
                headers={"content-type": "application/json"},
            )

        arguments = {
            key: values[0] for key, values in parse_qs(parsed.query).items() if values
        }

        workspace_id = _parse_required_uuid_argument(arguments, "workspace_id")
        if isinstance(workspace_id, McpToolResponse):
            return ProjectionFailureActionResponse(
                status_code=400,
                payload={"error": workspace_id.payload["error"]},
                headers={"content-type": "application/json"},
            )

        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, McpToolResponse):
            return ProjectionFailureActionResponse(
                status_code=400,
                payload={"error": workflow_instance_id.payload["error"]},
                headers={"content-type": "application/json"},
            )

        projection_type = _parse_optional_projection_type_argument(arguments)
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
    def _handler(path: str) -> RuntimeIntrospectionResponse:
        auth_error = _require_http_bearer_auth(server, path)
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
                        "message": "runtime introspection endpoint requires /debug/runtime",
                    }
                },
                headers={"content-type": "application/json"},
            )

        return build_runtime_introspection_response(server)

    return _handler


def build_runtime_routes_http_handler(
    server: CtxLedgerServer,
):
    def _handler(path: str) -> RuntimeIntrospectionResponse:
        auth_error = _require_http_bearer_auth(server, path)
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
    def _handler(path: str) -> RuntimeIntrospectionResponse:
        auth_error = _require_http_bearer_auth(server, path)
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
    def _validate_auth(path: str) -> StreamableHttpResponse | None:
        auth_error = _require_http_bearer_auth(server, path)
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


def build_http_runtime_adapter(server: CtxLedgerServer) -> HttpRuntimeAdapter:
    runtime = HttpRuntimeAdapter(server.settings)
    mcp_runtime = build_stdio_runtime_adapter(server)
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


def collect_runtime_introspection(
    runtime: ServerRuntime | None,
) -> tuple[RuntimeIntrospection, ...]:
    if runtime is None:
        return ()

    if isinstance(runtime, CompositeRuntimeAdapter):
        collected: list[RuntimeIntrospection] = []
        for nested_runtime in runtime._runtimes:
            collected.extend(collect_runtime_introspection(nested_runtime))
        return tuple(collected)

    if isinstance(runtime, HttpRuntimeAdapter):
        return (runtime.introspect(),)

    if isinstance(runtime, StdioRuntimeAdapter):
        introspection = runtime.introspect()
        return (
            RuntimeIntrospection(
                transport=introspection.transport,
                routes=tuple(getattr(introspection, "routes", ())),
                tools=tuple(introspection.tools),
                resources=tuple(introspection.resources),
            ),
        )

    return ()


def serialize_runtime_introspection_collection(
    introspections: tuple[RuntimeIntrospection, ...],
) -> list[dict[str, Any]]:
    return [
        serialize_runtime_introspection(introspection)
        for introspection in introspections
    ]


def build_stdio_runtime_adapter(server: CtxLedgerServer) -> StdioRuntimeAdapter:
    memory_service = MemoryService()
    return build_extracted_stdio_runtime_adapter(
        server,
        memory_service=memory_service,
        workflow_resume_tool_handler_factory=lambda current_server: (
            build_resume_workflow_tool_handler(current_server),
            WORKFLOW_RESUME_TOOL_SCHEMA,
        ),
        workspace_register_tool_handler_factory=lambda current_server: (
            build_workspace_register_tool_handler(current_server),
            WORKSPACE_REGISTER_TOOL_SCHEMA,
        ),
        workflow_start_tool_handler_factory=lambda current_server: (
            build_workflow_start_tool_handler(current_server),
            WORKFLOW_START_TOOL_SCHEMA,
        ),
        workflow_checkpoint_tool_handler_factory=lambda current_server: (
            build_workflow_checkpoint_tool_handler(current_server),
            WORKFLOW_CHECKPOINT_TOOL_SCHEMA,
        ),
        workflow_complete_tool_handler_factory=lambda current_server: (
            build_workflow_complete_tool_handler(current_server),
            WORKFLOW_COMPLETE_TOOL_SCHEMA,
        ),
        projection_failures_ignore_tool_handler_factory=lambda current_server: (
            build_projection_failures_ignore_tool_handler(current_server),
            PROJECTION_FAILURES_IGNORE_TOOL_SCHEMA,
        ),
        projection_failures_resolve_tool_handler_factory=lambda current_server: (
            build_projection_failures_resolve_tool_handler(current_server),
            PROJECTION_FAILURES_RESOLVE_TOOL_SCHEMA,
        ),
        memory_remember_episode_tool_handler_factory=lambda current_memory_service: (
            build_memory_remember_episode_tool_handler(current_memory_service),
            MEMORY_REMEMBER_EPISODE_TOOL_SCHEMA,
        ),
        memory_search_tool_handler_factory=lambda current_memory_service: (
            build_memory_search_tool_handler(current_memory_service),
            MEMORY_SEARCH_TOOL_SCHEMA,
        ),
        memory_get_context_tool_handler_factory=lambda current_memory_service: (
            build_memory_get_context_tool_handler(current_memory_service),
            MEMORY_GET_CONTEXT_TOOL_SCHEMA,
        ),
        workspace_resume_resource_handler_factory=build_workspace_resume_resource_handler,
        workflow_detail_resource_handler_factory=build_workflow_detail_resource_handler,
    )


def create_runtime(
    settings: AppSettings,
    server: CtxLedgerServer | None = None,
) -> ServerRuntime | None:
    runtimes: list[ServerRuntime] = []

    if settings.http.enabled:
        http_runtime = (
            build_http_runtime_adapter(server)
            if server is not None
            else HttpRuntimeAdapter(settings)
        )
        runtimes.append(http_runtime)

    if settings.stdio.enabled:
        stdio_runtime = build_stdio_runtime(
            settings,
            server=server,
            runtime_builder=build_stdio_runtime_adapter,
        )
        runtimes.append(stdio_runtime)

    if not runtimes:
        return None

    if len(runtimes) == 1:
        return runtimes[0]

    return CompositeRuntimeAdapter(runtimes)


def build_workflow_service_factory(
    settings: AppSettings,
) -> WorkflowServiceFactory | None:
    if not settings.database.url:
        return None

    postgres_config = PostgresConfig.from_settings(settings)
    uow_factory = build_postgres_uow_factory(postgres_config)

    def _factory() -> WorkflowService:
        return WorkflowService(uow_factory)

    return _factory


def create_server(
    settings: AppSettings,
    db_health_checker: DatabaseHealthChecker | None = None,
    runtime: ServerRuntime | None = None,
    workflow_service_factory: WorkflowServiceFactory | None = None,
) -> CtxLedgerServer:
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=db_health_checker,
        runtime=None,
        workflow_service_factory=(
            workflow_service_factory
            if workflow_service_factory is not None
            else build_workflow_service_factory(settings)
        ),
    )
    server.runtime = (
        runtime if runtime is not None else create_runtime(settings, server)
    )
    return server


def _apply_overrides(
    settings: AppSettings,
    *,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> AppSettings:
    if transport is None and host is None and port is None:
        return settings

    transport_mode = settings.transport
    http_enabled = settings.http.enabled
    stdio_enabled = settings.stdio.enabled

    if transport is not None:
        transport_mode = TransportMode(transport)
        http_enabled = transport_mode in (TransportMode.HTTP, TransportMode.BOTH)
        stdio_enabled = transport_mode in (TransportMode.STDIO, TransportMode.BOTH)

    http_settings = type(settings.http)(
        enabled=http_enabled,
        host=host if host is not None else settings.http.host,
        port=port if port is not None else settings.http.port,
        path=settings.http.path,
    )

    stdio_settings = type(settings.stdio)(
        enabled=stdio_enabled,
    )

    overridden = type(settings)(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        transport=transport_mode,
        database=settings.database,
        http=http_settings,
        stdio=stdio_settings,
        auth=settings.auth,
        debug=settings.debug,
        projection=settings.projection,
        logging=settings.logging,
    )
    overridden.validate()
    return overridden


def _install_signal_handlers(server: CtxLedgerServer) -> None:
    def _handle_signal(signum: int, frame: FrameType | None) -> None:
        logger.info(
            "Received shutdown signal",
            extra={"signal": signum},
        )
        server.shutdown()
        raise SystemExit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except ValueError:
            # Signal registration can fail outside the main thread.
            logger.debug("Signal handler registration skipped", extra={"signal": sig})


def _print_runtime_summary(server: CtxLedgerServer) -> None:
    readiness = server.readiness()
    health = server.health()
    runtime_introspection = serialize_runtime_introspection_collection(
        collect_runtime_introspection(server.runtime)
    )

    print(
        f"{server.settings.app_name} {server.settings.app_version} started",
        file=sys.stderr,
    )
    print(f"health={health.status}", file=sys.stderr)
    print(f"readiness={readiness.status}", file=sys.stderr)
    print(f"runtime={runtime_introspection}", file=sys.stderr)

    if server.settings.http.enabled:
        print(f"mcp_endpoint={server.settings.http.mcp_url}", file=sys.stderr)
    if server.settings.stdio.enabled:
        print("stdio_transport=enabled", file=sys.stderr)


def run_server(
    *,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> int:
    """
    Runnable server entrypoint used by the CLI.

    In v0.1.0 this starts bootstrap/runtime adapters and reports health/readiness.
    The actual MCP transport implementations can later replace the placeholder
    adapters without changing the entrypoint contract.
    """
    try:
        settings = get_settings()
        settings = _apply_overrides(
            settings,
            transport=transport,
            host=host,
            port=port,
        )
        server = create_server(settings)
        _install_signal_handlers(server)
        server.startup()
        _print_runtime_summary(server)

        if settings.stdio.enabled and run_stdio_runtime_if_present(server.runtime):
            return 0

        return 0
    except ServerBootstrapError as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled server error: {exc}", file=sys.stderr)
        return 1


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

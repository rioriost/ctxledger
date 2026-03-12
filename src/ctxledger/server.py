from __future__ import annotations

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
from .memory.service import (
    GetMemoryContextRequest,
    MemoryService,
    MemoryServiceError,
    RememberEpisodeRequest,
    SearchMemoryRequest,
    StubResponse,
)
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


@dataclass(slots=True)
class RuntimeIntrospection:
    transport: str
    routes: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()


WorkflowHttpHandler = Any
McpToolHandler = Any
McpResourceHandler = Any


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

    def dispatch(self, route_name: str, path: str) -> WorkflowResumeResponse:
        return dispatch_http_request(self, route_name, path).response

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


class StdioRuntimeAdapter:
    """
    Placeholder stdio runtime adapter.

    This class establishes the lifecycle and logging contract for the future
    MCP stdio implementation.
    """

    def __init__(
        self,
        settings: AppSettings,
        tool_handlers: dict[str, McpToolHandler] | None = None,
        resource_handlers: dict[str, McpResourceHandler] | None = None,
    ) -> None:
        self.settings = settings
        self._started = False
        self._tool_handlers: dict[str, McpToolHandler] = tool_handlers or {}
        self._resource_handlers: dict[str, McpResourceHandler] = resource_handlers or {}

    def register_tool_handler(self, tool_name: str, handler: McpToolHandler) -> None:
        self._tool_handlers[tool_name] = handler

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

    def introspect(self) -> RuntimeIntrospection:
        return RuntimeIntrospection(
            transport="stdio",
            tools=self.registered_tools(),
            resources=self.registered_resources(),
        )

    def dispatch_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> McpToolResponse:
        return dispatch_mcp_tool(self, tool_name, arguments).response

    def dispatch_resource(self, uri: str) -> McpResourceResponse:
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


def build_mcp_success_response(result: dict[str, Any]) -> McpToolResponse:
    return McpToolResponse(
        payload={
            "ok": True,
            "result": result,
        }
    )


def build_mcp_error_response(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> McpToolResponse:
    return McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        }
    )


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

    response = handler(path)
    return RuntimeDispatchResult(
        transport="http",
        target=route_name,
        status="ok" if response.status_code < 400 else "error",
        response=response,
    )


def dispatch_mcp_tool(
    runtime: StdioRuntimeAdapter,
    tool_name: str,
    arguments: dict[str, Any],
) -> RuntimeDispatchResult:
    handler = runtime._tool_handlers.get(tool_name)
    if handler is None:
        response = McpToolResponse(
            payload={
                "error": {
                    "code": "tool_not_found",
                    "message": f"no MCP tool handler is registered for tool '{tool_name}'",
                }
            }
        )
        return RuntimeDispatchResult(
            transport="stdio",
            target=tool_name,
            status="tool_not_found",
            response=response,
        )

    response = handler(arguments)
    error_payload = response.payload.get("error")
    return RuntimeDispatchResult(
        transport="stdio",
        target=tool_name,
        status="error" if error_payload is not None else "ok",
        response=response,
    )


def dispatch_mcp_resource(
    runtime: StdioRuntimeAdapter,
    uri: str,
) -> RuntimeDispatchResult:
    for resource_pattern, handler in runtime._resource_handlers.items():
        if resource_pattern == "workspace://{workspace_id}/resume":
            if parse_workspace_resume_resource_uri(uri) is not None:
                response = handler(uri)
                status = "ok" if response.status_code < 400 else "error"
                return RuntimeDispatchResult(
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
                return RuntimeDispatchResult(
                    transport="stdio",
                    target=uri,
                    status=status,
                    response=response,
                )

    response = McpResourceResponse(
        status_code=404,
        payload={
            "error": {
                "code": "resource_not_found",
                "message": f"no MCP resource handler is registered for resource '{uri}'",
            }
        },
        headers={"content-type": "application/json"},
    )
    return RuntimeDispatchResult(
        transport="stdio",
        target=uri,
        status="resource_not_found",
        response=response,
    )


def build_workflow_resume_response(
    server: CtxLedgerServer,
    workflow_instance_id: UUID,
) -> WorkflowResumeResponse:
    return server.build_workflow_resume_response(workflow_instance_id)


def build_workspace_resume_resource_response(
    server: CtxLedgerServer,
    workspace_id: UUID,
) -> McpResourceResponse:
    return server.build_workspace_resume_resource_response(workspace_id)


def build_workflow_detail_resource_response(
    server: CtxLedgerServer,
    *,
    workspace_id: UUID,
    workflow_instance_id: UUID,
) -> McpResourceResponse:
    return server.build_workflow_detail_resource_response(
        workspace_id,
        workflow_instance_id,
    )


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


def parse_workspace_resume_resource_uri(uri: str) -> UUID | None:
    normalized_uri = uri.strip()
    if not normalized_uri:
        return None

    prefix = "workspace://"
    if not normalized_uri.startswith(prefix):
        return None

    remainder = normalized_uri[len(prefix) :]
    parts = remainder.split("/")
    if len(parts) != 2 or parts[1] != "resume":
        return None

    try:
        return UUID(parts[0])
    except ValueError:
        return None


def parse_workflow_detail_resource_uri(uri: str) -> tuple[UUID, UUID] | None:
    normalized_uri = uri.strip()
    if not normalized_uri:
        return None

    prefix = "workspace://"
    if not normalized_uri.startswith(prefix):
        return None

    remainder = normalized_uri[len(prefix) :]
    parts = remainder.split("/")
    if len(parts) != 3 or parts[1] != "workflow":
        return None

    try:
        return UUID(parts[0]), UUID(parts[2])
    except ValueError:
        return None


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


def _parse_required_string_argument(
    arguments: dict[str, Any],
    field_name: str,
) -> str | McpToolResponse:
    raw_value = arguments.get(field_name)
    if not isinstance(raw_value, str) or not raw_value.strip():
        return build_mcp_error_response(
            code="invalid_request",
            message=f"{field_name} must be a non-empty string",
            details={"field": field_name},
        )
    return raw_value.strip()


def _parse_optional_string_argument(
    arguments: dict[str, Any],
    field_name: str,
) -> str | None | McpToolResponse:
    raw_value = arguments.get(field_name)
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        return build_mcp_error_response(
            code="invalid_request",
            message=f"{field_name} must be a string when provided",
            details={"field": field_name},
        )
    return raw_value


def _parse_optional_dict_argument(
    arguments: dict[str, Any],
    field_name: str,
) -> dict[str, Any] | McpToolResponse:
    raw_value = arguments.get(field_name)
    if raw_value is None:
        return {}
    if not isinstance(raw_value, dict):
        return build_mcp_error_response(
            code="invalid_request",
            message=f"{field_name} must be an object when provided",
            details={"field": field_name},
        )
    return dict(raw_value)


def _parse_optional_verify_status_argument(
    arguments: dict[str, Any],
) -> VerifyStatus | None | McpToolResponse:
    raw_value = arguments.get("verify_status")
    if raw_value is None:
        return None
    if not isinstance(raw_value, str) or not raw_value.strip():
        return build_mcp_error_response(
            code="invalid_request",
            message="verify_status must be a non-empty string when provided",
            details={"field": "verify_status"},
        )
    try:
        return VerifyStatus(raw_value.strip())
    except ValueError:
        return build_mcp_error_response(
            code="invalid_request",
            message="verify_status must be a supported verification status",
            details={
                "field": "verify_status",
                "allowed_values": [status.value for status in VerifyStatus],
            },
        )


def _parse_required_workflow_status_argument(
    arguments: dict[str, Any],
) -> WorkflowInstanceStatus | McpToolResponse:
    raw_value = arguments.get("workflow_status")
    if not isinstance(raw_value, str) or not raw_value.strip():
        return build_mcp_error_response(
            code="invalid_request",
            message="workflow_status must be a non-empty string",
            details={"field": "workflow_status"},
        )
    try:
        return WorkflowInstanceStatus(raw_value.strip())
    except ValueError:
        return build_mcp_error_response(
            code="invalid_request",
            message="workflow_status must be a supported workflow status",
            details={
                "field": "workflow_status",
                "allowed_values": [status.value for status in WorkflowInstanceStatus],
            },
        )


def _map_workflow_error_to_mcp_response(
    exc: Exception,
    *,
    default_message: str,
) -> McpToolResponse:
    if isinstance(exc, WorkflowError):
        code = exc.code
        if code in {
            "validation_error",
            "authentication_error",
            "active_workflow_exists",
            "workspace_registration_conflict",
            "invalid_state_transition",
            "workflow_attempt_mismatch",
        }:
            mapped_code = "invalid_request"
        elif code in {
            "workspace_not_found",
            "workflow_not_found",
            "attempt_not_found",
            "not_found",
        }:
            mapped_code = "not_found"
        else:
            mapped_code = "server_error"
        return build_mcp_error_response(
            code=mapped_code,
            message=str(exc) or default_message,
            details=getattr(exc, "details", {}),
        )

    message = str(exc) or default_message
    lowered = message.lower()
    if "not found" in lowered:
        code = "not_found"
    elif "invalid" in lowered or "mismatch" in lowered or "already" in lowered:
        code = "invalid_request"
    else:
        code = "server_error"

    return build_mcp_error_response(
        code=code,
        message=message,
        details={},
    )


def build_resume_workflow_tool_handler(
    server: CtxLedgerServer,
):
    def _handler(arguments: dict[str, Any]) -> McpToolResponse:
        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, McpToolResponse):
            return workflow_instance_id

        response = build_workflow_resume_response(server, workflow_instance_id)
        if response.status_code != 200:
            error = response.payload.get("error", {})
            return build_mcp_error_response(
                code=str(error.get("code", "server_error")),
                message=str(error.get("message", "failed to resume workflow")),
                details={},
            )

        return build_mcp_success_response(response.payload)

    return _handler


def build_workspace_resume_resource_handler(
    server: CtxLedgerServer,
):
    def _handler(uri: str) -> McpResourceResponse:
        workspace_id = parse_workspace_resume_resource_uri(uri)
        if workspace_id is None:
            return McpResourceResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": (
                            "workspace resume resource requires "
                            "workspace://{workspace_id}/resume"
                        ),
                    }
                },
                headers={"content-type": "application/json"},
            )

        return build_workspace_resume_resource_response(server, workspace_id)

    return _handler


def build_workflow_detail_resource_handler(
    server: CtxLedgerServer,
):
    def _handler(uri: str) -> McpResourceResponse:
        parsed = parse_workflow_detail_resource_uri(uri)
        if parsed is None:
            return McpResourceResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": (
                            "workflow detail resource requires "
                            "workspace://{workspace_id}/workflow/{workflow_instance_id}"
                        ),
                    }
                },
                headers={"content-type": "application/json"},
            )

        workspace_id, workflow_instance_id = parsed
        return build_workflow_detail_resource_response(
            server,
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
        )

    return _handler


def build_workspace_register_tool_handler(
    server: CtxLedgerServer,
):
    def _handler(arguments: dict[str, Any]) -> McpToolResponse:
        repo_url = _parse_required_string_argument(arguments, "repo_url")
        if isinstance(repo_url, McpToolResponse):
            return repo_url

        canonical_path = _parse_required_string_argument(arguments, "canonical_path")
        if isinstance(canonical_path, McpToolResponse):
            return canonical_path

        default_branch = _parse_required_string_argument(arguments, "default_branch")
        if isinstance(default_branch, McpToolResponse):
            return default_branch

        raw_workspace_id = arguments.get("workspace_id")
        workspace_id: UUID | None
        if raw_workspace_id is None:
            workspace_id = None
        elif not isinstance(raw_workspace_id, str) or not raw_workspace_id.strip():
            return build_mcp_error_response(
                code="invalid_request",
                message="workspace_id must be a non-empty string when provided",
                details={"field": "workspace_id"},
            )
        else:
            try:
                workspace_id = UUID(raw_workspace_id)
            except ValueError:
                return build_mcp_error_response(
                    code="invalid_request",
                    message="workspace_id must be a valid UUID",
                    details={"field": "workspace_id"},
                )

        metadata = _parse_optional_dict_argument(arguments, "metadata")
        if isinstance(metadata, McpToolResponse):
            return metadata

        if server.workflow_service is None:
            return build_mcp_error_response(
                code="server_not_ready",
                message="workflow service is not initialized",
                details={},
            )

        try:
            workspace = server.workflow_service.register_workspace(
                RegisterWorkspaceInput(
                    workspace_id=workspace_id,
                    repo_url=repo_url,
                    canonical_path=canonical_path,
                    default_branch=default_branch,
                    metadata=metadata,
                )
            )
        except Exception as exc:
            return _map_workflow_error_to_mcp_response(
                exc,
                default_message="failed to register workspace",
            )

        return build_mcp_success_response(
            {
                "workspace_id": str(workspace.workspace_id),
                "repo_url": workspace.repo_url,
                "canonical_path": workspace.canonical_path,
                "default_branch": workspace.default_branch,
                "metadata": workspace.metadata,
                "created_at": workspace.created_at.isoformat(),
                "updated_at": workspace.updated_at.isoformat(),
            }
        )

    return _handler


def build_workflow_start_tool_handler(
    server: CtxLedgerServer,
):
    def _handler(arguments: dict[str, Any]) -> McpToolResponse:
        workspace_id = _parse_required_uuid_argument(arguments, "workspace_id")
        if isinstance(workspace_id, McpToolResponse):
            return workspace_id

        ticket_id = _parse_required_string_argument(arguments, "ticket_id")
        if isinstance(ticket_id, McpToolResponse):
            return ticket_id

        metadata = _parse_optional_dict_argument(arguments, "metadata")
        if isinstance(metadata, McpToolResponse):
            return metadata

        if server.workflow_service is None:
            return build_mcp_error_response(
                code="server_not_ready",
                message="workflow service is not initialized",
                details={},
            )

        try:
            result = server.workflow_service.start_workflow(
                StartWorkflowInput(
                    workspace_id=workspace_id,
                    ticket_id=ticket_id,
                    metadata=metadata,
                )
            )
        except Exception as exc:
            return _map_workflow_error_to_mcp_response(
                exc,
                default_message="failed to start workflow",
            )

        return build_mcp_success_response(
            {
                "workflow_instance_id": str(
                    result.workflow_instance.workflow_instance_id
                ),
                "attempt_id": str(result.attempt.attempt_id),
                "workspace_id": str(result.workflow_instance.workspace_id),
                "ticket_id": result.workflow_instance.ticket_id,
                "workflow_status": result.workflow_instance.status.value,
                "attempt_status": result.attempt.status.value,
                "created_at": result.workflow_instance.created_at.isoformat(),
            }
        )

    return _handler


def build_workflow_checkpoint_tool_handler(
    server: CtxLedgerServer,
):
    def _handler(arguments: dict[str, Any]) -> McpToolResponse:
        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, McpToolResponse):
            return workflow_instance_id

        attempt_id = _parse_required_uuid_argument(arguments, "attempt_id")
        if isinstance(attempt_id, McpToolResponse):
            return attempt_id

        step_name = _parse_required_string_argument(arguments, "step_name")
        if isinstance(step_name, McpToolResponse):
            return step_name

        summary = _parse_optional_string_argument(arguments, "summary")
        if isinstance(summary, McpToolResponse):
            return summary

        checkpoint_json = _parse_optional_dict_argument(arguments, "checkpoint_json")
        if isinstance(checkpoint_json, McpToolResponse):
            return checkpoint_json

        verify_status = _parse_optional_verify_status_argument(arguments)
        if isinstance(verify_status, McpToolResponse):
            return verify_status

        raw_verify_report = arguments.get("verify_report")
        if raw_verify_report is None:
            verify_report = None
        elif isinstance(raw_verify_report, dict):
            verify_report = dict(raw_verify_report)
        else:
            return build_mcp_error_response(
                code="invalid_request",
                message="verify_report must be an object when provided",
                details={"field": "verify_report"},
            )

        if server.workflow_service is None:
            return build_mcp_error_response(
                code="server_not_ready",
                message="workflow service is not initialized",
                details={},
            )

        try:
            result = server.workflow_service.create_checkpoint(
                CreateCheckpointInput(
                    workflow_instance_id=workflow_instance_id,
                    attempt_id=attempt_id,
                    step_name=step_name,
                    summary=summary,
                    checkpoint_json=checkpoint_json,
                    verify_status=verify_status,
                    verify_report=verify_report,
                )
            )
        except Exception as exc:
            return _map_workflow_error_to_mcp_response(
                exc,
                default_message="failed to create checkpoint",
            )

        return build_mcp_success_response(
            {
                "checkpoint_id": str(result.checkpoint.checkpoint_id),
                "workflow_instance_id": str(
                    result.workflow_instance.workflow_instance_id
                ),
                "attempt_id": str(result.attempt.attempt_id),
                "step_name": result.checkpoint.step_name,
                "created_at": result.checkpoint.created_at.isoformat(),
                "latest_verify_status": (
                    result.verify_report.status.value
                    if result.verify_report is not None
                    else (
                        result.attempt.verify_status.value
                        if result.attempt.verify_status is not None
                        else None
                    )
                ),
            }
        )

    return _handler


def build_workflow_complete_tool_handler(
    server: CtxLedgerServer,
):
    def _handler(arguments: dict[str, Any]) -> McpToolResponse:
        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, McpToolResponse):
            return workflow_instance_id

        attempt_id = _parse_required_uuid_argument(arguments, "attempt_id")
        if isinstance(attempt_id, McpToolResponse):
            return attempt_id

        workflow_status = _parse_required_workflow_status_argument(arguments)
        if isinstance(workflow_status, McpToolResponse):
            return workflow_status

        summary = _parse_optional_string_argument(arguments, "summary")
        if isinstance(summary, McpToolResponse):
            return summary

        verify_status = _parse_optional_verify_status_argument(arguments)
        if isinstance(verify_status, McpToolResponse):
            return verify_status

        raw_verify_report = arguments.get("verify_report")
        if raw_verify_report is None:
            verify_report = None
        elif isinstance(raw_verify_report, dict):
            verify_report = dict(raw_verify_report)
        else:
            return build_mcp_error_response(
                code="invalid_request",
                message="verify_report must be an object when provided",
                details={"field": "verify_report"},
            )

        failure_reason = _parse_optional_string_argument(arguments, "failure_reason")
        if isinstance(failure_reason, McpToolResponse):
            return failure_reason

        if server.workflow_service is None:
            return build_mcp_error_response(
                code="server_not_ready",
                message="workflow service is not initialized",
                details={},
            )

        try:
            result = server.workflow_service.complete_workflow(
                CompleteWorkflowInput(
                    workflow_instance_id=workflow_instance_id,
                    attempt_id=attempt_id,
                    workflow_status=workflow_status,
                    summary=summary,
                    verify_status=verify_status,
                    verify_report=verify_report,
                    failure_reason=failure_reason,
                )
            )
        except Exception as exc:
            return _map_workflow_error_to_mcp_response(
                exc,
                default_message="failed to complete workflow",
            )

        return build_mcp_success_response(
            {
                "workflow_instance_id": str(
                    result.workflow_instance.workflow_instance_id
                ),
                "attempt_id": str(result.attempt.attempt_id),
                "workflow_status": result.workflow_instance.status.value,
                "attempt_status": result.attempt.status.value,
                "finished_at": (
                    result.attempt.finished_at.isoformat()
                    if result.attempt.finished_at is not None
                    else None
                ),
                "latest_verify_status": (
                    result.verify_report.status.value
                    if result.verify_report is not None
                    else (
                        result.attempt.verify_status.value
                        if result.attempt.verify_status is not None
                        else None
                    )
                ),
            }
        )

    return _handler


def build_projection_failures_ignore_tool_handler(
    server: CtxLedgerServer,
):
    def _handler(arguments: dict[str, Any]) -> McpToolResponse:
        workspace_id = _parse_required_uuid_argument(arguments, "workspace_id")
        if isinstance(workspace_id, McpToolResponse):
            return workspace_id

        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, McpToolResponse):
            return workflow_instance_id

        projection_type = _parse_optional_projection_type_argument(arguments)
        if isinstance(projection_type, McpToolResponse):
            return projection_type

        if server.workflow_service is None:
            return build_mcp_error_response(
                code="server_not_ready",
                message="workflow service is not initialized",
                details={},
            )

        try:
            updated_failure_count = (
                server.workflow_service.ignore_resume_projection_failures(
                    workspace_id=workspace_id,
                    workflow_instance_id=workflow_instance_id,
                    projection_type=projection_type,
                )
            )
        except Exception as exc:
            message = str(exc) or "failed to ignore projection failures"
            lowered = message.lower()
            if "not found" in lowered:
                code = "not_found"
            elif "does not belong to workspace" in lowered or "mismatch" in lowered:
                code = "invalid_request"
            else:
                code = "server_error"
            return build_mcp_error_response(
                code=code,
                message=message,
                details={},
            )

        return build_mcp_success_response(
            {
                "workspace_id": str(workspace_id),
                "workflow_instance_id": str(workflow_instance_id),
                "projection_type": (
                    projection_type.value if projection_type is not None else None
                ),
                "updated_failure_count": updated_failure_count,
                "status": "ignored",
            }
        )

    return _handler


def build_projection_failures_resolve_tool_handler(
    server: CtxLedgerServer,
):
    def _handler(arguments: dict[str, Any]) -> McpToolResponse:
        workspace_id = _parse_required_uuid_argument(arguments, "workspace_id")
        if isinstance(workspace_id, McpToolResponse):
            return workspace_id

        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, McpToolResponse):
            return workflow_instance_id

        projection_type = _parse_optional_projection_type_argument(arguments)
        if isinstance(projection_type, McpToolResponse):
            return projection_type

        if server.workflow_service is None:
            return build_mcp_error_response(
                code="server_not_ready",
                message="workflow service is not initialized",
                details={},
            )

        try:
            updated_failure_count = (
                server.workflow_service.resolve_resume_projection_failures(
                    workspace_id=workspace_id,
                    workflow_instance_id=workflow_instance_id,
                    projection_type=projection_type,
                )
            )
        except Exception as exc:
            message = str(exc) or "failed to resolve projection failures"
            lowered = message.lower()
            if "not found" in lowered:
                code = "not_found"
            elif "does not belong to workspace" in lowered or "mismatch" in lowered:
                code = "invalid_request"
            else:
                code = "server_error"
            return build_mcp_error_response(
                code=code,
                message=message,
                details={},
            )

        return build_mcp_success_response(
            {
                "workspace_id": str(workspace_id),
                "workflow_instance_id": str(workflow_instance_id),
                "projection_type": (
                    projection_type.value if projection_type is not None else None
                ),
                "updated_failure_count": updated_failure_count,
                "status": "resolved",
            }
        )

    return _handler


def build_memory_remember_episode_tool_handler(
    memory_service: MemoryService,
):
    def _handler(arguments: dict[str, Any]) -> McpToolResponse:
        try:
            response = memory_service.remember_episode(
                RememberEpisodeRequest(
                    workflow_instance_id=str(arguments.get("workflow_instance_id", "")),
                    summary=str(arguments.get("summary", "")),
                    attempt_id=(
                        str(arguments["attempt_id"])
                        if arguments.get("attempt_id") is not None
                        else None
                    ),
                    metadata=(
                        arguments["metadata"]
                        if isinstance(arguments.get("metadata"), dict)
                        else {}
                    ),
                )
            )
            return build_mcp_success_response(serialize_stub_response(response))
        except MemoryServiceError as exc:
            return build_mcp_error_response(
                code=exc.code.value,
                message=exc.message,
                details=exc.details,
            )

    return _handler


def build_memory_search_tool_handler(
    memory_service: MemoryService,
):
    def _handler(arguments: dict[str, Any]) -> McpToolResponse:
        try:
            response = memory_service.search(
                SearchMemoryRequest(
                    query=str(arguments.get("query", "")),
                    workspace_id=(
                        str(arguments["workspace_id"])
                        if arguments.get("workspace_id") is not None
                        else None
                    ),
                    limit=(
                        arguments["limit"]
                        if isinstance(arguments.get("limit"), int)
                        else 10
                    ),
                    filters=(
                        arguments["filters"]
                        if isinstance(arguments.get("filters"), dict)
                        else {}
                    ),
                )
            )
            return build_mcp_success_response(serialize_stub_response(response))
        except MemoryServiceError as exc:
            return build_mcp_error_response(
                code=exc.code.value,
                message=exc.message,
                details=exc.details,
            )

    return _handler


def build_memory_get_context_tool_handler(
    memory_service: MemoryService,
):
    def _handler(arguments: dict[str, Any]) -> McpToolResponse:
        try:
            response = memory_service.get_context(
                GetMemoryContextRequest(
                    query=(
                        str(arguments["query"])
                        if arguments.get("query") is not None
                        else None
                    ),
                    workspace_id=(
                        str(arguments["workspace_id"])
                        if arguments.get("workspace_id") is not None
                        else None
                    ),
                    workflow_instance_id=(
                        str(arguments["workflow_instance_id"])
                        if arguments.get("workflow_instance_id") is not None
                        else None
                    ),
                    ticket_id=(
                        str(arguments["ticket_id"])
                        if arguments.get("ticket_id") is not None
                        else None
                    ),
                    limit=(
                        arguments["limit"]
                        if isinstance(arguments.get("limit"), int)
                        else 10
                    ),
                    include_episodes=(
                        arguments["include_episodes"]
                        if isinstance(arguments.get("include_episodes"), bool)
                        else True
                    ),
                    include_memory_items=(
                        arguments["include_memory_items"]
                        if isinstance(arguments.get("include_memory_items"), bool)
                        else True
                    ),
                    include_summaries=(
                        arguments["include_summaries"]
                        if isinstance(arguments.get("include_summaries"), bool)
                        else True
                    ),
                )
            )
            return build_mcp_success_response(serialize_stub_response(response))
        except MemoryServiceError as exc:
            return build_mcp_error_response(
                code=exc.code.value,
                message=exc.message,
                details=exc.details,
            )

    return _handler


def build_http_runtime_adapter(server: CtxLedgerServer) -> HttpRuntimeAdapter:
    runtime = HttpRuntimeAdapter(server.settings)
    debug_settings = getattr(server.settings, "debug", None)
    debug_http_endpoints_enabled = (
        True if debug_settings is None else getattr(debug_settings, "enabled", True)
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
        return (runtime.introspect(),)

    return ()


def serialize_runtime_introspection_collection(
    introspections: tuple[RuntimeIntrospection, ...],
) -> list[dict[str, Any]]:
    return [
        serialize_runtime_introspection(introspection)
        for introspection in introspections
    ]


def build_stdio_runtime_adapter(server: CtxLedgerServer) -> StdioRuntimeAdapter:
    runtime = StdioRuntimeAdapter(server.settings)
    memory_service = MemoryService()
    runtime.register_resource_handler(
        "workspace://{workspace_id}/resume",
        build_workspace_resume_resource_handler(server),
    )
    runtime.register_resource_handler(
        "workspace://{workspace_id}/workflow/{workflow_instance_id}",
        build_workflow_detail_resource_handler(server),
    )
    runtime.register_tool_handler(
        "workflow_resume",
        build_resume_workflow_tool_handler(server),
    )
    runtime.register_tool_handler(
        "workspace_register",
        build_workspace_register_tool_handler(server),
    )
    runtime.register_tool_handler(
        "workflow_start",
        build_workflow_start_tool_handler(server),
    )
    runtime.register_tool_handler(
        "workflow_checkpoint",
        build_workflow_checkpoint_tool_handler(server),
    )
    runtime.register_tool_handler(
        "workflow_complete",
        build_workflow_complete_tool_handler(server),
    )
    runtime.register_tool_handler(
        "projection_failures_ignore",
        build_projection_failures_ignore_tool_handler(server),
    )
    runtime.register_tool_handler(
        "projection_failures_resolve",
        build_projection_failures_resolve_tool_handler(server),
    )
    runtime.register_tool_handler(
        "memory_remember_episode",
        build_memory_remember_episode_tool_handler(memory_service),
    )
    runtime.register_tool_handler(
        "memory_search",
        build_memory_search_tool_handler(memory_service),
    )
    runtime.register_tool_handler(
        "memory_get_context",
        build_memory_get_context_tool_handler(memory_service),
    )
    return runtime


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
        stdio_runtime = (
            build_stdio_runtime_adapter(server)
            if server is not None
            else StdioRuntimeAdapter(settings)
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

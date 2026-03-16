from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from .config import AppSettings
from .db.postgres import (
    PostgresConfig,
    build_connection_pool,
)
from .runtime.database_health import (
    build_database_health_checker,
)
from .runtime.errors import ServerBootstrapError
from .runtime.http_runtime import (
    build_http_runtime_adapter,
)
from .runtime.introspection import (
    collect_runtime_introspection,
)
from .runtime.protocols import (
    DatabaseHealthChecker,
    ServerRuntime,
    WorkflowServiceFactory,
)
from .runtime.serializers import (
    serialize_runtime_introspection_collection,
)
from .runtime.server_factory import (
    build_workflow_service_factory,
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
    McpResourceResponse,
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
        connection_pool: Any | None = None,
    ) -> None:
        self.settings = settings
        self.db_health_checker = db_health_checker or build_database_health_checker(
            settings.database.url
        )
        self.runtime = runtime
        self.workflow_service_factory = workflow_service_factory
        self.workflow_service: WorkflowService | None = None
        self.connection_pool = connection_pool
        self._owns_connection_pool = (
            connection_pool is None
            and workflow_service_factory is None
            and bool(settings.database.url)
        )
        self._started = False

    def get_workflow_resume(
        self,
        workflow_instance_id: UUID,
        *,
        include_closed_projection_failures: bool = False,
    ) -> WorkflowResume:
        if self.workflow_service is None:
            raise ServerBootstrapError("workflow service is not initialized")
        return self.workflow_service.resume_workflow(
            ResumeWorkflowInput(
                workflow_instance_id=workflow_instance_id,
                include_closed_projection_failures=include_closed_projection_failures,
            )
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

        if self.connection_pool is None and self._owns_connection_pool:
            postgres_config = PostgresConfig.from_settings(self.settings)
            self.connection_pool = build_connection_pool(postgres_config)

        if self.workflow_service_factory is not None:
            if self.connection_pool is not None:
                try:
                    self.workflow_service = self.workflow_service_factory(
                        connection_pool=self.connection_pool
                    )
                except TypeError as exc:
                    if "connection_pool" not in str(exc):
                        raise
                    self.workflow_service = self.workflow_service_factory()
            else:
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
                "runtime": self._serialized_runtime_introspection(),
            },
        )

    def shutdown(self) -> None:
        logger.info("ctxledger shutdown initiated")

        if self.runtime is not None and self._started:
            self.runtime.stop()

        self.workflow_service = None

        if self.connection_pool is not None and self._owns_connection_pool:
            self.connection_pool.close()
            self.connection_pool = None

        self._started = False
        logger.info("ctxledger shutdown complete")

    def health(self) -> HealthStatus:
        return build_health_status(self)

    def readiness(self) -> ReadinessStatus:
        return build_readiness_status(self)

    def _serialized_runtime_introspection(self) -> list[dict[str, object]]:
        return serialize_runtime_introspection_collection(
            collect_runtime_introspection(self.runtime)
        )


def create_server(
    settings: AppSettings,
    db_health_checker: DatabaseHealthChecker | None = None,
    runtime: ServerRuntime | None = None,
    workflow_service_factory: WorkflowServiceFactory | None = None,
    connection_pool: Any | None = None,
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
        connection_pool=connection_pool,
    )
    server.runtime = (
        runtime if runtime is not None else build_http_runtime_adapter(server)
    )
    return server


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
    "CtxLedgerServer",
    "create_server",
    "run_server",
]

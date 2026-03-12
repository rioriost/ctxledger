from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from ..config import AppSettings
from .types import McpResourceResponse, McpToolResponse

if TYPE_CHECKING:
    from ..mcp.tool_schemas import McpToolSchema
    from ..workflow.service import ProjectionArtifactType, WorkflowService


class DatabaseHealthChecker(Protocol):
    def ping(self) -> None: ...
    def schema_ready(self) -> bool: ...


class ServerRuntime(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


class WorkflowServiceFactory(Protocol):
    def __call__(self) -> WorkflowService: ...


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


class HttpHandlerFactoryServer(Protocol):
    settings: AppSettings


class WorkflowResponseBuilderServer(HttpHandlerFactoryServer, Protocol):
    workflow_service: WorkflowService | None
    runtime: ServerRuntime | None

    def get_workflow_resume(self, workflow_instance_id): ...

    def build_workflow_resume_response(self, workflow_instance_id): ...
    def build_closed_projection_failures_response(self, workflow_instance_id): ...

    def build_projection_failures_ignore_response(
        self,
        *,
        workspace_id,
        workflow_instance_id,
        projection_type: ProjectionArtifactType | None = None,
    ): ...

    def build_projection_failures_resolve_response(
        self,
        *,
        workspace_id,
        workflow_instance_id,
        projection_type: ProjectionArtifactType | None = None,
    ): ...

    def build_runtime_introspection_response(self): ...
    def build_runtime_routes_response(self): ...
    def build_runtime_tools_response(self): ...


__all__ = [
    "DatabaseHealthChecker",
    "ServerRuntime",
    "WorkflowServiceFactory",
    "McpRuntimeProtocol",
    "HttpHandlerFactoryServer",
    "WorkflowResponseBuilderServer",
]

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from ..workflow.service import ProjectionArtifactType

if TYPE_CHECKING:
    from ..server import CtxLedgerServer
    from .types import (
        McpResourceResponse,
        ProjectionFailureActionResponse,
        ProjectionFailureHistoryResponse,
        RuntimeIntrospectionResponse,
        WorkflowResumeResponse,
    )


def build_workflow_resume_response(
    server: CtxLedgerServer,
    workflow_instance_id: UUID,
) -> WorkflowResumeResponse:
    from ..runtime.database_health import ServerBootstrapError
    from .serializers import serialize_workflow_resume
    from .types import WorkflowResumeResponse

    try:
        resume = server.get_workflow_resume(workflow_instance_id)
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
    server: CtxLedgerServer,
    workflow_instance_id: UUID,
) -> ProjectionFailureHistoryResponse:
    from ..runtime.database_health import ServerBootstrapError
    from .serializers import serialize_closed_projection_failures_history
    from .types import ProjectionFailureHistoryResponse

    try:
        resume = server.get_workflow_resume(workflow_instance_id)
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
    server: CtxLedgerServer,
    *,
    workspace_id: UUID,
    workflow_instance_id: UUID,
    projection_type: ProjectionArtifactType | None = None,
) -> ProjectionFailureActionResponse:
    from .types import ProjectionFailureActionResponse

    if server.workflow_service is None:
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
    server: CtxLedgerServer,
    *,
    workspace_id: UUID,
    workflow_instance_id: UUID,
    projection_type: ProjectionArtifactType | None = None,
) -> ProjectionFailureActionResponse:
    from .types import ProjectionFailureActionResponse

    if server.workflow_service is None:
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


def build_runtime_introspection_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    from .introspection import (
        collect_runtime_introspection,
        serialize_runtime_introspection_collection,
    )
    from .types import RuntimeIntrospectionResponse

    introspections = collect_runtime_introspection(server.runtime)
    return RuntimeIntrospectionResponse(
        status_code=200,
        payload={
            "runtime": serialize_runtime_introspection_collection(introspections),
        },
        headers={"content-type": "application/json"},
    )


def build_runtime_routes_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    from .introspection import collect_runtime_introspection
    from .types import RuntimeIntrospectionResponse

    introspections = collect_runtime_introspection(server.runtime)
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


def build_runtime_tools_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    from .introspection import collect_runtime_introspection
    from .types import RuntimeIntrospectionResponse

    introspections = collect_runtime_introspection(server.runtime)
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
    server: CtxLedgerServer,
    workspace_id: UUID,
) -> McpResourceResponse:
    from ..server import McpResourceResponse

    if server.workflow_service is None:
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

    if hasattr(server.workflow_service, "_uow_factory"):
        with server.workflow_service._uow_factory() as uow:
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
                selected_workflow = uow.workflow_instances.get_latest_by_workspace_id(
                    workspace_id
                )

        if selected_workflow is None:
            return McpResourceResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": f"no workflow is available for workspace '{workspace_id}'",
                    }
                },
                headers={"content-type": "application/json"},
            )

        workflow_response = build_workflow_resume_response(
            server,
            selected_workflow.workflow_instance_id,
        )
    else:
        workflow_response = build_workflow_resume_response(
            server,
            getattr(server.workflow_service.resume_result.workspace, "workspace_id"),
        )
        if workflow_response.status_code == 200:
            response_workspace_id = workflow_response.payload.get("workspace", {}).get(
                "workspace_id"
            )
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
    server: CtxLedgerServer,
    workspace_id: UUID,
    workflow_instance_id: UUID,
) -> McpResourceResponse:
    from ..server import McpResourceResponse

    if server.workflow_service is None:
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

    if hasattr(server.workflow_service, "_uow_factory"):
        with server.workflow_service._uow_factory() as uow:
            workflow = uow.workflow_instances.get_by_id(workflow_instance_id)
            if workflow is None:
                return McpResourceResponse(
                    status_code=404,
                    payload={
                        "error": {
                            "code": "not_found",
                            "message": f"workflow '{workflow_instance_id}' was not found",
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
                            "message": "workflow instance does not belong to workspace",
                        }
                    },
                    headers={"content-type": "application/json"},
                )
    else:
        resume = server.workflow_service.resume_result
        if resume.workflow_instance.workflow_instance_id != workflow_instance_id:
            return McpResourceResponse(
                status_code=404,
                payload={
                    "error": {
                        "code": "not_found",
                        "message": f"workflow '{workflow_instance_id}' was not found",
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

    workflow_response = build_workflow_resume_response(server, workflow_instance_id)
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


__all__ = [
    "build_closed_projection_failures_response",
    "build_projection_failures_ignore_response",
    "build_projection_failures_resolve_response",
    "build_runtime_introspection_response",
    "build_runtime_routes_response",
    "build_runtime_tools_response",
    "build_workflow_detail_resource_response",
    "build_workflow_resume_response",
    "build_workspace_resume_resource_response",
]

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from ..workflow.service import WorkflowError

if TYPE_CHECKING:
    from ..server import CtxLedgerServer
    from .types import (
        McpResourceResponse,
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
    except WorkflowError as exc:
        status_code, code, message, details = _workflow_resume_error_payload(
            exc,
            workflow_instance_id=workflow_instance_id,
        )
        return WorkflowResumeResponse(
            status_code=status_code,
            payload={
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                }
            },
            headers={"content-type": "application/json"},
        )

    return WorkflowResumeResponse(
        status_code=200,
        payload=serialize_workflow_resume(resume),
        headers={"content-type": "application/json"},
    )


def _age_prototype_runtime_details(server: CtxLedgerServer) -> dict[str, Any]:
    database_settings = server.settings.database
    details: dict[str, Any] = {
        "age_enabled": database_settings.age_enabled,
        "age_graph_name": database_settings.age_graph_name,
        "observability_routes": [
            "/debug/runtime",
            "/debug/routes",
            "/debug/tools",
        ],
    }

    health_checker = getattr(server, "db_health_checker", None)
    if health_checker is None:
        details["age_graph_status"] = "unknown"
        return details

    age_available = getattr(health_checker, "age_available", None)
    if callable(age_available):
        try:
            details["age_available"] = bool(age_available())
        except Exception as exc:
            details["age_available_error"] = str(exc)

    age_graph_status = getattr(health_checker, "age_graph_status", None)
    if callable(age_graph_status):
        try:
            graph_status = age_graph_status(database_settings.age_graph_name)
            details["age_graph_status"] = getattr(graph_status, "value", graph_status)
            return details
        except Exception as exc:
            details["age_graph_status_error"] = str(exc)

    age_graph_available = getattr(health_checker, "age_graph_available", None)
    if callable(age_graph_available):
        try:
            details["age_graph_available"] = bool(
                age_graph_available(database_settings.age_graph_name)
            )
        except Exception as exc:
            details["age_graph_available_error"] = str(exc)

    details.setdefault("age_graph_status", "unknown")
    return details


def build_runtime_introspection_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    from .introspection import collect_runtime_introspection
    from .serializers import serialize_runtime_introspection_collection
    from .types import RuntimeIntrospectionResponse

    introspections = collect_runtime_introspection(server.runtime)
    return RuntimeIntrospectionResponse(
        status_code=200,
        payload={
            "runtime": serialize_runtime_introspection_collection(introspections),
            "age_prototype": _age_prototype_runtime_details(server),
        },
        headers={"content-type": "application/json"},
    )


def build_runtime_routes_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    from .introspection import collect_runtime_introspection
    from .serializers import serialize_runtime_introspection
    from .types import RuntimeIntrospectionResponse

    introspections = collect_runtime_introspection(server.runtime)
    return RuntimeIntrospectionResponse(
        status_code=200,
        payload={
            "routes": [
                {
                    "transport": serialized["transport"],
                    "routes": serialized["routes"],
                }
                for serialized in (
                    serialize_runtime_introspection(introspection)
                    for introspection in introspections
                )
                if serialized["routes"]
            ],
        },
        headers={"content-type": "application/json"},
    )


def build_runtime_tools_response(
    server: CtxLedgerServer,
) -> RuntimeIntrospectionResponse:
    from .introspection import collect_runtime_introspection
    from .serializers import serialize_runtime_introspection
    from .types import RuntimeIntrospectionResponse

    introspections = collect_runtime_introspection(server.runtime)
    return RuntimeIntrospectionResponse(
        status_code=200,
        payload={
            "tools": [
                {
                    "transport": serialized["transport"],
                    "tools": serialized["tools"],
                }
                for serialized in (
                    serialize_runtime_introspection(introspection)
                    for introspection in introspections
                )
                if serialized["tools"]
            ],
        },
        headers={"content-type": "application/json"},
    )


def build_workspace_resume_resource_response(
    server: CtxLedgerServer,
    workspace_id: UUID,
) -> McpResourceResponse:
    from .types import McpResourceResponse

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

            running_workflow = uow.workflow_instances.get_running_by_workspace_id(workspace_id)
            selected_workflow = running_workflow
            if selected_workflow is None:
                selected_workflow = uow.workflow_instances.get_latest_by_workspace_id(workspace_id)

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
            getattr(
                server.workflow_service.resume_result.workflow_instance,
                "workflow_instance_id",
            ),
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
    from .types import McpResourceResponse

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

        workflow_response = build_workflow_resume_response(
            server,
            workflow_instance_id,
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


def _workflow_resume_error_payload(
    exc: WorkflowError,
    *,
    workflow_instance_id: UUID,
) -> tuple[int, str, str, dict[str, str]]:
    details = {key: str(value) for key, value in getattr(exc, "details", {}).items()}
    code = getattr(exc, "code", "workflow_error")

    if code in {"workflow_not_found", "not_found"}:
        if "workflow_instance_id" not in details:
            details["workflow_instance_id"] = str(workflow_instance_id)
        message = str(exc) or "workflow not found"
        return 404, "not_found", message, details

    if code in {"workflow_attempt_mismatch", "validation_error"}:
        message = str(exc) or "invalid workflow resume request"
        return 400, "invalid_request", message, details

    message = str(exc) or "failed to resume workflow"
    return 500, "server_error", message, details


__all__ = [
    "build_runtime_introspection_response",
    "build_runtime_routes_response",
    "build_runtime_tools_response",
    "build_workflow_detail_resource_response",
    "build_workflow_resume_response",
    "build_workspace_resume_resource_response",
]

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from ..memory.service import (
    GetMemoryContextRequest,
    MemoryService,
    MemoryServiceError,
    RememberEpisodeRequest,
    SearchMemoryRequest,
)
from ..workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    ProjectionArtifactType,
    RegisterWorkspaceInput,
    ResumeWorkflowInput,
    StartWorkflowInput,
    VerifyStatus,
    WorkflowError,
    WorkflowInstanceStatus,
)

if TYPE_CHECKING:
    from ..runtime.types import McpToolResponse
    from ..server import CtxLedgerServer


def _mcp_tool_response_cls() -> type["McpToolResponse"]:
    from ..runtime.types import McpToolResponse

    return McpToolResponse


def build_mcp_success_response(result: dict[str, Any]) -> "McpToolResponse":
    response_cls = _mcp_tool_response_cls()
    return response_cls(
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
) -> "McpToolResponse":
    response_cls = _mcp_tool_response_cls()
    return response_cls(
        payload={
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        }
    )


def _parse_required_uuid_argument(
    arguments: dict[str, Any],
    field_name: str,
) -> UUID | "McpToolResponse":
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
) -> ProjectionArtifactType | None | "McpToolResponse":
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
) -> str | "McpToolResponse":
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
) -> str | None | "McpToolResponse":
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
) -> dict[str, Any] | "McpToolResponse":
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
) -> VerifyStatus | None | "McpToolResponse":
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
) -> WorkflowInstanceStatus | "McpToolResponse":
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
) -> "McpToolResponse":
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
    server: "CtxLedgerServer",
):
    def _handler(arguments: dict[str, Any]) -> "McpToolResponse":
        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, _mcp_tool_response_cls()):
            return workflow_instance_id

        response = server.build_workflow_resume_response(workflow_instance_id)
        if response.status_code != 200:
            error = response.payload.get("error", {})
            return build_mcp_error_response(
                code=str(error.get("code", "server_error")),
                message=str(error.get("message", "failed to resume workflow")),
                details={},
            )

        return build_mcp_success_response(response.payload)

    return _handler


def build_workspace_register_tool_handler(
    server: "CtxLedgerServer",
):
    def _handler(arguments: dict[str, Any]) -> "McpToolResponse":
        repo_url = _parse_required_string_argument(arguments, "repo_url")
        if isinstance(repo_url, _mcp_tool_response_cls()):
            return repo_url

        canonical_path = _parse_required_string_argument(arguments, "canonical_path")
        if isinstance(canonical_path, _mcp_tool_response_cls()):
            return canonical_path

        default_branch = _parse_required_string_argument(arguments, "default_branch")
        if isinstance(default_branch, _mcp_tool_response_cls()):
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
        if isinstance(metadata, _mcp_tool_response_cls()):
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
    server: "CtxLedgerServer",
):
    def _handler(arguments: dict[str, Any]) -> "McpToolResponse":
        workspace_id = _parse_required_uuid_argument(arguments, "workspace_id")
        if isinstance(workspace_id, _mcp_tool_response_cls()):
            return workspace_id

        ticket_id = _parse_required_string_argument(arguments, "ticket_id")
        if isinstance(ticket_id, _mcp_tool_response_cls()):
            return ticket_id

        metadata = _parse_optional_dict_argument(arguments, "metadata")
        if isinstance(metadata, _mcp_tool_response_cls()):
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
    server: "CtxLedgerServer",
):
    def _handler(arguments: dict[str, Any]) -> "McpToolResponse":
        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, _mcp_tool_response_cls()):
            return workflow_instance_id

        attempt_id = _parse_required_uuid_argument(arguments, "attempt_id")
        if isinstance(attempt_id, _mcp_tool_response_cls()):
            return attempt_id

        step_name = _parse_required_string_argument(arguments, "step_name")
        if isinstance(step_name, _mcp_tool_response_cls()):
            return step_name

        summary = _parse_optional_string_argument(arguments, "summary")
        if isinstance(summary, _mcp_tool_response_cls()):
            return summary

        checkpoint_json = _parse_optional_dict_argument(arguments, "checkpoint_json")
        if isinstance(checkpoint_json, _mcp_tool_response_cls()):
            return checkpoint_json

        verify_status = _parse_optional_verify_status_argument(arguments)
        if isinstance(verify_status, _mcp_tool_response_cls()):
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
    server: "CtxLedgerServer",
):
    def _handler(arguments: dict[str, Any]) -> "McpToolResponse":
        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, _mcp_tool_response_cls()):
            return workflow_instance_id

        attempt_id = _parse_required_uuid_argument(arguments, "attempt_id")
        if isinstance(attempt_id, _mcp_tool_response_cls()):
            return attempt_id

        workflow_status = _parse_required_workflow_status_argument(arguments)
        if isinstance(workflow_status, _mcp_tool_response_cls()):
            return workflow_status

        summary = _parse_optional_string_argument(arguments, "summary")
        if isinstance(summary, _mcp_tool_response_cls()):
            return summary

        verify_status = _parse_optional_verify_status_argument(arguments)
        if isinstance(verify_status, _mcp_tool_response_cls()):
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
        if isinstance(failure_reason, _mcp_tool_response_cls()):
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
    server: "CtxLedgerServer",
):
    def _handler(arguments: dict[str, Any]) -> "McpToolResponse":
        workspace_id = _parse_required_uuid_argument(arguments, "workspace_id")
        if isinstance(workspace_id, _mcp_tool_response_cls()):
            return workspace_id

        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, _mcp_tool_response_cls()):
            return workflow_instance_id

        projection_type = _parse_optional_projection_type_argument(arguments)
        if isinstance(projection_type, _mcp_tool_response_cls()):
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
    server: "CtxLedgerServer",
):
    def _handler(arguments: dict[str, Any]) -> "McpToolResponse":
        workspace_id = _parse_required_uuid_argument(arguments, "workspace_id")
        if isinstance(workspace_id, _mcp_tool_response_cls()):
            return workspace_id

        workflow_instance_id = _parse_required_uuid_argument(
            arguments,
            "workflow_instance_id",
        )
        if isinstance(workflow_instance_id, _mcp_tool_response_cls()):
            return workflow_instance_id

        projection_type = _parse_optional_projection_type_argument(arguments)
        if isinstance(projection_type, _mcp_tool_response_cls()):
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
    def _handler(arguments: dict[str, Any]) -> "McpToolResponse":
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
            from ..runtime.serializers import serialize_stub_response

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
    def _handler(arguments: dict[str, Any]) -> "McpToolResponse":
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
            from ..runtime.serializers import serialize_stub_response

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
    def _handler(arguments: dict[str, Any]) -> "McpToolResponse":
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
            from ..runtime.serializers import serialize_stub_response

            return build_mcp_success_response(serialize_stub_response(response))
        except MemoryServiceError as exc:
            return build_mcp_error_response(
                code=exc.code.value,
                message=exc.message,
                details=exc.details,
            )

    return _handler

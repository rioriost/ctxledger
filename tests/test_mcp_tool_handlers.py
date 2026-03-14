from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.mcp.tool_handlers import (
    _map_workflow_error_to_mcp_response,
    _mcp_tool_response_cls,
    _parse_optional_dict_argument,
    _parse_optional_projection_type_argument,
    _parse_optional_string_argument,
    _parse_optional_verify_status_argument,
    _parse_required_string_argument,
    _parse_required_uuid_argument,
    _parse_required_workflow_status_argument,
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
from ctxledger.memory.service import (
    GetContextResponse,
    MemoryErrorCode,
    MemoryFeature,
    MemoryServiceError,
    RememberEpisodeResponse,
    SearchMemoryResponse,
    SearchResultRecord,
    StubResponse,
)
from ctxledger.runtime.types import McpToolResponse, WorkflowResumeResponse
from ctxledger.workflow.service import (
    ProjectionArtifactType,
    VerifyStatus,
    WorkflowError,
    WorkflowInstanceStatus,
)


def test_mcp_tool_response_cls_returns_runtime_type() -> None:
    assert _mcp_tool_response_cls() is McpToolResponse


def test_build_mcp_success_response_wraps_result() -> None:
    response = build_mcp_success_response({"value": 1})

    assert response == McpToolResponse(
        payload={
            "ok": True,
            "result": {"value": 1},
        }
    )


def test_build_mcp_error_response_uses_empty_details_by_default() -> None:
    response = build_mcp_error_response(
        code="invalid_request",
        message="bad request",
    )

    assert response == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "bad request",
                "details": {},
            },
        }
    )


@pytest.mark.parametrize("raw_value", [None, "", "   ", 123])
def test_parse_required_uuid_argument_rejects_missing_or_invalid_type(
    raw_value: object,
) -> None:
    result = _parse_required_uuid_argument(
        {"workflow_instance_id": raw_value}, "workflow_instance_id"
    )

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "workflow_instance_id must be a non-empty string",
                "details": {"field": "workflow_instance_id"},
            },
        }
    )


def test_parse_required_uuid_argument_rejects_invalid_uuid() -> None:
    result = _parse_required_uuid_argument(
        {"workflow_instance_id": "not-a-uuid"},
        "workflow_instance_id",
    )

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "workflow_instance_id must be a valid UUID",
                "details": {"field": "workflow_instance_id"},
            },
        }
    )


def test_parse_required_uuid_argument_returns_uuid() -> None:
    value = uuid4()

    result = _parse_required_uuid_argument(
        {"workflow_instance_id": str(value)},
        "workflow_instance_id",
    )

    assert result == value


def test_parse_optional_projection_type_argument_returns_none_when_missing() -> None:
    assert _parse_optional_projection_type_argument({}) is None


@pytest.mark.parametrize("raw_value", ["", "   ", 1])
def test_parse_optional_projection_type_argument_rejects_blank_or_non_string(
    raw_value: object,
) -> None:
    result = _parse_optional_projection_type_argument({"projection_type": raw_value})

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "projection_type must be a non-empty string when provided",
                "details": {"field": "projection_type"},
            },
        }
    )


def test_parse_optional_projection_type_argument_rejects_unknown_value() -> None:
    result = _parse_optional_projection_type_argument({"projection_type": "unknown"})

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "projection_type must be a supported projection artifact type",
                "details": {
                    "field": "projection_type",
                    "allowed_values": ["resume_json", "resume_md"],
                },
            },
        }
    )


def test_parse_optional_projection_type_argument_returns_enum_value() -> None:
    assert (
        _parse_optional_projection_type_argument({"projection_type": "resume_json"})
        is ProjectionArtifactType.RESUME_JSON
    )


@pytest.mark.parametrize("raw_value", [None, "", "   ", 1])
def test_parse_required_string_argument_rejects_invalid_values(
    raw_value: object,
) -> None:
    result = _parse_required_string_argument({"field": raw_value}, "field")

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "field must be a non-empty string",
                "details": {"field": "field"},
            },
        }
    )


def test_parse_required_string_argument_strips_value() -> None:
    assert _parse_required_string_argument({"field": "  hello  "}, "field") == "hello"


def test_parse_optional_string_argument_returns_none_when_missing() -> None:
    assert _parse_optional_string_argument({}, "summary") is None


def test_parse_optional_string_argument_rejects_non_string() -> None:
    result = _parse_optional_string_argument({"summary": 1}, "summary")

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "summary must be a string when provided",
                "details": {"field": "summary"},
            },
        }
    )


def test_parse_optional_string_argument_returns_string_without_stripping() -> None:
    assert (
        _parse_optional_string_argument({"summary": "  value  "}, "summary")
        == "  value  "
    )


def test_parse_optional_dict_argument_returns_empty_dict_when_missing() -> None:
    assert _parse_optional_dict_argument({}, "metadata") == {}


def test_parse_optional_dict_argument_rejects_non_dict() -> None:
    result = _parse_optional_dict_argument({"metadata": []}, "metadata")

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "metadata must be an object when provided",
                "details": {"field": "metadata"},
            },
        }
    )


def test_parse_optional_dict_argument_returns_copied_dict() -> None:
    source = {"a": 1}
    result = _parse_optional_dict_argument({"metadata": source}, "metadata")

    assert result == source
    assert result is not source


def test_parse_optional_verify_status_argument_returns_none_when_missing() -> None:
    assert _parse_optional_verify_status_argument({}) is None


@pytest.mark.parametrize("raw_value", ["", "   ", 1])
def test_parse_optional_verify_status_argument_rejects_invalid_values(
    raw_value: object,
) -> None:
    result = _parse_optional_verify_status_argument({"verify_status": raw_value})

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "verify_status must be a non-empty string when provided",
                "details": {"field": "verify_status"},
            },
        }
    )


def test_parse_optional_verify_status_argument_rejects_unknown_value() -> None:
    result = _parse_optional_verify_status_argument({"verify_status": "unknown"})

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "verify_status must be a supported verification status",
                "details": {
                    "field": "verify_status",
                    "allowed_values": ["pending", "passed", "failed", "skipped"],
                },
            },
        }
    )


def test_parse_optional_verify_status_argument_returns_enum() -> None:
    assert (
        _parse_optional_verify_status_argument({"verify_status": "passed"})
        is VerifyStatus.PASSED
    )


@pytest.mark.parametrize("raw_value", [None, "", "   ", 1])
def test_parse_required_workflow_status_argument_rejects_invalid_values(
    raw_value: object,
) -> None:
    result = _parse_required_workflow_status_argument({"workflow_status": raw_value})

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "workflow_status must be a non-empty string",
                "details": {"field": "workflow_status"},
            },
        }
    )


def test_parse_required_workflow_status_argument_rejects_unknown_value() -> None:
    result = _parse_required_workflow_status_argument({"workflow_status": "weird"})

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "workflow_status must be a supported workflow status",
                "details": {
                    "field": "workflow_status",
                    "allowed_values": ["running", "completed", "failed", "cancelled"],
                },
            },
        }
    )


def test_parse_required_workflow_status_argument_returns_enum() -> None:
    assert (
        _parse_required_workflow_status_argument({"workflow_status": "completed"})
        is WorkflowInstanceStatus.COMPLETED
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("validation_error", "invalid_request"),
        ("authentication_error", "invalid_request"),
        ("active_workflow_exists", "invalid_request"),
        ("workspace_registration_conflict", "invalid_request"),
        ("invalid_state_transition", "invalid_request"),
        ("workflow_attempt_mismatch", "invalid_request"),
        ("workspace_not_found", "not_found"),
        ("workflow_not_found", "not_found"),
        ("attempt_not_found", "not_found"),
        ("not_found", "not_found"),
        ("unexpected", "server_error"),
    ],
)
def test_map_workflow_error_to_mcp_response_maps_workflow_error_codes(
    code: str,
    expected: str,
) -> None:
    exc = WorkflowError("boom", details={"x": 1})
    exc.code = code

    response = _map_workflow_error_to_mcp_response(
        exc,
        default_message="fallback",
    )

    assert response == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": expected,
                "message": "boom",
                "details": {"x": 1},
            },
        }
    )


@pytest.mark.parametrize(
    ("message", "expected_code"),
    [
        ("resource not found", "not_found"),
        ("invalid transition", "invalid_request"),
        ("attempt mismatch", "invalid_request"),
        ("already exists", "invalid_request"),
        ("internal boom", "server_error"),
    ],
)
def test_map_workflow_error_to_mcp_response_maps_generic_exceptions(
    message: str,
    expected_code: str,
) -> None:
    response = _map_workflow_error_to_mcp_response(
        RuntimeError(message),
        default_message="fallback",
    )

    assert response == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": expected_code,
                "message": message,
                "details": {},
            },
        }
    )


def test_map_workflow_error_to_mcp_response_uses_default_message_for_empty_exception() -> (
    None
):
    response = _map_workflow_error_to_mcp_response(
        RuntimeError(""),
        default_message="fallback",
    )

    assert response == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "server_error",
                "message": "fallback",
                "details": {},
            },
        }
    )


@dataclass
class FakeWorkflowService:
    register_result: object | None = None
    start_result: object | None = None
    checkpoint_result: object | None = None
    complete_result: object | None = None
    ignore_result: int = 0
    resolve_result: int = 0
    register_exc: Exception | None = None
    start_exc: Exception | None = None
    checkpoint_exc: Exception | None = None
    complete_exc: Exception | None = None
    ignore_exc: Exception | None = None
    resolve_exc: Exception | None = None
    register_calls: list[object] | None = None
    start_calls: list[object] | None = None
    checkpoint_calls: list[object] | None = None
    complete_calls: list[object] | None = None
    ignore_calls: list[dict[str, object]] | None = None
    resolve_calls: list[dict[str, object]] | None = None

    def __post_init__(self) -> None:
        self.register_calls = []
        self.start_calls = []
        self.checkpoint_calls = []
        self.complete_calls = []
        self.ignore_calls = []
        self.resolve_calls = []

    def register_workspace(self, data: object) -> object:
        assert self.register_calls is not None
        self.register_calls.append(data)
        if self.register_exc is not None:
            raise self.register_exc
        assert self.register_result is not None
        return self.register_result

    def start_workflow(self, data: object) -> object:
        assert self.start_calls is not None
        self.start_calls.append(data)
        if self.start_exc is not None:
            raise self.start_exc
        assert self.start_result is not None
        return self.start_result

    def create_checkpoint(self, data: object) -> object:
        assert self.checkpoint_calls is not None
        self.checkpoint_calls.append(data)
        if self.checkpoint_exc is not None:
            raise self.checkpoint_exc
        assert self.checkpoint_result is not None
        return self.checkpoint_result

    def complete_workflow(self, data: object) -> object:
        assert self.complete_calls is not None
        self.complete_calls.append(data)
        if self.complete_exc is not None:
            raise self.complete_exc
        assert self.complete_result is not None
        return self.complete_result

    def ignore_resume_projection_failures(
        self,
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object,
    ) -> int:
        assert self.ignore_calls is not None
        self.ignore_calls.append(
            {
                "workspace_id": workspace_id,
                "workflow_instance_id": workflow_instance_id,
                "projection_type": projection_type,
            }
        )
        if self.ignore_exc is not None:
            raise self.ignore_exc
        return self.ignore_result

    def resolve_resume_projection_failures(
        self,
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object,
    ) -> int:
        assert self.resolve_calls is not None
        self.resolve_calls.append(
            {
                "workspace_id": workspace_id,
                "workflow_instance_id": workflow_instance_id,
                "projection_type": projection_type,
            }
        )
        if self.resolve_exc is not None:
            raise self.resolve_exc
        return self.resolve_result


def make_server(
    *,
    workflow_service: object | None = None,
    workflow_resume_response: WorkflowResumeResponse | None = None,
) -> object:
    if workflow_resume_response is None:
        workflow_resume_response = WorkflowResumeResponse(
            status_code=200,
            payload={"workflow": {"status": "ok"}},
            headers={"content-type": "application/json"},
        )

    class FakeServer:
        def __init__(self) -> None:
            self.workflow_service = workflow_service
            self.resume_calls: list[object] = []

        def build_workflow_resume_response(
            self, workflow_instance_id: object
        ) -> WorkflowResumeResponse:
            self.resume_calls.append(workflow_instance_id)
            return workflow_resume_response

    return FakeServer()


def test_build_resume_workflow_tool_handler_rejects_invalid_uuid() -> None:
    handler = build_resume_workflow_tool_handler(make_server())

    response = handler({"workflow_instance_id": "bad"})

    assert response.payload["ok"] is False
    assert response.payload["error"]["code"] == "invalid_request"


def test_build_resume_workflow_tool_handler_maps_non_200_response() -> None:
    handler = build_resume_workflow_tool_handler(
        make_server(
            workflow_resume_response=WorkflowResumeResponse(
                status_code=404,
                payload={"error": {"code": "not_found", "message": "missing"}},
                headers={"content-type": "application/json"},
            )
        )
    )

    response = handler({"workflow_instance_id": str(uuid4())})

    assert response == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "not_found",
                "message": "missing",
                "details": {},
            },
        }
    )


def test_build_resume_workflow_tool_handler_returns_success_payload() -> None:
    workflow_instance_id = uuid4()
    server = make_server(
        workflow_resume_response=WorkflowResumeResponse(
            status_code=200,
            payload={"resume": {"id": str(workflow_instance_id)}},
            headers={"content-type": "application/json"},
        )
    )
    handler = build_resume_workflow_tool_handler(server)

    response = handler({"workflow_instance_id": str(workflow_instance_id)})

    assert response == McpToolResponse(
        payload={
            "ok": True,
            "result": {"resume": {"id": str(workflow_instance_id)}},
        }
    )
    assert server.resume_calls == [workflow_instance_id]


def test_build_workspace_register_tool_handler_rejects_invalid_workspace_id() -> None:
    handler = build_workspace_register_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "repo_url": "https://example.com/repo.git",
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
            "workspace_id": "bad",
        }
    )

    assert response.payload["error"]["message"] == "workspace_id must be a valid UUID"


def test_build_workspace_register_tool_handler_rejects_non_dict_metadata() -> None:
    handler = build_workspace_register_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "repo_url": "https://example.com/repo.git",
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
            "metadata": [],
        }
    )

    assert (
        response.payload["error"]["message"]
        == "metadata must be an object when provided"
    )


def test_build_workspace_register_tool_handler_requires_server_workflow_service() -> (
    None
):
    handler = build_workspace_register_tool_handler(make_server(workflow_service=None))

    response = handler(
        {
            "repo_url": "https://example.com/repo.git",
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
        }
    )

    assert response == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "server_not_ready",
                "message": "workflow service is not initialized",
                "details": {},
            },
        }
    )


def test_build_workspace_register_tool_handler_maps_workflow_error() -> None:
    service = FakeWorkflowService(
        register_exc=WorkflowError(
            "workspace exists",
            details={"repo_url": "https://example.com/repo.git"},
        )
    )
    assert service.register_exc is not None
    service.register_exc.code = "workspace_registration_conflict"
    handler = build_workspace_register_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "repo_url": "https://example.com/repo.git",
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
        }
    )

    assert response.payload["error"]["code"] == "invalid_request"
    assert response.payload["error"]["details"] == {
        "repo_url": "https://example.com/repo.git"
    }


def test_build_workspace_register_tool_handler_returns_success() -> None:
    now = datetime(2024, 1, 1, tzinfo=UTC)
    workspace_id = uuid4()
    workspace = SimpleNamespace(
        workspace_id=workspace_id,
        repo_url="https://example.com/repo.git",
        canonical_path="/tmp/repo",
        default_branch="main",
        metadata={"team": "platform"},
        created_at=now,
        updated_at=now,
    )
    service = FakeWorkflowService(register_result=workspace)
    handler = build_workspace_register_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workspace_id": str(workspace_id),
            "repo_url": "https://example.com/repo.git",
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
            "metadata": {"team": "platform"},
        }
    )

    assert response.payload == {
        "ok": True,
        "result": {
            "workspace_id": str(workspace_id),
            "repo_url": "https://example.com/repo.git",
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
            "metadata": {"team": "platform"},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
    }
    assert service.register_calls is not None
    call = service.register_calls[0]
    assert call.workspace_id == workspace_id
    assert call.metadata == {"team": "platform"}


def test_build_workflow_start_tool_handler_requires_service() -> None:
    handler = build_workflow_start_tool_handler(make_server(workflow_service=None))

    response = handler({"workspace_id": str(uuid4()), "ticket_id": "T-1"})

    assert response.payload["error"]["code"] == "server_not_ready"


def test_build_workflow_start_tool_handler_maps_exception() -> None:
    service = FakeWorkflowService(start_exc=RuntimeError("workspace not found"))
    handler = build_workflow_start_tool_handler(make_server(workflow_service=service))

    response = handler({"workspace_id": str(uuid4()), "ticket_id": "T-1"})

    assert response.payload["error"]["code"] == "not_found"


def test_build_workflow_start_tool_handler_returns_success() -> None:
    now = datetime(2024, 1, 1, tzinfo=UTC)
    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    workspace_id = uuid4()
    result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
            ticket_id="T-1",
            status=WorkflowInstanceStatus.RUNNING,
            created_at=now,
        ),
        attempt=SimpleNamespace(
            attempt_id=attempt_id,
            status=SimpleNamespace(value="running"),
        ),
    )
    service = FakeWorkflowService(start_result=result)
    handler = build_workflow_start_tool_handler(make_server(workflow_service=service))

    response = handler(
        {
            "workspace_id": str(workspace_id),
            "ticket_id": "T-1",
            "metadata": {"priority": "high"},
        }
    )

    assert response.payload == {
        "ok": True,
        "result": {
            "workflow_instance_id": str(workflow_instance_id),
            "attempt_id": str(attempt_id),
            "workspace_id": str(workspace_id),
            "ticket_id": "T-1",
            "workflow_status": "running",
            "attempt_status": "running",
            "created_at": now.isoformat(),
        },
    }
    assert service.start_calls is not None
    assert service.start_calls[0].metadata == {"priority": "high"}


def test_build_workflow_checkpoint_tool_handler_rejects_invalid_verify_report_type() -> (
    None
):
    handler = build_workflow_checkpoint_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "step_name": "implement",
            "verify_report": [],
        }
    )

    assert (
        response.payload["error"]["message"]
        == "verify_report must be an object when provided"
    )


def test_build_workflow_checkpoint_tool_handler_requires_service() -> None:
    handler = build_workflow_checkpoint_tool_handler(make_server(workflow_service=None))

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "step_name": "implement",
        }
    )

    assert response.payload["error"]["code"] == "server_not_ready"


def test_build_workflow_checkpoint_tool_handler_maps_exception() -> None:
    service = FakeWorkflowService(
        checkpoint_exc=WorkflowError(
            "attempt not found",
            details={"attempt_id": "x"},
        )
    )
    assert service.checkpoint_exc is not None
    service.checkpoint_exc.code = "attempt_not_found"
    handler = build_workflow_checkpoint_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "step_name": "implement",
        }
    )

    assert response.payload["error"]["code"] == "not_found"
    assert response.payload["error"]["details"] == {"attempt_id": "x"}


def test_build_workflow_checkpoint_tool_handler_returns_verify_report_status_when_present() -> (
    None
):
    now = datetime(2024, 1, 1, tzinfo=UTC)
    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    checkpoint_id = uuid4()
    result = SimpleNamespace(
        checkpoint=SimpleNamespace(
            checkpoint_id=checkpoint_id,
            step_name="implement",
            created_at=now,
        ),
        workflow_instance=SimpleNamespace(workflow_instance_id=workflow_instance_id),
        attempt=SimpleNamespace(
            attempt_id=attempt_id,
            verify_status=VerifyStatus.FAILED,
        ),
        verify_report=SimpleNamespace(status=VerifyStatus.PASSED),
    )
    service = FakeWorkflowService(checkpoint_result=result)
    handler = build_workflow_checkpoint_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workflow_instance_id": str(workflow_instance_id),
            "attempt_id": str(attempt_id),
            "step_name": "implement",
            "summary": "done",
            "checkpoint_json": {"a": 1},
            "verify_status": "failed",
            "verify_report": {"status": "passed"},
        }
    )

    assert response.payload == {
        "ok": True,
        "result": {
            "checkpoint_id": str(checkpoint_id),
            "workflow_instance_id": str(workflow_instance_id),
            "attempt_id": str(attempt_id),
            "step_name": "implement",
            "created_at": now.isoformat(),
            "latest_verify_status": "passed",
        },
    }
    assert service.checkpoint_calls is not None
    call = service.checkpoint_calls[0]
    assert call.summary == "done"
    assert call.checkpoint_json == {"a": 1}
    assert call.verify_status is VerifyStatus.FAILED
    assert call.verify_report == {"status": "passed"}


def test_build_workflow_checkpoint_tool_handler_falls_back_to_attempt_verify_status() -> (
    None
):
    now = datetime(2024, 1, 1, tzinfo=UTC)
    result = SimpleNamespace(
        checkpoint=SimpleNamespace(
            checkpoint_id=uuid4(),
            step_name="implement",
            created_at=now,
        ),
        workflow_instance=SimpleNamespace(workflow_instance_id=uuid4()),
        attempt=SimpleNamespace(
            attempt_id=uuid4(),
            verify_status=VerifyStatus.PASSED,
        ),
        verify_report=None,
    )
    service = FakeWorkflowService(checkpoint_result=result)
    handler = build_workflow_checkpoint_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "step_name": "implement",
        }
    )

    assert response.payload["result"]["latest_verify_status"] == "passed"


def test_build_workflow_complete_tool_handler_rejects_invalid_verify_report_type() -> (
    None
):
    handler = build_workflow_complete_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "workflow_status": "completed",
            "verify_report": [],
        }
    )

    assert (
        response.payload["error"]["message"]
        == "verify_report must be an object when provided"
    )


def test_build_workflow_complete_tool_handler_requires_service() -> None:
    handler = build_workflow_complete_tool_handler(make_server(workflow_service=None))

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "workflow_status": "completed",
        }
    )

    assert response.payload["error"]["code"] == "server_not_ready"


def test_build_workflow_complete_tool_handler_maps_exception() -> None:
    service = FakeWorkflowService(complete_exc=RuntimeError("invalid transition"))
    handler = build_workflow_complete_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "workflow_status": "completed",
        }
    )

    assert response.payload["error"]["code"] == "invalid_request"


def test_build_workflow_complete_tool_handler_returns_verify_report_status_when_present() -> (
    None
):
    finished_at = datetime(2024, 1, 1, tzinfo=UTC)
    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=SimpleNamespace(
            attempt_id=attempt_id,
            status=SimpleNamespace(value="completed"),
            finished_at=finished_at,
            verify_status=VerifyStatus.FAILED,
        ),
        verify_report=SimpleNamespace(status=VerifyStatus.PASSED),
    )
    service = FakeWorkflowService(complete_result=result)
    handler = build_workflow_complete_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workflow_instance_id": str(workflow_instance_id),
            "attempt_id": str(attempt_id),
            "workflow_status": "completed",
            "summary": "done",
            "verify_status": "failed",
            "verify_report": {"status": "passed"},
            "failure_reason": "none",
        }
    )

    assert response.payload == {
        "ok": True,
        "result": {
            "workflow_instance_id": str(workflow_instance_id),
            "attempt_id": str(attempt_id),
            "workflow_status": "completed",
            "attempt_status": "completed",
            "finished_at": finished_at.isoformat(),
            "latest_verify_status": "passed",
        },
    }
    assert service.complete_calls is not None
    call = service.complete_calls[0]
    assert call.workflow_status is WorkflowInstanceStatus.COMPLETED
    assert call.verify_status is VerifyStatus.FAILED
    assert call.verify_report == {"status": "passed"}
    assert call.failure_reason == "none"


def test_build_workflow_complete_tool_handler_falls_back_to_attempt_verify_status() -> (
    None
):
    result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=uuid4(),
            status=WorkflowInstanceStatus.FAILED,
        ),
        attempt=SimpleNamespace(
            attempt_id=uuid4(),
            status=SimpleNamespace(value="failed"),
            finished_at=None,
            verify_status=VerifyStatus.FAILED,
        ),
        verify_report=None,
    )
    service = FakeWorkflowService(complete_result=result)
    handler = build_workflow_complete_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "workflow_status": "failed",
        }
    )

    assert response.payload["result"]["finished_at"] is None
    assert response.payload["result"]["latest_verify_status"] == "failed"


@pytest.mark.parametrize(
    ("message", "expected_code"),
    [
        ("workflow not found", "not_found"),
        ("workflow does not belong to workspace", "invalid_request"),
        ("attempt mismatch", "invalid_request"),
        ("boom", "server_error"),
    ],
)
def test_build_projection_failures_ignore_tool_handler_maps_exceptions(
    message: str,
    expected_code: str,
) -> None:
    service = FakeWorkflowService(ignore_exc=RuntimeError(message))
    handler = build_projection_failures_ignore_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "workflow_instance_id": str(uuid4()),
        }
    )

    assert response.payload["error"]["code"] == expected_code
    assert response.payload["error"]["message"] == message


def test_build_projection_failures_ignore_tool_handler_returns_success() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    service = FakeWorkflowService(ignore_result=3)
    handler = build_projection_failures_ignore_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workspace_id": str(workspace_id),
            "workflow_instance_id": str(workflow_instance_id),
            "projection_type": "resume_md",
        }
    )

    assert response.payload == {
        "ok": True,
        "result": {
            "workspace_id": str(workspace_id),
            "workflow_instance_id": str(workflow_instance_id),
            "projection_type": "resume_md",
            "updated_failure_count": 3,
            "status": "ignored",
        },
    }
    assert service.ignore_calls == [
        {
            "workspace_id": workspace_id,
            "workflow_instance_id": workflow_instance_id,
            "projection_type": ProjectionArtifactType.RESUME_MD,
        }
    ]


@pytest.mark.parametrize(
    ("message", "expected_code"),
    [
        ("workflow not found", "not_found"),
        ("workflow does not belong to workspace", "invalid_request"),
        ("attempt mismatch", "invalid_request"),
        ("boom", "server_error"),
    ],
)
def test_build_projection_failures_resolve_tool_handler_maps_exceptions(
    message: str,
    expected_code: str,
) -> None:
    service = FakeWorkflowService(resolve_exc=RuntimeError(message))
    handler = build_projection_failures_resolve_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "workflow_instance_id": str(uuid4()),
        }
    )

    assert response.payload["error"]["code"] == expected_code
    assert response.payload["error"]["message"] == message


def test_build_projection_failures_resolve_tool_handler_returns_success_without_projection_type() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    service = FakeWorkflowService(resolve_result=2)
    handler = build_projection_failures_resolve_tool_handler(
        make_server(workflow_service=service)
    )

    response = handler(
        {
            "workspace_id": str(workspace_id),
            "workflow_instance_id": str(workflow_instance_id),
        }
    )

    assert response.payload == {
        "ok": True,
        "result": {
            "workspace_id": str(workspace_id),
            "workflow_instance_id": str(workflow_instance_id),
            "projection_type": None,
            "updated_failure_count": 2,
            "status": "resolved",
        },
    }
    assert service.resolve_calls == [
        {
            "workspace_id": workspace_id,
            "workflow_instance_id": workflow_instance_id,
            "projection_type": None,
        }
    ]


def test_build_workspace_register_tool_handler_rejects_missing_repo_url() -> None:
    handler = build_workspace_register_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "repo_url must be a non-empty string",
            "details": {"field": "repo_url"},
        },
    }


def test_build_workspace_register_tool_handler_rejects_missing_canonical_path() -> None:
    handler = build_workspace_register_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "repo_url": "https://example.com/repo.git",
            "default_branch": "main",
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "canonical_path must be a non-empty string",
            "details": {"field": "canonical_path"},
        },
    }


def test_build_workspace_register_tool_handler_rejects_missing_default_branch() -> None:
    handler = build_workspace_register_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "repo_url": "https://example.com/repo.git",
            "canonical_path": "/tmp/repo",
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "default_branch must be a non-empty string",
            "details": {"field": "default_branch"},
        },
    }


def test_build_workflow_start_tool_handler_rejects_missing_workspace_id() -> None:
    handler = build_workflow_start_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler({"ticket_id": "T-1"})

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workspace_id must be a non-empty string",
            "details": {"field": "workspace_id"},
        },
    }


def test_build_workflow_start_tool_handler_rejects_missing_ticket_id() -> None:
    handler = build_workflow_start_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler({"workspace_id": str(uuid4())})

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "ticket_id must be a non-empty string",
            "details": {"field": "ticket_id"},
        },
    }


def test_build_workflow_checkpoint_tool_handler_rejects_missing_workflow_instance_id() -> (
    None
):
    handler = build_workflow_checkpoint_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "attempt_id": str(uuid4()),
            "step_name": "implement",
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workflow_instance_id must be a non-empty string",
            "details": {"field": "workflow_instance_id"},
        },
    }


def test_build_workflow_checkpoint_tool_handler_rejects_missing_attempt_id() -> None:
    handler = build_workflow_checkpoint_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "step_name": "implement",
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "attempt_id must be a non-empty string",
            "details": {"field": "attempt_id"},
        },
    }


def test_build_workflow_checkpoint_tool_handler_rejects_missing_step_name() -> None:
    handler = build_workflow_checkpoint_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "step_name must be a non-empty string",
            "details": {"field": "step_name"},
        },
    }


def test_build_workflow_complete_tool_handler_rejects_missing_workflow_instance_id() -> (
    None
):
    handler = build_workflow_complete_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "attempt_id": str(uuid4()),
            "workflow_status": "completed",
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workflow_instance_id must be a non-empty string",
            "details": {"field": "workflow_instance_id"},
        },
    }


def test_build_workflow_complete_tool_handler_rejects_missing_attempt_id() -> None:
    handler = build_workflow_complete_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "workflow_status": "completed",
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "attempt_id must be a non-empty string",
            "details": {"field": "attempt_id"},
        },
    }


def test_build_workflow_complete_tool_handler_rejects_missing_workflow_status() -> None:
    handler = build_workflow_complete_tool_handler(
        make_server(workflow_service=FakeWorkflowService())
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workflow_status must be a non-empty string",
            "details": {"field": "workflow_status"},
        },
    }


def test_build_projection_failures_ignore_tool_handler_requires_service() -> None:
    handler = build_projection_failures_ignore_tool_handler(
        make_server(workflow_service=None)
    )

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "workflow_instance_id": str(uuid4()),
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_projection_failures_resolve_tool_handler_requires_service() -> None:
    handler = build_projection_failures_resolve_tool_handler(
        make_server(workflow_service=None)
    )

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "workflow_instance_id": str(uuid4()),
        }
    )

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


@dataclass
class FakeMemoryService:
    remember_result: object | None = None
    search_result: object | None = None
    context_result: object | None = None
    remember_exc: Exception | None = None
    search_exc: Exception | None = None
    context_exc: Exception | None = None
    remember_calls: list[object] | None = None
    search_calls: list[object] | None = None
    context_calls: list[object] | None = None

    def __post_init__(self) -> None:
        self.remember_calls = []
        self.search_calls = []
        self.context_calls = []

    def remember_episode(self, request: object) -> object:
        assert self.remember_calls is not None
        self.remember_calls.append(request)
        if self.remember_exc is not None:
            raise self.remember_exc
        assert self.remember_result is not None
        return self.remember_result

    def search(self, request: object) -> object:
        assert self.search_calls is not None
        self.search_calls.append(request)
        if self.search_exc is not None:
            raise self.search_exc
        assert self.search_result is not None
        return self.search_result

    def get_context(self, request: object) -> object:
        assert self.context_calls is not None
        self.context_calls.append(request)
        if self.context_exc is not None:
            raise self.context_exc
        assert self.context_result is not None
        return self.context_result


def make_stub_response() -> StubResponse:
    return StubResponse(
        feature=MemoryFeature.REMEMBER_EPISODE,
        implemented=False,
        message="ok",
        status="not_implemented",
        available_in_version="0.1.0",
        details={"value": 1, "source": "test"},
    )


def make_remember_episode_response() -> RememberEpisodeResponse:
    from ctxledger.memory.service import EpisodeRecord, MemoryFeature

    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    created_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)

    return RememberEpisodeResponse(
        feature=MemoryFeature.REMEMBER_EPISODE,
        implemented=True,
        message="Episode recorded successfully.",
        status="recorded",
        available_in_version="0.2.0",
        timestamp=created_at,
        episode=EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            summary="remember this",
            attempt_id=attempt_id,
            metadata={"kind": "checkpoint"},
            status="recorded",
            created_at=created_at,
            updated_at=created_at,
        ),
        details={
            "workflow_instance_id": str(workflow_instance_id),
            "attempt_id": str(attempt_id),
        },
    )


def test_build_memory_remember_episode_tool_handler_returns_success() -> None:
    service = FakeMemoryService(remember_result=make_remember_episode_response())
    handler = build_memory_remember_episode_tool_handler(service)

    response = handler(
        {
            "workflow_instance_id": uuid4(),
            "summary": "remember this",
            "attempt_id": uuid4(),
            "metadata": {"kind": "checkpoint"},
        }
    )

    assert response.payload["ok"] is True
    assert response.payload["result"]["feature"] == "memory_remember_episode"
    assert response.payload["result"]["implemented"] is True
    assert response.payload["result"]["message"] == "Episode recorded successfully."
    assert response.payload["result"]["status"] == "recorded"
    assert response.payload["result"]["available_in_version"] == "0.2.0"
    assert "timestamp" in response.payload["result"]
    assert response.payload["result"]["episode"]["summary"] == "remember this"
    assert response.payload["result"]["episode"]["metadata"] == {"kind": "checkpoint"}
    assert response.payload["result"]["episode"]["status"] == "recorded"
    assert response.payload["result"]["details"]["workflow_instance_id"]
    assert response.payload["result"]["details"]["attempt_id"]
    assert service.remember_calls is not None
    call = service.remember_calls[0]
    assert isinstance(call.workflow_instance_id, str)
    assert call.summary == "remember this"
    assert isinstance(call.attempt_id, str)
    assert call.metadata == {"kind": "checkpoint"}


def test_build_memory_remember_episode_tool_handler_maps_memory_error() -> None:
    service = FakeMemoryService(
        remember_exc=MemoryServiceError(
            MemoryErrorCode.INVALID_REQUEST,
            "bad episode",
            feature="memory_remember_episode",
            details={"field": "summary"},
        )
    )
    handler = build_memory_remember_episode_tool_handler(service)

    response = handler({"summary": ""})

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "memory_invalid_request",
            "message": "bad episode",
            "details": {"field": "summary"},
        },
    }


def test_build_memory_search_tool_handler_uses_defaults_for_invalid_optional_values() -> (
    None
):
    created_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    workspace_id = uuid4()
    attempt_id = uuid4()
    episode_id = uuid4()
    memory_id = uuid4()
    service = FakeMemoryService(
        search_result=SearchMemoryResponse(
            feature=MemoryFeature.SEARCH,
            implemented=True,
            message="Hybrid lexical and semantic memory search completed successfully.",
            status="ok",
            available_in_version="0.3.0",
            timestamp=created_at,
            results=(
                SearchResultRecord(
                    memory_id=memory_id,
                    workspace_id=workspace_id,
                    episode_id=episode_id,
                    workflow_instance_id=None,
                    summary="needle found in summary",
                    attempt_id=attempt_id,
                    metadata={"kind": "checkpoint"},
                    score=3.0,
                    matched_fields=("content",),
                    lexical_score=3.0,
                    semantic_score=0.0,
                    ranking_details={
                        "lexical_component": 3.0,
                        "semantic_component": 0.0,
                        "score_mode": "lexical_only",
                        "semantic_only_discount_applied": False,
                    },
                    created_at=created_at,
                    updated_at=created_at,
                ),
            ),
            details={
                "query": "needle",
                "normalized_query": "needle",
                "workspace_id": str(workspace_id),
                "limit": 10,
                "filters": {},
                "search_mode": "hybrid_memory_item_search",
                "memory_items_considered": 1,
                "semantic_candidates_considered": 1,
                "semantic_query_generated": True,
                "hybrid_scoring": {
                    "lexical_weight": 1.0,
                    "semantic_weight": 1.0,
                    "semantic_only_discount": 0.75,
                },
                "result_mode_counts": {
                    "hybrid": 0,
                    "lexical_only": 1,
                    "semantic_only_discounted": 0,
                },
                "result_composition": {
                    "with_lexical_signal": 1,
                    "with_semantic_signal": 0,
                    "with_both_signals": 0,
                },
                "results_returned": 1,
            },
        )
    )
    handler = build_memory_search_tool_handler(service)

    response = handler(
        {
            "query": "needle",
            "workspace_id": uuid4(),
            "limit": "bad",
            "filters": [],
        }
    )

    assert response.payload["ok"] is True
    assert response.payload["result"]["feature"] == "memory_search"
    assert response.payload["result"]["implemented"] is True
    assert (
        response.payload["result"]["message"]
        == "Hybrid lexical and semantic memory search completed successfully."
    )
    assert response.payload["result"]["status"] == "ok"
    assert response.payload["result"]["available_in_version"] == "0.3.0"
    assert response.payload["result"]["details"] == {
        "query": "needle",
        "normalized_query": "needle",
        "workspace_id": str(workspace_id),
        "limit": 10,
        "filters": {},
        "search_mode": "hybrid_memory_item_search",
        "memory_items_considered": 1,
        "semantic_candidates_considered": 1,
        "semantic_query_generated": True,
        "hybrid_scoring": {
            "lexical_weight": 1.0,
            "semantic_weight": 1.0,
            "semantic_only_discount": 0.75,
        },
        "result_mode_counts": {
            "lexical_only": 1,
            "hybrid": 0,
            "semantic_only_discounted": 0,
        },
        "result_composition": {
            "with_lexical_signal": 1,
            "with_semantic_signal": 0,
            "with_both_signals": 0,
        },
        "results_returned": 1,
    }
    assert "timestamp" in response.payload["result"]
    assert response.payload["result"]["results"] == [
        {
            "memory_id": str(memory_id),
            "workspace_id": str(workspace_id),
            "episode_id": str(episode_id),
            "workflow_instance_id": None,
            "summary": "needle found in summary",
            "attempt_id": str(attempt_id),
            "metadata": {"kind": "checkpoint"},
            "score": 3.0,
            "matched_fields": ["content"],
            "lexical_score": 3.0,
            "semantic_score": 0.0,
            "ranking_details": {
                "lexical_component": 3.0,
                "semantic_component": 0.0,
                "score_mode": "lexical_only",
                "semantic_only_discount_applied": False,
            },
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
    ]
    assert service.search_calls is not None
    call = service.search_calls[0]
    assert call.query == "needle"
    assert isinstance(call.workspace_id, str)
    assert call.limit == 10
    assert call.filters == {}


def test_build_memory_search_tool_handler_maps_memory_error() -> None:
    service = FakeMemoryService(
        search_exc=MemoryServiceError(
            MemoryErrorCode.INVALID_REQUEST,
            "not found",
            feature="memory_search",
            details={"query": "needle"},
        )
    )
    handler = build_memory_search_tool_handler(service)

    response = handler({"query": "needle"})

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "memory_invalid_request",
            "message": "not found",
            "details": {"query": "needle"},
        },
    }


def test_build_memory_get_context_tool_handler_uses_defaults_for_optional_values() -> (
    None
):
    created_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    workflow_instance_id = uuid4()
    service = FakeMemoryService(
        context_result=GetContextResponse(
            feature=MemoryFeature.GET_CONTEXT,
            implemented=True,
            message="Episode-oriented memory context retrieved successfully.",
            status="ok",
            available_in_version="0.2.0",
            timestamp=created_at,
            episodes=(),
            details={"episodes_returned": 0},
        )
    )
    handler = build_memory_get_context_tool_handler(service)

    response = handler(
        {
            "query": 123,
            "workspace_id": uuid4(),
            "workflow_instance_id": workflow_instance_id,
            "ticket_id": 999,
            "limit": "bad",
            "include_episodes": "bad",
            "include_memory_items": "bad",
            "include_summaries": "bad",
        }
    )

    assert response.payload["ok"] is True
    assert response.payload["result"]["feature"] == "memory_get_context"
    assert response.payload["result"]["implemented"] is True
    assert (
        response.payload["result"]["message"]
        == "Episode-oriented memory context retrieved successfully."
    )
    assert response.payload["result"]["status"] == "ok"
    assert response.payload["result"]["available_in_version"] == "0.2.0"
    assert response.payload["result"]["details"] == {"episodes_returned": 0}
    assert response.payload["result"]["episodes"] == []
    assert response.payload["result"]["timestamp"] == created_at.isoformat()
    assert service.context_calls is not None
    call = service.context_calls[0]
    assert call.query == "123"
    assert isinstance(call.workspace_id, str)
    assert isinstance(call.workflow_instance_id, str)
    assert call.ticket_id == "999"
    assert call.limit == 10
    assert call.include_episodes is True
    assert call.include_memory_items is True
    assert call.include_summaries is True


def test_build_memory_get_context_tool_handler_maps_memory_error() -> None:
    service = FakeMemoryService(
        context_exc=MemoryServiceError(
            MemoryErrorCode.INVALID_REQUEST,
            "bad context request",
            feature="memory_get_context",
            details={"field": "workspace_id"},
        )
    )
    handler = build_memory_get_context_tool_handler(service)

    response = handler({"workspace_id": "bad"})

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "memory_invalid_request",
            "message": "bad context request",
            "details": {"field": "workspace_id"},
        },
    }

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from ctxledger.mcp.tool_handlers import (
    build_resume_workflow_tool_handler,
    build_workflow_checkpoint_tool_handler,
    build_workflow_complete_tool_handler,
    build_workflow_start_tool_handler,
    build_workspace_register_tool_handler,
)
from ctxledger.runtime.types import McpToolResponse, WorkflowResumeResponse
from ctxledger.workflow.service import VerifyStatus, WorkflowInstanceStatus

from .conftest import (
    FakeWorkflowService,
    make_server,
    make_workflow_error,
    make_workspace_namespace,
)


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
                payload={
                    "error": {
                        "code": "not_found",
                        "message": "missing",
                        "details": {"workflow_instance_id": "wf-123"},
                    }
                },
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
                "details": {"workflow_instance_id": "wf-123"},
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

    assert response.payload["error"]["message"] == "metadata must be an object when provided"


def test_build_workspace_register_tool_handler_requires_server_workflow_service() -> None:
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
        register_exc=make_workflow_error(
            "workspace exists",
            code="workspace_registration_conflict",
            details={"repo_url": "https://example.com/repo.git"},
        )
    )
    handler = build_workspace_register_tool_handler(make_server(workflow_service=service))

    response = handler(
        {
            "repo_url": "https://example.com/repo.git",
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
        }
    )

    assert response.payload["error"]["code"] == "invalid_request"
    assert response.payload["error"]["details"] == {"repo_url": "https://example.com/repo.git"}


def test_build_workspace_register_tool_handler_returns_success() -> None:
    now = datetime(2024, 1, 1, tzinfo=UTC)
    workspace_id = uuid4()
    workspace = make_workspace_namespace(
        workspace_id=workspace_id,
        metadata={"team": "platform"},
        now=now,
    )
    service = FakeWorkflowService(register_result=workspace)
    handler = build_workspace_register_tool_handler(make_server(workflow_service=service))

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


def test_build_workflow_checkpoint_tool_handler_rejects_invalid_verify_report_type() -> None:
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

    assert response.payload["error"]["message"] == "verify_report must be an object when provided"


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
        checkpoint_exc=make_workflow_error(
            "attempt not found",
            code="attempt_not_found",
            details={"attempt_id": "x"},
        )
    )
    handler = build_workflow_checkpoint_tool_handler(make_server(workflow_service=service))

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "step_name": "implement",
        }
    )

    assert response.payload["error"]["code"] == "not_found"
    assert response.payload["error"]["details"] == {"attempt_id": "x"}


def test_build_workflow_checkpoint_tool_handler_returns_verify_report_status_when_present() -> None:
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
    handler = build_workflow_checkpoint_tool_handler(make_server(workflow_service=service))

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


def test_build_workflow_checkpoint_tool_handler_falls_back_to_attempt_verify_status() -> None:
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
    handler = build_workflow_checkpoint_tool_handler(make_server(workflow_service=service))

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "step_name": "implement",
        }
    )

    assert response.payload["result"]["latest_verify_status"] == "passed"


def test_build_workflow_complete_tool_handler_rejects_invalid_verify_report_type() -> None:
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

    assert response.payload["error"]["message"] == "verify_report must be an object when provided"


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
    handler = build_workflow_complete_tool_handler(make_server(workflow_service=service))

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "workflow_status": "completed",
        }
    )

    assert response.payload["error"]["code"] == "invalid_request"


def test_build_workflow_complete_tool_handler_returns_verify_report_status_when_present() -> None:
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
        warnings=(),
        auto_memory_details=None,
    )
    service = FakeWorkflowService(complete_result=result)
    handler = build_workflow_complete_tool_handler(make_server(workflow_service=service))

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
            "warnings": [],
            "auto_memory_details": None,
        },
    }
    assert service.complete_calls is not None
    call = service.complete_calls[0]
    assert call.workflow_status is WorkflowInstanceStatus.COMPLETED
    assert call.verify_status is VerifyStatus.FAILED
    assert call.verify_report == {"status": "passed"}
    assert call.failure_reason == "none"


def test_build_workflow_complete_tool_handler_falls_back_to_attempt_verify_status() -> None:
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
        warnings=(),
        auto_memory_details=None,
    )
    service = FakeWorkflowService(complete_result=result)
    handler = build_workflow_complete_tool_handler(make_server(workflow_service=service))

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "workflow_status": "failed",
        }
    )

    assert response.payload["result"]["finished_at"] is None
    assert response.payload["result"]["latest_verify_status"] == "failed"
    assert response.payload["result"]["warnings"] == []
    assert response.payload["result"]["auto_memory_details"] is None


def test_build_workflow_complete_tool_handler_preserves_summary_build_metadata() -> None:
    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    finished_at = datetime(2024, 1, 2, tzinfo=UTC)
    auto_memory_details = {
        "auto_memory_recorded": True,
        "summary_build": {
            "summary_build_attempted": True,
            "summary_build_succeeded": True,
            "summary_build_requested": True,
            "summary_build_status": "built",
            "summary_build_skipped_reason": None,
            "summary_build_trigger": "latest_checkpoint.build_episode_summary_true",
            "summary_build_scope": "workflow_completion_auto_memory_episode",
            "summary_build_kind": "episode_summary",
            "summary_build_replace_existing": True,
            "summary_build_non_fatal": True,
            "summary_build_replaced_existing_summary": False,
            "built_memory_summary_id": str(uuid4()),
            "built_summary_kind": "episode_summary",
            "built_summary_membership_count": 1,
        },
    }
    result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=SimpleNamespace(
            attempt_id=attempt_id,
            status=SimpleNamespace(value="completed"),
            finished_at=finished_at,
            verify_status=VerifyStatus.PASSED,
        ),
        verify_report=SimpleNamespace(status=VerifyStatus.PASSED),
        warnings=(),
        auto_memory_details=auto_memory_details,
    )
    service = FakeWorkflowService(complete_result=result)
    handler = build_workflow_complete_tool_handler(make_server(workflow_service=service))

    response = handler(
        {
            "workflow_instance_id": str(workflow_instance_id),
            "attempt_id": str(attempt_id),
            "workflow_status": "completed",
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
            "warnings": [],
            "auto_memory_details": auto_memory_details,
        },
    }


def test_build_workflow_complete_tool_handler_preserves_structured_auto_memory_stage_details() -> (
    None
):
    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    finished_at = datetime(2024, 1, 3, tzinfo=UTC)
    auto_memory_details = {
        "auto_memory_recorded": True,
        "episode_id": str(uuid4()),
        "memory_item_id": str(uuid4()),
        "promoted_memory_item_ids": [str(uuid4()), str(uuid4())],
        "promoted_memory_item_count": 2,
        "memory_relation_count": 1,
        "stage_details": {
            "gating": {
                "attempted": True,
                "status": "passed",
                "skipped_reason": None,
            },
            "promoted_memory_items": {
                "attempted": True,
                "status": "recorded",
                "created_count": 2,
                "created_memory_ids": [str(uuid4()), str(uuid4())],
                "created_types": [
                    "workflow_objective",
                    "workflow_next_action",
                ],
                "skipped_reason": None,
            },
            "relations": {
                "attempted": True,
                "status": "recorded",
                "created_count": 1,
                "created_relation_ids": [str(uuid4())],
                "relation_type_counts": {"supports": 1},
                "skipped_reason": None,
            },
            "embedding": {
                "attempted": True,
                "status": "stored",
                "skipped_reason": None,
                "provider": "local_stub",
                "model": "local-stub-v1",
            },
        },
    }
    result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=SimpleNamespace(
            attempt_id=attempt_id,
            status=SimpleNamespace(value="completed"),
            finished_at=finished_at,
            verify_status=VerifyStatus.PASSED,
        ),
        verify_report=SimpleNamespace(status=VerifyStatus.PASSED),
        warnings=(),
        auto_memory_details=auto_memory_details,
    )
    service = FakeWorkflowService(complete_result=result)
    handler = build_workflow_complete_tool_handler(make_server(workflow_service=service))

    response = handler(
        {
            "workflow_instance_id": str(workflow_instance_id),
            "attempt_id": str(attempt_id),
            "workflow_status": "completed",
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
            "warnings": [],
            "auto_memory_details": auto_memory_details,
        },
    }


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
    handler = build_workflow_start_tool_handler(make_server(workflow_service=FakeWorkflowService()))

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
    handler = build_workflow_start_tool_handler(make_server(workflow_service=FakeWorkflowService()))

    response = handler({"workspace_id": str(uuid4())})

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "ticket_id must be a non-empty string",
            "details": {"field": "ticket_id"},
        },
    }


def test_build_workflow_checkpoint_tool_handler_rejects_missing_workflow_instance_id() -> None:
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


def test_build_workflow_complete_tool_handler_rejects_missing_workflow_instance_id() -> None:
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

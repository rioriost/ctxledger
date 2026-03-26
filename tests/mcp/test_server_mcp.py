from __future__ import annotations

import json
from dataclasses import replace
from uuid import uuid4

import pytest

from ctxledger.mcp.resource_handlers import (
    build_workflow_detail_resource_handler,
    build_workspace_resume_resource_handler,
    parse_workflow_detail_resource_uri,
    parse_workspace_resume_resource_uri,
)
from ctxledger.mcp.tool_handlers import (
    build_memory_get_context_tool_handler,
    build_memory_remember_episode_tool_handler,
    build_memory_search_tool_handler,
    build_resume_workflow_tool_handler,
    build_workflow_checkpoint_tool_handler,
    build_workflow_complete_tool_handler,
    build_workflow_start_tool_handler,
    build_workspace_register_tool_handler,
)
from ctxledger.memory.service import MemoryService
from ctxledger.runtime.types import McpResourceResponse, McpToolResponse
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    RegisterWorkspaceInput,
    StartWorkflowInput,
    VerifyStatus,
    WorkflowInstanceStatus,
)
from tests.support.server_test_support import (
    FakeWorkflowService,
    make_completed_workflow_result_stub,
    make_ready_resource_handler,
    make_ready_tool_handler,
    make_resource_handler,
    make_resume_fixture,
    make_settings,
    make_tool_handler,
)


def test_build_resume_workflow_tool_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    handler, resume, _ = make_ready_tool_handler(
        build_resume_workflow_tool_handler,
        settings=settings,
        resume=resume,
    )

    response = handler({"workflow_instance_id": str(resume.workflow_instance.workflow_instance_id)})

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is True
    assert response.payload["result"]["workflow"]["workflow_instance_id"] == str(
        resume.workflow_instance.workflow_instance_id
    )


def test_build_resume_workflow_tool_handler_returns_invalid_request_for_missing_id() -> None:
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_resume_workflow_tool_handler,
        settings=settings,
    )

    response = handler({})

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workflow_instance_id must be a non-empty string",
            "details": {"field": "workflow_instance_id"},
        },
    }


def test_build_resume_workflow_tool_handler_returns_invalid_request_for_bad_uuid() -> None:
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_resume_workflow_tool_handler,
        settings=settings,
    )

    response = handler({"workflow_instance_id": "not-a-uuid"})

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workflow_instance_id must be a valid UUID",
            "details": {"field": "workflow_instance_id"},
        },
    }


def test_build_resume_workflow_tool_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_resume_workflow_tool_handler,
        settings=settings,
    )

    response = handler({"workflow_instance_id": str(uuid4())})

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_workspace_register_tool_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    registered_workspace = replace(
        resume.workspace,
        repo_url="https://example.com/registered.git",
        canonical_path="/tmp/registered",
        default_branch="main",
        metadata={"team": "platform"},
    )
    fake_workflow_service = FakeWorkflowService(
        resume,
        register_workspace_result=registered_workspace,
    )
    handler, _, fake_workflow_service = make_ready_tool_handler(
        build_workspace_register_tool_handler,
        settings=settings,
        resume=resume,
        fake_workflow_service=fake_workflow_service,
    )

    response = handler(
        {
            "repo_url": registered_workspace.repo_url,
            "canonical_path": registered_workspace.canonical_path,
            "default_branch": registered_workspace.default_branch,
            "metadata": {"team": "platform"},
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "workspace_id": str(registered_workspace.workspace_id),
            "repo_url": registered_workspace.repo_url,
            "canonical_path": registered_workspace.canonical_path,
            "default_branch": registered_workspace.default_branch,
            "metadata": registered_workspace.metadata,
            "created_at": registered_workspace.created_at.isoformat(),
            "updated_at": registered_workspace.updated_at.isoformat(),
        },
    }
    assert fake_workflow_service.register_workspace_calls == [
        RegisterWorkspaceInput(
            workspace_id=None,
            repo_url=registered_workspace.repo_url,
            canonical_path=registered_workspace.canonical_path,
            default_branch=registered_workspace.default_branch,
            metadata={"team": "platform"},
        )
    ]


def test_build_workspace_register_tool_handler_returns_invalid_request_for_missing_repo_url() -> (
    None
):
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_workspace_register_tool_handler,
        settings=settings,
    )

    response = handler(
        {
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "repo_url must be a non-empty string",
            "details": {"field": "repo_url"},
        },
    }


def test_build_workspace_register_tool_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_workspace_register_tool_handler,
        settings=settings,
    )

    response = handler(
        {
            "repo_url": "https://example.com/repo.git",
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_workflow_start_tool_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(
        resume,
        start_workflow_result=type(
            "WorkflowStartResultStub",
            (),
            {
                "workflow_instance": resume.workflow_instance,
                "attempt": resume.attempt,
            },
        )(),
    )
    handler, resume, fake_workflow_service = make_ready_tool_handler(
        build_workflow_start_tool_handler,
        settings=settings,
        resume=resume,
        fake_workflow_service=fake_workflow_service,
    )

    response = handler(
        {
            "workspace_id": str(resume.workspace.workspace_id),
            "ticket_id": resume.workflow_instance.ticket_id,
            "metadata": {"priority": "high"},
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "attempt_id": str(resume.attempt.attempt_id),
            "workspace_id": str(resume.workflow_instance.workspace_id),
            "ticket_id": resume.workflow_instance.ticket_id,
            "workflow_status": resume.workflow_instance.status.value,
            "attempt_status": resume.attempt.status.value,
            "created_at": resume.workflow_instance.created_at.isoformat(),
        },
    }
    assert fake_workflow_service.start_workflow_calls == [
        StartWorkflowInput(
            workspace_id=resume.workspace.workspace_id,
            ticket_id=resume.workflow_instance.ticket_id,
            metadata={"priority": "high"},
        )
    ]


def test_build_workflow_start_tool_handler_returns_invalid_request_for_bad_workspace_id() -> None:
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_workflow_start_tool_handler,
        settings=settings,
    )

    response = handler(
        {
            "workspace_id": "not-a-uuid",
            "ticket_id": "SRV-123",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workspace_id must be a valid UUID",
            "details": {"field": "workspace_id"},
        },
    }


def test_build_workflow_start_tool_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_workflow_start_tool_handler,
        settings=settings,
    )

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "ticket_id": "SRV-123",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_workflow_checkpoint_tool_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(
        resume,
        create_checkpoint_result=type(
            "WorkflowCheckpointResultStub",
            (),
            {
                "checkpoint": resume.latest_checkpoint,
                "workflow_instance": resume.workflow_instance,
                "attempt": resume.attempt,
                "verify_report": resume.latest_verify_report,
            },
        )(),
    )
    handler, resume, fake_workflow_service = make_ready_tool_handler(
        build_workflow_checkpoint_tool_handler,
        settings=settings,
        resume=resume,
        fake_workflow_service=fake_workflow_service,
    )

    response = handler(
        {
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "attempt_id": str(resume.attempt.attempt_id),
            "step_name": resume.latest_checkpoint.step_name,
            "summary": resume.latest_checkpoint.summary,
            "checkpoint_json": resume.latest_checkpoint.checkpoint_json,
            "verify_status": resume.latest_verify_report.status.value,
            "verify_report": resume.latest_verify_report.report_json,
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "checkpoint_id": str(resume.latest_checkpoint.checkpoint_id),
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "attempt_id": str(resume.attempt.attempt_id),
            "step_name": resume.latest_checkpoint.step_name,
            "created_at": resume.latest_checkpoint.created_at.isoformat(),
            "latest_verify_status": resume.latest_verify_report.status.value,
        },
    }
    assert fake_workflow_service.create_checkpoint_calls == [
        CreateCheckpointInput(
            workflow_instance_id=resume.workflow_instance.workflow_instance_id,
            attempt_id=resume.attempt.attempt_id,
            step_name=resume.latest_checkpoint.step_name,
            summary=resume.latest_checkpoint.summary,
            checkpoint_json=resume.latest_checkpoint.checkpoint_json,
            verify_status=resume.latest_verify_report.status,
            verify_report=resume.latest_verify_report.report_json,
        )
    ]


def test_build_workflow_checkpoint_tool_handler_returns_invalid_request_for_missing_step_name() -> (
    None
):
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_workflow_checkpoint_tool_handler,
        settings=settings,
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "step_name must be a non-empty string",
            "details": {"field": "step_name"},
        },
    }


def test_build_workflow_checkpoint_tool_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_workflow_checkpoint_tool_handler,
        settings=settings,
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "step_name": "implement_server_api",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_workflow_complete_tool_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume, complete_result = make_completed_workflow_result_stub(
        resume=make_resume_fixture(),
    )
    fake_workflow_service = FakeWorkflowService(
        resume,
        complete_workflow_result=complete_result,
    )
    handler, resume, fake_workflow_service = make_ready_tool_handler(
        build_workflow_complete_tool_handler,
        settings=settings,
        resume=resume,
        fake_workflow_service=fake_workflow_service,
    )

    response = handler(
        {
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "attempt_id": str(resume.attempt.attempt_id),
            "workflow_status": WorkflowInstanceStatus.COMPLETED.value,
            "summary": "Completed successfully",
            "verify_status": VerifyStatus.PASSED.value,
            "verify_report": {"checks": ["pytest"], "status": "passed"},
        }
    )

    finished_attempt = complete_result.attempt
    completed_workflow = complete_result.workflow_instance

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "workflow_instance_id": str(completed_workflow.workflow_instance_id),
            "attempt_id": str(finished_attempt.attempt_id),
            "workflow_status": completed_workflow.status.value,
            "attempt_status": finished_attempt.status.value,
            "finished_at": finished_attempt.finished_at.isoformat(),
            "latest_verify_status": complete_result.verify_report.status.value,
            "warnings": [],
            "auto_memory_details": None,
        },
    }
    assert fake_workflow_service.complete_workflow_calls == [
        CompleteWorkflowInput(
            workflow_instance_id=resume.workflow_instance.workflow_instance_id,
            attempt_id=resume.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed successfully",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
            failure_reason=None,
        )
    ]


def test_build_workflow_complete_tool_handler_returns_auto_memory_warning_payload() -> None:
    settings = make_settings()
    auto_memory_details = {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "failed",
        "embedding_generation_skipped_reason": "embedding_generation_failed:openai",
    }
    warning = resume_warning = make_resume_fixture().warnings[0]
    warning = replace(
        resume_warning,
        code="auto_memory_embedding_failed",
        message=("workflow completion memory was recorded but embedding persistence failed"),
        details=auto_memory_details,
    )
    resume, complete_result = make_completed_workflow_result_stub(
        resume=make_resume_fixture(),
        warning=warning,
        auto_memory_details=auto_memory_details,
    )
    fake_workflow_service = FakeWorkflowService(
        resume,
        complete_workflow_result=complete_result,
    )
    handler, _, _ = make_ready_tool_handler(
        build_workflow_complete_tool_handler,
        settings=settings,
        resume=resume,
        fake_workflow_service=fake_workflow_service,
    )

    response = handler(
        {
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "attempt_id": str(resume.attempt.attempt_id),
            "workflow_status": WorkflowInstanceStatus.COMPLETED.value,
            "summary": "Completed successfully",
            "verify_status": VerifyStatus.PASSED.value,
            "verify_report": {"checks": ["pytest"], "status": "passed"},
        }
    )

    finished_attempt = complete_result.attempt
    completed_workflow = complete_result.workflow_instance

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "workflow_instance_id": str(completed_workflow.workflow_instance_id),
            "attempt_id": str(finished_attempt.attempt_id),
            "workflow_status": completed_workflow.status.value,
            "attempt_status": finished_attempt.status.value,
            "finished_at": finished_attempt.finished_at.isoformat(),
            "latest_verify_status": complete_result.verify_report.status.value,
            "warnings": [
                {
                    "code": "auto_memory_embedding_failed",
                    "message": (
                        "workflow completion memory was recorded but embedding persistence failed"
                    ),
                    "details": auto_memory_details,
                }
            ],
            "auto_memory_details": auto_memory_details,
        },
    }


def test_build_workflow_complete_tool_handler_returns_invalid_request_for_bad_status() -> None:
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_workflow_complete_tool_handler,
        settings=settings,
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "workflow_status": "not-a-real-status",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
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


def test_build_workflow_complete_tool_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    handler, _, _ = make_tool_handler(
        build_workflow_complete_tool_handler,
        settings=settings,
    )

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "workflow_status": WorkflowInstanceStatus.COMPLETED.value,
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_memory_remember_episode_tool_handler_returns_stub_payload() -> None:
    handler = build_memory_remember_episode_tool_handler(MemoryService())

    response = handler(
        {
            "workflow_instance_id": "wf-123",
            "summary": "Capture useful implementation notes",
            "attempt_id": "attempt-1",
            "metadata": {"source": "agent"},
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is False
    assert response.payload["error"]["code"] == "memory_invalid_request"


def test_build_memory_remember_episode_tool_handler_returns_invalid_request() -> None:
    handler = build_memory_remember_episode_tool_handler(MemoryService())

    response = handler({"workflow_instance_id": "", "summary": ""})

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is False
    assert response.payload["error"]["code"] == "memory_invalid_request"


def test_build_memory_search_tool_handler_returns_implemented_payload() -> None:
    handler = build_memory_search_tool_handler(MemoryService())

    response = handler(
        {
            "query": "projection drift",
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "limit": 5,
            "filters": {"kind": "summary"},
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is True
    assert response.payload["result"]["feature"] == "memory_search"
    assert response.payload["result"]["implemented"] is True
    assert response.payload["result"]["status"] == "ok"
    assert response.payload["result"]["available_in_version"] == "0.4.0"
    assert response.payload["result"]["details"] == {
        "query": "projection drift",
        "normalized_query": "projection drift",
        "workspace_id": "00000000-0000-0000-0000-000000000001",
        "limit": 5,
        "filters": {"kind": "summary"},
        "search_mode": "memory_item_lexical",
        "memory_items_considered": 0,
        "semantic_candidates_considered": 0,
        "semantic_query_generated": False,
        "hybrid_scoring": {
            "lexical_weight": 1.0,
            "semantic_weight": 1.0,
            "semantic_only_discount": 0.75,
        },
        "result_mode_counts": {
            "hybrid": 0,
            "lexical_only": 0,
            "semantic_only_discounted": 0,
        },
        "result_composition": {
            "with_lexical_signal": 0,
            "with_semantic_signal": 0,
            "with_both_signals": 0,
        },
        "results_returned": 0,
        "semantic_generation_skipped_reason": "embedding_search_not_configured",
        "task_recall_context_present": False,
        "task_recall_latest_considered_workflow_instance_id": None,
        "task_recall_selected_workflow_instance_id": None,
        "task_recall_selected_equals_latest": False,
        "task_recall_latest_vs_selected_comparison_present": False,
        "task_recall_latest_vs_selected_candidate_details": {
            "latest_workflow_instance_id": None,
            "selected_workflow_instance_id": None,
            "latest_considered": {
                "workflow_instance_id": None,
                "checkpoint_step_name": None,
                "checkpoint_summary": None,
                "primary_objective_text": None,
                "next_intended_action_text": None,
                "ticket_detour_like": False,
                "checkpoint_detour_like": False,
                "detour_like": False,
                "workflow_terminal": False,
                "has_attempt_signal": False,
                "attempt_terminal": False,
                "has_checkpoint_signal": False,
            },
            "selected": {
                "workflow_instance_id": None,
                "checkpoint_step_name": None,
                "checkpoint_summary": None,
                "primary_objective_text": None,
                "next_intended_action_text": None,
                "ticket_detour_like": False,
                "checkpoint_detour_like": False,
                "detour_like": False,
                "workflow_terminal": False,
                "has_attempt_signal": False,
                "attempt_terminal": False,
                "has_checkpoint_signal": False,
            },
            "same_workflow": True,
            "same_checkpoint_details": True,
            "comparison_source": "memory_search_task_recall_context",
        },
        "task_recall_latest_vs_selected_primary_block": "candidate_details",
        "task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias": True,
        "task_recall_latest_vs_selected_checkpoint_details_present": False,
        "task_recall_latest_vs_selected_checkpoint_details": {
            "latest_workflow_instance_id": None,
            "selected_workflow_instance_id": None,
            "latest_considered": {
                "workflow_instance_id": None,
                "checkpoint_step_name": None,
                "checkpoint_summary": None,
                "primary_objective_text": None,
                "next_intended_action_text": None,
                "ticket_detour_like": False,
                "checkpoint_detour_like": False,
                "detour_like": False,
                "workflow_terminal": False,
                "has_attempt_signal": False,
                "attempt_terminal": False,
                "has_checkpoint_signal": False,
            },
            "selected": {
                "workflow_instance_id": None,
                "checkpoint_step_name": None,
                "checkpoint_summary": None,
                "primary_objective_text": None,
                "next_intended_action_text": None,
                "ticket_detour_like": False,
                "checkpoint_detour_like": False,
                "detour_like": False,
                "workflow_terminal": False,
                "has_attempt_signal": False,
                "attempt_terminal": False,
                "has_checkpoint_signal": False,
            },
            "same_workflow": True,
            "same_checkpoint_details": True,
            "comparison_source": "memory_search_task_recall_context",
        },
        "task_recall_comparison_summary_explanations_present": False,
        "task_recall_comparison_summary_explanations": [],
    }
    assert response.payload["result"]["results"] == []


def test_build_memory_search_tool_handler_returns_invalid_request() -> None:
    handler = build_memory_search_tool_handler(MemoryService())

    response = handler({"query": "", "limit": 0})

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is False
    assert response.payload["error"]["code"] == "memory_invalid_request"


def test_build_memory_get_context_tool_handler_returns_stub_payload() -> None:
    handler = build_memory_get_context_tool_handler(MemoryService())

    response = handler(
        {
            "workflow_instance_id": "wf-123",
            "limit": 3,
            "include_episodes": True,
            "include_memory_items": False,
            "include_summaries": True,
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is False
    assert response.payload["error"]["code"] == "memory_invalid_request"


def test_build_memory_get_context_tool_handler_returns_invalid_request() -> None:
    handler = build_memory_get_context_tool_handler(MemoryService())

    response = handler({})

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is False
    assert response.payload["error"]["code"] == "memory_invalid_request"


def test_parse_workspace_resume_resource_uri_returns_workspace_id_for_valid_uri() -> None:
    workspace_id = uuid4()

    assert parse_workspace_resume_resource_uri(f"workspace://{workspace_id}/resume") == workspace_id


def test_parse_workspace_resume_resource_uri_returns_none_for_invalid_uri() -> None:
    assert parse_workspace_resume_resource_uri("") is None
    assert parse_workspace_resume_resource_uri("workspace://not-a-uuid/resume") is None
    assert parse_workspace_resume_resource_uri("workspace://abc/workflow") is None
    assert parse_workspace_resume_resource_uri("memory://episode/123") is None


def test_parse_workflow_detail_resource_uri_returns_ids_for_valid_uri() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    assert parse_workflow_detail_resource_uri(
        f"workspace://{workspace_id}/workflow/{workflow_instance_id}"
    ) == (workspace_id, workflow_instance_id)


def test_parse_workflow_detail_resource_uri_returns_none_for_invalid_uri() -> None:
    workspace_id = uuid4()

    assert parse_workflow_detail_resource_uri("") is None
    assert (
        parse_workflow_detail_resource_uri(f"workspace://{workspace_id}/workflow/not-a-uuid")
        is None
    )
    assert parse_workflow_detail_resource_uri(f"workspace://not-a-uuid/workflow/{uuid4()}") is None
    assert parse_workflow_detail_resource_uri("workspace://abc/resume") is None


def test_build_workspace_resume_resource_handler_returns_success_payload() -> None:
    settings = make_settings()
    handler, resume, _ = make_ready_resource_handler(
        build_workspace_resume_resource_handler,
        settings=settings,
    )

    response = handler(f"workspace://{resume.workspace.workspace_id}/resume")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 200
    assert response.payload["uri"] == f"workspace://{resume.workspace.workspace_id}/resume"
    resource = response.payload["resource"]
    assert resource["workspace"]["workspace_id"] == str(resume.workspace.workspace_id)
    assert resource["workspace"]["repo_url"] == resume.workspace.repo_url
    assert resource["workflow"]["workflow_instance_id"] == str(
        resume.workflow_instance.workflow_instance_id
    )
    assert resource["attempt"]["attempt_id"] == str(resume.attempt.attempt_id)
    assert resource["latest_checkpoint"]["checkpoint_id"] == str(
        resume.latest_checkpoint.checkpoint_id
    )
    assert resource["latest_verify_report"]["verify_id"] == str(
        resume.latest_verify_report.verify_id
    )
    assert resource["resumable_status"] == resume.resumable_status.value
    assert resource["warnings"] == [
        {
            "code": issue.code,
            "message": issue.message,
            "details": issue.details,
        }
        for issue in resume.warnings
    ]
    assert resource["next_hint"] == resume.next_hint
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_handler_returns_not_found_for_invalid_uri() -> None:
    settings = make_settings()
    handler = make_resource_handler(
        build_workspace_resume_resource_handler,
        settings=settings,
    )

    response = handler("workspace://not-a-uuid/resume")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "workspace resume resource requires workspace://{workspace_id}/resume",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    handler = make_resource_handler(
        build_workspace_resume_resource_handler,
        settings=settings,
    )

    response = handler(f"workspace://{uuid4()}/resume")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_handler_returns_success_payload() -> None:
    settings = make_settings()
    handler, resume, _ = make_ready_resource_handler(
        build_workflow_detail_resource_handler,
        settings=settings,
    )

    uri = (
        f"workspace://{resume.workspace.workspace_id}/workflow/"
        f"{resume.workflow_instance.workflow_instance_id}"
    )
    response = handler(uri)

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 200
    assert response.payload["uri"] == uri
    assert response.payload["resource"]["workflow"]["workflow_instance_id"] == str(
        resume.workflow_instance.workflow_instance_id
    )
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_handler_returns_not_found_for_invalid_uri() -> None:
    settings = make_settings()
    handler = make_resource_handler(
        build_workflow_detail_resource_handler,
        settings=settings,
    )

    response = handler("workspace://not-a-uuid/workflow/not-a-uuid")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": (
                "workflow detail resource requires "
                "workspace://{workspace_id}/workflow/{workflow_instance_id}"
            ),
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    handler = make_resource_handler(
        build_workflow_detail_resource_handler,
        settings=settings,
    )

    response = handler(f"workspace://{uuid4()}/workflow/{uuid4()}")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}

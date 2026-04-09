from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.runtime.server_responses import (
    build_workflow_resume_response,
    build_workspace_resume_resource_response,
)
from ctxledger.workflow.service import WorkflowError

from ..support.coverage_targets_support import make_server, make_settings


def _load_http_app_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(),
    )
    sys.modules.pop("ctxledger.http_app", None)
    return importlib.import_module("ctxledger.http_app")


def test_build_workspace_resume_resource_response_uses_resume_result_branch() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workspace=SimpleNamespace(workspace_id=workspace_id),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={
                "workspace": {
                    "workspace_id": str(workspace_id),
                },
                "workflow_instance_id": str(workflow_instance_id),
            },
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workspace": {
                "workspace_id": str(workspace_id),
            },
            "workflow_instance_id": str(workflow_instance_id),
        },
        "selection": {
            "strategy": "resume_result",
            "candidate_count": 1,
            "selected_workflow_instance_id": str(workflow_instance_id),
            "running_workflow_instance_id": None,
            "latest_workflow_instance_id": str(workflow_instance_id),
            "selected_reason": "used workflow returned by resume result branch",
            "latest_deprioritized": False,
            "signals": {
                "running_workflow_available": False,
                "latest_workflow_terminal": False,
                "non_terminal_candidate_available": False,
                "selected_equals_latest": True,
                "selected_equals_running": False,
                "latest_ticket_detour_like": False,
                "latest_checkpoint_detour_like": False,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": False,
                "ranking_details_present": False,
                "explanations_present": False,
            },
            "explanations": [],
            "ranking_details": [],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_returns_not_found_for_workspace_mismatch() -> (
    None
):
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workspace=SimpleNamespace(workspace_id=other_workspace_id),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=other_workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={
                "workspace": {
                    "workspace_id": str(other_workspace_id),
                },
                "workflow_instance_id": str(workflow_instance_id),
            },
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"workspace '{workspace_id}' was not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_returns_workspace_not_found() -> (
    None
):
    workspace_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(get_by_id=lambda _workspace_id: None)
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: None,
                list_by_workspace_id=lambda _workspace_id, *, limit: (),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda _workflow_instance_id: None,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())

    response = build_workspace_resume_resource_response(server, workspace_id)

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"workspace '{workspace_id}' was not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_response_returns_not_found_for_explicit_workflow_not_found_code() -> (
    None
):
    workflow_instance_id = uuid4()
    server = make_server()

    class WorkflowNotFoundError(WorkflowError):
        code = "workflow_not_found"

        def __init__(self) -> None:
            super().__init__("workflow missing", details={})

    def raise_workflow_not_found(
        _workflow_instance_id: object,
    ) -> object:
        raise WorkflowNotFoundError()

    server.get_workflow_resume = raise_workflow_not_found

    response = build_workflow_resume_response(server, workflow_instance_id)

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "workflow missing",
            "details": {
                "workflow_instance_id": str(workflow_instance_id),
            },
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_returns_no_workflow() -> (
    None
):
    workspace_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(
                    workspace_id=workspace_id
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: None,
                list_by_workspace_id=lambda _workspace_id, *, limit: (),
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())

    response = build_workspace_resume_resource_response(server, workspace_id)

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"no workflow is available for workspace '{workspace_id}'",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_uses_latest_when_running_missing() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            latest_workflow = SimpleNamespace(workflow_instance_id=workflow_instance_id)
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(
                    workspace_id=workspace_id
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: latest_workflow,
                list_by_workspace_id=lambda _workspace_id, *, limit: (latest_workflow,),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda _workflow_instance_id: None,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(workflow_instance_id),
        },
        "selection": {
            "strategy": "running_or_latest",
            "candidate_count": 1,
            "selected_workflow_instance_id": str(workflow_instance_id),
            "running_workflow_instance_id": None,
            "latest_workflow_instance_id": str(workflow_instance_id),
            "selected_reason": "selected latest workflow because no running workflow was available",
            "latest_deprioritized": False,
            "signals": {
                "running_workflow_available": False,
                "latest_workflow_terminal": False,
                "non_terminal_candidate_available": True,
                "selected_equals_latest": True,
                "selected_equals_running": False,
                "latest_ticket_detour_like": False,
                "latest_checkpoint_detour_like": False,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": False,
                "ranking_details_present": True,
                "explanations_present": False,
            },
            "explanations": [],
            "ranking_details": [
                {
                    "workflow_instance_id": str(workflow_instance_id),
                    "is_latest": True,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": False,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 35,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "latest_candidate",
                            "message": "candidate is the latest workflow considered for resume",
                        },
                        {
                            "code": "selected_candidate",
                            "message": "candidate was selected after applying workspace resume heuristics",
                        },
                    ],
                    "selected": True,
                },
            ],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_prefers_running_workflow() -> (
    None
):
    workspace_id = uuid4()
    running_workflow_instance_id = uuid4()
    latest_workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            running_workflow = SimpleNamespace(
                workflow_instance_id=running_workflow_instance_id
            )
            latest_workflow = SimpleNamespace(
                workflow_instance_id=latest_workflow_instance_id
            )
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(
                    workspace_id=workspace_id
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: running_workflow,
                get_latest_by_workspace_id=lambda _workspace_id: latest_workflow,
                list_by_workspace_id=lambda _workspace_id, *, limit: (
                    latest_workflow,
                    running_workflow,
                ),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda _workflow_instance_id: None,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == running_workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(running_workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(running_workflow_instance_id),
        },
        "selection": {
            "strategy": "running_or_latest",
            "candidate_count": 2,
            "selected_workflow_instance_id": str(running_workflow_instance_id),
            "running_workflow_instance_id": str(running_workflow_instance_id),
            "latest_workflow_instance_id": str(latest_workflow_instance_id),
            "selected_reason": "selected running workflow for workspace resume",
            "latest_deprioritized": True,
            "signals": {
                "running_workflow_available": True,
                "latest_workflow_terminal": False,
                "non_terminal_candidate_available": True,
                "selected_equals_latest": False,
                "selected_equals_running": True,
                "latest_ticket_detour_like": False,
                "latest_checkpoint_detour_like": False,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": False,
                "ranking_details_present": True,
                "explanations_present": False,
            },
            "explanations": [],
            "ranking_details": [
                {
                    "workflow_instance_id": str(latest_workflow_instance_id),
                    "is_latest": True,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": False,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 35,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "latest_candidate",
                            "message": "candidate is the latest workflow considered for resume",
                        },
                    ],
                    "selected": False,
                },
                {
                    "workflow_instance_id": str(running_workflow_instance_id),
                    "is_latest": False,
                    "is_running": True,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": False,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 135,
                    "reason_list": [
                        {
                            "code": "running_workflow_priority",
                            "message": "running workflows are prioritized for continuation",
                            "impact": 100,
                        },
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "selected_candidate",
                            "message": "candidate was selected after applying workspace resume heuristics",
                        },
                    ],
                    "selected": True,
                },
            ],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_surfaces_resumability_explanations_for_latest_selected_candidate() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            latest_workflow = SimpleNamespace(
                workflow_instance_id=workflow_instance_id,
                status="running",
                ticket_id="TASK-PRIMARY-RESUME-HTTP-1",
                latest_attempt=SimpleNamespace(status="running"),
            )
            latest_checkpoint = SimpleNamespace(
                summary="Resume primary workflow implementation",
                step_name="implement_task_recall",
                checkpoint_json={},
            )
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(
                    workspace_id=workspace_id
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: latest_workflow,
                list_by_workspace_id=lambda _workspace_id, *, limit: (latest_workflow,),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda _workflow_instance_id: (
                    latest_checkpoint
                ),
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(workflow_instance_id),
        },
        "selection": {
            "strategy": "running_or_latest",
            "candidate_count": 1,
            "selected_workflow_instance_id": str(workflow_instance_id),
            "running_workflow_instance_id": None,
            "latest_workflow_instance_id": str(workflow_instance_id),
            "selected_reason": "selected latest workflow because no running workflow was available",
            "latest_deprioritized": False,
            "signals": {
                "running_workflow_available": False,
                "latest_workflow_terminal": False,
                "non_terminal_candidate_available": True,
                "selected_equals_latest": True,
                "selected_equals_running": False,
                "latest_ticket_detour_like": False,
                "latest_checkpoint_detour_like": False,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": False,
                "ranking_details_present": True,
                "explanations_present": True,
            },
            "explanations": [
                {
                    "code": "latest_attempt_present",
                    "message": "candidate has a latest attempt signal that improves resumability confidence",
                },
                {
                    "code": "latest_checkpoint_present",
                    "message": "candidate has checkpoint history that improves resumability confidence",
                },
            ],
            "ranking_details": [
                {
                    "workflow_instance_id": str(workflow_instance_id),
                    "is_latest": True,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": True,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": True,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 45,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "latest_attempt_present_bonus",
                            "message": "candidate has a latest attempt signal available",
                            "impact": 5,
                        },
                        {
                            "code": "latest_checkpoint_present_bonus",
                            "message": "candidate has checkpoint history for resumability",
                            "impact": 5,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "latest_candidate",
                            "message": "candidate is the latest workflow considered for resume",
                        },
                        {
                            "code": "selected_candidate",
                            "message": "candidate was selected after applying workspace resume heuristics",
                        },
                    ],
                    "selected": True,
                },
            ],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_prefers_non_terminal_candidate_over_latest_terminal() -> (
    None
):
    workspace_id = uuid4()
    older_non_terminal_workflow_instance_id = uuid4()
    latest_terminal_workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            latest_terminal_workflow = SimpleNamespace(
                workflow_instance_id=latest_terminal_workflow_instance_id,
                status="completed",
            )
            older_non_terminal_workflow = SimpleNamespace(
                workflow_instance_id=older_non_terminal_workflow_instance_id,
                status="running",
            )
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(
                    workspace_id=workspace_id
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: (
                    latest_terminal_workflow
                ),
                list_by_workspace_id=lambda _workspace_id, *, limit: (
                    latest_terminal_workflow,
                    older_non_terminal_workflow,
                ),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda _workflow_instance_id: None,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == older_non_terminal_workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={
                "workflow_instance_id": str(older_non_terminal_workflow_instance_id)
            },
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(older_non_terminal_workflow_instance_id),
        },
        "selection": {
            "strategy": "running_or_latest",
            "candidate_count": 2,
            "selected_workflow_instance_id": str(
                older_non_terminal_workflow_instance_id
            ),
            "running_workflow_instance_id": None,
            "latest_workflow_instance_id": str(latest_terminal_workflow_instance_id),
            "selected_reason": "selected non-terminal workflow candidate instead of latest terminal workflow",
            "latest_deprioritized": True,
            "signals": {
                "running_workflow_available": False,
                "latest_workflow_terminal": True,
                "non_terminal_candidate_available": True,
                "selected_equals_latest": False,
                "selected_equals_running": False,
                "latest_ticket_detour_like": False,
                "latest_checkpoint_detour_like": False,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": False,
                "ranking_details_present": True,
                "explanations_present": True,
            },
            "explanations": [
                {
                    "code": "latest_workflow_terminal",
                    "message": "latest workflow was terminal",
                },
                {
                    "code": "selected_non_terminal_candidate",
                    "message": "selected a non-terminal candidate instead",
                },
            ],
            "ranking_details": [
                {
                    "workflow_instance_id": str(latest_terminal_workflow_instance_id),
                    "is_latest": True,
                    "is_running": False,
                    "workflow_terminal": True,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": False,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": -15,
                    "reason_list": [
                        {
                            "code": "workflow_terminal_penalty",
                            "message": "terminal workflows are less suitable for continuation",
                            "impact": -25,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "latest_candidate",
                            "message": "candidate is the latest workflow considered for resume",
                        },
                    ],
                    "selected": False,
                },
                {
                    "workflow_instance_id": str(
                        older_non_terminal_workflow_instance_id
                    ),
                    "is_latest": False,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": False,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 35,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "selected_candidate",
                            "message": "candidate was selected after applying workspace resume heuristics",
                        },
                    ],
                    "selected": True,
                },
            ],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_prefers_non_detour_like_ticket_over_latest_detour_like_ticket() -> (
    None
):
    workspace_id = uuid4()
    mainline_workflow_instance_id = uuid4()
    latest_detour_workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            latest_detour_workflow = SimpleNamespace(
                workflow_instance_id=latest_detour_workflow_instance_id,
                status="running",
                ticket_id="COVERAGE-DET-1",
            )
            mainline_workflow = SimpleNamespace(
                workflow_instance_id=mainline_workflow_instance_id,
                status="running",
                ticket_id="TASK-PRIMARY-1",
            )
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(
                    workspace_id=workspace_id
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: latest_detour_workflow,
                list_by_workspace_id=lambda _workspace_id, *, limit: (
                    latest_detour_workflow,
                    mainline_workflow,
                ),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda workflow_instance_id: {
                    latest_detour_workflow_instance_id: SimpleNamespace(
                        summary="Coverage follow-up for workspace resume selection",
                        step_name="coverage_followup",
                        checkpoint_json={},
                    ),
                    mainline_workflow_instance_id: SimpleNamespace(
                        summary="Resume primary task recall implementation",
                        step_name="implement_task_recall",
                        checkpoint_json={},
                    ),
                }.get(workflow_instance_id),
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == mainline_workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(mainline_workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(mainline_workflow_instance_id),
        },
        "selection": {
            "strategy": "running_or_latest",
            "candidate_count": 2,
            "selected_workflow_instance_id": str(mainline_workflow_instance_id),
            "running_workflow_instance_id": None,
            "latest_workflow_instance_id": str(latest_detour_workflow_instance_id),
            "selected_reason": "selected non-detour-like workflow candidate instead of latest detour-like workflow",
            "latest_deprioritized": True,
            "signals": {
                "running_workflow_available": False,
                "latest_workflow_terminal": False,
                "non_terminal_candidate_available": True,
                "selected_equals_latest": False,
                "selected_equals_running": False,
                "latest_ticket_detour_like": True,
                "latest_checkpoint_detour_like": True,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": True,
                "ranking_details_present": True,
                "explanations_present": True,
            },
            "explanations": [
                {
                    "code": "latest_ticket_detour_like",
                    "message": "latest workflow ticket looked detour-like",
                },
                {
                    "code": "latest_checkpoint_detour_like",
                    "message": "latest workflow checkpoint looked detour-like",
                },
                {
                    "code": "selected_non_detour_candidate",
                    "message": "selected a non-detour-like candidate instead",
                },
                {
                    "code": "candidate_reason_details_available",
                    "message": "ranking details include candidate-level reasons for the selection outcome",
                },
            ],
            "ranking_details": [
                {
                    "workflow_instance_id": str(latest_detour_workflow_instance_id),
                    "is_latest": True,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": True,
                    "ticket_detour_like": True,
                    "checkpoint_detour_like": True,
                    "detour_like": True,
                    "score": 20,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "latest_checkpoint_present_bonus",
                            "message": "candidate has checkpoint history for resumability",
                            "impact": 5,
                        },
                        {
                            "code": "ticket_detour_like_penalty",
                            "message": "workflow ticket looked detour-like",
                            "impact": -10,
                        },
                        {
                            "code": "checkpoint_detour_like_penalty",
                            "message": "latest checkpoint looked detour-like",
                            "impact": -10,
                        },
                        {
                            "code": "latest_candidate",
                            "message": "candidate is the latest workflow considered for resume",
                        },
                    ],
                    "selected": False,
                },
                {
                    "workflow_instance_id": str(mainline_workflow_instance_id),
                    "is_latest": False,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": True,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 40,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "latest_checkpoint_present_bonus",
                            "message": "candidate has checkpoint history for resumability",
                            "impact": 5,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "selected_candidate",
                            "message": "candidate was selected after applying workspace resume heuristics",
                        },
                    ],
                    "selected": True,
                },
            ],
        },
    }
    assert response.headers == {"content-type": "application/json"}

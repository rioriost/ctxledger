from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import ctxledger.__init__ as cli_module

from .conftest import (
    FakeWorkflowService,
    make_settings,
    patch_cli_connection_pool,
    patch_cli_postgres_config,
)


def test_main_resume_workflow_renders_text_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    workflow_instance_id = uuid4()

    fake_resume = SimpleNamespace(
        workspace=SimpleNamespace(
            workspace_id=uuid4(),
            repo_url="https://example.com/org/repo.git",
            canonical_path=str(tmp_path),
            default_branch="main",
            metadata={"team": "platform"},
        ),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=uuid4(),
            ticket_id="CLI-RESUME-1",
            status=SimpleNamespace(value="running"),
            metadata={"priority": "high"},
        ),
        attempt=SimpleNamespace(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_number=2,
            status=SimpleNamespace(value="running"),
            failure_reason=None,
            verify_status=SimpleNamespace(value="passed"),
            started_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00+00:00"),
            finished_at=None,
        ),
        latest_checkpoint=SimpleNamespace(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_id=uuid4(),
            step_name="implement_cli",
            summary="Resume from latest checkpoint",
            checkpoint_json={"next_intended_action": "Run CLI resume command"},
            created_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:01:00+00:00"),
        ),
        latest_verify_report=None,
        resumable_status=SimpleNamespace(value="resumable"),
        warnings=(),
        next_hint="Run CLI resume command",
    )

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: FakeWorkflowService(fake_resume),
    )

    exit_code = cli_module.main(
        [
            "resume-workflow",
            "--workflow-instance-id",
            str(workflow_instance_id),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0, captured.err
    assert "Resume workflow" in captured.out
    assert f"Workflow: {workflow_instance_id}" in captured.out
    assert "Ticket: CLI-RESUME-1" in captured.out
    assert "Resumable status: resumable" in captured.out
    assert f"Workspace: {tmp_path}" in captured.out
    assert "Latest checkpoint step: implement_cli" in captured.out
    assert "Next hint: Run CLI resume command" in captured.out
    assert captured.err == ""


def test_main_resume_workflow_renders_json_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    workflow_instance_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    fake_resume = SimpleNamespace(
        workspace=SimpleNamespace(
            workspace_id=workspace_id,
            repo_url="https://example.com/org/repo.git",
            canonical_path=str(tmp_path),
            default_branch="main",
            metadata={"team": "platform"},
        ),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
            ticket_id="CLI-RESUME-JSON-1",
            status=SimpleNamespace(value="running"),
            metadata={"priority": "high"},
        ),
        attempt=SimpleNamespace(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_instance_id,
            attempt_number=1,
            status=SimpleNamespace(value="running"),
            failure_reason=None,
            verify_status=SimpleNamespace(value="passed"),
            started_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00+00:00"),
            finished_at=None,
        ),
        latest_checkpoint=SimpleNamespace(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_id=attempt_id,
            step_name="implement_cli",
            summary="Render JSON output",
            checkpoint_json={"next_intended_action": "Inspect JSON"},
            created_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:01:00+00:00"),
        ),
        latest_verify_report=None,
        resumable_status=SimpleNamespace(value="resumable"),
        warnings=(),
        next_hint="Inspect JSON",
    )

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: FakeWorkflowService(fake_resume),
    )
    monkeypatch.setattr(
        "ctxledger.runtime.serializers.serialize_workflow_resume",
        lambda resume: {
            "workspace": {
                "workspace_id": str(workspace_id),
            },
            "workflow": {
                "workflow_instance_id": str(workflow_instance_id),
            },
            "attempt": {
                "attempt_id": str(attempt_id),
            },
            "latest_checkpoint": {
                "step_name": "implement_cli",
            },
            "resumable_status": "resumable",
            "next_hint": "Inspect JSON",
            "warnings": [],
        },
    )

    exit_code = cli_module.main(
        [
            "resume-workflow",
            "--workflow-instance-id",
            str(workflow_instance_id),
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0, captured.err
    assert payload["workspace"]["workspace_id"] == str(workspace_id)
    assert payload["workflow"]["workflow_instance_id"] == str(workflow_instance_id)
    assert payload["attempt"]["attempt_id"] == str(attempt_id)
    assert payload["latest_checkpoint"]["step_name"] == "implement_cli"
    assert payload["resumable_status"] == "resumable"
    assert payload["next_hint"] == "Inspect JSON"
    assert payload["warnings"] == []
    assert captured.err == ""


def test_main_resume_workflow_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow_instance_id = uuid4()

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url=""),
    )

    exit_code = cli_module.main(
        [
            "resume-workflow",
            "--workflow-instance-id",
            str(workflow_instance_id),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_main_dispatches_resume_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_ids: list[str] = []

    def fake_resume_workflow(args) -> int:
        received_ids.append(args.workflow_instance_id)
        return 9

    monkeypatch.setattr(cli_module, "_resume_workflow", fake_resume_workflow)

    result = cli_module.main(
        ["resume-workflow", "--workflow-instance-id", "workflow-123"]
    )

    assert result == 9
    assert received_ids == ["workflow-123"]

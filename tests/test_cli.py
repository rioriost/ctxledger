from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.config import (
    AppSettings,
    DatabaseSettings,
    DebugSettings,
    HttpSettings,
    LoggingSettings,
    LogLevel,
    ProjectionSettings,
)
from ctxledger.workflow.service import (
    CreateCheckpointInput,
    ProjectionArtifactType,
    ProjectionStatus,
    RegisterWorkspaceInput,
    ResumeIssue,
    StartWorkflowInput,
)


def make_settings(
    *, database_url: str = "postgresql://ctxledger:test@localhost:5432/ctxledger"
) -> AppSettings:
    return AppSettings(
        app_name="ctxledger",
        app_version="0.1.0",
        environment="test",
        database=DatabaseSettings(
            url=database_url,
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
        ),
        http=HttpSettings(
            host="127.0.0.1",
            port=8080,
            path="/mcp",
        ),
        debug=DebugSettings(enabled=True),
        projection=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
        logging=LoggingSettings(
            level=LogLevel.INFO,
            structured=False,
        ),
    )


class FakeWorkflowService:
    def __init__(self, resume_result: object) -> None:
        self.resume_result = resume_result
        self.resume_calls: list[object] = []

    def resume_workflow(self, data: object) -> object:
        self.resume_calls.append(data)
        return self.resume_result


class FakeWriter:
    instances: list["FakeWriter"] = []

    def __init__(
        self, *, workflow_service: object, projection_settings: ProjectionSettings
    ) -> None:
        self.workflow_service = workflow_service
        self.projection_settings = projection_settings
        self.calls: list[dict[str, object]] = []
        type(self).instances.append(self)

    def write_and_reconcile_resume_projection(
        self,
        *,
        workspace_root: str | Path,
        workflow_instance_id: object,
        workspace_id: object,
    ) -> object:
        self.calls.append(
            {
                "workspace_root": workspace_root,
                "workflow_instance_id": workflow_instance_id,
                "workspace_id": workspace_id,
            }
        )
        return SimpleNamespace(
            json_path=Path(workspace_root) / ".agent" / "resume.json",
            markdown_path=Path(workspace_root) / ".agent" / "resume.md",
            state_updates=(),
            failure_updates=(),
        )


def test_main_write_resume_projection_uses_workflow_lookup_and_writer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    settings = make_settings()
    fake_resume = SimpleNamespace(
        workspace=SimpleNamespace(
            workspace_id=workspace_id,
            canonical_path=str(tmp_path),
        )
    )
    fake_service = FakeWorkflowService(fake_resume)

    uow_factory_calls: list[object] = []
    workflow_service_ctor_args: list[object] = []

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresConfig.from_settings",
        lambda loaded_settings: SimpleNamespace(settings=loaded_settings),
    )

    def fake_build_postgres_uow_factory(config: object) -> object:
        uow_factory_calls.append(config)
        return "fake-uow-factory"

    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        fake_build_postgres_uow_factory,
    )

    def fake_workflow_service_ctor(uow_factory: object) -> FakeWorkflowService:
        workflow_service_ctor_args.append(uow_factory)
        return fake_service

    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        fake_workflow_service_ctor,
    )
    monkeypatch.setattr(
        "ctxledger.projection.writer.ResumeProjectionWriter", FakeWriter
    )

    exit_code = cli_module.main(
        [
            "write-resume-projection",
            "--workflow-instance-id",
            str(workflow_instance_id),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resume projection written successfully." in captured.out
    assert f"JSON: {tmp_path / '.agent' / 'resume.json'}" in captured.out
    assert f"Markdown: {tmp_path / '.agent' / 'resume.md'}" in captured.out
    assert "Summary: 0 state update(s), 0 failure update(s)" in captured.out
    assert captured.err == ""

    assert len(uow_factory_calls) == 1
    assert getattr(uow_factory_calls[0], "settings") is settings
    assert workflow_service_ctor_args == ["fake-uow-factory"]

    assert len(fake_service.resume_calls) == 1
    assert fake_service.resume_calls[0].workflow_instance_id == workflow_instance_id

    assert len(FakeWriter.instances) == 1
    writer = FakeWriter.instances[0]
    assert writer.workflow_service is fake_service
    assert writer.projection_settings == settings.projection
    assert writer.calls == [
        {
            "workspace_root": str(tmp_path),
            "workflow_instance_id": workflow_instance_id,
            "workspace_id": workspace_id,
        }
    ]


def test_main_write_resume_projection_returns_error_when_resume_projection_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow_instance_id = uuid4()

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())

    def fake_build_postgres_uow_factory(config: object) -> object:
        return "fake-uow-factory"

    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresConfig.from_settings",
        lambda loaded_settings: SimpleNamespace(settings=loaded_settings),
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        fake_build_postgres_uow_factory,
    )

    class ExplodingWorkflowService:
        def __init__(self, uow_factory: object) -> None:
            self.uow_factory = uow_factory

        def resume_workflow(self, data: object) -> object:
            raise RuntimeError("workflow not found")

    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        ExplodingWorkflowService,
    )
    monkeypatch.setattr(
        "ctxledger.projection.writer.ResumeProjectionWriter", FakeWriter
    )

    exit_code = cli_module.main(
        [
            "write-resume-projection",
            "--workflow-instance-id",
            str(workflow_instance_id),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to write resume projection: workflow not found" in captured.err


def test_main_write_resume_projection_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow_instance_id = uuid4()
    settings = make_settings(database_url="")

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)

    exit_code = cli_module.main(
        [
            "write-resume-projection",
            "--workflow-instance-id",
            str(workflow_instance_id),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_main_write_resume_projection_wires_real_command_arguments(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    from ctxledger.db import InMemoryStore, build_in_memory_uow_factory
    from ctxledger.projection.writer import ResumeProjectionWriter
    from ctxledger.workflow.service import ResumeWorkflowInput, WorkflowService

    settings = make_settings()
    store = InMemoryStore.create()
    service = WorkflowService(build_in_memory_uow_factory(store))

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo.git",
            canonical_path=str(tmp_path),
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="CLI-123",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="implement_cli",
            summary="Connect CLI to projection writer",
            checkpoint_json={
                "next_intended_action": "Run write-resume-projection",
            },
        )
    )

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresConfig.from_settings",
        lambda loaded_settings: SimpleNamespace(settings=loaded_settings),
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config: build_in_memory_uow_factory(store),
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: WorkflowService(uow_factory),
    )
    monkeypatch.setattr(
        "ctxledger.projection.writer.ResumeProjectionWriter",
        ResumeProjectionWriter,
    )

    exit_code = cli_module.main(
        [
            "write-resume-projection",
            "--workflow-instance-id",
            str(started.workflow_instance.workflow_instance_id),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resume projection written successfully." in captured.out
    assert f"JSON: {tmp_path / '.agent' / 'resume.json'}" in captured.out
    assert f"Markdown: {tmp_path / '.agent' / 'resume.md'}" in captured.out
    assert "Summary: 2 state update(s), 0 failure update(s)" in captured.out
    assert captured.err == ""

    json_path = tmp_path / ".agent" / "resume.json"
    markdown_path = tmp_path / ".agent" / "resume.md"

    assert json_path.exists()
    assert markdown_path.exists()

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )
    assert len(resume.projections) == 2
    assert {projection.target_path for projection in resume.projections} == {
        ".agent/resume.json",
        ".agent/resume.md",
    }
    assert all(projection.open_failure_count == 0 for projection in resume.projections)


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
        projections=(
            SimpleNamespace(
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
                last_successful_write_at=None,
                last_canonical_update_at=None,
                open_failure_count=0,
            ),
            SimpleNamespace(
                projection_type=ProjectionArtifactType.RESUME_MD,
                status=ProjectionStatus.STALE,
                target_path=".agent/resume.md",
                last_successful_write_at=None,
                last_canonical_update_at=None,
                open_failure_count=1,
            ),
        ),
        resumable_status=SimpleNamespace(value="resumable"),
        warnings=(
            ResumeIssue(
                code="stale_projection",
                message="resume projection is stale relative to canonical workflow state",
                details={"projection_type": "resume_md"},
            ),
        ),
        next_hint="Run CLI resume command",
    )

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresConfig.from_settings",
        lambda loaded_settings: SimpleNamespace(settings=loaded_settings),
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config: "fake-uow-factory",
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
    assert "Projections:" in captured.out
    assert "- resume_json: fresh [.agent/resume.json] failures=0" in captured.out
    assert "- resume_md: stale [.agent/resume.md] failures=1" in captured.out
    assert "Warnings:" in captured.out
    assert (
        "- stale_projection: resume projection is stale relative to canonical workflow state"
        in captured.out
    )
    assert "Next hint: Run CLI resume command" in captured.out
    assert captured.err == ""


def test_main_resume_workflow_renders_ignored_projection_warning_details(
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
            metadata={},
        ),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=uuid4(),
            ticket_id="CLI-RESUME-IGNORED-1",
            status=SimpleNamespace(value="running"),
            metadata={},
        ),
        attempt=SimpleNamespace(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_number=1,
            status=SimpleNamespace(value="failed"),
            failure_reason="projection write failed previously",
            verify_status=None,
            started_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00+00:00"),
            finished_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:05:00+00:00"),
        ),
        latest_checkpoint=SimpleNamespace(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_id=uuid4(),
            step_name="inspect_projection_failure",
            summary="Investigate ignored projection failures",
            checkpoint_json={"next_intended_action": "Review warning output"},
            created_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:04:00+00:00"),
        ),
        latest_verify_report=None,
        projections=(
            SimpleNamespace(
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FAILED,
                target_path=".agent/resume.json",
                last_successful_write_at=None,
                last_canonical_update_at=None,
                open_failure_count=0,
            ),
        ),
        resumable_status=SimpleNamespace(value="resumable"),
        warnings=(
            ResumeIssue(
                code="ignored_projection_failure",
                message="resume projection has ignored or previously resolved write failures",
                details={
                    "projection_type": "resume_json",
                    "target_path": ".agent/resume.json",
                    "open_failure_count": 0,
                    "failures": [
                        {
                            "projection_type": "resume_json",
                            "target_path": ".agent/resume.json",
                            "attempt_id": "11111111-1111-1111-1111-111111111111",
                            "error_code": "permission_error",
                            "error_message": "previous projection write was ignored",
                            "occurred_at": "2024-01-01T00:03:00+00:00",
                            "resolved_at": "2024-01-01T00:04:00+00:00",
                            "open_failure_count": 1,
                            "retry_count": 0,
                            "status": "ignored",
                        }
                    ],
                },
            ),
        ),
        next_hint="Review warning output",
    )

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresConfig.from_settings",
        lambda loaded_settings: SimpleNamespace(settings=loaded_settings),
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config: "fake-uow-factory",
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
    assert "Warnings:" in captured.out
    assert (
        "- ignored_projection_failure: "
        "resume projection has ignored or previously resolved write failures "
        "[projection=resume_json] [path=.agent/resume.json] [open_failures=0]"
        in captured.out
    )
    assert "Next hint: Review warning output" in captured.out
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
        projections=(
            SimpleNamespace(
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
                last_successful_write_at=SimpleNamespace(
                    isoformat=lambda: "2024-01-01T00:02:00+00:00"
                ),
                last_canonical_update_at=SimpleNamespace(
                    isoformat=lambda: "2024-01-01T00:02:00+00:00"
                ),
                open_failure_count=0,
            ),
        ),
        resumable_status=SimpleNamespace(value="resumable"),
        warnings=(
            ResumeIssue(
                code="ignored_projection_failure",
                message="resume projection has ignored or previously resolved write failures",
                details={
                    "projection_type": "resume_json",
                    "target_path": ".agent/resume.json",
                    "open_failure_count": 0,
                    "failures": [
                        {
                            "projection_type": "resume_json",
                            "target_path": ".agent/resume.json",
                            "attempt_id": str(attempt_id),
                            "error_code": "io_error",
                            "error_message": "previous projection write was resolved",
                            "occurred_at": "2024-01-01T00:01:30+00:00",
                            "resolved_at": "2024-01-01T00:02:00+00:00",
                            "open_failure_count": 1,
                            "retry_count": 0,
                            "status": "resolved",
                        }
                    ],
                },
            ),
        ),
        next_hint="Inspect JSON",
    )

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresConfig.from_settings",
        lambda loaded_settings: SimpleNamespace(settings=loaded_settings),
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config: "fake-uow-factory",
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
    assert payload["projections"] == [
        {
            "last_canonical_update_at": "2024-01-01T00:02:00+00:00",
            "last_successful_write_at": "2024-01-01T00:02:00+00:00",
            "open_failure_count": 0,
            "projection_type": "resume_json",
            "status": "fresh",
            "target_path": ".agent/resume.json",
        }
    ]
    assert payload["resumable_status"] == "resumable"
    assert payload["next_hint"] == "Inspect JSON"
    assert payload["warnings"] == [
        {
            "code": "ignored_projection_failure",
            "message": "resume projection has ignored or previously resolved write failures",
            "details": {
                "projection_type": "resume_json",
                "target_path": ".agent/resume.json",
                "open_failure_count": 0,
                "failures": [
                    {
                        "projection_type": "resume_json",
                        "target_path": ".agent/resume.json",
                        "attempt_id": str(attempt_id),
                        "error_code": "io_error",
                        "error_message": "previous projection write was resolved",
                        "occurred_at": "2024-01-01T00:01:30+00:00",
                        "resolved_at": "2024-01-01T00:02:00+00:00",
                        "open_failure_count": 1,
                        "retry_count": 0,
                        "status": "resolved",
                    }
                ],
            },
        }
    ]
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


def test_main_serve_renders_startup_summary_from_run_server(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received_kwargs: dict[str, object] = {}

    def fake_run_server(**kwargs: object) -> int:
        received_kwargs.update(kwargs)
        print("ctxledger 0.1.0 started", file=sys.stderr)
        print("health=ok", file=sys.stderr)
        print("readiness=ready", file=sys.stderr)
        print(
            "runtime=[{'transport': 'http', 'routes': ['runtime_introspection', "
            "'runtime_routes', 'runtime_tools', 'workflow_resume'], 'tools': []}]",
            file=sys.stderr,
        )
        print("mcp_endpoint=http://127.0.0.1:8080/mcp", file=sys.stderr)
        return 0

    monkeypatch.setattr("ctxledger.server.run_server", fake_run_server)

    exit_code = cli_module.main(["serve"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert received_kwargs == {}
    assert captured.out == ""
    assert "ctxledger 0.1.0 started" in captured.err
    assert "health=ok" in captured.err
    assert "readiness=ready" in captured.err
    assert "runtime=[{'transport': 'http'" in captured.err
    assert "mcp_endpoint=http://127.0.0.1:8080/mcp" in captured.err


def test_main_serve_passes_transport_and_network_overrides(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received_kwargs: dict[str, object] = {}

    def fake_run_server(**kwargs: object) -> int:
        received_kwargs.update(kwargs)
        print("ctxledger 0.1.0 started", file=sys.stderr)
        print("health=ok", file=sys.stderr)
        print("readiness=ready", file=sys.stderr)
        print(
            "runtime=[{'transport': 'http', 'routes': ['runtime_introspection', "
            "'runtime_routes', 'runtime_tools', 'workflow_resume'], 'tools': []}]",
            file=sys.stderr,
        )
        print("mcp_endpoint=http://0.0.0.0:9090/mcp", file=sys.stderr)
        return 0

    monkeypatch.setattr("ctxledger.server.run_server", fake_run_server)

    exit_code = cli_module.main(
        [
            "serve",
            "--transport",
            "http",
            "--host",
            "0.0.0.0",
            "--port",
            "9090",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert received_kwargs == {
        "transport": "http",
        "host": "0.0.0.0",
        "port": 9090,
    }
    assert captured.out == ""
    assert "mcp_endpoint=http://0.0.0.0:9090/mcp" in captured.err


def test_main_serve_returns_failure_when_run_server_reports_startup_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_server(**kwargs: object) -> int:
        print(
            "Startup failed: database schema is not ready",
            file=sys.stderr,
        )
        return 1

    monkeypatch.setattr("ctxledger.server.run_server", fake_run_server)

    exit_code = cli_module.main(["serve"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Startup failed: database schema is not ready" in captured.err


def test_main_serve_returns_failure_when_server_runtime_import_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original_import = __import__

    def fake_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "ctxledger.server" or (
            level == 1
            and name == "server"
            and globals
            and globals.get("__package__") == "ctxledger"
        ):
            raise ImportError("server module unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    exit_code = cli_module.main(["serve"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to import server runtime: server module unavailable" in captured.err

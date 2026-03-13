from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctxledger.config import ProjectionSettings
from ctxledger.db import InMemoryStore, build_in_memory_uow_factory
from ctxledger.projection.writer import (
    ProjectionWriteError,
    ResumeProjectionWriter,
)
from ctxledger.workflow.service import (
    CreateCheckpointInput,
    ProjectionArtifactType,
    ProjectionStatus,
    RecordProjectionFailureInput,
    RecordProjectionStateInput,
    RegisterWorkspaceInput,
    ResumeWorkflowInput,
    StartWorkflowInput,
    WorkflowService,
)


def make_service() -> WorkflowService:
    store = InMemoryStore.create()
    return WorkflowService(build_in_memory_uow_factory(store))


def make_projection_settings(
    *,
    directory_name: str = ".agent",
    write_json: bool = True,
    write_markdown: bool = True,
) -> ProjectionSettings:
    return ProjectionSettings(
        enabled=True,
        directory_name=directory_name,
        write_markdown=write_markdown,
        write_json=write_json,
    )


def create_resumable_workflow(
    service: WorkflowService,
    workspace_root: Path,
) -> tuple[object, object, object]:
    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo.git",
            canonical_path=str(workspace_root),
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="PROJ-123",
        )
    )
    checkpoint = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="edit_files",
            summary="Updated projection writer tests",
            checkpoint_json={
                "next_intended_action": "Run projection writer",
                "changed_files": ["src/app.py", "README.md"],
            },
        )
    )
    return workspace, started, checkpoint


def test_write_resume_projection_writes_json_and_markdown_under_workspace_root(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(),
    )

    result = writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    json_path = tmp_path / ".agent" / "resume.json"
    markdown_path = tmp_path / ".agent" / "resume.md"

    assert result.json_path == json_path.resolve()
    assert result.markdown_path == markdown_path.resolve()
    assert json_path.exists()
    assert markdown_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["resumable_status"] == "resumable"
    assert payload["next_hint"] == "Run projection writer"
    assert payload["latest_checkpoint"]["step_name"] == "edit_files"

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Resume" in markdown
    assert "## Workspace" in markdown
    assert "## Latest checkpoint" in markdown
    assert "Run projection writer" in markdown

    assert len(result.state_updates) == 2
    assert result.state_updates[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert result.state_updates[0].status == ProjectionStatus.FRESH
    assert result.state_updates[0].target_path == ".agent/resume.json"
    assert result.state_updates[1].projection_type == ProjectionArtifactType.RESUME_MD
    assert result.state_updates[1].target_path == ".agent/resume.md"


def test_write_resume_projection_can_write_only_json(tmp_path: Path) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(write_markdown=False),
    )

    result = writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.markdown_path is None
    assert (tmp_path / ".agent" / "resume.json").exists()
    assert not (tmp_path / ".agent" / "resume.md").exists()
    assert len(result.state_updates) == 1
    assert result.state_updates[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert result.state_updates[0].target_path == ".agent/resume.json"


def test_write_resume_projection_can_write_only_markdown(tmp_path: Path) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(write_json=False),
    )

    result = writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    assert result.json_path is None
    assert result.markdown_path == (tmp_path / ".agent" / "resume.md").resolve()
    assert not (tmp_path / ".agent" / "resume.json").exists()
    assert (tmp_path / ".agent" / "resume.md").exists()
    assert len(result.state_updates) == 1
    assert result.state_updates[0].projection_type == ProjectionArtifactType.RESUME_MD
    assert result.state_updates[0].target_path == ".agent/resume.md"


def test_write_resume_projection_allows_nested_safe_projection_directory(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(directory_name=".agent/state"),
    )

    result = writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    assert result.json_path == (tmp_path / ".agent" / "state" / "resume.json").resolve()
    assert (
        result.markdown_path == (tmp_path / ".agent" / "state" / "resume.md").resolve()
    )
    assert (tmp_path / ".agent" / "state" / "resume.json").exists()
    assert (tmp_path / ".agent" / "state" / "resume.md").exists()


def test_write_resume_projection_rejects_projection_directory_escape(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(directory_name="../outside"),
    )

    with pytest.raises(
        ProjectionWriteError,
        match="Projection path must stay within the workspace root",
    ):
        writer.write_resume_projection(
            workspace_root=tmp_path,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            workspace_id=workspace.workspace_id,
        )


def test_write_resume_projection_rejects_empty_projection_directory_name(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(directory_name="   "),
    )

    with pytest.raises(
        ProjectionWriteError,
        match="Projection directory name must not be empty",
    ):
        writer.write_resume_projection(
            workspace_root=tmp_path,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            workspace_id=workspace.workspace_id,
        )


def test_state_updates_can_be_recorded_back_into_workflow_service(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(write_markdown=False),
    )

    result = writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    for update in result.state_updates:
        recorded = service.record_resume_projection(update)
        assert recorded.status == ProjectionStatus.FRESH

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].last_successful_write_at is not None
    assert resume.projections[0].last_canonical_update_at is not None


def test_reconcile_resume_projection_records_state_updates(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(write_markdown=False),
    )

    result = writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    reconciled = service.reconcile_resume_projection(
        success_updates=result.state_updates,
        failure_updates=result.failure_updates,
    )

    assert len(reconciled) == 1
    assert reconciled[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert reconciled[0].status == ProjectionStatus.FRESH
    assert reconciled[0].target_path == ".agent/resume.json"

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].open_failure_count == 0


def test_write_and_reconcile_resume_projection_updates_canonical_projection_state(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(write_markdown=False),
    )

    result = writer.write_and_reconcile_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.failure_updates == ()

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].last_successful_write_at is not None
    assert resume.projections[0].last_canonical_update_at is not None


def test_reconcile_resume_projection_resolves_open_failures_on_success(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="disk full",
            error_code="io_error",
        )
    )

    reconciled = service.reconcile_resume_projection(
        success_updates=(
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
            ),
        ),
        failure_updates=(),
    )

    assert len(reconciled) == 1
    assert reconciled[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert reconciled[0].status == ProjectionStatus.FRESH

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].open_failure_count == 0
    assert all(warning.code != "open_projection_failure" for warning in resume.warnings)


def test_write_and_reconcile_resume_projection_clears_existing_failures(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="permission denied",
            error_code="permission_error",
        )
    )

    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(write_markdown=False),
    )

    result = writer.write_and_reconcile_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    assert result.failure_updates == ()

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].open_failure_count == 0
    assert all(warning.code != "open_projection_failure" for warning in resume.warnings)


def test_reconcile_resume_projection_partial_success_does_not_clear_unrelated_failures(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )
    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.md",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="json write failed",
            error_code="io_error",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            target_path=".agent/resume.md",
            error_message="markdown write failed",
            error_code="permission_error",
        )
    )

    reconciled = service.reconcile_resume_projection(
        success_updates=(
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
            ),
        ),
        failure_updates=(),
    )

    assert len(reconciled) == 1
    assert reconciled[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert reconciled[0].status == ProjectionStatus.FRESH

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }

    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FRESH
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 0
    )

    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FAILED
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 1

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_md"
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.md"


def test_write_and_reconcile_resume_projection_partial_success_preserves_other_failures(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.md",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            target_path=".agent/resume.md",
            error_message="existing markdown failure",
            error_code="permission_error",
        )
    )

    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(write_markdown=False),
    )

    result = writer.write_and_reconcile_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    assert result.failure_updates == ()
    assert len(result.state_updates) == 1
    assert result.state_updates[0].projection_type == ProjectionArtifactType.RESUME_JSON

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }

    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FRESH
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 0
    )

    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FAILED
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 1

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_md"


def test_failure_updates_can_be_recorded_in_memory_for_failed_projection(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)

    failure = RecordProjectionFailureInput(
        workspace_id=workspace.workspace_id,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
        target_path=".agent/resume.json",
        error_message="disk full",
        error_code="io_error",
    )
    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )

    failure_info = service.record_resume_projection_failure(failure)

    assert failure_info.projection_type == ProjectionArtifactType.RESUME_JSON
    assert failure_info.error_code == "io_error"
    assert failure_info.error_message == "disk full"
    assert failure_info.target_path == ".agent/resume.json"
    assert failure_info.attempt_id is None
    assert failure_info.open_failure_count == 1

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FAILED
    assert resume.projections[0].open_failure_count == 1
    assert any(warning.code == "open_projection_failure" for warning in resume.warnings)


def test_multiple_in_memory_projection_failures_increment_open_failure_count(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )

    first = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first failure",
            error_code="io_error",
        )
    )
    second = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            target_path=".agent/resume.md",
            error_message="second failure",
            error_code="permission_error",
        )
    )
    with service._uow_factory() as uow:
        assert uow.projection_failures is not None
        failures = uow.projection_failures.get_open_failures_by_workflow_id(
            workspace.workspace_id,
            started.workflow_instance.workflow_instance_id,
        )

    assert first.projection_type == ProjectionArtifactType.RESUME_JSON
    assert first.open_failure_count == 1
    assert first.retry_count == 0
    assert first.status == "open"
    assert first.occurred_at is not None
    assert first.resolved_at is None
    assert second.projection_type == ProjectionArtifactType.RESUME_MD
    assert second.open_failure_count == 1
    assert second.retry_count == 0
    assert second.status == "open"
    assert second.occurred_at is not None
    assert second.resolved_at is None
    assert len(failures) == 2
    assert failures[0].target_path == ".agent/resume.json"
    assert failures[0].attempt_id is None
    assert failures[0].retry_count == 0
    assert failures[0].status == "open"
    assert failures[0].occurred_at is not None
    assert failures[0].resolved_at is None
    assert failures[1].target_path == ".agent/resume.md"
    assert failures[1].attempt_id is None
    assert failures[1].retry_count == 0
    assert failures[1].status == "open"
    assert failures[1].occurred_at is not None
    assert failures[1].resolved_at is None

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FAILED
    assert resume.projections[0].open_failure_count == 1


def test_repeated_in_memory_projection_failures_increment_retry_count(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )

    first = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first failure",
            error_code="io_error",
        )
    )
    second = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="second failure",
            error_code="permission_error",
        )
    )

    with service._uow_factory() as uow:
        assert uow.projection_failures is not None
        failures = uow.projection_failures.get_open_failures_by_workflow_id(
            workspace.workspace_id,
            started.workflow_instance.workflow_instance_id,
        )

    assert first.open_failure_count == 1
    assert first.retry_count == 0
    assert first.status == "open"
    assert first.occurred_at is not None
    assert first.resolved_at is None
    assert second.open_failure_count == 2
    assert second.retry_count == 1
    assert second.status == "open"
    assert second.occurred_at is not None
    assert second.resolved_at is None

    assert len(failures) == 2
    assert failures[0].open_failure_count == 1
    assert failures[0].attempt_id is None
    assert failures[0].retry_count == 0
    assert failures[0].status == "open"
    assert failures[0].occurred_at is not None
    assert failures[0].resolved_at is None
    assert failures[1].open_failure_count == 2
    assert failures[1].attempt_id is None
    assert failures[1].retry_count == 1
    assert failures[1].status == "open"
    assert failures[1].occurred_at is not None
    assert failures[1].resolved_at is None

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]

    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["open_failure_count"] == 2
    assert open_failure_warnings[0].details["failures"][0]["retry_count"] == 0
    assert open_failure_warnings[0].details["failures"][0]["status"] == "open"
    assert open_failure_warnings[0].details["failures"][1]["retry_count"] == 1
    assert open_failure_warnings[0].details["failures"][1]["status"] == "open"


def test_ignore_in_memory_projection_failures_clears_open_failure_warning(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first failure",
            error_code="io_error",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="second failure",
            error_code="permission_error",
        )
    )

    ignored_count = service.ignore_resume_projection_failures(
        workspace_id=workspace.workspace_id,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
    )

    with service._uow_factory() as uow:
        assert uow.projection_failures is not None
        failures = uow.projection_failures.get_closed_failures_by_workflow_id(
            workspace.workspace_id,
            started.workflow_instance.workflow_instance_id,
        )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert ignored_count == 2
    assert len(failures) == 2
    assert all(failure.status == "ignored" for failure in failures)
    assert all(failure.occurred_at is not None for failure in failures)
    assert all(failure.resolved_at is not None for failure in failures)
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FAILED
    assert resume.projections[0].open_failure_count == 0
    assert all(warning.code != "open_projection_failure" for warning in resume.warnings)
    ignored_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "ignored_projection_failure"
    ]
    assert len(ignored_failure_warnings) == 1
    assert ignored_failure_warnings[0].details["projection_type"] == "resume_json"
    assert ignored_failure_warnings[0].details["target_path"] == ".agent/resume.json"
    assert ignored_failure_warnings[0].details["open_failure_count"] == 0
    assert len(ignored_failure_warnings[0].details["failures"]) == 2
    assert (
        ignored_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_json"
    )
    assert (
        ignored_failure_warnings[0].details["failures"][0]["target_path"]
        == ".agent/resume.json"
    )
    assert ignored_failure_warnings[0].details["failures"][0]["attempt_id"] is None
    assert (
        ignored_failure_warnings[0].details["failures"][0]["error_code"] == "io_error"
    )
    assert ignored_failure_warnings[0].details["failures"][0]["error_message"] == (
        "first failure"
    )
    assert ignored_failure_warnings[0].details["failures"][0]["occurred_at"] is not None
    assert ignored_failure_warnings[0].details["failures"][0]["resolved_at"] is not None
    assert ignored_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1
    assert ignored_failure_warnings[0].details["failures"][0]["retry_count"] == 0
    assert ignored_failure_warnings[0].details["failures"][0]["status"] == "ignored"
    assert (
        ignored_failure_warnings[0].details["failures"][1]["projection_type"]
        == "resume_json"
    )
    assert (
        ignored_failure_warnings[0].details["failures"][1]["target_path"]
        == ".agent/resume.json"
    )
    assert ignored_failure_warnings[0].details["failures"][1]["attempt_id"] is None
    assert ignored_failure_warnings[0].details["failures"][1]["error_code"] == (
        "permission_error"
    )
    assert ignored_failure_warnings[0].details["failures"][1]["error_message"] == (
        "second failure"
    )
    assert ignored_failure_warnings[0].details["failures"][1]["occurred_at"] is not None
    assert ignored_failure_warnings[0].details["failures"][1]["resolved_at"] is not None
    assert ignored_failure_warnings[0].details["failures"][1]["open_failure_count"] == 2
    assert ignored_failure_warnings[0].details["failures"][1]["retry_count"] == 1
    assert ignored_failure_warnings[0].details["failures"][1]["status"] == "ignored"


def test_state_update_object_contains_expected_identifiers(tmp_path: Path) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(write_markdown=False),
    )

    result = writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    update = result.state_updates[0]
    assert isinstance(update, RecordProjectionStateInput)
    assert update.workspace_id == workspace.workspace_id
    assert update.workflow_instance_id == started.workflow_instance.workflow_instance_id
    assert update.projection_type == ProjectionArtifactType.RESUME_JSON
    assert update.status == ProjectionStatus.FRESH
    assert update.target_path == ".agent/resume.json"


def test_written_json_contains_expected_identity_fields(tmp_path: Path) -> None:
    service = make_service()
    workspace, started, checkpoint = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(write_markdown=False),
    )

    writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    payload = json.loads(
        (tmp_path / ".agent" / "resume.json").read_text(encoding="utf-8")
    )

    assert payload["workspace"]["workspace_id"] == str(workspace.workspace_id)
    assert payload["workflow"]["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert payload["attempt"]["attempt_id"] == str(started.attempt.attempt_id)
    assert payload["latest_checkpoint"]["checkpoint_id"] == str(
        checkpoint.checkpoint.checkpoint_id
    )
    assert payload["projections"] == []
    assert payload["warnings"] == []


def test_written_markdown_contains_status_summary_for_resumable_workflow(
    tmp_path: Path,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(write_json=False),
    )

    writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    markdown = (tmp_path / ".agent" / "resume.md").read_text(encoding="utf-8")
    assert "## Resume status summary" in markdown
    assert "Workflow can be resumed from the latest checkpoint." in markdown
    assert "## Projections" in markdown
    assert "- No projection metadata available" in markdown


def test_write_resume_projection_records_json_failure_and_markdown_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(),
    )

    real_write_text = Path.write_text

    def flaky_write_text(
        self: Path, data: str, *, encoding: str | None = None, **kwargs: object
    ) -> int:
        if self.name == "resume.json":
            raise OSError("json write failed")
        return real_write_text(self, data, encoding=encoding, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write_text)

    result = writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.markdown_path == (tmp_path / ".agent" / "resume.md").resolve()
    assert not (tmp_path / ".agent" / "resume.json").exists()
    assert (tmp_path / ".agent" / "resume.md").exists()

    assert len(result.state_updates) == 2
    state_updates_by_type = {
        update.projection_type: update for update in result.state_updates
    }
    assert state_updates_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FAILED
    )
    assert state_updates_by_type[ProjectionArtifactType.RESUME_JSON].target_path == (
        ".agent/resume.json"
    )
    assert state_updates_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FRESH
    )
    assert state_updates_by_type[ProjectionArtifactType.RESUME_MD].target_path == (
        ".agent/resume.md"
    )

    assert len(result.failure_updates) == 1
    assert (
        result.failure_updates[0].projection_type == ProjectionArtifactType.RESUME_JSON
    )
    assert result.failure_updates[0].target_path == ".agent/resume.json"
    assert result.failure_updates[0].error_message == "json write failed"
    assert result.failure_updates[0].error_code is None

    service.reconcile_resume_projection(
        success_updates=result.state_updates,
        failure_updates=result.failure_updates,
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }

    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FAILED
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 1
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FRESH
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 0

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_json"
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.json"


def test_write_resume_projection_records_markdown_failure_and_json_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service()
    workspace, started, _ = create_resumable_workflow(service, tmp_path)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=make_projection_settings(),
    )

    real_write_text = Path.write_text

    def flaky_write_text(
        self: Path, data: str, *, encoding: str | None = None, **kwargs: object
    ) -> int:
        if self.name == "resume.md":
            raise OSError("markdown write failed")
        return real_write_text(self, data, encoding=encoding, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write_text)

    result = writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.markdown_path == (tmp_path / ".agent" / "resume.md").resolve()
    assert (tmp_path / ".agent" / "resume.json").exists()
    assert not (tmp_path / ".agent" / "resume.md").exists()

    assert len(result.state_updates) == 2
    state_updates_by_type = {
        update.projection_type: update for update in result.state_updates
    }
    assert state_updates_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FRESH
    )
    assert state_updates_by_type[ProjectionArtifactType.RESUME_JSON].target_path == (
        ".agent/resume.json"
    )
    assert state_updates_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FAILED
    )
    assert state_updates_by_type[ProjectionArtifactType.RESUME_MD].target_path == (
        ".agent/resume.md"
    )

    assert len(result.failure_updates) == 1
    assert result.failure_updates[0].projection_type == ProjectionArtifactType.RESUME_MD
    assert result.failure_updates[0].target_path == ".agent/resume.md"
    assert result.failure_updates[0].error_message == "markdown write failed"
    assert result.failure_updates[0].error_code is None

    service.reconcile_resume_projection(
        success_updates=result.state_updates,
        failure_updates=result.failure_updates,
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }

    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FRESH
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 0
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FAILED
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 1

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_md"
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.md"

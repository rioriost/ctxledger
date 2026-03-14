from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Iterator

import pytest

from ctxledger.config import ProjectionSettings, load_settings
from ctxledger.db.postgres import PostgresConfig, build_postgres_uow_factory
from ctxledger.projection.writer import ResumeProjectionWriter
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    ProjectionArtifactType,
    ProjectionStatus,
    RecordProjectionFailureInput,
    RecordProjectionStateInput,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeWorkflowInput,
    StartWorkflowInput,
    VerifyStatus,
    WorkflowAttemptStatus,
    WorkflowInstanceStatus,
    WorkflowService,
)

DOCKER_COMPOSE_FILE = (
    Path(__file__).resolve().parents[1] / "docker" / "docker-compose.yml"
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger"
POSTGRES_SERVICE_NAME = "postgres"


def _docker_compose_cmd(*args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(DOCKER_COMPOSE_FILE),
        *args,
    ]


def _run_command(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def _run_compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run_command(*_docker_compose_cmd(*args), check=check)


def _is_docker_available() -> bool:
    try:
        completed = _run_command("docker", "--version", check=False)
    except OSError:
        return False
    return completed.returncode == 0


def _wait_for_postgres_ready(timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        result = _run_compose("ps", "--format", "json", check=False)
        if result.returncode == 0 and "healthy" in result.stdout.lower():
            return
        time.sleep(1.0)

    logs = _run_compose("logs", POSTGRES_SERVICE_NAME, check=False)
    raise AssertionError(
        "PostgreSQL container did not become healthy in time.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
        f"logs:\n{logs.stdout}\n{logs.stderr}"
    )


def _apply_schema() -> None:
    schema_path = PROJECT_ROOT / "schemas" / "postgres.sql"
    command = (
        "docker exec -i ctxledger-postgres "
        "psql -U ctxledger -d ctxledger -v ON_ERROR_STOP=1"
    )
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        input=schema_path.read_text(encoding="utf-8"),
        shell=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "Failed to apply PostgreSQL schema.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def _truncate_workflow_tables() -> None:
    sql = """
    TRUNCATE TABLE
      verify_reports,
      workflow_checkpoints,
      workflow_attempts,
      workflow_instances,
      projection_failures,
      projection_states,
      workspaces
    RESTART IDENTITY CASCADE;
    """
    command = (
        "docker exec -i ctxledger-postgres "
        "psql -U ctxledger -d ctxledger -v ON_ERROR_STOP=1"
    )
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        input=sql,
        shell=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "Failed to truncate PostgreSQL workflow tables.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


@pytest.fixture(scope="session")
def postgres_integration_environment() -> Iterator[None]:
    if not _is_docker_available():
        pytest.skip("Docker is required for PostgreSQL integration tests")

    try:
        import psycopg  # noqa: F401
    except ImportError:
        pytest.skip("psycopg is required for PostgreSQL integration tests")

    up_result = _run_compose("up", "-d", POSTGRES_SERVICE_NAME, check=False)
    if up_result.returncode != 0:
        pytest.skip(
            "Could not start PostgreSQL container for integration tests.\n"
            f"{up_result.stdout}\n{up_result.stderr}"
        )

    try:
        _wait_for_postgres_ready()
        yield
    finally:
        _run_compose("down", "-v", check=False)


@pytest.fixture
def postgres_database_url(postgres_integration_environment: None) -> str:
    return os.getenv("CTXLEDGER_TEST_DATABASE_URL", DEFAULT_DATABASE_URL)


@pytest.fixture
def clean_postgres_database(
    postgres_integration_environment: None,
) -> Iterator[None]:
    _truncate_workflow_tables()
    try:
        yield
    finally:
        _truncate_workflow_tables()


@pytest.fixture
def postgres_workflow_service(
    postgres_database_url: str,
    clean_postgres_database: None,
) -> WorkflowService:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
    )
    return WorkflowService(build_postgres_uow_factory(config))


def test_postgres_workflow_service_round_trip_happy_path(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo.git",
            canonical_path="/tmp/integration-repo",
            default_branch="main",
            metadata={"suite": "integration"},
        )
    )

    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-123",
            metadata={"priority": "high"},
        )
    )

    checkpoint_result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="edit_files",
            summary="Persisted checkpoint to PostgreSQL",
            checkpoint_json={"next_intended_action": "Run tests"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    completed = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    terminal_resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert workspace.repo_url == "https://example.com/org/repo.git"
    assert started.workflow_instance.workspace_id == workspace.workspace_id
    assert started.attempt.attempt_number == 1

    assert checkpoint_result.checkpoint.step_name == "edit_files"
    assert checkpoint_result.verify_report is not None
    assert checkpoint_result.verify_report.status == VerifyStatus.PASSED

    assert resume.workspace.workspace_id == workspace.workspace_id
    assert resume.attempt is not None
    assert resume.latest_checkpoint is not None
    assert (
        resume.latest_checkpoint.checkpoint_id
        == checkpoint_result.checkpoint.checkpoint_id
    )
    assert resume.resumable_status == ResumableStatus.RESUMABLE
    assert resume.next_hint == "Run tests"

    assert completed.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert completed.attempt.finished_at is not None
    assert completed.verify_report is not None
    assert completed.verify_report.status == VerifyStatus.PASSED

    assert terminal_resume.resumable_status == ResumableStatus.TERMINAL


def test_postgres_terminal_resume_is_for_inspection_not_continuation(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-terminal.git",
            canonical_path="/tmp/integration-repo-terminal",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-TERMINAL-001",
        )
    )
    checkpoint_result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="finalize",
            checkpoint_json={"next_intended_action": "No further execution"},
        )
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    terminal_resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert terminal_resume.resumable_status == ResumableStatus.TERMINAL
    assert terminal_resume.attempt is not None
    assert terminal_resume.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert terminal_resume.latest_checkpoint is not None
    assert (
        terminal_resume.latest_checkpoint.checkpoint_id
        == checkpoint_result.checkpoint.checkpoint_id
    )
    assert (
        terminal_resume.next_hint
        == "Workflow is terminal. Inspect the final state instead of resuming execution."
    )


def test_postgres_workflow_service_resume_without_projection_state_is_still_resumable(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-2.git",
            canonical_path="/tmp/integration-repo-2",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-456",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Resume implementation"},
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.resumable_status == ResumableStatus.RESUMABLE
    assert resume.projections == ()
    assert all(warning.code != "stale_projection" for warning in resume.warnings)


def test_postgres_workflow_service_records_projection_failures(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection.git",
            canonical_path="/tmp/integration-repo-projection",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Retry projection write"},
        )
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

    first_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="disk full",
            error_code="io_error",
        )
    )
    second_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            target_path=".agent/resume.md",
            error_message="permission denied",
            error_code="permission_error",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert first_failure.attempt_id == started.attempt.attempt_id
    assert first_failure.open_failure_count == 1
    assert second_failure.attempt_id == started.attempt.attempt_id
    assert second_failure.open_failure_count == 1
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FAILED
    assert resume.projections[0].open_failure_count == 1
    assert any(warning.code == "open_projection_failure" for warning in resume.warnings)

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1

    open_failure_warning = open_failure_warnings[0]
    assert open_failure_warning.details["projection_type"] == "resume_json"
    assert open_failure_warning.details["open_failure_count"] == 1
    assert open_failure_warning.details["target_path"] == ".agent/resume.json"
    assert len(open_failure_warning.details["failures"]) == 1
    assert (
        open_failure_warning.details["failures"][0]["projection_type"] == "resume_json"
    )
    assert open_failure_warning.details["failures"][0]["error_code"] == "io_error"
    assert open_failure_warning.details["failures"][0]["occurred_at"] is not None
    assert open_failure_warning.details["failures"][0]["resolved_at"] is None


def test_postgres_workflow_service_resolves_projection_failures_after_successful_projection_write(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-resolve.git",
            canonical_path="/tmp/integration-repo-projection-resolve",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-RESOLVE-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Rewrite projection successfully"},
        )
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
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="disk full",
            error_code="io_error",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            target_path=".agent/resume.md",
            error_message="permission denied",
            error_code="permission_error",
        )
    )

    resolved_count = service.resolve_resume_projection_failures(
        workspace_id=workspace.workspace_id,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
    )
    recorded = service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path=".agent/resume.json",
        )
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resolved_count == 2
    assert recorded.status == ProjectionStatus.FRESH
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].open_failure_count == 0
    assert all(warning.code != "open_projection_failure" for warning in resume.warnings)


def test_postgres_workflow_service_reconcile_resolves_only_successful_projection_failures(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-partial.git",
            canonical_path="/tmp/integration-repo-projection-partial",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-PARTIAL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Rewrite only JSON projection successfully"
            },
        )
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
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="json disk full",
            error_code="io_error",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            target_path=".agent/resume.md",
            error_message="markdown permission denied",
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
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(reconciled) == 1
    assert reconciled[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert reconciled[0].status == ProjectionStatus.FRESH

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }
    assert set(projections_by_type) == {
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
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
    assert open_failure_warnings[0].details["open_failure_count"] == 1
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.md"


def test_postgres_workflow_service_reconcile_records_partial_json_failure_and_markdown_success(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-writer-json-fail.git",
            canonical_path="/tmp/integration-repo-projection-writer-json-fail",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-WRITER-JSON-FAIL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Persist markdown while json remains failed"
            },
        )
    )

    reconciled = service.reconcile_resume_projection(
        success_updates=(
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FAILED,
                target_path=".agent/resume.json",
            ),
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_MD,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.md",
            ),
        ),
        failure_updates=(
            RecordProjectionFailureInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                target_path=".agent/resume.json",
                error_message="json write failed",
                error_code="io_error",
            ),
        ),
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(reconciled) == 2

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }
    assert set(projections_by_type) == {
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
    }

    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FAILED
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 1
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].target_path == (
        ".agent/resume.json"
    )

    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FRESH
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 0
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].target_path == (
        ".agent/resume.md"
    )

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_json"
    assert open_failure_warnings[0].details["open_failure_count"] == 1
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.json"
    assert len(open_failure_warnings[0].details["failures"]) == 1
    assert (
        open_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_json"
    )
    assert open_failure_warnings[0].details["failures"][0]["target_path"] == (
        ".agent/resume.json"
    )
    assert open_failure_warnings[0].details["failures"][0]["error_code"] == "io_error"
    assert open_failure_warnings[0].details["failures"][0]["error_message"] == (
        "json write failed"
    )
    assert open_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1


def test_postgres_workflow_service_reconcile_records_partial_markdown_failure_and_json_success(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-writer-md-fail.git",
            canonical_path="/tmp/integration-repo-projection-writer-md-fail",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-WRITER-MD-FAIL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Persist json while markdown remains failed"
            },
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
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_MD,
                status=ProjectionStatus.FAILED,
                target_path=".agent/resume.md",
            ),
        ),
        failure_updates=(
            RecordProjectionFailureInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                projection_type=ProjectionArtifactType.RESUME_MD,
                target_path=".agent/resume.md",
                error_message="markdown write failed",
                error_code="permission_error",
            ),
        ),
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(reconciled) == 2

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }
    assert set(projections_by_type) == {
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
    }

    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FRESH
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 0
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].target_path == (
        ".agent/resume.json"
    )

    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FAILED
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 1
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].target_path == (
        ".agent/resume.md"
    )

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_md"
    assert open_failure_warnings[0].details["open_failure_count"] == 1
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.md"
    assert len(open_failure_warnings[0].details["failures"]) == 1
    assert (
        open_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_md"
    )
    assert open_failure_warnings[0].details["failures"][0]["target_path"] == (
        ".agent/resume.md"
    )
    assert (
        open_failure_warnings[0].details["failures"][0]["error_code"]
        == "permission_error"
    )
    assert open_failure_warnings[0].details["failures"][0]["error_message"] == (
        "markdown write failed"
    )
    assert open_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1


def test_postgres_workflow_service_reports_multiple_failures_for_same_projection(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-multi-failure.git",
            canonical_path="/tmp/integration-repo-projection-multi-failure",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-MULTI-FAIL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Inspect repeated JSON projection failures"
            },
        )
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
    first_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first json failure",
            error_code="io_error",
        )
    )
    second_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="second json failure",
            error_code="permission_error",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert first_failure.open_failure_count == 1
    assert second_failure.open_failure_count == 2

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FAILED
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].open_failure_count == 2

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_json"
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.json"
    assert open_failure_warnings[0].details["open_failure_count"] == 2
    assert len(open_failure_warnings[0].details["failures"]) == 2
    assert (
        open_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_json"
    )
    assert open_failure_warnings[0].details["failures"][0]["target_path"] == (
        ".agent/resume.json"
    )
    assert open_failure_warnings[0].details["failures"][0]["error_code"] == "io_error"
    assert open_failure_warnings[0].details["failures"][0]["error_message"] == (
        "first json failure"
    )
    assert open_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1
    assert (
        open_failure_warnings[0].details["failures"][1]["projection_type"]
        == "resume_json"
    )
    assert open_failure_warnings[0].details["failures"][1]["target_path"] == (
        ".agent/resume.json"
    )
    assert (
        open_failure_warnings[0].details["failures"][1]["error_code"]
        == "permission_error"
    )
    assert open_failure_warnings[0].details["failures"][1]["error_message"] == (
        "second json failure"
    )
    assert open_failure_warnings[0].details["failures"][1]["open_failure_count"] == 2


def test_postgres_workflow_service_resolve_clears_repeated_failures_for_same_projection(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-multi-failure-resolve.git",
            canonical_path="/tmp/integration-repo-projection-multi-failure-resolve",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-MULTI-RESOLVE-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Resolve repeated JSON projection failures"
            },
        )
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
    first_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first json failure",
            error_code="io_error",
        )
    )
    second_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="second json failure",
            error_code="permission_error",
        )
    )

    resolved_count = service.resolve_resume_projection_failures(
        workspace_id=workspace.workspace_id,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
    )
    recorded = service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path=".agent/resume.json",
        )
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert first_failure.open_failure_count == 1
    assert second_failure.open_failure_count == 2
    assert resolved_count == 2
    assert recorded.status == ProjectionStatus.FRESH

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].open_failure_count == 0
    assert all(warning.code != "open_projection_failure" for warning in resume.warnings)


def test_postgres_workflow_service_repeated_failures_increment_retry_count(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-retry-count.git",
            canonical_path="/tmp/integration-repo-projection-retry-count",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-RETRY-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Inspect retry_count for repeated JSON projection failures"
            },
        )
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
    first_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first json failure",
            error_code="io_error",
        )
    )
    second_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="second json failure",
            error_code="permission_error",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert first_failure.attempt_id == started.attempt.attempt_id
    assert first_failure.open_failure_count == 1
    assert first_failure.retry_count == 0
    assert first_failure.status == "open"
    assert first_failure.occurred_at is not None
    assert first_failure.resolved_at is None
    assert second_failure.attempt_id == started.attempt.attempt_id
    assert second_failure.open_failure_count == 2
    assert second_failure.retry_count == 1
    assert second_failure.status == "open"
    assert second_failure.occurred_at is not None
    assert second_failure.resolved_at is None

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_json"
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.json"
    assert open_failure_warnings[0].details["open_failure_count"] == 2
    assert len(open_failure_warnings[0].details["failures"]) == 2
    assert open_failure_warnings[0].details["failures"][0]["retry_count"] == 0
    assert open_failure_warnings[0].details["failures"][0]["status"] == "open"
    assert open_failure_warnings[0].details["failures"][0]["occurred_at"] is not None
    assert open_failure_warnings[0].details["failures"][0]["resolved_at"] is None
    assert open_failure_warnings[0].details["failures"][1]["retry_count"] == 1
    assert open_failure_warnings[0].details["failures"][1]["status"] == "open"
    assert open_failure_warnings[0].details["failures"][1]["occurred_at"] is not None
    assert open_failure_warnings[0].details["failures"][1]["resolved_at"] is None


def test_postgres_workflow_service_ignore_clears_open_projection_failure_warning(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-ignore.git",
            canonical_path="/tmp/integration-repo-projection-ignore",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-IGNORE-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Ignore repeated JSON projection failures"
            },
        )
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
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first json failure",
            error_code="io_error",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="second json failure",
            error_code="permission_error",
        )
    )

    ignored_count = service.ignore_resume_projection_failures(
        workspace_id=workspace.workspace_id,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert ignored_count == 2
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FAILED
    assert resume.projections[0].target_path == ".agent/resume.json"
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
    assert ignored_failure_warnings[0].details["failures"][0]["attempt_id"] == str(
        started.attempt.attempt_id
    )
    assert ignored_failure_warnings[0].details["failures"][0]["status"] == "ignored"
    assert ignored_failure_warnings[0].details["failures"][0]["resolved_at"] is not None
    assert ignored_failure_warnings[0].details["failures"][1]["attempt_id"] == str(
        started.attempt.attempt_id
    )
    assert ignored_failure_warnings[0].details["failures"][1]["status"] == "ignored"
    assert ignored_failure_warnings[0].details["failures"][1]["resolved_at"] is not None


def test_postgres_writer_and_reconcile_end_to_end_json_only(
    postgres_database_url: str,
    clean_postgres_database: None,
    tmp_path: Path,
) -> None:
    service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
            )
        )
    )

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-e2e-json-only.git",
            canonical_path=str(tmp_path),
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-E2E-JSON-ONLY-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Write JSON projection"},
        )
    )

    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=False,
            write_json=True,
        ),
    )

    result = writer.write_and_reconcile_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.markdown_path is None
    assert result.failure_updates == ()
    assert (tmp_path / ".agent" / "resume.json").exists()
    assert not (tmp_path / ".agent" / "resume.md").exists()

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].open_failure_count == 0
    assert all(warning.code != "open_projection_failure" for warning in resume.warnings)


def test_postgres_writer_and_reconcile_end_to_end_markdown_failure(
    postgres_database_url: str,
    clean_postgres_database: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
            )
        )
    )

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-e2e-md-failure.git",
            canonical_path=str(tmp_path),
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-E2E-MD-FAIL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Write projections"},
        )
    )

    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    real_write_text = Path.write_text

    def flaky_write_text(
        self: Path, data: str, *, encoding: str | None = None, **kwargs: object
    ) -> int:
        if self.name == "resume.md":
            raise OSError("markdown write failed")
        return real_write_text(self, data, encoding=encoding, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write_text)

    result = writer.write_and_reconcile_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.markdown_path == (tmp_path / ".agent" / "resume.md").resolve()
    assert (tmp_path / ".agent" / "resume.json").exists()
    assert not (tmp_path / ".agent" / "resume.md").exists()
    assert len(result.failure_updates) == 1
    assert result.failure_updates[0].projection_type == ProjectionArtifactType.RESUME_MD
    assert result.failure_updates[0].target_path == ".agent/resume.md"
    assert result.failure_updates[0].error_message == "markdown write failed"

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }
    assert set(projections_by_type) == {
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
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
    assert open_failure_warnings[0].details["open_failure_count"] == 1
    assert len(open_failure_warnings[0].details["failures"]) == 1
    assert (
        open_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_md"
    )
    assert open_failure_warnings[0].details["failures"][0]["target_path"] == (
        ".agent/resume.md"
    )
    assert open_failure_warnings[0].details["failures"][0]["error_code"] is None
    assert open_failure_warnings[0].details["failures"][0]["error_message"] == (
        "markdown write failed"
    )
    assert open_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1


def test_postgres_writer_and_reconcile_end_to_end_json_failure(
    postgres_database_url: str,
    clean_postgres_database: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
            )
        )
    )

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-e2e-json-failure.git",
            canonical_path=str(tmp_path),
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-E2E-JSON-FAIL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Write projections"},
        )
    )

    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    real_write_text = Path.write_text

    def flaky_write_text(
        self: Path, data: str, *, encoding: str | None = None, **kwargs: object
    ) -> int:
        if self.name == "resume.json":
            raise OSError("json write failed")
        return real_write_text(self, data, encoding=encoding, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write_text)

    result = writer.write_and_reconcile_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.markdown_path == (tmp_path / ".agent" / "resume.md").resolve()
    assert not (tmp_path / ".agent" / "resume.json").exists()
    assert (tmp_path / ".agent" / "resume.md").exists()
    assert len(result.failure_updates) == 1
    assert (
        result.failure_updates[0].projection_type == ProjectionArtifactType.RESUME_JSON
    )
    assert result.failure_updates[0].target_path == ".agent/resume.json"
    assert result.failure_updates[0].error_message == "json write failed"

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }
    assert set(projections_by_type) == {
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
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
    assert open_failure_warnings[0].details["open_failure_count"] == 1
    assert len(open_failure_warnings[0].details["failures"]) == 1
    assert (
        open_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_json"
    )
    assert open_failure_warnings[0].details["failures"][0]["target_path"] == (
        ".agent/resume.json"
    )
    assert open_failure_warnings[0].details["failures"][0]["error_code"] is None
    assert open_failure_warnings[0].details["failures"][0]["error_message"] == (
        "json write failed"
    )
    assert open_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1


def test_postgres_settings_can_build_uow_factory_from_loaded_settings(
    postgres_database_url: str,
    clean_postgres_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "CTXLEDGER_DATABASE_URL": postgres_database_url,
        "CTXLEDGER_TRANSPORT": "http",
        "CTXLEDGER_ENABLE_HTTP": "true",
        "CTXLEDGER_HOST": "127.0.0.1",
        "CTXLEDGER_PORT": "8080",
        "CTXLEDGER_HTTP_PATH": "/mcp",
        "CTXLEDGER_PROJECTION_ENABLED": "true",
        "CTXLEDGER_PROJECTION_DIRECTORY": ".agent",
        "CTXLEDGER_PROJECTION_WRITE_JSON": "true",
        "CTXLEDGER_PROJECTION_WRITE_MARKDOWN": "true",
        "CTXLEDGER_LOG_LEVEL": "info",
        "CTXLEDGER_LOG_STRUCTURED": "true",
        "CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS": "5",
        "CTXLEDGER_DB_STATEMENT_TIMEOUT_MS": "5000",
    }

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    settings = load_settings()
    config = PostgresConfig.from_settings(settings)
    service = WorkflowService(build_postgres_uow_factory(config))

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-3.git",
            canonical_path="/tmp/integration-repo-3",
            default_branch="main",
        )
    )

    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-789",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert config.database_url == postgres_database_url
    assert config.connect_timeout_seconds == 5
    assert config.statement_timeout_ms == 5000
    assert resume.resumable_status == ResumableStatus.BLOCKED


def test_postgres_projection_state_can_be_observed_after_projection_write(
    postgres_database_url: str,
    clean_postgres_database: None,
) -> None:
    service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
            )
        )
    )

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/projection.git",
            canonical_path="/tmp/integration-projection-repo",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJECTION-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Resume implementation"},
        )
    )

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path=".agent/resume.json",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.resumable_status == ResumableStatus.RESUMABLE
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].last_successful_write_at is not None
    assert resume.projections[0].last_canonical_update_at is not None
    assert resume.projections[0].open_failure_count == 0
    assert all(
        warning.code not in {"stale_projection", "missing_projection"}
        for warning in resume.warnings
    )

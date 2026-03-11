from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Iterator

import pytest

from ctxledger.config import load_settings
from ctxledger.db.postgres import PostgresConfig, build_postgres_uow_factory
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    ProjectionStatus,
    RecordProjectionStateInput,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeWorkflowInput,
    StartWorkflowInput,
    VerifyStatus,
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
    assert resume.projection is None
    assert all(warning.code != "stale_projection" for warning in resume.warnings)


def test_postgres_settings_can_build_uow_factory_from_loaded_settings(
    postgres_database_url: str,
    clean_postgres_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "CTXLEDGER_DATABASE_URL": postgres_database_url,
        "CTXLEDGER_TRANSPORT": "http",
        "CTXLEDGER_ENABLE_HTTP": "true",
        "CTXLEDGER_ENABLE_STDIO": "false",
        "CTXLEDGER_HOST": "127.0.0.1",
        "CTXLEDGER_PORT": "8080",
        "CTXLEDGER_HTTP_PATH": "/mcp",
        "CTXLEDGER_REQUIRE_AUTH": "false",
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
    assert resume.projection is not None
    assert resume.projection.status == ProjectionStatus.FRESH
    assert resume.projection.target_path == ".agent/resume.json"
    assert resume.projection.last_successful_write_at is not None
    assert resume.projection.last_canonical_update_at is not None
    assert resume.projection.open_failure_count == 0
    assert all(
        warning.code not in {"stale_projection", "missing_projection"}
        for warning in resume.warnings
    )

from __future__ import annotations

import pytest

from ctxledger.config import load_settings
from ctxledger.db.postgres import (
    PostgresConfig,
    build_connection_pool,
    build_postgres_uow_factory,
)
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeWorkflowInput,
    StartWorkflowInput,
    WorkflowAttemptStatus,
    WorkflowInstanceStatus,
    WorkflowService,
)


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


def test_postgres_settings_can_build_uow_factory_from_loaded_settings(
    postgres_pooled_uow_factory,
    postgres_database_url: str,
    clean_postgres_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "CTXLEDGER_DATABASE_URL": postgres_database_url,
        "CTXLEDGER_TRANSPORT": "http",
        "CTXLEDGER_ENABLE_HTTP": "true",
        "CTXLEDGER_HOST": "127.0.0.1",
        "CTXLEDGER_PORT": "8080",
        "CTXLEDGER_HTTP_PATH": "/mcp",
        "CTXLEDGER_LOG_LEVEL": "info",
        "CTXLEDGER_LOG_STRUCTURED": "true",
        "CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS": "5",
        "CTXLEDGER_DB_STATEMENT_TIMEOUT_MS": "5000",
    }

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    settings = load_settings()
    config = PostgresConfig.from_settings(settings)
    config = PostgresConfig(
        database_url=config.database_url,
        connect_timeout_seconds=config.connect_timeout_seconds,
        statement_timeout_ms=config.statement_timeout_ms,
        schema_name=clean_postgres_database,
    )
    connection_pool = build_connection_pool(config)
    try:
        service = WorkflowService(build_postgres_uow_factory(config, connection_pool))

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
    finally:
        connection_pool.close()

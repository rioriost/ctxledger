from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from ctxledger.workflow.service import (
    PersistenceError,
    VerifyReport,
    VerifyReportRepository,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptRepository,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowCheckpointRepository,
    WorkflowInstance,
    WorkflowInstanceRepository,
    WorkflowInstanceStatus,
    Workspace,
    WorkspaceRepository,
)

from .postgres_common import (
    Connection,
    _json_dumps,
    _json_loads,
    _optional_datetime,
    _optional_str_enum,
    _to_datetime,
    _to_uuid,
)


class PostgresWorkspaceRepository(WorkspaceRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM workspaces")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name not in {"created_at", "updated_at"}:
            raise PersistenceError(f"Unsupported datetime field '{field_name}' for workspaces")
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT MAX({field_name}) AS value FROM workspaces")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    workspace_id,
                    repo_url,
                    canonical_path,
                    default_branch,
                    metadata_json,
                    created_at,
                    updated_at
                FROM workspaces
                WHERE workspace_id = %s
                """,
                (workspace_id,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_workspace(row)

    def get_by_canonical_path(self, canonical_path: str) -> Workspace | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    workspace_id,
                    repo_url,
                    canonical_path,
                    default_branch,
                    metadata_json,
                    created_at,
                    updated_at
                FROM workspaces
                WHERE canonical_path = %s
                """,
                (canonical_path,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_workspace(row)

    def get_by_repo_url(self, repo_url: str) -> list[Workspace]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    workspace_id,
                    repo_url,
                    canonical_path,
                    default_branch,
                    metadata_json,
                    created_at,
                    updated_at
                FROM workspaces
                WHERE repo_url = %s
                ORDER BY created_at ASC
                """,
                (repo_url,),
            )
            rows = cur.fetchall()
        return [self._row_to_workspace(row) for row in rows]

    def create(self, workspace: Workspace) -> Workspace:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workspaces (
                    workspace_id,
                    repo_url,
                    canonical_path,
                    default_branch,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                RETURNING
                    workspace_id,
                    repo_url,
                    canonical_path,
                    default_branch,
                    metadata_json,
                    created_at,
                    updated_at
                """,
                (
                    workspace.workspace_id,
                    workspace.repo_url,
                    workspace.canonical_path,
                    workspace.default_branch,
                    _json_dumps(workspace.metadata),
                    workspace.created_at,
                    workspace.updated_at,
                ),
            )
            row = cur.fetchone()
        if row is None:
            raise PersistenceError("Failed to insert workspace")
        return self._row_to_workspace(row)

    def update(self, workspace: Workspace) -> Workspace:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workspaces
                SET
                    repo_url = %s,
                    canonical_path = %s,
                    default_branch = %s,
                    metadata_json = %s::jsonb,
                    updated_at = %s
                WHERE workspace_id = %s
                RETURNING
                    workspace_id,
                    repo_url,
                    canonical_path,
                    default_branch,
                    metadata_json,
                    created_at,
                    updated_at
                """,
                (
                    workspace.repo_url,
                    workspace.canonical_path,
                    workspace.default_branch,
                    _json_dumps(workspace.metadata),
                    workspace.updated_at,
                    workspace.workspace_id,
                ),
            )
            row = cur.fetchone()
        if row is None:
            raise PersistenceError("Failed to update workspace")
        return self._row_to_workspace(row)

    def _row_to_workspace(self, row: dict[str, Any]) -> Workspace:
        return Workspace(
            workspace_id=_to_uuid(row["workspace_id"]),
            repo_url=str(row["repo_url"]),
            canonical_path=str(row["canonical_path"]),
            default_branch=str(row["default_branch"]),
            metadata=_json_loads(row["metadata_json"]),
            created_at=_to_datetime(row["created_at"]),
            updated_at=_to_datetime(row["updated_at"]),
        )


class PostgresWorkflowInstanceRepository(WorkflowInstanceRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM workflow_instances")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def count_by_status(self) -> dict[str, int]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM workflow_instances
                GROUP BY status
                """
            )
            rows = cur.fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name not in {"created_at", "updated_at"}:
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for workflow_instances"
            )
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT MAX({field_name}) AS value FROM workflow_instances")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def get_by_id(self, workflow_instance_id: UUID) -> WorkflowInstance | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    workflow_instance_id,
                    workspace_id,
                    ticket_id,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                FROM workflow_instances
                WHERE workflow_instance_id = %s
                """,
                (workflow_instance_id,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_workflow(row)

    def get_running_by_workspace_id(self, workspace_id: UUID) -> WorkflowInstance | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    workflow_instance_id,
                    workspace_id,
                    ticket_id,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                FROM workflow_instances
                WHERE workspace_id = %s
                  AND status = 'running'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (workspace_id,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_workflow(row)

    def get_latest_by_workspace_id(self, workspace_id: UUID) -> WorkflowInstance | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    workflow_instance_id,
                    workspace_id,
                    ticket_id,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                FROM workflow_instances
                WHERE workspace_id = %s
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (workspace_id,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_workflow(row)

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[WorkflowInstance, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    workflow_instance_id,
                    workspace_id,
                    ticket_id,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                FROM workflow_instances
                WHERE workspace_id = %s
                ORDER BY updated_at DESC, created_at DESC
                LIMIT %s
                """,
                (workspace_id, limit),
            )
            rows = cur.fetchall()
        return tuple(self._row_to_workflow(row) for row in rows)

    def list_by_ticket_id(
        self,
        ticket_id: str,
        *,
        limit: int,
    ) -> tuple[WorkflowInstance, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    workflow_instance_id,
                    workspace_id,
                    ticket_id,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                FROM workflow_instances
                WHERE ticket_id = %s
                ORDER BY updated_at DESC, created_at DESC
                LIMIT %s
                """,
                (ticket_id, limit),
            )
            rows = cur.fetchall()
        return tuple(self._row_to_workflow(row) for row in rows)

    def list_recent(
        self,
        *,
        limit: int,
        status: str | None = None,
        workspace_id: UUID | None = None,
        ticket_id: str | None = None,
    ) -> tuple[WorkflowInstance, ...]:
        where_clauses: list[str] = []
        parameters: list[Any] = []

        if status is not None:
            where_clauses.append("status = %s")
            parameters.append(status)
        if workspace_id is not None:
            where_clauses.append("workspace_id = %s")
            parameters.append(workspace_id)
        if ticket_id is not None:
            where_clauses.append("ticket_id = %s")
            parameters.append(ticket_id)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    workflow_instance_id,
                    workspace_id,
                    ticket_id,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                FROM workflow_instances
                {where_sql}
                ORDER BY updated_at DESC, created_at DESC
                LIMIT %s
                """,
                (*parameters, limit),
            )
            rows = cur.fetchall()
        return tuple(self._row_to_workflow(row) for row in rows)

    def create(self, workflow: WorkflowInstance) -> WorkflowInstance:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_instances (
                    workflow_instance_id,
                    workspace_id,
                    ticket_id,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                RETURNING
                    workflow_instance_id,
                    workspace_id,
                    ticket_id,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                """,
                (
                    workflow.workflow_instance_id,
                    workflow.workspace_id,
                    workflow.ticket_id,
                    workflow.status.value,
                    _json_dumps(workflow.metadata),
                    workflow.created_at,
                    workflow.updated_at,
                ),
            )
            row = cur.fetchone()
        if row is None:
            raise PersistenceError("Failed to insert workflow instance")
        return self._row_to_workflow(row)

    def update(self, workflow: WorkflowInstance) -> WorkflowInstance:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workflow_instances
                SET
                    status = %s,
                    metadata_json = %s::jsonb,
                    updated_at = %s
                WHERE workflow_instance_id = %s
                RETURNING
                    workflow_instance_id,
                    workspace_id,
                    ticket_id,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                """,
                (
                    workflow.status.value,
                    _json_dumps(workflow.metadata),
                    workflow.updated_at,
                    workflow.workflow_instance_id,
                ),
            )
            row = cur.fetchone()
        if row is None:
            raise PersistenceError("Failed to update workflow instance")
        return self._row_to_workflow(row)

    def _row_to_workflow(self, row: dict[str, Any]) -> WorkflowInstance:
        return WorkflowInstance(
            workflow_instance_id=_to_uuid(row["workflow_instance_id"]),
            workspace_id=_to_uuid(row["workspace_id"]),
            ticket_id=str(row["ticket_id"]),
            status=WorkflowInstanceStatus(str(row["status"])),
            metadata=_json_loads(row["metadata_json"]),
            created_at=_to_datetime(row["created_at"]),
            updated_at=_to_datetime(row["updated_at"]),
        )


class PostgresWorkflowAttemptRepository(WorkflowAttemptRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM workflow_attempts")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def count_by_status(self) -> dict[str, int]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM workflow_attempts
                GROUP BY status
                """
            )
            rows = cur.fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name not in {"started_at", "finished_at", "created_at", "updated_at"}:
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for workflow_attempts"
            )
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT MAX({field_name}) AS value FROM workflow_attempts")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def get_by_id(self, attempt_id: UUID) -> WorkflowAttempt | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    attempt_id,
                    workflow_instance_id,
                    attempt_number,
                    status,
                    failure_reason,
                    verify_status,
                    started_at,
                    finished_at,
                    created_at,
                    updated_at
                FROM workflow_attempts
                WHERE attempt_id = %s
                """,
                (attempt_id,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_attempt(row)

    def get_running_by_workflow_id(self, workflow_instance_id: UUID) -> WorkflowAttempt | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    attempt_id,
                    workflow_instance_id,
                    attempt_number,
                    status,
                    failure_reason,
                    verify_status,
                    started_at,
                    finished_at,
                    created_at,
                    updated_at
                FROM workflow_attempts
                WHERE workflow_instance_id = %s
                  AND status = 'running'
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (workflow_instance_id,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_attempt(row)

    def get_latest_by_workflow_id(self, workflow_instance_id: UUID) -> WorkflowAttempt | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    attempt_id,
                    workflow_instance_id,
                    attempt_number,
                    status,
                    failure_reason,
                    verify_status,
                    started_at,
                    finished_at,
                    created_at,
                    updated_at
                FROM workflow_attempts
                WHERE workflow_instance_id = %s
                ORDER BY attempt_number DESC, started_at DESC
                LIMIT 1
                """,
                (workflow_instance_id,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_attempt(row)

    def get_next_attempt_number(self, workflow_instance_id: UUID) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(MAX(attempt_number), 0) AS max_attempt_number
                FROM workflow_attempts
                WHERE workflow_instance_id = %s
                """,
                (workflow_instance_id,),
            )
            row = cur.fetchone()
        if row is None:
            return 1
        return int(row["max_attempt_number"]) + 1

    def create(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_attempts (
                    attempt_id,
                    workflow_instance_id,
                    attempt_number,
                    status,
                    failure_reason,
                    verify_status,
                    started_at,
                    finished_at,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    attempt_id,
                    workflow_instance_id,
                    attempt_number,
                    status,
                    failure_reason,
                    verify_status,
                    started_at,
                    finished_at,
                    created_at,
                    updated_at
                """,
                (
                    attempt.attempt_id,
                    attempt.workflow_instance_id,
                    attempt.attempt_number,
                    attempt.status.value,
                    attempt.failure_reason,
                    attempt.verify_status.value if attempt.verify_status is not None else None,
                    attempt.started_at,
                    attempt.finished_at,
                    attempt.created_at,
                    attempt.updated_at,
                ),
            )
            row = cur.fetchone()
        if row is None:
            raise PersistenceError("Failed to insert workflow attempt")
        return self._row_to_attempt(row)

    def update(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workflow_attempts
                SET
                    status = %s,
                    failure_reason = %s,
                    verify_status = %s,
                    started_at = %s,
                    finished_at = %s,
                    updated_at = %s
                WHERE attempt_id = %s
                RETURNING
                    attempt_id,
                    workflow_instance_id,
                    attempt_number,
                    status,
                    failure_reason,
                    verify_status,
                    started_at,
                    finished_at,
                    created_at,
                    updated_at
                """,
                (
                    attempt.status.value,
                    attempt.failure_reason,
                    attempt.verify_status.value if attempt.verify_status is not None else None,
                    attempt.started_at,
                    attempt.finished_at,
                    attempt.updated_at,
                    attempt.attempt_id,
                ),
            )
            row = cur.fetchone()
        if row is None:
            raise PersistenceError("Failed to update workflow attempt")
        return self._row_to_attempt(row)

    def _row_to_attempt(self, row: dict[str, Any]) -> WorkflowAttempt:
        return WorkflowAttempt(
            attempt_id=_to_uuid(row["attempt_id"]),
            workflow_instance_id=_to_uuid(row["workflow_instance_id"]),
            attempt_number=int(row["attempt_number"]),
            status=WorkflowAttemptStatus(str(row["status"])),
            failure_reason=row["failure_reason"],
            verify_status=_optional_str_enum(VerifyStatus, row["verify_status"]),
            started_at=_to_datetime(row["started_at"]),
            finished_at=_optional_datetime(row["finished_at"]),
            created_at=_to_datetime(row["created_at"]),
            updated_at=_to_datetime(row["updated_at"]),
        )


class PostgresWorkflowCheckpointRepository(WorkflowCheckpointRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM workflow_checkpoints")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name != "created_at":
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for workflow_checkpoints"
            )
        with self._conn.cursor() as cur:
            cur.execute("SELECT MAX(created_at) AS value FROM workflow_checkpoints")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def get_latest_by_workflow_id(self, workflow_instance_id: UUID) -> WorkflowCheckpoint | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    checkpoint_id,
                    workflow_instance_id,
                    attempt_id,
                    step_name,
                    summary,
                    checkpoint_json,
                    created_at
                FROM workflow_checkpoints
                WHERE workflow_instance_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (workflow_instance_id,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_checkpoint(row)

    def get_latest_by_attempt_id(self, attempt_id: UUID) -> WorkflowCheckpoint | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    checkpoint_id,
                    workflow_instance_id,
                    attempt_id,
                    step_name,
                    summary,
                    checkpoint_json,
                    created_at
                FROM workflow_checkpoints
                WHERE attempt_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (attempt_id,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_checkpoint(row)

    def list_recent(self, *, limit: int) -> tuple[WorkflowCheckpoint, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    checkpoint_id,
                    workflow_instance_id,
                    attempt_id,
                    step_name,
                    summary,
                    checkpoint_json,
                    created_at
                FROM workflow_checkpoints
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return tuple(self._row_to_checkpoint(row) for row in rows)

    def create(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_checkpoints (
                    checkpoint_id,
                    workflow_instance_id,
                    attempt_id,
                    step_name,
                    summary,
                    checkpoint_json,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                RETURNING
                    checkpoint_id,
                    workflow_instance_id,
                    attempt_id,
                    step_name,
                    summary,
                    checkpoint_json,
                    created_at
                """,
                (
                    checkpoint.checkpoint_id,
                    checkpoint.workflow_instance_id,
                    checkpoint.attempt_id,
                    checkpoint.step_name,
                    checkpoint.summary,
                    _json_dumps(checkpoint.checkpoint_json),
                    checkpoint.created_at,
                ),
            )
            row = cur.fetchone()
        if row is None:
            raise PersistenceError("Failed to insert workflow checkpoint")
        return self._row_to_checkpoint(row)

    def _row_to_checkpoint(self, row: dict[str, Any]) -> WorkflowCheckpoint:
        return WorkflowCheckpoint(
            checkpoint_id=_to_uuid(row["checkpoint_id"]),
            workflow_instance_id=_to_uuid(row["workflow_instance_id"]),
            attempt_id=_to_uuid(row["attempt_id"]),
            step_name=str(row["step_name"]),
            summary=row["summary"],
            checkpoint_json=_json_loads(row["checkpoint_json"]),
            created_at=_to_datetime(row["created_at"]),
        )


class PostgresVerifyReportRepository(VerifyReportRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM verify_reports")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def count_by_status(self) -> dict[str, int]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM verify_reports
                GROUP BY status
                """
            )
            rows = cur.fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name != "created_at":
            raise PersistenceError(f"Unsupported datetime field '{field_name}' for verify_reports")
        with self._conn.cursor() as cur:
            cur.execute("SELECT MAX(created_at) AS value FROM verify_reports")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def get_latest_by_attempt_id(self, attempt_id: UUID) -> VerifyReport | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    verify_id,
                    attempt_id,
                    status,
                    report_json,
                    created_at
                FROM verify_reports
                WHERE attempt_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (attempt_id,),
            )
            row = cur.fetchone()
        return None if row is None else self._row_to_verify_report(row)

    def create(self, verify_report: VerifyReport) -> VerifyReport:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO verify_reports (
                    verify_id,
                    attempt_id,
                    status,
                    report_json,
                    created_at
                )
                VALUES (%s, %s, %s, %s::jsonb, %s)
                RETURNING
                    verify_id,
                    attempt_id,
                    status,
                    report_json,
                    created_at
                """,
                (
                    verify_report.verify_id,
                    verify_report.attempt_id,
                    verify_report.status.value,
                    _json_dumps(verify_report.report_json),
                    verify_report.created_at,
                ),
            )
            row = cur.fetchone()
        if row is None:
            raise PersistenceError("Failed to insert verify report")
        return self._row_to_verify_report(row)

    def _row_to_verify_report(self, row: dict[str, Any]) -> VerifyReport:
        return VerifyReport(
            verify_id=_to_uuid(row["verify_id"]),
            attempt_id=_to_uuid(row["attempt_id"]),
            status=VerifyStatus(str(row["status"])),
            report_json=_json_loads(row["report_json"]),
            created_at=_to_datetime(row["created_at"]),
        )


__all__ = [
    "PostgresVerifyReportRepository",
    "PostgresWorkflowAttemptRepository",
    "PostgresWorkflowCheckpointRepository",
    "PostgresWorkflowInstanceRepository",
    "PostgresWorkspaceRepository",
]

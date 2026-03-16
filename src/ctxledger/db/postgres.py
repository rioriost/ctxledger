from __future__ import annotations

import json
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from ctxledger.workflow.service import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryEmbeddingRepository,
    MemoryEpisodeRepository,
    MemoryItemRecord,
    MemoryItemRepository,
    PersistenceError,
    ProjectionArtifactType,
    ProjectionFailureInfo,
    ProjectionFailureRepository,
    ProjectionInfo,
    ProjectionStateRepository,
    ProjectionStatus,
    RecordProjectionFailureInput,
    RecordProjectionStateInput,
    UnitOfWork,
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
    utc_now,
)

try:
    import psycopg
    from psycopg import Connection
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover
    psycopg = None
    Connection = Any  # type: ignore[assignment]
    ConnectionPool = Any  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]


def _require_psycopg() -> None:
    if psycopg is None or dict_row is None:
        raise RuntimeError(
            "psycopg is required for PostgreSQL support. "
            "Install it with: pip install psycopg[binary]"
        )


def _require_connection_pool() -> None:
    if psycopg is None or dict_row is None or ConnectionPool is Any:
        raise RuntimeError(
            "psycopg-pool is required for PostgreSQL connection pooling. "
            "Install it with: pip install psycopg-pool"
        )


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _json_loads(value: Any) -> dict[str, Any]:
    loaded = _json_object_or_none(value)
    return loaded if loaded is not None else {}


def _json_object_or_none(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else None
    loaded = dict(value)
    return loaded if isinstance(loaded, dict) else None


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    raise PersistenceError(f"Expected datetime, got {type(value).__name__}")


def _to_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return _to_datetime(value)


def _optional_str_enum(enum_type: Any, value: Any) -> Any | None:
    if value is None:
        return None
    return enum_type(str(value))


def _normalized_schema_name(value: Any) -> str:
    return (str(value).strip() if value is not None else "public") or "public"


def _parse_embedding_values(raw_embedding: Any) -> tuple[float, ...]:
    if raw_embedding is None:
        return ()
    if isinstance(raw_embedding, str):
        normalized = raw_embedding.strip().strip("[]")
        if not normalized:
            return ()
        return tuple(
            float(part.strip()) for part in normalized.split(",") if part.strip()
        )
    return tuple(float(part) for part in raw_embedding)


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "schemas" / "postgres.sql"


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _episode_status(value: Any) -> str:
    return str(value) if value is not None else "recorded"


def _pgvector_literal(values: tuple[float, ...]) -> str:
    return "[" + ",".join(format(value, ".17g") for value in values) + "]"


def _memory_item_row_to_record(row: dict[str, Any]) -> MemoryItemRecord:
    return MemoryItemRecord(
        memory_id=_to_uuid(row["memory_id"]),
        workspace_id=(
            _to_uuid(row["workspace_id"])
            if row.get("workspace_id") is not None
            else None
        ),
        episode_id=(
            _to_uuid(row["episode_id"]) if row.get("episode_id") is not None else None
        ),
        type=str(row["type"]),
        provenance=str(row["provenance"]),
        content=str(row["content"]),
        metadata=_json_loads(row["metadata_json"]),
        created_at=_to_datetime(row["created_at"]),
        updated_at=_to_datetime(row["updated_at"]),
    )


def _memory_embedding_row_to_record(row: dict[str, Any]) -> MemoryEmbeddingRecord:
    embedding_values = _parse_embedding_values(row.get("embedding"))

    return MemoryEmbeddingRecord(
        memory_embedding_id=_to_uuid(row["memory_embedding_id"]),
        memory_id=_to_uuid(row["memory_id"]),
        embedding_model=str(row["embedding_model"]),
        embedding=embedding_values,
        content_hash=str(row["content_hash"])
        if row.get("content_hash") is not None
        else None,
        created_at=_to_datetime(row["created_at"]),
    )


def _connect(database_url: str) -> Connection:
    _require_psycopg()
    return psycopg.connect(database_url, row_factory=dict_row)  # type: ignore[misc]


def build_connection_pool(config: PostgresConfig) -> ConnectionPool:
    _require_connection_pool()
    kwargs: dict[str, Any] = {
        "conninfo": config.database_url,
        "min_size": config.pool_min_size,
        "max_size": config.pool_max_size,
        "timeout": config.pool_timeout_seconds,
        "kwargs": {"row_factory": dict_row},
        "open": True,
    }
    return ConnectionPool(**kwargs)  # type: ignore[misc]


@dataclass(slots=True, frozen=True)
class PostgresConfig:
    database_url: str
    connect_timeout_seconds: int = 5
    statement_timeout_ms: int | None = None
    schema_name: str = "public"
    pool_min_size: int = 1
    pool_max_size: int = 10
    pool_timeout_seconds: int = 5

    @classmethod
    def from_settings(cls, settings: Any) -> PostgresConfig:
        schema_name = getattr(
            getattr(settings, "database", None), "schema_name", "public"
        )
        normalized_schema_name = _normalized_schema_name(schema_name)
        return cls(
            database_url=settings.database.url,
            connect_timeout_seconds=settings.database.connect_timeout_seconds,
            statement_timeout_ms=settings.database.statement_timeout_ms,
            schema_name=normalized_schema_name,
            pool_min_size=getattr(settings.database, "pool_min_size", 1),
            pool_max_size=getattr(settings.database, "pool_max_size", 10),
            pool_timeout_seconds=getattr(settings.database, "pool_timeout_seconds", 5),
        )


class PostgresDatabaseHealthChecker:
    def __init__(self, config: PostgresConfig) -> None:
        self._config = config

    def ping(self) -> None:
        with _connect(self._config.database_url) as conn:
            self._apply_session_settings(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

    def schema_ready(self) -> bool:
        required_tables = {
            "workspaces",
            "workflow_instances",
            "workflow_attempts",
            "workflow_checkpoints",
            "verify_reports",
            "projection_states",
        }

        with _connect(self._config.database_url) as conn:
            self._apply_session_settings(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    """,
                    (self._config.schema_name,),
                )
                present = {str(row["table_name"]) for row in cur.fetchall()}

        return required_tables.issubset(present)

    def _apply_session_settings(self, conn: Connection) -> None:
        with conn.cursor() as cur:
            timeout_ms = (
                self._config.statement_timeout_ms
                if self._config.statement_timeout_ms is not None
                else 0
            )
            cur.execute(f"SET statement_timeout = {timeout_ms}")
            cur.execute(
                f"SET search_path TO {_quote_ident(self._config.schema_name)}, public"
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
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for workspaces"
            )
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

    def get_running_by_workspace_id(
        self, workspace_id: UUID
    ) -> WorkflowInstance | None:
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

    def get_running_by_workflow_id(
        self, workflow_instance_id: UUID
    ) -> WorkflowAttempt | None:
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

    def get_latest_by_workflow_id(
        self, workflow_instance_id: UUID
    ) -> WorkflowAttempt | None:
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
                    attempt.verify_status.value
                    if attempt.verify_status is not None
                    else None,
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
                    attempt.verify_status.value
                    if attempt.verify_status is not None
                    else None,
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

    def get_latest_by_workflow_id(
        self, workflow_instance_id: UUID
    ) -> WorkflowCheckpoint | None:
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
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for verify_reports"
            )
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


class PostgresMemoryEpisodeRepository(MemoryEpisodeRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM episodes")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name not in {"created_at", "updated_at"}:
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for episodes"
            )
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT MAX({field_name}) AS value FROM episodes")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def create(self, episode: EpisodeRecord) -> EpisodeRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO episodes (
                    episode_id,
                    workflow_instance_id,
                    attempt_id,
                    summary,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                RETURNING
                    episode_id,
                    workflow_instance_id,
                    attempt_id,
                    summary,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                """,
                (
                    episode.episode_id,
                    episode.workflow_instance_id,
                    episode.attempt_id,
                    episode.summary,
                    episode.status,
                    _json_dumps(episode.metadata),
                    episode.created_at,
                    episode.updated_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create episode")

        return self._row_to_episode(row)

    def list_by_workflow_id(
        self,
        workflow_instance_id: UUID,
        *,
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    episode_id,
                    workflow_instance_id,
                    attempt_id,
                    summary,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                FROM episodes
                WHERE workflow_instance_id = %s
                ORDER BY created_at DESC, episode_id DESC
                LIMIT %s
                """,
                (workflow_instance_id, limit),
            )
            rows = cur.fetchall()

        return tuple(self._row_to_episode(row) for row in rows)

    def _row_to_episode(
        self,
        row: dict[str, Any],
    ) -> EpisodeRecord:
        return EpisodeRecord(
            episode_id=_to_uuid(row["episode_id"]),
            workflow_instance_id=_to_uuid(row["workflow_instance_id"]),
            summary=str(row["summary"]),
            attempt_id=(
                _to_uuid(row["attempt_id"])
                if row.get("attempt_id") is not None
                else None
            ),
            metadata=_json_loads(row["metadata_json"]),
            status=_episode_status(row.get("status")),
            created_at=_to_datetime(row["created_at"]),
            updated_at=_to_datetime(row["updated_at"]),
        )


class PostgresMemoryItemRepository(MemoryItemRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM memory_items")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def count_by_provenance(self) -> dict[str, int]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT provenance, COUNT(*) AS count
                FROM memory_items
                GROUP BY provenance
                ORDER BY provenance ASC
                """
            )
            rows = cur.fetchall()
        return {str(row["provenance"]): int(row["count"]) for row in rows}

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name not in {"created_at", "updated_at"}:
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for memory_items"
            )
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT MAX({field_name}) AS value FROM memory_items")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_items (
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                RETURNING
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                """,
                (
                    memory_item.memory_id,
                    memory_item.workspace_id,
                    memory_item.episode_id,
                    memory_item.type,
                    memory_item.provenance,
                    memory_item.content,
                    _json_dumps(memory_item.metadata),
                    memory_item.created_at,
                    memory_item.updated_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create memory item")

        return _memory_item_row_to_record(row)

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_items
                WHERE workspace_id = %s
                ORDER BY created_at DESC, memory_id DESC
                LIMIT %s
                """,
                (workspace_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_item_row_to_record(row) for row in rows)

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_items
                WHERE episode_id = %s
                ORDER BY created_at DESC, memory_id DESC
                LIMIT %s
                """,
                (episode_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_item_row_to_record(row) for row in rows)


class PostgresMemoryEmbeddingRepository(MemoryEmbeddingRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM memory_embeddings")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name != "created_at":
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for memory_embeddings"
            )
        with self._conn.cursor() as cur:
            cur.execute("SELECT MAX(created_at) AS value FROM memory_embeddings")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_embeddings (
                    memory_embedding_id,
                    memory_id,
                    embedding_model,
                    embedding,
                    content_hash,
                    created_at
                )
                VALUES (%s, %s, %s, %s::vector, %s, %s)
                RETURNING
                    memory_embedding_id,
                    memory_id,
                    embedding_model,
                    embedding,
                    content_hash,
                    created_at
                """,
                (
                    embedding.memory_embedding_id,
                    embedding.memory_id,
                    embedding.embedding_model,
                    _pgvector_literal(embedding.embedding),
                    embedding.content_hash,
                    embedding.created_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create memory embedding")

        return _memory_embedding_row_to_record(row)

    def list_by_memory_id(
        self,
        memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_embedding_id,
                    memory_id,
                    embedding_model,
                    embedding,
                    content_hash,
                    created_at
                FROM memory_embeddings
                WHERE memory_id = %s
                ORDER BY created_at DESC, memory_embedding_id DESC
                LIMIT %s
                """,
                (memory_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_embedding_row_to_record(row) for row in rows)

    def find_similar(
        self,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
        workspace_id: UUID | None = None,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        workspace_filter_sql = ""
        if workspace_id is None:
            params: tuple[Any, ...] = (
                _pgvector_literal(query_embedding),
                limit,
            )
        else:
            workspace_filter_sql = "AND mi.workspace_id = %s"
            params = (
                workspace_id,
                _pgvector_literal(query_embedding),
                limit,
            )

        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    me.memory_embedding_id,
                    me.memory_id,
                    me.embedding_model,
                    me.embedding,
                    me.content_hash,
                    me.created_at
                FROM memory_embeddings AS me
                INNER JOIN memory_items AS mi
                    ON mi.memory_id = me.memory_id
                WHERE me.embedding IS NOT NULL
                  {workspace_filter_sql}
                ORDER BY me.embedding <-> %s::vector ASC, me.created_at DESC, me.memory_embedding_id DESC
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()

        return tuple(_memory_embedding_row_to_record(row) for row in rows)


class PostgresMemoryRelationRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM memory_relations")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name != "created_at":
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for memory_relations"
            )
        with self._conn.cursor() as cur:
            cur.execute("SELECT MAX(created_at) AS value FROM memory_relations")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])


class PostgresProjectionStateRepository(ProjectionStateRepository):
    """
    Minimal read-only projection state repository.

    The current workflow service only requires resume projection lookup.
    We map the most recently updated projection_state row for a workflow into
    `ProjectionInfo`.
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get_resume_projections(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
    ) -> tuple[ProjectionInfo, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ps.projection_type,
                    ps.status,
                    ps.target_path,
                    ps.last_successful_write_at,
                    ps.last_canonical_update_at,
                    COUNT(pf.projection_failure_id) FILTER (
                        WHERE pf.status = 'open'
                    ) AS open_failure_count
                FROM projection_states AS ps
                LEFT JOIN projection_failures AS pf
                  ON pf.workspace_id = ps.workspace_id
                 AND pf.workflow_instance_id = ps.workflow_instance_id
                 AND pf.projection_type = ps.projection_type
                WHERE ps.workspace_id = %s
                  AND ps.workflow_instance_id = %s
                GROUP BY
                    ps.projection_type,
                    ps.status,
                    ps.target_path,
                    ps.last_successful_write_at,
                    ps.last_canonical_update_at,
                    ps.updated_at
                ORDER BY
                    ps.last_canonical_update_at DESC NULLS LAST,
                    ps.last_successful_write_at DESC NULLS LAST,
                    ps.updated_at DESC,
                    ps.projection_type DESC
                """,
                (workspace_id, workflow_instance_id),
            )
            rows = cur.fetchall()

        return tuple(
            ProjectionInfo(
                projection_type=ProjectionArtifactType(str(row["projection_type"])),
                status=ProjectionStatus(str(row["status"])),
                target_path=row["target_path"],
                last_successful_write_at=_optional_datetime(
                    row["last_successful_write_at"]
                ),
                last_canonical_update_at=_optional_datetime(
                    row["last_canonical_update_at"]
                ),
                open_failure_count=int(row["open_failure_count"] or 0),
            )
            for row in rows
        )

    def record_resume_projection(self, projection: RecordProjectionStateInput) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO projection_states (
                    projection_state_id,
                    workspace_id,
                    workflow_instance_id,
                    projection_type,
                    target_path,
                    status,
                    last_successful_write_at,
                    last_canonical_update_at
                )
                VALUES (
                    gen_random_uuid(),
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT (workspace_id, projection_type)
                DO UPDATE SET
                    workflow_instance_id = EXCLUDED.workflow_instance_id,
                    target_path = EXCLUDED.target_path,
                    status = EXCLUDED.status,
                    last_successful_write_at = EXCLUDED.last_successful_write_at,
                    last_canonical_update_at = EXCLUDED.last_canonical_update_at
                """,
                (
                    projection.workspace_id,
                    projection.workflow_instance_id,
                    projection.projection_type.value,
                    projection.target_path,
                    projection.status.value,
                    projection.last_successful_write_at,
                    projection.last_canonical_update_at,
                ),
            )


class PostgresProjectionFailureRepository(ProjectionFailureRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_open_failures(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM projection_failures
                WHERE status = 'open'
                """
            )
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def list_failures(
        self,
        *,
        limit: int,
        status: str | None = None,
        open_only: bool = False,
    ) -> tuple[ProjectionFailureInfo, ...]:
        where_clauses: list[str] = []
        parameters: list[Any] = []

        if open_only:
            where_clauses.append("status = 'open'")
        elif status is not None:
            where_clauses.append("status = %s")
            parameters.append(status)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    projection_type,
                    attempt_id,
                    error_code,
                    error_message,
                    target_path,
                    retry_count,
                    occurred_at,
                    resolved_at,
                    status
                FROM projection_failures
                {where_sql}
                ORDER BY occurred_at DESC, projection_type ASC, target_path ASC
                LIMIT %s
                """,
                (*parameters, limit),
            )
            rows = cur.fetchall()

        failures: list[ProjectionFailureInfo] = []
        counts_by_key: dict[tuple[ProjectionArtifactType, str], int] = {}
        for row in rows:
            projection_type = ProjectionArtifactType(str(row["projection_type"]))
            failure_status = str(row["status"])
            count_key = (projection_type, failure_status)
            count_value = counts_by_key.get(count_key, 0) + 1
            counts_by_key[count_key] = count_value
            failures.append(
                ProjectionFailureInfo(
                    projection_type=projection_type,
                    error_code=row["error_code"],
                    error_message=row["error_message"],
                    target_path=row["target_path"],
                    attempt_id=_to_uuid(row["attempt_id"])
                    if row["attempt_id"] is not None
                    else None,
                    occurred_at=_optional_datetime(row["occurred_at"]),
                    resolved_at=_optional_datetime(row["resolved_at"]),
                    open_failure_count=count_value,
                    retry_count=int(row["retry_count"] or 0),
                    status=failure_status,
                )
            )

        return tuple(failures)

    def get_open_failures_by_workflow_id(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
    ) -> list[ProjectionFailureInfo]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    projection_type,
                    attempt_id,
                    error_code,
                    error_message,
                    target_path,
                    retry_count,
                    occurred_at,
                    resolved_at,
                    status
                FROM projection_failures
                WHERE workspace_id = %s
                  AND workflow_instance_id = %s
                  AND status = 'open'
                ORDER BY projection_type ASC, occurred_at ASC
                """,
                (workspace_id, workflow_instance_id),
            )
            rows = cur.fetchall()

        failures: list[ProjectionFailureInfo] = []
        open_counts_by_projection_type: dict[ProjectionArtifactType, int] = {}
        for row in rows:
            projection_type = ProjectionArtifactType(str(row["projection_type"]))
            open_count = open_counts_by_projection_type.get(projection_type, 0) + 1
            open_counts_by_projection_type[projection_type] = open_count
            failures.append(
                ProjectionFailureInfo(
                    projection_type=projection_type,
                    error_code=row["error_code"],
                    error_message=row["error_message"],
                    target_path=row["target_path"],
                    attempt_id=_to_uuid(row["attempt_id"])
                    if row["attempt_id"] is not None
                    else None,
                    occurred_at=_optional_datetime(row["occurred_at"]),
                    resolved_at=_optional_datetime(row["resolved_at"]),
                    open_failure_count=open_count,
                    retry_count=int(row["retry_count"] or 0),
                    status=str(row["status"]),
                )
            )
        return failures

    def get_closed_failures_by_workflow_id(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
    ) -> list[ProjectionFailureInfo]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    projection_type,
                    attempt_id,
                    error_code,
                    error_message,
                    target_path,
                    retry_count,
                    occurred_at,
                    resolved_at,
                    status
                FROM projection_failures
                WHERE workspace_id = %s
                  AND workflow_instance_id = %s
                  AND status IN ('resolved', 'ignored')
                ORDER BY projection_type ASC, occurred_at ASC
                """,
                (workspace_id, workflow_instance_id),
            )
            rows = cur.fetchall()

        failures: list[ProjectionFailureInfo] = []
        closed_counts_by_projection_type: dict[ProjectionArtifactType, int] = {}
        for row in rows:
            projection_type = ProjectionArtifactType(str(row["projection_type"]))
            closed_count = closed_counts_by_projection_type.get(projection_type, 0) + 1
            closed_counts_by_projection_type[projection_type] = closed_count
            failures.append(
                ProjectionFailureInfo(
                    projection_type=projection_type,
                    error_code=row["error_code"],
                    error_message=row["error_message"],
                    target_path=row["target_path"],
                    attempt_id=_to_uuid(row["attempt_id"])
                    if row["attempt_id"] is not None
                    else None,
                    occurred_at=_optional_datetime(row["occurred_at"]),
                    resolved_at=_optional_datetime(row["resolved_at"]),
                    open_failure_count=closed_count,
                    retry_count=int(row["retry_count"] or 0),
                    status=str(row["status"]),
                )
            )
        return failures

    def record_resume_projection_failure(
        self,
        failure: RecordProjectionFailureInput,
    ) -> ProjectionFailureInfo:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO projection_failures (
                    projection_failure_id,
                    workspace_id,
                    workflow_instance_id,
                    attempt_id,
                    projection_type,
                    target_path,
                    error_code,
                    error_message,
                    status,
                    retry_count,
                    occurred_at
                )
                VALUES (
                    gen_random_uuid(),
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'open',
                    %s,
                    now()
                )
                """,
                (
                    failure.workspace_id,
                    failure.workflow_instance_id,
                    failure.attempt_id,
                    failure.projection_type.value,
                    failure.target_path,
                    failure.error_code,
                    failure.error_message,
                    self._count_open_failures(
                        failure.workspace_id,
                        failure.workflow_instance_id,
                        failure.projection_type,
                    ),
                ),
            )

        open_failure_count = self._count_open_failures(
            failure.workspace_id,
            failure.workflow_instance_id,
            failure.projection_type,
        )
        return ProjectionFailureInfo(
            projection_type=failure.projection_type,
            error_code=failure.error_code,
            error_message=failure.error_message,
            target_path=failure.target_path,
            attempt_id=failure.attempt_id,
            occurred_at=utc_now(),
            open_failure_count=open_failure_count,
            retry_count=open_failure_count - 1,
            status="open",
        )

    def resolve_resume_projection_failures(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> int:
        with self._conn.cursor() as cur:
            if projection_type is None:
                cur.execute(
                    """
                    UPDATE projection_failures
                    SET
                        status = 'resolved',
                        resolved_at = now()
                    WHERE workspace_id = %s
                      AND workflow_instance_id = %s
                      AND status = 'open'
                    """,
                    (workspace_id, workflow_instance_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE projection_failures
                    SET
                        status = 'resolved',
                        resolved_at = now()
                    WHERE workspace_id = %s
                      AND workflow_instance_id = %s
                      AND projection_type = %s
                      AND status = 'open'
                    """,
                    (
                        workspace_id,
                        workflow_instance_id,
                        projection_type.value,
                    ),
                )
            return cur.rowcount

    def ignore_resume_projection_failures(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> int:
        with self._conn.cursor() as cur:
            if projection_type is None:
                cur.execute(
                    """
                    UPDATE projection_failures
                    SET
                        status = 'ignored',
                        resolved_at = now()
                    WHERE workspace_id = %s
                      AND workflow_instance_id = %s
                      AND status = 'open'
                    """,
                    (workspace_id, workflow_instance_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE projection_failures
                    SET
                        status = 'ignored',
                        resolved_at = now()
                    WHERE workspace_id = %s
                      AND workflow_instance_id = %s
                      AND projection_type = %s
                      AND status = 'open'
                    """,
                    (
                        workspace_id,
                        workflow_instance_id,
                        projection_type.value,
                    ),
                )
            return cur.rowcount

    def _count_open_failures(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> int:
        with self._conn.cursor() as cur:
            if projection_type is None:
                cur.execute(
                    """
                    SELECT COUNT(*) AS failure_count
                    FROM projection_failures
                    WHERE workspace_id = %s
                      AND workflow_instance_id = %s
                      AND status = 'open'
                    """,
                    (workspace_id, workflow_instance_id),
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(*) AS failure_count
                    FROM projection_failures
                    WHERE workspace_id = %s
                      AND workflow_instance_id = %s
                      AND projection_type = %s
                      AND status = 'open'
                    """,
                    (
                        workspace_id,
                        workflow_instance_id,
                        projection_type.value,
                    ),
                )
            row = cur.fetchone()
        if row is None:
            return 0
        return int(row["failure_count"])


class PostgresUnitOfWork(UnitOfWork, AbstractContextManager["PostgresUnitOfWork"]):
    def __init__(self, config: PostgresConfig, pool: ConnectionPool) -> None:
        self._config = config
        self._pool = pool
        self._conn: Connection | None = None
        self._pool_conn_context: Any = None
        self._committed = False

    def __enter__(self) -> PostgresUnitOfWork:
        self._pool_conn_context = self._pool.connection()
        self._conn = self._pool_conn_context.__enter__()
        self._apply_session_settings()
        self.workspaces = PostgresWorkspaceRepository(self._conn)
        self.workflow_instances = PostgresWorkflowInstanceRepository(self._conn)
        self.workflow_attempts = PostgresWorkflowAttemptRepository(self._conn)
        self.workflow_checkpoints = PostgresWorkflowCheckpointRepository(self._conn)
        self.verify_reports = PostgresVerifyReportRepository(self._conn)
        self.memory_episodes = PostgresMemoryEpisodeRepository(self._conn)
        self.memory_items = PostgresMemoryItemRepository(self._conn)
        self.memory_embeddings = PostgresMemoryEmbeddingRepository(self._conn)
        self.memory_relations = PostgresMemoryRelationRepository(self._conn)
        self.projection_states = PostgresProjectionStateRepository(self._conn)
        self.projection_failures = PostgresProjectionFailureRepository(self._conn)
        self._committed = False
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pool_conn_context = self._pool_conn_context
        conn = self._conn

        self._pool_conn_context = None
        self._conn = None

        if conn is None or pool_conn_context is None:
            return

        try:
            if exc_type is not None and not self._committed:
                conn.rollback()
            elif not self._committed:
                conn.rollback()
        finally:
            pool_conn_context.__exit__(exc_type, exc, tb)

    def commit(self) -> None:
        if self._conn is None:
            raise PersistenceError("Unit of work is not active")
        self._conn.commit()
        self._committed = True

    def rollback(self) -> None:
        if self._conn is None:
            raise PersistenceError("Unit of work is not active")
        self._conn.rollback()
        self._committed = False

    def _apply_session_settings(self) -> None:
        if self._conn is None:
            raise PersistenceError("Unit of work is not active")
        with self._conn.cursor() as cur:
            timeout_ms = (
                self._config.statement_timeout_ms
                if self._config.statement_timeout_ms is not None
                else 0
            )
            cur.execute(f"SET statement_timeout = {timeout_ms}")
            cur.execute(
                f"SET search_path TO {_quote_ident(self._config.schema_name)}, public"
            )


def build_postgres_uow_factory(
    config: PostgresConfig,
    pool: ConnectionPool | None = None,
) -> Any:
    if pool is None:
        raise ValueError(
            "A shared PostgreSQL connection pool is required to build a unit-of-work factory"
        )

    def _factory() -> PostgresUnitOfWork:
        return PostgresUnitOfWork(config, pool)

    return _factory


def load_postgres_schema_sql() -> str:
    return _schema_path().read_text(encoding="utf-8")


__all__ = [
    "PostgresConfig",
    "PostgresDatabaseHealthChecker",
    "PostgresMemoryEmbeddingRepository",
    "PostgresMemoryEpisodeRepository",
    "PostgresMemoryItemRepository",
    "PostgresMemoryRelationRepository",
    "PostgresProjectionStateRepository",
    "PostgresUnitOfWork",
    "PostgresVerifyReportRepository",
    "PostgresWorkflowAttemptRepository",
    "PostgresWorkflowCheckpointRepository",
    "PostgresWorkflowInstanceRepository",
    "PostgresWorkspaceRepository",
    "build_connection_pool",
    "build_postgres_uow_factory",
    "load_postgres_schema_sql",
]

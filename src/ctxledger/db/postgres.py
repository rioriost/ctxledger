from __future__ import annotations

import json
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from ctxledger.memory.service import (
    MemoryRelationRecord,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
)
from ctxledger.workflow.service import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryEmbeddingRepository,
    MemoryEpisodeRepository,
    MemoryItemRecord,
    MemoryItemRepository,
    PersistenceError,
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
        return tuple(float(part.strip()) for part in normalized.split(",") if part.strip())
    return tuple(float(part) for part in raw_embedding)


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "schemas" / "postgres.sql"


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _episode_status(value: Any) -> str:
    return str(value) if value is not None else "recorded"


def _pgvector_literal(values: tuple[float, ...]) -> str:
    return "[" + ",".join(format(value, ".17g") for value in values) + "]"


class AgeGraphStatus(StrEnum):
    AGE_UNAVAILABLE = "age_unavailable"
    GRAPH_UNAVAILABLE = "graph_unavailable"
    GRAPH_READY = "graph_ready"


def _memory_item_row_to_record(row: dict[str, Any]) -> MemoryItemRecord:
    return MemoryItemRecord(
        memory_id=_to_uuid(row["memory_id"]),
        workspace_id=(
            _to_uuid(row["workspace_id"]) if row.get("workspace_id") is not None else None
        ),
        episode_id=(_to_uuid(row["episode_id"]) if row.get("episode_id") is not None else None),
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
        content_hash=str(row["content_hash"]) if row.get("content_hash") is not None else None,
        created_at=_to_datetime(row["created_at"]),
    )


def _memory_summary_row_to_record(row: dict[str, Any]) -> MemorySummaryRecord:
    return MemorySummaryRecord(
        memory_summary_id=_to_uuid(row["memory_summary_id"]),
        workspace_id=_to_uuid(row["workspace_id"]),
        episode_id=(_to_uuid(row["episode_id"]) if row.get("episode_id") is not None else None),
        summary_text=str(row["summary_text"]),
        summary_kind=str(row["summary_kind"]),
        metadata=_json_loads(row["metadata_json"]),
        created_at=_to_datetime(row["created_at"]),
        updated_at=_to_datetime(row["updated_at"]),
    )


def _memory_summary_membership_row_to_record(
    row: dict[str, Any],
) -> MemorySummaryMembershipRecord:
    return MemorySummaryMembershipRecord(
        memory_summary_membership_id=_to_uuid(row["memory_summary_membership_id"]),
        memory_summary_id=_to_uuid(row["memory_summary_id"]),
        memory_id=_to_uuid(row["memory_id"]),
        membership_order=(
            int(row["membership_order"]) if row.get("membership_order") is not None else None
        ),
        metadata=_json_loads(row["metadata_json"]),
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
    age_enabled: bool = False
    age_graph_name: str = "ctxledger_memory"

    @classmethod
    def from_settings(cls, settings: Any) -> PostgresConfig:
        schema_name = getattr(getattr(settings, "database", None), "schema_name", "public")
        normalized_schema_name = _normalized_schema_name(schema_name)
        return cls(
            database_url=settings.database.url,
            connect_timeout_seconds=settings.database.connect_timeout_seconds,
            statement_timeout_ms=settings.database.statement_timeout_ms,
            schema_name=normalized_schema_name,
            pool_min_size=getattr(settings.database, "pool_min_size", 1),
            pool_max_size=getattr(settings.database, "pool_max_size", 10),
            pool_timeout_seconds=getattr(settings.database, "pool_timeout_seconds", 5),
            age_enabled=getattr(settings.database, "age_enabled", False),
            age_graph_name=getattr(settings.database, "age_graph_name", "ctxledger_memory"),
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

    def age_available(self) -> bool:
        with _connect(self._config.database_url) as conn:
            self._apply_session_settings(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM pg_extension
                    WHERE extname = 'age'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None

    def age_graph_available(self, graph_name: str) -> bool:
        if not self.age_available():
            return False

        with _connect(self._config.database_url) as conn:
            self._apply_session_settings(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM ag_catalog.ag_graph
                    WHERE name = %s
                    LIMIT 1
                    """,
                    (graph_name,),
                )
                return cur.fetchone() is not None

    def age_graph_status(self, graph_name: str) -> AgeGraphStatus:
        if not self.age_available():
            return AgeGraphStatus.AGE_UNAVAILABLE
        if not self.age_graph_available(graph_name):
            return AgeGraphStatus.GRAPH_UNAVAILABLE
        return AgeGraphStatus.GRAPH_READY

    def _apply_session_settings(self, conn: Connection) -> None:
        with conn.cursor() as cur:
            timeout_ms = (
                self._config.statement_timeout_ms
                if self._config.statement_timeout_ms is not None
                else 0
            )
            cur.execute(f"SET statement_timeout = {timeout_ms}")
            cur.execute(f"SET search_path TO {_quote_ident(self._config.schema_name)}, public")


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
            raise PersistenceError(f"Unsupported datetime field '{field_name}' for episodes")
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
            attempt_id=(_to_uuid(row["attempt_id"]) if row.get("attempt_id") is not None else None),
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
            raise PersistenceError(f"Unsupported datetime field '{field_name}' for memory_items")
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

    def list_workspace_root_items(
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
                  AND episode_id IS NULL
                ORDER BY created_at DESC, memory_id DESC
                LIMIT %s
                """,
                (workspace_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_item_row_to_record(row) for row in rows)

    def list_by_memory_ids(
        self,
        memory_ids: tuple[UUID, ...],
    ) -> tuple[MemoryItemRecord, ...]:
        if not memory_ids:
            return ()

        placeholders = ", ".join(["%s"] * len(memory_ids))
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
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
                WHERE memory_id IN ({placeholders})
                ORDER BY created_at DESC, memory_id DESC
                """,
                memory_ids,
            )
            rows = cur.fetchall()

        return tuple(_memory_item_row_to_record(row) for row in rows)

    def list_by_episode_ids(
        self,
        episode_ids: tuple[UUID, ...],
    ) -> tuple[MemoryItemRecord, ...]:
        if not episode_ids:
            return ()

        placeholders = ", ".join(["%s"] * len(episode_ids))
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
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
                WHERE episode_id IN ({placeholders})
                ORDER BY created_at DESC, memory_id DESC
                """,
                episode_ids,
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


class PostgresMemorySummaryRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def create(self, summary: MemorySummaryRecord) -> MemorySummaryRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_summaries (
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_text,
                    summary_kind,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                RETURNING
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_text,
                    summary_kind,
                    metadata_json,
                    created_at,
                    updated_at
                """,
                (
                    summary.memory_summary_id,
                    summary.workspace_id,
                    summary.episode_id,
                    summary.summary_text,
                    summary.summary_kind,
                    _json_dumps(summary.metadata),
                    summary.created_at,
                    summary.updated_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create memory summary")

        return _memory_summary_row_to_record(row)

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_text,
                    summary_kind,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_summaries
                WHERE workspace_id = %s
                ORDER BY created_at DESC, memory_summary_id DESC
                LIMIT %s
                """,
                (workspace_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_summary_row_to_record(row) for row in rows)

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_text,
                    summary_kind,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_summaries
                WHERE episode_id = %s
                ORDER BY created_at DESC, memory_summary_id DESC
                LIMIT %s
                """,
                (episode_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_summary_row_to_record(row) for row in rows)

    def list_by_summary_ids(
        self,
        summary_ids: tuple[UUID, ...],
    ) -> tuple[MemorySummaryRecord, ...]:
        if not summary_ids:
            return ()

        placeholders = ", ".join(["%s"] * len(summary_ids))
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_text,
                    summary_kind,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_summaries
                WHERE memory_summary_id IN ({placeholders})
                ORDER BY created_at DESC, memory_summary_id DESC
                """,
                summary_ids,
            )
            rows = cur.fetchall()

        return tuple(_memory_summary_row_to_record(row) for row in rows)


class PostgresMemorySummaryMembershipRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def create(
        self,
        membership: MemorySummaryMembershipRecord,
    ) -> MemorySummaryMembershipRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_summary_memberships (
                    memory_summary_membership_id,
                    memory_summary_id,
                    memory_id,
                    membership_order,
                    metadata_json,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                RETURNING
                    memory_summary_membership_id,
                    memory_summary_id,
                    memory_id,
                    membership_order,
                    metadata_json,
                    created_at
                """,
                (
                    membership.memory_summary_membership_id,
                    membership.memory_summary_id,
                    membership.memory_id,
                    membership.membership_order,
                    _json_dumps(membership.metadata),
                    membership.created_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create memory summary membership")

        return _memory_summary_membership_row_to_record(row)

    def list_by_summary_id(
        self,
        memory_summary_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryMembershipRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_summary_membership_id,
                    memory_summary_id,
                    memory_id,
                    membership_order,
                    metadata_json,
                    created_at
                FROM memory_summary_memberships
                WHERE memory_summary_id = %s
                ORDER BY membership_order ASC NULLS LAST, created_at ASC, memory_summary_membership_id ASC
                LIMIT %s
                """,
                (memory_summary_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_summary_membership_row_to_record(row) for row in rows)

    def list_by_summary_ids(
        self,
        memory_summary_ids: tuple[UUID, ...],
    ) -> tuple[MemorySummaryMembershipRecord, ...]:
        if not memory_summary_ids:
            return ()

        placeholders = ", ".join(["%s"] * len(memory_summary_ids))
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    memory_summary_membership_id,
                    memory_summary_id,
                    memory_id,
                    membership_order,
                    metadata_json,
                    created_at
                FROM memory_summary_memberships
                WHERE memory_summary_id IN ({placeholders})
                ORDER BY
                    memory_summary_id ASC,
                    membership_order ASC NULLS LAST,
                    created_at ASC,
                    memory_summary_membership_id ASC
                """,
                memory_summary_ids,
            )
            rows = cur.fetchall()

        return tuple(_memory_summary_membership_row_to_record(row) for row in rows)


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

    def list_distinct_support_target_memory_ids_by_source_memory_ids_via_age(
        self,
        source_memory_ids: tuple[UUID, ...],
        *,
        graph_name: str,
    ) -> tuple[UUID, ...]:
        if not source_memory_ids:
            return ()

        with self._conn.cursor() as cur:
            cur.execute("LOAD 'age'")
            cur.execute('SET search_path = ag_catalog, "$user", public')
            cur.execute(
                """
                SELECT target_memory_id
                FROM cypher(
                    %s,
                    $$
                    MATCH (source:memory_item)-[relation:supports]->(target:memory_item)
                    WHERE source.memory_id IN $source_memory_ids
                    RETURN DISTINCT target.memory_id AS target_memory_id
                    $$
                ) AS (
                    target_memory_id agtype
                )
                """,
                (
                    graph_name,
                    json.dumps(
                        {
                            "source_memory_ids": [
                                str(source_memory_id) for source_memory_id in source_memory_ids
                            ]
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )
            rows = cur.fetchall()

        target_memory_ids: list[UUID] = []
        for row in rows:
            raw_target_memory_id = row["target_memory_id"]
            if isinstance(raw_target_memory_id, str):
                normalized_target_memory_id = raw_target_memory_id.strip('"')
            else:
                normalized_target_memory_id = str(raw_target_memory_id)
            target_memory_ids.append(_to_uuid(normalized_target_memory_id))

        return tuple(target_memory_ids)

    def list_distinct_support_target_memory_ids_by_source_memory_ids_with_fallback(
        self,
        source_memory_ids: tuple[UUID, ...],
        *,
        graph_name: str,
        graph_status: AgeGraphStatus,
    ) -> tuple[UUID, ...]:
        if graph_status is not AgeGraphStatus.GRAPH_READY:
            return self.list_distinct_support_target_memory_ids_by_source_memory_ids(
                source_memory_ids
            )

        try:
            return self.list_distinct_support_target_memory_ids_by_source_memory_ids_via_age(
                source_memory_ids,
                graph_name=graph_name,
            )
        except Exception:
            return self.list_distinct_support_target_memory_ids_by_source_memory_ids(
                source_memory_ids
            )

    def list_distinct_support_target_memory_ids_by_source_memory_ids_for_config(
        self,
        source_memory_ids: tuple[UUID, ...],
        *,
        config: PostgresConfig,
        health_checker: PostgresDatabaseHealthChecker | None = None,
    ) -> tuple[UUID, ...]:
        if not config.age_enabled:
            return self.list_distinct_support_target_memory_ids_by_source_memory_ids(
                source_memory_ids
            )

        checker = health_checker or PostgresDatabaseHealthChecker(config)
        graph_status = checker.age_graph_status(config.age_graph_name)

        return self.list_distinct_support_target_memory_ids_by_source_memory_ids_with_fallback(
            source_memory_ids,
            graph_name=config.age_graph_name,
            graph_status=graph_status,
        )

    def create(self, relation: MemoryRelationRecord) -> MemoryRelationRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_relations (
                    memory_relation_id,
                    source_memory_id,
                    target_memory_id,
                    relation_type,
                    metadata_json,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                RETURNING
                    memory_relation_id,
                    source_memory_id,
                    target_memory_id,
                    relation_type,
                    metadata_json,
                    created_at
                """,
                (
                    relation.memory_relation_id,
                    relation.source_memory_id,
                    relation.target_memory_id,
                    relation.relation_type,
                    _json_dumps(relation.metadata),
                    relation.created_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create memory relation")

        return MemoryRelationRecord(
            memory_relation_id=_to_uuid(row["memory_relation_id"]),
            source_memory_id=_to_uuid(row["source_memory_id"]),
            target_memory_id=_to_uuid(row["target_memory_id"]),
            relation_type=str(row["relation_type"]),
            metadata=_json_loads(row["metadata_json"]),
            created_at=_to_datetime(row["created_at"]),
        )

    def list_by_source_memory_id(
        self,
        source_memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_relation_id,
                    source_memory_id,
                    target_memory_id,
                    relation_type,
                    metadata_json,
                    created_at
                FROM memory_relations
                WHERE source_memory_id = %s
                ORDER BY created_at DESC, memory_relation_id DESC
                LIMIT %s
                """,
                (source_memory_id, limit),
            )
            rows = cur.fetchall()

        return tuple(
            MemoryRelationRecord(
                memory_relation_id=_to_uuid(row["memory_relation_id"]),
                source_memory_id=_to_uuid(row["source_memory_id"]),
                target_memory_id=_to_uuid(row["target_memory_id"]),
                relation_type=str(row["relation_type"]),
                metadata=_json_loads(row["metadata_json"]),
                created_at=_to_datetime(row["created_at"]),
            )
            for row in rows
        )

    def list_by_source_memory_ids(
        self,
        source_memory_ids: tuple[UUID, ...],
    ) -> tuple[MemoryRelationRecord, ...]:
        if not source_memory_ids:
            return ()

        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_relation_id,
                    source_memory_id,
                    target_memory_id,
                    relation_type,
                    metadata_json,
                    created_at
                FROM memory_relations
                WHERE source_memory_id = ANY(%s)
                ORDER BY created_at DESC, memory_relation_id DESC
                """,
                (list(source_memory_ids),),
            )
            rows = cur.fetchall()

        return tuple(
            MemoryRelationRecord(
                memory_relation_id=_to_uuid(row["memory_relation_id"]),
                source_memory_id=_to_uuid(row["source_memory_id"]),
                target_memory_id=_to_uuid(row["target_memory_id"]),
                relation_type=str(row["relation_type"]),
                metadata=_json_loads(row["metadata_json"]),
                created_at=_to_datetime(row["created_at"]),
            )
            for row in rows
        )

    def list_distinct_support_target_memory_ids_by_source_memory_ids(
        self,
        source_memory_ids: tuple[UUID, ...],
    ) -> tuple[UUID, ...]:
        if not source_memory_ids:
            return ()

        with self._conn.cursor() as cur:
            cur.execute(
                """
                WITH ranked_support_relations AS (
                    SELECT
                        target_memory_id,
                        source_memory_id,
                        created_at,
                        memory_relation_id,
                        array_position(%s::uuid[], source_memory_id) AS source_position,
                        ROW_NUMBER() OVER (
                            PARTITION BY target_memory_id
                            ORDER BY
                                array_position(%s::uuid[], source_memory_id),
                                created_at DESC,
                                memory_relation_id DESC
                        ) AS target_rank
                    FROM memory_relations
                    WHERE source_memory_id = ANY(%s)
                      AND relation_type = 'supports'
                )
                SELECT target_memory_id
                FROM ranked_support_relations
                WHERE target_rank = 1
                ORDER BY source_position, created_at DESC, memory_relation_id DESC
                """,
                (
                    list(source_memory_ids),
                    list(source_memory_ids),
                    list(source_memory_ids),
                ),
            )
            rows = cur.fetchall()

        return tuple(_to_uuid(row["target_memory_id"]) for row in rows)

    def list_by_target_memory_id(
        self,
        target_memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_relation_id,
                    source_memory_id,
                    target_memory_id,
                    relation_type,
                    metadata_json,
                    created_at
                FROM memory_relations
                WHERE target_memory_id = %s
                ORDER BY created_at DESC, memory_relation_id DESC
                LIMIT %s
                """,
                (target_memory_id, limit),
            )
            rows = cur.fetchall()

        return tuple(
            MemoryRelationRecord(
                memory_relation_id=_to_uuid(row["memory_relation_id"]),
                source_memory_id=_to_uuid(row["source_memory_id"]),
                target_memory_id=_to_uuid(row["target_memory_id"]),
                relation_type=str(row["relation_type"]),
                metadata=_json_loads(row["metadata_json"]),
                created_at=_to_datetime(row["created_at"]),
            )
            for row in rows
        )

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


class PostgresUnitOfWork(UnitOfWork, AbstractContextManager["PostgresUnitOfWork"]):
    def __init__(self, config: PostgresConfig, pool: ConnectionPool) -> None:
        self._config = config
        self._pool = pool
        self._conn: Connection | None = None
        self._pool_conn_context: Any = None
        self._committed = False
        self.checkout_context_create_duration_ms = 0
        self.pool_checkout_duration_ms = 0
        self.session_setup_duration_ms = 0
        self.enter_duration_ms = 0

    def __enter__(self) -> PostgresUnitOfWork:
        enter_started_at = time.perf_counter()

        checkout_context_started_at = time.perf_counter()
        self._pool_conn_context = self._pool.connection()
        self.checkout_context_create_duration_ms = int(
            (time.perf_counter() - checkout_context_started_at) * 1000
        )

        pool_checkout_started_at = time.perf_counter()
        self._conn = self._pool_conn_context.__enter__()
        self.pool_checkout_duration_ms = int(
            (time.perf_counter() - pool_checkout_started_at) * 1000
        )

        session_setup_started_at = time.perf_counter()
        self._apply_session_settings()
        self.session_setup_duration_ms = int(
            (time.perf_counter() - session_setup_started_at) * 1000
        )

        self.workspaces = PostgresWorkspaceRepository(self._conn)
        self.workflow_instances = PostgresWorkflowInstanceRepository(self._conn)
        self.workflow_attempts = PostgresWorkflowAttemptRepository(self._conn)
        self.workflow_checkpoints = PostgresWorkflowCheckpointRepository(self._conn)
        self.verify_reports = PostgresVerifyReportRepository(self._conn)
        self.memory_episodes = PostgresMemoryEpisodeRepository(self._conn)
        self.memory_items = PostgresMemoryItemRepository(self._conn)
        self.memory_summaries = PostgresMemorySummaryRepository(self._conn)
        self.memory_summary_memberships = PostgresMemorySummaryMembershipRepository(self._conn)
        self.memory_embeddings = PostgresMemoryEmbeddingRepository(self._conn)
        self.memory_relations = PostgresMemoryRelationRepository(self._conn)
        self._committed = False
        self.enter_duration_ms = int((time.perf_counter() - enter_started_at) * 1000)
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
            cur.execute(f"SET search_path TO {_quote_ident(self._config.schema_name)}, public")


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
    "AgeGraphStatus",
    "PostgresConfig",
    "PostgresDatabaseHealthChecker",
    "PostgresMemoryEmbeddingRepository",
    "PostgresMemoryEpisodeRepository",
    "PostgresMemoryItemRepository",
    "PostgresMemoryRelationRepository",
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

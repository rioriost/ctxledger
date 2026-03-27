from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from ctxledger.memory.service import (
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
)
from ctxledger.workflow.service import (
    MemoryEmbeddingRecord,
    MemoryItemRecord,
    PersistenceError,
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
    GRAPH_STALE = "graph_stale"
    GRAPH_DEGRADED = "graph_degraded"
    GRAPH_READ_FAILED = "graph_read_failed"
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
        try:
            if not self.age_graph_available(graph_name):
                return AgeGraphStatus.GRAPH_UNAVAILABLE

            with _connect(self._config.database_url) as conn:
                self._apply_session_settings(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*)::bigint AS membership_count
                        FROM memory_summary_memberships
                        """
                    )
                    membership_row = cur.fetchone()
                    canonical_membership_count = (
                        int(membership_row["membership_count"])
                        if membership_row is not None
                        and membership_row.get("membership_count") is not None
                        else 0
                    )

                    cur.execute(
                        """
                        SELECT COUNT(*)::bigint AS graph_edge_count
                        FROM cypher(%s, $$
                            MATCH (:memory_summary)-[r:summarizes]->(:memory_item)
                            RETURN count(r) AS graph_edge_count
                        $$) AS (graph_edge_count agtype)
                        """,
                        (graph_name,),
                    )
                    graph_row = cur.fetchone()
                    graph_edge_count = (
                        int(str(graph_row["graph_edge_count"]).strip('"'))
                        if graph_row is not None and graph_row.get("graph_edge_count") is not None
                        else 0
                    )

            if canonical_membership_count == graph_edge_count:
                return AgeGraphStatus.GRAPH_READY
            if canonical_membership_count > 0 and graph_edge_count == 0:
                return AgeGraphStatus.GRAPH_UNAVAILABLE
            return AgeGraphStatus.GRAPH_STALE
        except Exception:
            return AgeGraphStatus.GRAPH_READ_FAILED

    def _apply_session_settings(self, conn: Connection) -> None:
        with conn.cursor() as cur:
            timeout_ms = (
                self._config.statement_timeout_ms
                if self._config.statement_timeout_ms is not None
                else 0
            )
            cur.execute(f"SET statement_timeout = {timeout_ms}")
            cur.execute(f"SET search_path TO {_quote_ident(self._config.schema_name)}, public")


__all__ = [
    "AgeGraphStatus",
    "Connection",
    "ConnectionPool",
    "PostgresConfig",
    "PostgresDatabaseHealthChecker",
    "build_connection_pool",
    "dict_row",
    "psycopg",
    "_connect",
    "_episode_status",
    "_json_dumps",
    "_json_loads",
    "_json_object_or_none",
    "_memory_embedding_row_to_record",
    "_memory_item_row_to_record",
    "_memory_summary_membership_row_to_record",
    "_memory_summary_row_to_record",
    "_normalized_schema_name",
    "_optional_datetime",
    "_optional_str_enum",
    "_parse_embedding_values",
    "_pgvector_literal",
    "_quote_ident",
    "_require_connection_pool",
    "_require_psycopg",
    "_schema_path",
    "_to_datetime",
    "_to_uuid",
]

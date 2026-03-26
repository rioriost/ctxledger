from __future__ import annotations

import time
from contextlib import AbstractContextManager
from typing import Any

from ctxledger.workflow.service import PersistenceError, UnitOfWork

from .postgres_common import Connection, ConnectionPool, PostgresConfig, _quote_ident, _schema_path
from .postgres_memory import (
    PostgresMemoryEmbeddingRepository,
    PostgresMemoryEpisodeRepository,
    PostgresMemoryItemRepository,
    PostgresMemoryRelationRepository,
    PostgresMemorySummaryMembershipRepository,
    PostgresMemorySummaryRepository,
)
from .postgres_workflow import (
    PostgresVerifyReportRepository,
    PostgresWorkflowAttemptRepository,
    PostgresWorkflowCheckpointRepository,
    PostgresWorkflowInstanceRepository,
    PostgresWorkspaceRepository,
)


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
    "PostgresUnitOfWork",
    "build_postgres_uow_factory",
    "load_postgres_schema_sql",
]

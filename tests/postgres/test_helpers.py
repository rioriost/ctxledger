from __future__ import annotations

import types
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.db import postgres as postgres_module
from ctxledger.db import postgres_common as postgres_common_module
from ctxledger.db.postgres import (
    PostgresConfig,
    PostgresDatabaseHealthChecker,
    PostgresUnitOfWork,
    PostgresVerifyReportRepository,
    PostgresWorkflowAttemptRepository,
    PostgresWorkflowCheckpointRepository,
    PostgresWorkflowInstanceRepository,
    PostgresWorkspaceRepository,
    _connect,
    _json_dumps,
    _json_loads,
    _optional_datetime,
    _optional_str_enum,
    _require_psycopg,
    _schema_path,
    _to_datetime,
    _to_uuid,
    build_postgres_uow_factory,
    load_postgres_schema_sql,
)
from ctxledger.workflow.service import (
    PersistenceError,
    VerifyStatus,
    WorkflowAttemptStatus,
    WorkflowInstanceStatus,
)


class FakeCursor:
    def __init__(
        self,
        *,
        fetchone_result: object | None = None,
        fetchall_result: list[dict[str, object]] | None = None,
        executed: list[tuple[str, object | None]] | None = None,
        rowcount: int = 0,
    ) -> None:
        self._fetchone_result = fetchone_result
        self._fetchall_result = fetchall_result or []
        self._executed = executed if executed is not None else []
        self.rowcount = rowcount

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query: str, params: object = None) -> None:
        self._executed.append((query.strip(), params))

    def fetchone(self) -> object | None:
        return self._fetchone_result

    def fetchall(self) -> list[dict[str, object]]:
        return list(self._fetchall_result)


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1


class FakePoolConnectionContext:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection
        self.enter_calls = 0
        self.exit_calls = 0
        self.exit_args: list[tuple[object, object, object]] = []

    def __enter__(self) -> FakeConnection:
        self.enter_calls += 1
        return self._connection

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exit_calls += 1
        self.exit_args.append((exc_type, exc, tb))
        self._connection.close()


class FakeConnectionPool:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection
        self.connection_calls = 0
        self.contexts: list[FakePoolConnectionContext] = []

    def connection(self) -> FakePoolConnectionContext:
        self.connection_calls += 1
        context = FakePoolConnectionContext(self._connection)
        self.contexts.append(context)
        return context


def test_require_psycopg_raises_when_driver_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(postgres_common_module, "psycopg", None)
    monkeypatch.setattr(postgres_common_module, "dict_row", None)

    with pytest.raises(RuntimeError, match="psycopg is required for PostgreSQL support"):
        _require_psycopg()


def test_require_psycopg_succeeds_when_driver_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(postgres_common_module, "psycopg", object())
    monkeypatch.setattr(postgres_common_module, "dict_row", object())

    _require_psycopg()


def test_json_dumps_returns_compact_sorted_json() -> None:
    assert _json_dumps({"b": 2, "a": 1}) == '{"a":1,"b":2}'


def test_json_loads_handles_none_dict_json_string_and_mapping() -> None:
    class MappingLike:
        def __iter__(self):
            return iter((("x", 1), ("y", 2)))

    assert _json_loads(None) == {}
    assert _json_loads({"a": 1}) == {"a": 1}
    assert _json_loads('{"b":2}') == {"b": 2}
    assert _json_loads("[1,2,3]") == {}
    assert _json_loads(MappingLike()) == {"x": 1, "y": 2}


def test_to_datetime_keeps_timezone_aware_values() -> None:
    value = datetime(2024, 1, 1, tzinfo=UTC)
    assert _to_datetime(value) is value


def test_to_datetime_adds_utc_to_naive_datetime() -> None:
    value = datetime(2024, 1, 1)
    result = _to_datetime(value)

    assert result.tzinfo == UTC
    assert result.year == 2024


def test_to_datetime_raises_for_invalid_type() -> None:
    with pytest.raises(PersistenceError, match="Expected datetime, got str"):
        _to_datetime("2024-01-01")


def test_to_uuid_accepts_uuid_and_string() -> None:
    value = uuid4()

    assert _to_uuid(value) == value
    assert _to_uuid(str(value)) == value


def test_optional_datetime_returns_none_or_datetime() -> None:
    value = datetime(2024, 1, 1, tzinfo=UTC)

    assert _optional_datetime(None) is None
    assert _optional_datetime(value) == value


def test_optional_str_enum_returns_none_or_enum_value() -> None:
    assert _optional_str_enum(VerifyStatus, None) is None
    assert _optional_str_enum(VerifyStatus, "passed") is VerifyStatus.PASSED


def test_schema_path_points_to_bundled_schema_file() -> None:
    path = _schema_path()

    assert isinstance(path, Path)
    assert path.name == "postgres.sql"
    assert path.parent.name == "schemas"
    assert path.exists()


def test_connect_uses_psycopg_connect_with_dict_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []

    fake_psycopg = types.SimpleNamespace(
        connect=lambda database_url, row_factory: (
            calls.append((database_url, row_factory)) or "CONN"
        )
    )
    marker = object()

    monkeypatch.setattr(postgres_common_module, "psycopg", fake_psycopg)
    monkeypatch.setattr(postgres_common_module, "dict_row", marker)

    result = _connect("postgresql://example/db")

    assert result == "CONN"
    assert calls == [("postgresql://example/db", marker)]


def test_postgres_config_from_settings_reads_database_values() -> None:
    settings = SimpleNamespace(
        database=SimpleNamespace(
            url="postgresql://ctxledger/db",
            connect_timeout_seconds=9,
            statement_timeout_ms=3210,
            pool_min_size=2,
            pool_max_size=11,
            pool_timeout_seconds=7,
        )
    )

    config = PostgresConfig.from_settings(settings)

    assert config == PostgresConfig(
        database_url="postgresql://ctxledger/db",
        connect_timeout_seconds=9,
        statement_timeout_ms=3210,
        pool_min_size=2,
        pool_max_size=11,
        pool_timeout_seconds=7,
    )


def test_health_checker_ping_executes_select_and_session_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed: list[tuple[str, object | None]] = []
    cursor = FakeCursor(fetchone_result={"?column?": 1}, executed=executed)
    connection = FakeConnection(cursor)

    monkeypatch.setattr(postgres_common_module, "_connect", lambda database_url: connection)

    checker = PostgresDatabaseHealthChecker(
        PostgresConfig(
            database_url="postgresql://ctxledger/db",
            statement_timeout_ms=1234,
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
        )
    )
    checker.ping()

    assert executed == [
        ("SET statement_timeout = 1234", None),
        ('SET search_path TO "public", public', None),
        ("SELECT 1", None),
    ]


def test_health_checker_schema_ready_returns_false_when_tables_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = FakeCursor(
        fetchall_result=[
            {"table_name": "workspaces"},
            {"table_name": "workflow_instances"},
        ]
    )
    connection = FakeConnection(cursor)

    monkeypatch.setattr(postgres_common_module, "_connect", lambda database_url: connection)

    checker = PostgresDatabaseHealthChecker(
        PostgresConfig(
            database_url="postgresql://ctxledger/db",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
        )
    )

    assert checker.schema_ready() is False


def test_build_postgres_uow_factory_returns_factory_bound_to_config() -> None:
    config = PostgresConfig(database_url="postgresql://ctxledger/db")
    pool = FakeConnectionPool(FakeConnection(FakeCursor()))
    factory = build_postgres_uow_factory(config, pool)

    assert callable(factory)
    uow = factory()

    assert uow._config == config
    assert uow._pool is pool


def test_postgres_workspace_repository_getters_create_update_and_row_mapping() -> None:
    workspace_id = uuid4()
    created_at = datetime(2024, 1, 1, tzinfo=UTC)
    updated_at = datetime(2024, 1, 2, tzinfo=UTC)
    row = {
        "workspace_id": str(workspace_id),
        "repo_url": "https://example.com/repo.git",
        "canonical_path": "/tmp/repo",
        "default_branch": "main",
        "metadata_json": '{"team":"platform"}',
        "created_at": created_at,
        "updated_at": updated_at,
    }

    connection = FakeConnection(FakeCursor(fetchone_result=row, fetchall_result=[row]))
    repo = PostgresWorkspaceRepository(connection)

    workspace = repo.get_by_id(workspace_id)
    assert workspace is not None
    assert workspace.workspace_id == workspace_id
    assert workspace.metadata == {"team": "platform"}

    workspace = repo.get_by_canonical_path("/tmp/repo")
    assert workspace is not None
    assert workspace.canonical_path == "/tmp/repo"

    workspaces = repo.get_by_repo_url("https://example.com/repo.git")
    assert len(workspaces) == 1
    assert workspaces[0].repo_url == "https://example.com/repo.git"

    inserted = repo.create(workspaces[0])
    assert inserted.workspace_id == workspace_id

    updated = repo.update(workspaces[0])
    assert updated.updated_at == updated_at

    assert len(connection._cursor._executed) == 5


def test_postgres_workspace_repository_create_and_update_raise_when_no_row_returned() -> None:
    connection = FakeConnection(FakeCursor(fetchone_result=None))
    repo = PostgresWorkspaceRepository(connection)
    now = datetime(2024, 1, 1, tzinfo=UTC)
    workspace = SimpleNamespace(
        workspace_id=uuid4(),
        repo_url="https://example.com/repo.git",
        canonical_path="/tmp/repo",
        default_branch="main",
        metadata={},
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(PersistenceError, match="Failed to insert workspace"):
        repo.create(workspace)

    with pytest.raises(PersistenceError, match="Failed to update workspace"):
        repo.update(workspace)


def test_postgres_workflow_instance_repository_covers_crud_and_row_mapping() -> None:
    workflow_instance_id = uuid4()
    workspace_id = uuid4()
    created_at = datetime(2024, 1, 3, tzinfo=UTC)
    updated_at = datetime(2024, 1, 4, tzinfo=UTC)
    row = {
        "workflow_instance_id": str(workflow_instance_id),
        "workspace_id": str(workspace_id),
        "ticket_id": "T-1",
        "status": "running",
        "metadata_json": {"priority": "high"},
        "created_at": created_at,
        "updated_at": updated_at,
    }

    connection = FakeConnection(FakeCursor(fetchone_result=row))
    repo = PostgresWorkflowInstanceRepository(connection)

    workflow = repo.get_by_id(workflow_instance_id)
    assert workflow is not None
    assert workflow.status is WorkflowInstanceStatus.RUNNING

    workflow = repo.get_running_by_workspace_id(workspace_id)
    assert workflow is not None
    assert workflow.workspace_id == workspace_id

    workflow = repo.get_latest_by_workspace_id(workspace_id)
    assert workflow is not None
    assert workflow.ticket_id == "T-1"

    created = repo.create(workflow)
    assert created.workflow_instance_id == workflow_instance_id

    updated = repo.update(workflow)
    assert updated.updated_at == updated_at


def test_postgres_workflow_instance_repository_create_and_update_raise_when_missing_row() -> None:
    connection = FakeConnection(FakeCursor(fetchone_result=None))
    repo = PostgresWorkflowInstanceRepository(connection)
    now = datetime(2024, 1, 1, tzinfo=UTC)
    workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        workspace_id=uuid4(),
        ticket_id="T-1",
        status=WorkflowInstanceStatus.RUNNING,
        metadata={},
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(PersistenceError, match="Failed to insert workflow instance"):
        repo.create(workflow)

    with pytest.raises(PersistenceError, match="Failed to update workflow instance"):
        repo.update(workflow)


def test_postgres_workflow_attempt_repository_covers_crud_queries_and_row_mapping() -> None:
    attempt_id = uuid4()
    workflow_instance_id = uuid4()
    started_at = datetime(2024, 1, 5, tzinfo=UTC)
    created_at = datetime(2024, 1, 5, tzinfo=UTC)
    updated_at = datetime(2024, 1, 6, tzinfo=UTC)
    row = {
        "attempt_id": str(attempt_id),
        "workflow_instance_id": str(workflow_instance_id),
        "attempt_number": 2,
        "status": "running",
        "failure_reason": None,
        "verify_status": "passed",
        "started_at": started_at,
        "finished_at": None,
        "created_at": created_at,
        "updated_at": updated_at,
    }

    connection = FakeConnection(FakeCursor(fetchone_result=row))
    repo = PostgresWorkflowAttemptRepository(connection)

    attempt = repo.get_by_id(attempt_id)
    assert attempt is not None
    assert attempt.verify_status is VerifyStatus.PASSED

    attempt = repo.get_running_by_workflow_id(workflow_instance_id)
    assert attempt is not None
    assert attempt.status is WorkflowAttemptStatus.RUNNING

    attempt = repo.get_latest_by_workflow_id(workflow_instance_id)
    assert attempt is not None
    assert attempt.attempt_number == 2

    next_number_cursor = FakeCursor(fetchone_result={"max_attempt_number": 4})
    next_number_repo = PostgresWorkflowAttemptRepository(FakeConnection(next_number_cursor))
    assert next_number_repo.get_next_attempt_number(workflow_instance_id) == 5

    empty_next_number_cursor = FakeCursor(fetchone_result=None)
    empty_next_number_repo = PostgresWorkflowAttemptRepository(
        FakeConnection(empty_next_number_cursor)
    )
    assert empty_next_number_repo.get_next_attempt_number(workflow_instance_id) == 1

    created = repo.create(attempt)
    assert created.attempt_id == attempt_id

    updated = repo.update(attempt)
    assert updated.updated_at == updated_at


def test_postgres_workflow_attempt_repository_create_and_update_raise_when_missing_row() -> None:
    connection = FakeConnection(FakeCursor(fetchone_result=None))
    repo = PostgresWorkflowAttemptRepository(connection)
    now = datetime(2024, 1, 1, tzinfo=UTC)
    attempt = SimpleNamespace(
        attempt_id=uuid4(),
        workflow_instance_id=uuid4(),
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        failure_reason=None,
        verify_status=None,
        started_at=now,
        finished_at=None,
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(PersistenceError, match="Failed to insert workflow attempt"):
        repo.create(attempt)

    with pytest.raises(PersistenceError, match="Failed to update workflow attempt"):
        repo.update(attempt)


def test_postgres_workflow_checkpoint_repository_covers_read_create_and_row_mapping() -> None:
    checkpoint_id = uuid4()
    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    created_at = datetime(2024, 1, 6, tzinfo=UTC)
    row = {
        "checkpoint_id": str(checkpoint_id),
        "workflow_instance_id": str(workflow_instance_id),
        "attempt_id": str(attempt_id),
        "step_name": "edit_files",
        "summary": "done",
        "checkpoint_json": '{"next":"test"}',
        "created_at": created_at,
    }

    connection = FakeConnection(FakeCursor(fetchone_result=row))
    repo = PostgresWorkflowCheckpointRepository(connection)

    checkpoint = repo.get_latest_by_workflow_id(workflow_instance_id)
    assert checkpoint is not None
    assert checkpoint.checkpoint_json == {"next": "test"}

    checkpoint = repo.get_latest_by_attempt_id(attempt_id)
    assert checkpoint is not None
    assert checkpoint.attempt_id == attempt_id

    created = repo.create(checkpoint)
    assert created.checkpoint_id == checkpoint_id


def test_postgres_workflow_checkpoint_repository_create_raises_when_missing_row() -> None:
    connection = FakeConnection(FakeCursor(fetchone_result=None))
    repo = PostgresWorkflowCheckpointRepository(connection)
    checkpoint = SimpleNamespace(
        checkpoint_id=uuid4(),
        workflow_instance_id=uuid4(),
        attempt_id=uuid4(),
        step_name="edit_files",
        summary="done",
        checkpoint_json={},
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    with pytest.raises(PersistenceError, match="Failed to insert workflow checkpoint"):
        repo.create(checkpoint)


def test_postgres_verify_report_repository_covers_read_create_and_row_mapping() -> None:
    verify_id = uuid4()
    attempt_id = uuid4()
    created_at = datetime(2024, 1, 7, tzinfo=UTC)
    row = {
        "verify_id": str(verify_id),
        "attempt_id": str(attempt_id),
        "status": "failed",
        "report_json": {"checks": ["pytest"]},
        "created_at": created_at,
    }

    connection = FakeConnection(FakeCursor(fetchone_result=row))
    repo = PostgresVerifyReportRepository(connection)

    report = repo.get_latest_by_attempt_id(attempt_id)
    assert report is not None
    assert report.status is VerifyStatus.FAILED

    created = repo.create(report)
    assert created.verify_id == verify_id


def test_postgres_verify_report_repository_create_raises_when_missing_row() -> None:
    connection = FakeConnection(FakeCursor(fetchone_result=None))
    repo = PostgresVerifyReportRepository(connection)
    report = SimpleNamespace(
        verify_id=uuid4(),
        attempt_id=uuid4(),
        status=VerifyStatus.PASSED,
        report_json={},
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    with pytest.raises(PersistenceError, match="Failed to insert verify report"):
        repo.create(report)


def test_postgres_unit_of_work_commit_rollback_and_context_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = FakeCursor(executed=[])
    connection = FakeConnection(cursor)

    monkeypatch.setattr(postgres_module, "_connect", lambda database_url: connection)

    config = PostgresConfig(
        database_url="postgresql://ctxledger/db",
        statement_timeout_ms=456,
    )
    pool = FakeConnectionPool(connection)
    uow = PostgresUnitOfWork(config, pool)

    with uow as active_uow:
        assert active_uow is uow
        assert isinstance(uow.workspaces, PostgresWorkspaceRepository)
        assert isinstance(uow.workflow_instances, PostgresWorkflowInstanceRepository)
        assert isinstance(uow.workflow_attempts, PostgresWorkflowAttemptRepository)
        assert isinstance(uow.workflow_checkpoints, PostgresWorkflowCheckpointRepository)
        assert isinstance(uow.verify_reports, PostgresVerifyReportRepository)
        uow.commit()

    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0
    assert connection.close_calls == 1
    assert cursor._executed[0] == ("SET statement_timeout = 456", None)

    inactive_uow = PostgresUnitOfWork(config, FakeConnectionPool(connection))
    with pytest.raises(PersistenceError, match="Unit of work is not active"):
        inactive_uow.commit()
    with pytest.raises(PersistenceError, match="Unit of work is not active"):
        inactive_uow.rollback()
    with pytest.raises(PersistenceError, match="Unit of work is not active"):
        inactive_uow._apply_session_settings()


def test_postgres_unit_of_work_rolls_back_on_explicit_rollback_and_exit() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    pool = FakeConnectionPool(connection)

    uow = PostgresUnitOfWork(
        PostgresConfig(
            database_url="postgresql://ctxledger/db",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
        ),
        pool,
    )

    with uow:
        uow.rollback()

    assert pool.connection_calls == 1
    assert len(pool.contexts) == 1
    assert pool.contexts[0].enter_calls == 1
    assert pool.contexts[0].exit_calls == 1
    assert connection.rollback_calls == 2
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


def test_postgres_unit_of_work_rolls_back_on_exception() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    pool = FakeConnectionPool(connection)

    uow = PostgresUnitOfWork(
        PostgresConfig(
            database_url="postgresql://ctxledger/db",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
        ),
        pool,
    )

    with pytest.raises(RuntimeError, match="boom"):
        with uow:
            raise RuntimeError("boom")

    assert pool.connection_calls == 1
    assert len(pool.contexts) == 1
    assert pool.contexts[0].enter_calls == 1
    assert pool.contexts[0].exit_calls == 1
    assert pool.contexts[0].exit_args[0][0] is RuntimeError
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


def test_build_postgres_uow_factory_requires_shared_pool() -> None:
    config = PostgresConfig(database_url="postgresql://ctxledger/db")

    with pytest.raises(
        ValueError,
        match="A shared PostgreSQL connection pool is required",
    ):
        build_postgres_uow_factory(config)


def test_load_postgres_schema_sql_returns_schema_contents() -> None:
    sql = load_postgres_schema_sql()

    assert isinstance(sql, str)
    assert "ctxledger PostgreSQL schema" in sql
    assert "CREATE TABLE IF NOT EXISTS workspaces" in sql

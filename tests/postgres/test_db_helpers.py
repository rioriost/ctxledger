from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.db import postgres_common as postgres_common_module
from ctxledger.db import postgres_uow as postgres_uow_module
from ctxledger.memory.types import MemoryRelationRecord
from ctxledger.workflow.service import PersistenceError, VerifyStatus
from tests.postgres.conftest import FakeConnection


def test_schema_file_exists() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "postgres.sql"

    assert schema_path.exists()
    assert (
        schema_path.read_text(encoding="utf-8").strip().startswith("-- ctxledger PostgreSQL schema")
    )


def test_schema_contains_core_workflow_tables() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "postgres.sql"
    schema = schema_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS workspaces" in schema
    assert "CREATE TABLE IF NOT EXISTS workflow_instances" in schema
    assert "CREATE TABLE IF NOT EXISTS workflow_attempts" in schema
    assert "CREATE TABLE IF NOT EXISTS workflow_checkpoints" in schema
    assert "CREATE TABLE IF NOT EXISTS verify_reports" in schema


def test_postgres_low_level_helpers_and_pool_builder() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")

    assert postgres._json_dumps({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert postgres._json_loads(None) == {}
    assert postgres._json_loads('{"a": 1}') == {"a": 1}
    assert postgres._json_object_or_none(None) is None
    assert postgres._json_object_or_none({"a": 1}) == {"a": 1}
    assert postgres._json_object_or_none('{"a": 1}') == {"a": 1}
    assert postgres._json_object_or_none("[1,2]") is None
    assert postgres._json_object_or_none([("a", 1)]) == {"a": 1}

    from datetime import UTC, datetime

    aware = datetime(2024, 1, 1, tzinfo=UTC)
    naive = datetime(2024, 1, 1)
    assert postgres._to_datetime(aware) == aware
    assert postgres._to_datetime(naive).tzinfo == UTC
    with pytest.raises(PersistenceError, match="Expected datetime, got str"):
        postgres._to_datetime("bad")

    value_uuid = uuid4()
    assert postgres._to_uuid(value_uuid) == value_uuid
    assert postgres._to_uuid(str(value_uuid)) == value_uuid
    assert postgres._optional_datetime(None) is None
    assert postgres._optional_datetime(aware) == aware
    assert postgres._optional_str_enum(VerifyStatus, None) is None
    assert postgres._optional_str_enum(VerifyStatus, "passed") == VerifyStatus.PASSED
    assert postgres._normalized_schema_name(None) == "public"
    assert postgres._normalized_schema_name("  ") == "public"
    assert postgres._normalized_schema_name(" custom ") == "custom"
    assert postgres._parse_embedding_values(None) == ()
    assert postgres._parse_embedding_values("") == ()
    assert postgres._parse_embedding_values("[1, 2.5]") == (1.0, 2.5)
    assert postgres._parse_embedding_values((1, "2.5")) == (1.0, 2.5)
    assert postgres._quote_ident('a"b') == '"a""b"'
    assert postgres._episode_status(None) == "recorded"
    assert postgres._episode_status("ignored") == "ignored"
    assert postgres._pgvector_literal((1.0, 2.5)) == "[1,2.5]"

    class FakePool:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    original_pool = postgres_common_module.ConnectionPool
    try:
        postgres_common_module.ConnectionPool = FakePool
        config = postgres.PostgresConfig(
            database_url="postgresql://example/db",
            pool_min_size=2,
            pool_max_size=7,
            pool_timeout_seconds=9,
        )
        pool = postgres.build_connection_pool(config)
    finally:
        postgres_common_module.ConnectionPool = original_pool

    assert isinstance(pool, FakePool)
    assert pool.kwargs["conninfo"] == "postgresql://example/db"
    assert pool.kwargs["min_size"] == 2
    assert pool.kwargs["max_size"] == 7
    assert pool.kwargs["timeout"] == 9
    assert pool.kwargs["open"] is True


def test_postgres_config_from_settings_and_schema_loader() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")

    settings = SimpleNamespace(
        database=SimpleNamespace(
            url="postgresql://example/db",
            connect_timeout_seconds=11,
            statement_timeout_ms=222,
            schema_name="  custom  ",
            pool_min_size=3,
            pool_max_size=6,
            pool_timeout_seconds=12,
        )
    )

    config = postgres.PostgresConfig.from_settings(settings)

    assert config.database_url == "postgresql://example/db"
    assert config.connect_timeout_seconds == 11
    assert config.statement_timeout_ms == 222
    assert config.schema_name == "custom"
    assert config.pool_min_size == 3
    assert config.pool_max_size == 6
    assert config.pool_timeout_seconds == 12

    schema_sql = postgres.load_postgres_schema_sql()
    assert "-- ctxledger PostgreSQL schema" in schema_sql


def test_database_health_checker_covers_schema_ready_and_session_settings() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")

    class FakeCursor:
        def __init__(self, rows: list[object] | None = None) -> None:
            self.rows = rows or []
            self.executed: list[tuple[str, object]] = []

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            self.executed.append((query, params))

        def fetchone(self) -> dict[str, int]:
            return {"ok": 1}

        def fetchall(self) -> list[object]:
            return self.rows

    class FakeConnection:
        def __init__(self, rows: list[object] | None = None) -> None:
            self._rows = rows or []
            self.cursors: list[FakeCursor] = []

        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> FakeCursor:
            cursor = FakeCursor(self._rows)
            self.cursors.append(cursor)
            return cursor

    class FakeConnector:
        def __init__(self, rows: list[object] | None = None) -> None:
            self.rows = rows or []
            self.calls: list[str] = []
            self.connections: list[FakeConnection] = []

        def __call__(self, database_url: str) -> FakeConnection:
            self.calls.append(database_url)
            connection = FakeConnection(self.rows)
            self.connections.append(connection)
            return connection

    config = postgres.PostgresConfig(
        database_url="postgresql://example/db",
        statement_timeout_ms=None,
        schema_name="ctxledger",
        age_enabled=False,
        age_graph_name="ctxledger_memory",
    )

    ping_connector = FakeConnector()
    original_connect = postgres_common_module._connect
    postgres_common_module._connect = ping_connector
    try:
        checker = postgres.PostgresDatabaseHealthChecker(config)
        checker.ping()
    finally:
        postgres_common_module._connect = original_connect

    assert ping_connector.calls == ["postgresql://example/db"]
    ping_queries = [
        query
        for cursor in ping_connector.connections[0].cursors
        for query, _params in cursor.executed
    ]
    assert "SET statement_timeout = 0" in ping_queries
    assert 'SET search_path TO "ctxledger", public' in ping_queries
    assert "SELECT 1" in ping_queries

    ready_connector = FakeConnector(
        rows=[
            {"table_name": "workspaces"},
            {"table_name": "workflow_instances"},
            {"table_name": "workflow_attempts"},
            {"table_name": "workflow_checkpoints"},
            {"table_name": "verify_reports"},
        ]
    )
    postgres_common_module._connect = ready_connector
    try:
        checker = postgres.PostgresDatabaseHealthChecker(config)
        assert checker.schema_ready() is True
    finally:
        postgres_common_module._connect = original_connect

    not_ready_connector = FakeConnector(
        rows=[
            {"table_name": "workspaces"},
            {"table_name": "workflow_instances"},
        ]
    )
    postgres_common_module._connect = not_ready_connector
    try:
        checker = postgres.PostgresDatabaseHealthChecker(config)
        assert checker.schema_ready() is False
    finally:
        postgres_common_module._connect = original_connect

    age_ready_connector = FakeConnector()
    postgres_common_module._connect = age_ready_connector
    try:
        checker = postgres.PostgresDatabaseHealthChecker(config)
        assert checker.age_available() is True
    finally:
        postgres_common_module._connect = original_connect

    class EmptyFetchoneCursor(FakeCursor):
        def fetchone(self) -> dict[str, int] | None:
            return None

    class EmptyFetchoneConnection(FakeConnection):
        def cursor(self) -> EmptyFetchoneCursor:
            cursor = EmptyFetchoneCursor(self._rows)
            self.cursors.append(cursor)
            return cursor

    class EmptyFetchoneConnector(FakeConnector):
        def __call__(self, database_url: str) -> EmptyFetchoneConnection:
            self.calls.append(database_url)
            connection = EmptyFetchoneConnection(self.rows)
            self.connections.append(connection)
            return connection

    age_not_ready_connector = EmptyFetchoneConnector()
    postgres_common_module._connect = age_not_ready_connector
    try:
        checker = postgres.PostgresDatabaseHealthChecker(config)
        assert checker.age_available() is False
        assert checker.age_graph_available("ctxledger_memory") is False
        assert checker.age_graph_status("ctxledger_memory").value == "age_unavailable"
    finally:
        postgres_common_module._connect = original_connect

    graph_ready_connector = FakeConnector()
    postgres_common_module._connect = graph_ready_connector
    try:
        checker = postgres.PostgresDatabaseHealthChecker(config)
        assert checker.age_graph_available("ctxledger_memory") is True
        assert checker.age_graph_status("ctxledger_memory").value == "graph_ready"
    finally:
        postgres_common_module._connect = original_connect

    class GraphMissingCursor(FakeCursor):
        def __init__(self, rows: list[object] | None = None) -> None:
            super().__init__(rows)

        def fetchone(self) -> dict[str, int] | None:
            if any("FROM pg_extension" in query for query, _params in self.executed):
                return {"ok": 1}
            return None

    class GraphMissingConnection(FakeConnection):
        def cursor(self) -> GraphMissingCursor:
            cursor = GraphMissingCursor(self._rows)
            self.cursors.append(cursor)
            return cursor

    class GraphMissingConnector(FakeConnector):
        def __call__(self, database_url: str) -> GraphMissingConnection:
            self.calls.append(database_url)
            connection = GraphMissingConnection(self.rows)
            self.connections.append(connection)
            return connection

    graph_not_ready_connector = GraphMissingConnector()
    postgres_common_module._connect = graph_not_ready_connector
    try:
        checker = postgres.PostgresDatabaseHealthChecker(config)
        assert checker.age_graph_available("ctxledger_memory") is False
        assert checker.age_graph_status("ctxledger_memory").value == "graph_unavailable"
    finally:
        postgres_common_module._connect = original_connect


def test_postgres_repository_edge_cases_cover_relation_listing_and_datetime_guards() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")
    connection = FakeConnection()

    workflow_repo = postgres.PostgresWorkflowInstanceRepository(connection)
    relation_repo = postgres.PostgresMemoryRelationRepository(connection)
    memory_item_repo = postgres.PostgresMemoryItemRepository(connection)

    workspace_id = uuid4()
    workflow_a = {
        "workflow_instance_id": uuid4(),
        "workspace_id": workspace_id,
        "ticket_id": "TICKET-A",
        "status": "running",
        "metadata_json": {"kind": "recent"},
        "created_at": datetime(2024, 1, 10, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 11, tzinfo=UTC),
    }
    workflow_b = {
        "workflow_instance_id": uuid4(),
        "workspace_id": workspace_id,
        "ticket_id": "TICKET-B",
        "status": "completed",
        "metadata_json": {},
        "created_at": datetime(2024, 1, 8, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 9, tzinfo=UTC),
    }

    connection.fetchall_results.append([workflow_a, workflow_b])
    by_workspace = workflow_repo.list_by_workspace_id(workspace_id, limit=2)
    assert tuple(item.ticket_id for item in by_workspace) == ("TICKET-A", "TICKET-B")

    connection.fetchall_results.append([workflow_b, workflow_a])
    by_ticket = workflow_repo.list_by_ticket_id("TICKET", limit=2)
    assert tuple(item.ticket_id for item in by_ticket) == ("TICKET-B", "TICKET-A")

    source_memory_id = uuid4()
    target_memory_id = uuid4()
    relation_row = {
        "memory_relation_id": uuid4(),
        "source_memory_id": source_memory_id,
        "target_memory_id": target_memory_id,
        "relation_type": "related_to",
        "metadata_json": {"score": 0.8},
        "created_at": datetime(2024, 1, 12, tzinfo=UTC),
    }

    connection.fetchall_results.append([relation_row])
    by_source = relation_repo.list_by_source_memory_id(source_memory_id, limit=5)
    assert by_source == (
        MemoryRelationRecord(
            memory_relation_id=relation_row["memory_relation_id"],
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relation_type="related_to",
            metadata={"score": 0.8},
            created_at=relation_row["created_at"],
        ),
    )

    other_source_memory_id = uuid4()
    newer_relation_row = {
        "memory_relation_id": uuid4(),
        "source_memory_id": source_memory_id,
        "target_memory_id": uuid4(),
        "relation_type": "supports",
        "metadata_json": {"kind": "newer"},
        "created_at": datetime(2024, 1, 13, tzinfo=UTC),
    }
    older_other_source_relation_row = {
        "memory_relation_id": uuid4(),
        "source_memory_id": other_source_memory_id,
        "target_memory_id": uuid4(),
        "relation_type": "references",
        "metadata_json": {"kind": "older-other-source"},
        "created_at": datetime(2024, 1, 11, tzinfo=UTC),
    }

    connection.fetchall_results.append(
        [
            newer_relation_row,
            relation_row,
            older_other_source_relation_row,
        ]
    )
    by_sources = relation_repo.list_by_source_memory_ids((source_memory_id, other_source_memory_id))
    assert by_sources == (
        MemoryRelationRecord(
            memory_relation_id=newer_relation_row["memory_relation_id"],
            source_memory_id=source_memory_id,
            target_memory_id=newer_relation_row["target_memory_id"],
            relation_type="supports",
            metadata={"kind": "newer"},
            created_at=newer_relation_row["created_at"],
        ),
        MemoryRelationRecord(
            memory_relation_id=relation_row["memory_relation_id"],
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relation_type="related_to",
            metadata={"score": 0.8},
            created_at=relation_row["created_at"],
        ),
        MemoryRelationRecord(
            memory_relation_id=older_other_source_relation_row["memory_relation_id"],
            source_memory_id=other_source_memory_id,
            target_memory_id=older_other_source_relation_row["target_memory_id"],
            relation_type="references",
            metadata={"kind": "older-other-source"},
            created_at=older_other_source_relation_row["created_at"],
        ),
    )
    assert relation_repo.list_by_source_memory_ids(()) == ()

    support_target_a = uuid4()
    support_target_b = uuid4()
    duplicate_support_target_row = {
        "target_memory_id": support_target_a,
    }
    newer_support_target_row = {
        "target_memory_id": support_target_b,
    }

    connection.fetchall_results.append(
        [
            duplicate_support_target_row,
            newer_support_target_row,
        ]
    )
    assert relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids(
        (source_memory_id, other_source_memory_id)
    ) == (
        support_target_a,
        support_target_b,
    )
    assert relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids(()) == ()

    graph_relation_row = {
        "target_memory_id": f'"{support_target_a}"',
    }
    connection.fetchall_results.append([graph_relation_row])
    assert relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids_via_age(
        (source_memory_id,),
        graph_name="ctxledger_memory",
    ) == (support_target_a,)

    fallback_relation_row = {
        "target_memory_id": support_target_b,
    }
    connection.fetchall_results.append([fallback_relation_row])
    assert relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids_with_fallback(
        (source_memory_id,),
        graph_name="ctxledger_memory",
        graph_status=postgres.AgeGraphStatus.GRAPH_READY,
    ) == (support_target_b,)

    original_via_age = (
        relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids_via_age
    )
    relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids_via_age = (  # type: ignore[method-assign]
        lambda source_memory_ids, *, graph_name: (_ for _ in ()).throw(RuntimeError("age failed"))
    )
    try:
        connection.fetchall_results.append([fallback_relation_row])
        assert (
            relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids_with_fallback(
                (source_memory_id,),
                graph_name="ctxledger_memory",
                graph_status=postgres.AgeGraphStatus.GRAPH_READY,
            )
            == (support_target_b,)
        )
    finally:
        relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids_via_age = (  # type: ignore[method-assign]
            original_via_age
        )

    assert (
        relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids_with_fallback(
            (source_memory_id,),
            graph_name="ctxledger_memory",
            graph_status=postgres.AgeGraphStatus.AGE_UNAVAILABLE,
        )
        == ()
    )

    disabled_age_config = postgres.PostgresConfig(
        database_url="postgresql://example/db",
        statement_timeout_ms=None,
        schema_name="ctxledger",
        age_enabled=False,
        age_graph_name="ctxledger_memory",
    )
    connection.fetchall_results.append([fallback_relation_row])
    assert relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids_for_config(
        (source_memory_id,),
        config=disabled_age_config,
    ) == (support_target_b,)

    class StubHealthChecker:
        def __init__(self, graph_status: object) -> None:
            self.graph_status = graph_status
            self.requested_graph_names: list[str] = []

        def age_graph_status(self, graph_name: str) -> object:
            self.requested_graph_names.append(graph_name)
            return self.graph_status

    enabled_age_config = postgres.PostgresConfig(
        database_url="postgresql://example/db",
        statement_timeout_ms=None,
        schema_name="ctxledger",
        age_enabled=True,
        age_graph_name="ctxledger_memory",
    )
    graph_ready_checker = StubHealthChecker(postgres.AgeGraphStatus.GRAPH_READY)
    connection.fetchall_results.append([graph_relation_row])
    assert relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids_for_config(
        (source_memory_id,),
        config=enabled_age_config,
        health_checker=graph_ready_checker,
    ) == (support_target_a,)
    assert graph_ready_checker.requested_graph_names == ["ctxledger_memory"]

    graph_unavailable_checker = StubHealthChecker(postgres.AgeGraphStatus.GRAPH_UNAVAILABLE)
    connection.fetchall_results.append([fallback_relation_row])
    assert relation_repo.list_distinct_support_target_memory_ids_by_source_memory_ids_for_config(
        (source_memory_id,),
        config=enabled_age_config,
        health_checker=graph_unavailable_checker,
    ) == (support_target_b,)
    assert graph_unavailable_checker.requested_graph_names == ["ctxledger_memory"]

    connection.fetchall_results.append([relation_row])
    by_target = relation_repo.list_by_target_memory_id(target_memory_id, limit=5)
    assert by_target == (
        MemoryRelationRecord(
            memory_relation_id=relation_row["memory_relation_id"],
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relation_type="related_to",
            metadata={"score": 0.8},
            created_at=relation_row["created_at"],
        ),
    )

    other_source_memory_id = uuid4()
    newer_relation_row = {
        "memory_relation_id": uuid4(),
        "source_memory_id": source_memory_id,
        "target_memory_id": uuid4(),
        "relation_type": "supports",
        "metadata_json": {"kind": "newer"},
        "created_at": datetime(2024, 1, 13, tzinfo=UTC),
    }
    older_other_source_relation_row = {
        "memory_relation_id": uuid4(),
        "source_memory_id": other_source_memory_id,
        "target_memory_id": uuid4(),
        "relation_type": "references",
        "metadata_json": {"kind": "older-other-source"},
        "created_at": datetime(2024, 1, 11, tzinfo=UTC),
    }

    connection.fetchall_results.append(
        [
            newer_relation_row,
            relation_row,
            older_other_source_relation_row,
        ]
    )
    by_sources = relation_repo.list_by_source_memory_ids((source_memory_id, other_source_memory_id))
    assert by_sources == (
        MemoryRelationRecord(
            memory_relation_id=newer_relation_row["memory_relation_id"],
            source_memory_id=source_memory_id,
            target_memory_id=newer_relation_row["target_memory_id"],
            relation_type="supports",
            metadata={"kind": "newer"},
            created_at=newer_relation_row["created_at"],
        ),
        MemoryRelationRecord(
            memory_relation_id=relation_row["memory_relation_id"],
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relation_type="related_to",
            metadata={"score": 0.8},
            created_at=relation_row["created_at"],
        ),
        MemoryRelationRecord(
            memory_relation_id=older_other_source_relation_row["memory_relation_id"],
            source_memory_id=other_source_memory_id,
            target_memory_id=older_other_source_relation_row["target_memory_id"],
            relation_type="references",
            metadata={"kind": "older-other-source"},
            created_at=older_other_source_relation_row["created_at"],
        ),
    )
    assert relation_repo.list_by_source_memory_ids(()) == ()

    with pytest.raises(
        PersistenceError,
        match="Unsupported datetime field 'bad_field' for workflow_instances",
    ):
        workflow_repo.max_datetime("bad_field")

    with pytest.raises(
        PersistenceError,
        match="Unsupported datetime field 'bad_field' for memory_items",
    ):
        memory_item_repo.max_datetime("bad_field")


def test_postgres_row_mapping_helpers_cover_memory_records() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")

    from datetime import UTC, datetime

    memory_id = uuid4()
    workspace_id = uuid4()
    episode_id = uuid4()
    embedding_id = uuid4()

    item_record = postgres._memory_item_row_to_record(
        {
            "memory_id": memory_id,
            "workspace_id": workspace_id,
            "episode_id": episode_id,
            "type": "episode_note",
            "provenance": "episode",
            "content": "Memory item content",
            "metadata_json": {"kind": "note"},
            "created_at": datetime(2024, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2024, 1, 2, tzinfo=UTC),
        }
    )
    assert item_record.memory_id == memory_id
    assert item_record.workspace_id == workspace_id
    assert item_record.episode_id == episode_id

    item_without_optional_ids = postgres._memory_item_row_to_record(
        {
            "memory_id": memory_id,
            "workspace_id": None,
            "episode_id": None,
            "type": "episode_note",
            "provenance": "episode",
            "content": "Memory item content",
            "metadata_json": None,
            "created_at": datetime(2024, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2024, 1, 2, tzinfo=UTC),
        }
    )
    assert item_without_optional_ids.workspace_id is None
    assert item_without_optional_ids.episode_id is None
    assert item_without_optional_ids.metadata == {}

    embedding_record = postgres._memory_embedding_row_to_record(
        {
            "memory_embedding_id": embedding_id,
            "memory_id": memory_id,
            "embedding_model": "test-model",
            "embedding": "[1,2.5]",
            "content_hash": "hash-123",
            "created_at": datetime(2024, 1, 3, tzinfo=UTC),
        }
    )
    assert embedding_record.memory_embedding_id == embedding_id
    assert embedding_record.embedding == (1.0, 2.5)
    assert embedding_record.content_hash == "hash-123"

    embedding_without_hash = postgres._memory_embedding_row_to_record(
        {
            "memory_embedding_id": embedding_id,
            "memory_id": memory_id,
            "embedding_model": "test-model",
            "embedding": None,
            "content_hash": None,
            "created_at": datetime(2024, 1, 3, tzinfo=UTC),
        }
    )
    assert embedding_without_hash.embedding == ()
    assert embedding_without_hash.content_hash is None


def test_postgres_connect_requires_driver_and_passes_row_factory() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")
    original_psycopg = postgres_common_module.psycopg
    original_dict_row = postgres_common_module.dict_row

    try:
        postgres_common_module.psycopg = None
        postgres_common_module.dict_row = None
        with pytest.raises(RuntimeError, match="psycopg is required"):
            postgres._require_psycopg()

        class FakePsycopg:
            def __init__(self) -> None:
                self.calls: list[tuple[str, object]] = []

            def connect(self, database_url: str, row_factory: object = None) -> str:
                self.calls.append((database_url, row_factory))
                return "CONNECTION"

        fake_psycopg = FakePsycopg()
        postgres_common_module.psycopg = fake_psycopg
        postgres_common_module.dict_row = "DICT_ROW"
        connection = postgres._connect("postgresql://example/db")
    finally:
        postgres_common_module.psycopg = original_psycopg
        postgres_common_module.dict_row = original_dict_row

    assert connection == "CONNECTION"
    assert fake_psycopg.calls == [("postgresql://example/db", "DICT_ROW")]

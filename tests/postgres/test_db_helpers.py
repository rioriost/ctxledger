from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.workflow.service import PersistenceError


def test_schema_file_exists() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "postgres.sql"

    assert schema_path.exists()
    assert (
        schema_path.read_text(encoding="utf-8")
        .strip()
        .startswith("-- ctxledger PostgreSQL schema")
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
    assert postgres._optional_str_enum(postgres.VerifyStatus, None) is None
    assert (
        postgres._optional_str_enum(postgres.VerifyStatus, "passed")
        == postgres.VerifyStatus.PASSED
    )
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

    original_pool = postgres.ConnectionPool
    try:
        postgres.ConnectionPool = FakePool
        config = postgres.PostgresConfig(
            database_url="postgresql://example/db",
            pool_min_size=2,
            pool_max_size=7,
            pool_timeout_seconds=9,
        )
        pool = postgres.build_connection_pool(config)
    finally:
        postgres.ConnectionPool = original_pool

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
    original_psycopg = postgres.psycopg
    original_dict_row = postgres.dict_row

    try:
        postgres.psycopg = None
        postgres.dict_row = None
        with pytest.raises(RuntimeError, match="psycopg is required"):
            postgres._require_psycopg()

        class FakePsycopg:
            def __init__(self) -> None:
                self.calls: list[tuple[str, object]] = []

            def connect(self, database_url: str, row_factory: object = None) -> str:
                self.calls.append((database_url, row_factory))
                return "CONNECTION"

        fake_psycopg = FakePsycopg()
        postgres.psycopg = fake_psycopg
        postgres.dict_row = "DICT_ROW"
        connection = postgres._connect("postgresql://example/db")
    finally:
        postgres.psycopg = original_psycopg
        postgres.dict_row = original_dict_row

    assert connection == "CONNECTION"
    assert fake_psycopg.calls == [("postgresql://example/db", "DICT_ROW")]

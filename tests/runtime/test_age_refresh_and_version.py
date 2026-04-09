from __future__ import annotations

from importlib import metadata
from types import SimpleNamespace

import pytest

from ctxledger.runtime.age_refresh import refresh_age_summary_graph
from ctxledger.version import (
    _get_installed_package_metadata_value,
    _get_pyproject_metadata_value,
    get_app_name,
    get_app_version,
)


class _FakeCursor:
    def __init__(
        self,
        *,
        fetchone_results: list[object | None] | None = None,
        fetchall_results: list[list[object]] | None = None,
    ) -> None:
        self.executed: list[tuple[str, object | None]] = []
        self._fetchone_results = list(fetchone_results or [])
        self._fetchall_results = list(fetchall_results or [])

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query: str, params: object = None) -> None:
        self.executed.append((query, params))

    def fetchone(self) -> object | None:
        if self._fetchone_results:
            return self._fetchone_results.pop(0)
        return None

    def fetchall(self) -> list[object]:
        if self._fetchall_results:
            return self._fetchall_results.pop(0)
        return []


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.commit_calls = 0

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.commit_calls += 1


def test_refresh_age_summary_graph_validates_required_inputs() -> None:
    fake_psycopg = SimpleNamespace(connect=lambda *_args, **_kwargs: None)

    with pytest.raises(ValueError, match="database_url must be a non-empty string"):
        refresh_age_summary_graph(
            database_url="  ",
            graph_name="ctxledger_graph",
            psycopg_module=fake_psycopg,
        )

    with pytest.raises(ValueError, match="graph_name must be a non-empty string"):
        refresh_age_summary_graph(
            database_url="postgresql://example/db",
            graph_name=" ",
            psycopg_module=fake_psycopg,
        )

    with pytest.raises(ValueError, match="psycopg_module is required"):
        refresh_age_summary_graph(
            database_url="postgresql://example/db",
            graph_name="ctxledger_graph",
            psycopg_module=None,
        )


def test_refresh_age_summary_graph_creates_graph_and_handles_tuple_rows() -> None:
    cursor = _FakeCursor(
        fetchone_results=[
            None,
            ('"2"',),
            ('"3"',),
        ],
        fetchall_results=[
            [
                (
                    "summary-1",
                    "workspace-1",
                    None,
                    "episode_summary",
                ),
                (
                    "summary-2",
                    "workspace-2",
                    "episode-2",
                    "workflow_summary",
                ),
            ],
            [
                (
                    "membership-1",
                    "summary-1",
                    "memory-1",
                    1,
                ),
                (
                    "membership-2",
                    "summary-2",
                    "memory-2",
                    None,
                ),
            ],
        ],
    )
    connection = _FakeConnection(cursor)
    fake_psycopg = SimpleNamespace(connect=lambda *_args, **_kwargs: connection)

    payload = refresh_age_summary_graph(
        database_url="  postgresql://example/db  ",
        graph_name="  ctxledger_graph  ",
        psycopg_module=fake_psycopg,
    )

    assert payload == {
        "graph_name": "ctxledger_graph",
        "memory_summary_node_count": 2,
        "summarizes_edge_count": 3,
    }
    assert connection.commit_calls == 1

    executed_queries = [query for query, _params in cursor.executed]
    executed_params = [params for _query, params in cursor.executed]

    assert executed_queries[0] == "LOAD 'age'"
    assert executed_queries[1] == 'SET search_path = ag_catalog, "$user", public'
    assert "FROM ag_catalog.ag_graph" in executed_queries[2]
    assert executed_params[2] == ("ctxledger_graph",)
    assert "create_graph" in executed_queries[3]
    assert "MATCH (n:memory_summary)-[r:summarizes]->()" in executed_queries[4]
    assert "MATCH (n:memory_summary)" in executed_queries[5]
    assert "FROM public.memory_summaries" in executed_queries[6]
    assert "CREATE (n:memory_summary" in executed_queries[7]
    assert "CREATE (n:memory_summary" in executed_queries[8]
    assert "FROM public.memory_summary_memberships" in executed_queries[9]
    assert "CREATE (summary)-[r:summarizes" in executed_queries[10]
    assert "CREATE (summary)-[r:summarizes" in executed_queries[11]
    assert "MATCH (n:memory_summary)" in executed_queries[12]
    assert (
        "MATCH (:memory_summary)-[r:summarizes]->(:memory_item)" in executed_queries[13]
    )


def test_refresh_age_summary_graph_uses_dict_rows_and_count_fallback_keys() -> None:
    cursor = _FakeCursor(
        fetchone_results=[
            {"ok": 1},
            {"count": '"4"'},
            {"count": '"5"'},
        ],
        fetchall_results=[
            [
                {
                    "memory_summary_id": "summary-1",
                    "workspace_id": "workspace-1",
                    "episode_id": "episode-1",
                    "summary_kind": "episode_summary",
                }
            ],
            [
                {
                    "memory_summary_membership_id": "membership-1",
                    "memory_summary_id": "summary-1",
                    "memory_id": "memory-1",
                    "membership_order": 7,
                }
            ],
        ],
    )
    connection = _FakeConnection(cursor)
    fake_psycopg = SimpleNamespace(connect=lambda *_args, **_kwargs: connection)

    payload = refresh_age_summary_graph(
        database_url="postgresql://example/db",
        graph_name="ctxledger_graph",
        psycopg_module=fake_psycopg,
    )

    assert payload == {
        "graph_name": "ctxledger_graph",
        "memory_summary_node_count": 4,
        "summarizes_edge_count": 5,
    }
    assert connection.commit_calls == 1

    create_graph_queries = [
        query for query, _params in cursor.executed if "create_graph" in query
    ]
    assert create_graph_queries == []


def test_refresh_age_summary_graph_leaves_counts_at_zero_when_final_queries_return_none() -> (
    None
):
    cursor = _FakeCursor(
        fetchone_results=[
            {"ok": 1},
            None,
            None,
        ],
        fetchall_results=[
            [],
            [],
        ],
    )
    connection = _FakeConnection(cursor)
    fake_psycopg = SimpleNamespace(connect=lambda *_args, **_kwargs: connection)

    payload = refresh_age_summary_graph(
        database_url="postgresql://example/db",
        graph_name="ctxledger_graph",
        psycopg_module=fake_psycopg,
    )

    assert payload == {
        "graph_name": "ctxledger_graph",
        "memory_summary_node_count": 0,
        "summarizes_edge_count": 0,
    }
    assert connection.commit_calls == 1


def test_get_installed_package_metadata_value_covers_name_version_unknown_and_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ctxledger.version.metadata.metadata",
        lambda package_name: {"Name": f"{package_name}-name"},
    )
    monkeypatch.setattr(
        "ctxledger.version.metadata.version",
        lambda package_name: f"{package_name}-version",
    )

    assert _get_installed_package_metadata_value("name") == "ctxledger-name"
    assert _get_installed_package_metadata_value("version") == "ctxledger-version"
    assert _get_installed_package_metadata_value("unknown") is None

    def raise_package_not_found(_package_name: str) -> str:
        raise metadata.PackageNotFoundError

    monkeypatch.setattr("ctxledger.version.metadata.version", raise_package_not_found)
    assert _get_installed_package_metadata_value("version") is None


def test_get_pyproject_metadata_value_falls_back_to_installed_metadata_when_missing_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePath:
        def resolve(self) -> "FakePath":
            return self

        @property
        def parents(self) -> list["FakePath"]:
            return [self, self, self]

        def __truediv__(self, _other: object) -> "FakePath":
            return self

        def exists(self) -> bool:
            return False

    monkeypatch.setattr("ctxledger.version.Path", lambda *_args, **_kwargs: FakePath())
    monkeypatch.setattr(
        "ctxledger.version._get_installed_package_metadata_value",
        lambda key: f"fallback-{key}",
    )

    assert _get_pyproject_metadata_value("name") == "fallback-name"
    assert _get_pyproject_metadata_value("version") == "fallback-version"


def test_get_pyproject_metadata_value_raises_when_file_and_metadata_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePath:
        def resolve(self) -> "FakePath":
            return self

        @property
        def parents(self) -> list["FakePath"]:
            return [self, self, self]

        def __truediv__(self, _other: object) -> "FakePath":
            return self

        def exists(self) -> bool:
            return False

    monkeypatch.setattr("ctxledger.version.Path", lambda *_args, **_kwargs: FakePath())
    monkeypatch.setattr(
        "ctxledger.version._get_installed_package_metadata_value",
        lambda _key: None,
    )

    with pytest.raises(
        RuntimeError,
        match="Could not determine ctxledger version from pyproject.toml or package metadata",
    ):
        _get_pyproject_metadata_value("version")


def test_get_app_name_and_version_read_project_section_from_pyproject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pyproject_text = """
[build-system]
requires = ["setuptools"]

[project]
name = "ctxledger-test"
version = "9.9.9"

[tool.pytest.ini_options]
addopts = "-q"
""".strip()

    class FakePath:
        def __init__(self, text: str) -> None:
            self._text = text

        def resolve(self) -> "FakePath":
            return self

        @property
        def parents(self) -> list["FakePath"]:
            return [self, self, self]

        def __truediv__(self, _other: object) -> "FakePath":
            return self

        def exists(self) -> bool:
            return True

        def read_text(self, encoding: str = "utf-8") -> str:
            assert encoding == "utf-8"
            return self._text

    monkeypatch.setattr(
        "ctxledger.version.Path",
        lambda *_args, **_kwargs: FakePath(pyproject_text),
    )

    assert get_app_name() == "ctxledger-test"
    assert get_app_version() == "9.9.9"

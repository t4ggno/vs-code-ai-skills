from __future__ import annotations

import argparse
import json
import runpy
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import load_module

MODULE = load_module("sql-query-runner/query.py", "sql_query_runner")
SCRIPT_PATH = Path(__file__).with_name("query.py")


def create_sqlite_db(tmp_path: Path) -> Path:
    database_path = tmp_path / "sample.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT)")
        connection.executemany(
            "INSERT INTO widgets (name) VALUES (?)",
            [("alpha",), ("beta",), ("gamma",)],
        )
        connection.commit()
    finally:
        connection.close()
    return database_path


def test_parse_json_argument_and_validate_query_reject_invalid_values() -> None:
    assert MODULE.parse_json_argument('{"limit": 2}') == {"limit": 2}
    assert MODULE.validate_query("  SELECT 1;; ", allow_write=False) == "SELECT 1"

    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_json_argument("{")

    with pytest.raises(RuntimeError):
        MODULE.validate_query("", allow_write=False)

    with pytest.raises(RuntimeError):
        MODULE.validate_query("SELECT 1; DROP TABLE widgets", allow_write=False)

    with pytest.raises(RuntimeError):
        MODULE.validate_query("DELETE FROM widgets", allow_write=False)

    with pytest.raises(RuntimeError):
        MODULE.validate_query("SELECT drop FROM widgets", allow_write=False)


def test_resolve_dsn_uses_explicit_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    assert MODULE.resolve_dsn(SimpleNamespace(sqlite_path="sample.sqlite", dsn=None, dsn_env=None)) is None
    assert MODULE.resolve_dsn(SimpleNamespace(sqlite_path=None, dsn="sqlite:///db.sqlite", dsn_env=None)) == "sqlite:///db.sqlite"

    monkeypatch.setenv("DB_DSN", "postgresql://example")
    assert MODULE.resolve_dsn(SimpleNamespace(sqlite_path=None, dsn=None, dsn_env="DB_DSN")) == "postgresql://example"

    with pytest.raises(RuntimeError):
        MODULE.resolve_dsn(SimpleNamespace(sqlite_path=None, dsn=None, dsn_env="MISSING_DSN"))

    with pytest.raises(RuntimeError):
        MODULE.resolve_dsn(SimpleNamespace(sqlite_path=None, dsn=None, dsn_env=None))


def test_stringify_value_and_render_markdown_table_handle_special_cases() -> None:
    class FakeDate:
        def isoformat(self) -> str:
            return "2026-03-30T00:00:00"

    assert MODULE.stringify_value(None) == "null"
    assert MODULE.stringify_value({"key": "value"}) == '{"key": "value"}'
    assert MODULE.stringify_value(FakeDate()) == "2026-03-30T00:00:00"
    assert MODULE.stringify_value("x" * 200).endswith("…")

    table = MODULE.render_markdown_table(["id", "name"], [[1, "alpha"], [2, "beta"]])
    assert "| id | name  |" in table
    assert "alpha" in table and "beta" in table


def test_execute_sqlite_select_respects_limit_and_truncation(tmp_path: Path) -> None:
    database_path = create_sqlite_db(tmp_path)

    result = MODULE.execute_sqlite(
        "SELECT id, name FROM widgets ORDER BY id",
        str(database_path),
        {},
        limit=2,
        allow_write=False,
    )

    assert result["columns"] == ["id", "name"]
    assert result["rows"] == [[1, "alpha"], [2, "beta"]]
    assert result["rowcount"] == 2
    assert result["truncated"] is True


def test_execute_sqlite_allows_write_when_enabled(tmp_path: Path) -> None:
    database_path = create_sqlite_db(tmp_path)

    result = MODULE.execute_sqlite(
        "INSERT INTO widgets (name) VALUES (:name)",
        str(database_path),
        {"name": "delta"},
        limit=5,
        allow_write=True,
    )

    assert result["columns"] == []
    assert result["rows"] == []

    connection = sqlite3.connect(database_path)
    try:
        names = [row[0] for row in connection.execute("SELECT name FROM widgets ORDER BY id")]
    finally:
        connection.close()

    assert names == ["alpha", "beta", "gamma", "delta"]


def test_execute_sqlite_ignores_query_only_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCursor:
        description = [("value",)]

        def fetchmany(self, _limit: int) -> list[tuple[int]]:
            return [(1,)]

    class FakeConnection:
        def __init__(self) -> None:
            self.query_only_attempted = False

        def execute(self, query: str, params: object | None = None) -> FakeCursor:
            if query == "PRAGMA query_only = ON":
                self.query_only_attempted = True
                raise sqlite3.DatabaseError("unsupported")
            return FakeCursor()

        def close(self) -> None:
            return None

    monkeypatch.setattr(MODULE.sqlite3, "connect", lambda _path: FakeConnection())

    result = MODULE.execute_sqlite("SELECT 1", "sample.sqlite", {}, limit=1, allow_write=False)

    assert result == {
        "columns": ["value"],
        "rows": [[1]],
        "rowcount": 1,
        "truncated": False,
    }


def test_execute_sqlalchemy_requires_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "create_engine", None)
    monkeypatch.setattr(MODULE, "text", None)

    with pytest.raises(RuntimeError):
        MODULE.execute_sqlalchemy("SELECT 1", "sqlite:///sample.sqlite", {}, limit=1)


def test_validate_query_allow_write_and_execute_sqlalchemy_success_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert MODULE.validate_query(" UPDATE widgets SET name = 'delta' ", allow_write=True) == "UPDATE widgets SET name = 'delta'"

    class FakeResult:
        rowcount = 2

        def keys(self) -> list[str]:
            return ["id", "name"]

        def fetchmany(self, size: int) -> list[tuple[int, str]]:
            assert size == 2
            return [(1, "alpha"), (2, "beta")]

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        def execute(self, statement: str, params: object) -> FakeResult:
            assert statement == "TEXT::SELECT id, name FROM widgets"
            assert params == {"limit": 1}
            return FakeResult()

    class FakeEngine:
        def __init__(self) -> None:
            self.disposed = False

        def connect(self) -> FakeConnection:
            return FakeConnection()

        def dispose(self) -> None:
            self.disposed = True

    engine = FakeEngine()
    monkeypatch.setattr(MODULE, "create_engine", lambda dsn, future=True: engine)
    monkeypatch.setattr(MODULE, "text", lambda query: f"TEXT::{query}")

    result = MODULE.execute_sqlalchemy("SELECT id, name FROM widgets", "sqlite:///sample.sqlite", {"limit": 1}, limit=1)

    assert result == {
        "columns": ["id", "name"],
        "rows": [[1, "alpha"]],
        "rowcount": 1,
        "truncated": True,
    }
    assert engine.disposed is True


def test_execute_sqlalchemy_handles_non_tabular_results(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResult:
        rowcount = 3

        def keys(self) -> None:
            return None

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        def execute(self, statement: str, params: object) -> FakeResult:
            return FakeResult()

    class FakeEngine:
        def connect(self) -> FakeConnection:
            return FakeConnection()

        def dispose(self) -> None:
            return None

    monkeypatch.setattr(MODULE, "create_engine", lambda dsn, future=True: FakeEngine())
    monkeypatch.setattr(MODULE, "text", lambda query: query)

    assert MODULE.execute_sqlalchemy("UPDATE widgets SET name = 'delta'", "sqlite:///sample.sqlite", {}, limit=1) == {
        "columns": [],
        "rows": [],
        "rowcount": 3,
        "truncated": False,
    }


def test_validate_args_requires_single_connection_and_positive_limit() -> None:
    parser = MODULE.build_parser()

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(sqlite_path=None, dsn=None, dsn_env=None, limit=1, params={}),
            parser,
        )

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(sqlite_path="a.sqlite", dsn="sqlite:///b.sqlite", dsn_env=None, limit=1, params={}),
            parser,
        )

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(sqlite_path="a.sqlite", dsn=None, dsn_env=None, limit=0, params={}),
            parser,
        )

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(sqlite_path="a.sqlite", dsn=None, dsn_env=None, limit=1, params="bad"),
            parser,
        )


def test_main_outputs_json_for_sqlite_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = create_sqlite_db(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query.py",
            "SELECT id, name FROM widgets ORDER BY id",
            "--sqlite-path",
            str(database_path),
            "--output",
            "json",
            "--limit",
            "2",
        ],
    )

    assert MODULE.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["engine"] == "sqlite"
    assert payload["rows"] == [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]
    assert payload["truncated"] is True


def test_main_outputs_write_summaries_and_database_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = create_sqlite_db(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query.py",
            "INSERT INTO widgets (name) VALUES ('delta')",
            "--sqlite-path",
            str(database_path),
            "--allow-write",
        ],
    )

    assert MODULE.main() == 0
    assert "No tabular result. Rows affected: 1" in capsys.readouterr().out

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query.py",
            "SELECT * FROM missing_table",
            "--sqlite-path",
            str(database_path),
        ],
    )

    assert MODULE.main() == 1
    assert "Error:" in capsys.readouterr().err


def test_main_outputs_table_for_dsn_queries(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        MODULE,
        "execute_sqlalchemy",
        lambda query, dsn, params, limit: {
            "columns": ["id"],
            "rows": [[1]],
            "rowcount": 1,
            "truncated": True,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["query.py", "SELECT id FROM widgets", "--dsn", "sqlite:///widgets.db", "--limit", "1"],
    )

    assert MODULE.main() == 0
    truncated_output = capsys.readouterr().out
    assert "| id |" in truncated_output
    assert "Rows shown: 1 (truncated)" in truncated_output

    monkeypatch.setattr(
        MODULE,
        "execute_sqlalchemy",
        lambda query, dsn, params, limit: {
            "columns": ["id"],
            "rows": [[1]],
            "rowcount": 1,
            "truncated": False,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["query.py", "SELECT id FROM widgets", "--dsn", "sqlite:///widgets.db", "--limit", "1"],
    )

    assert MODULE.main() == 0
    full_output = capsys.readouterr().out
    assert "Rows shown: 1" in full_output


def test_script_entrypoint_exits_with_main_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = create_sqlite_db(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT_PATH),
            "SELECT id FROM widgets ORDER BY id LIMIT 1",
            "--sqlite-path",
            str(database_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 0
    assert "Rows shown: 1" in capsys.readouterr().out

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from sqlalchemy import create_engine, text
except ImportError:  # pragma: no cover - dependency validation happens at runtime
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]

DEFAULT_LIMIT = 100
CELL_PREVIEW_LIMIT = 120
BLOCKED_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "grant",
    "revoke",
    "attach",
    "detach",
    "copy",
    "merge",
    "replace",
    "vacuum",
)
READ_ONLY_PREFIXES = ("select", "with", "pragma", "explain", "show", "describe")


def load_local_env() -> None:
    env_paths = [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]
    seen: set[Path] = set()
    for env_path in env_paths:
        if not env_path.exists() or env_path in seen:
            continue
        seen.add(env_path)
        load_dotenv(env_path, override=False)


def parse_json_argument(raw_value: str) -> Any:
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"Invalid JSON: {exc.msg}.") from exc


def normalize_query(query: str) -> str:
    normalized = query.strip()
    while normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()
    return normalized


def validate_query(query: str, allow_write: bool) -> str:
    normalized = normalize_query(query)
    if not normalized:
        raise RuntimeError("Query cannot be empty.")
    if ";" in normalized:
        raise RuntimeError("Only single-statement SQL is allowed.")
    lowered = normalized.lower()
    if allow_write:
        return normalized
    if not lowered.startswith(READ_ONLY_PREFIXES):
        raise RuntimeError("Read-only mode only allows SELECT, WITH, PRAGMA, EXPLAIN, SHOW, or DESCRIBE queries.")
    keyword_pattern = r"\b(" + "|".join(BLOCKED_KEYWORDS) + r")\b"
    if re.search(keyword_pattern, lowered):
        raise RuntimeError("Query contains a blocked keyword while running in read-only mode.")
    return normalized


def resolve_dsn(args: argparse.Namespace) -> str | None:
    if args.sqlite_path:
        return None
    if args.dsn:
        return args.dsn
    if args.dsn_env:
        dsn = os.environ.get(args.dsn_env)
        if dsn:
            return dsn
        raise RuntimeError(f"Environment variable '{args.dsn_env}' is missing or empty.")
    raise RuntimeError("Provide either --sqlite-path, --dsn, or --dsn-env.")


def stringify_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        text_value = json.dumps(value, ensure_ascii=False)
    elif hasattr(value, "isoformat") and callable(value.isoformat):
        text_value = value.isoformat()
    else:
        text_value = str(value)
    if len(text_value) <= CELL_PREVIEW_LIMIT:
        return text_value
    return f"{text_value[:CELL_PREVIEW_LIMIT]}…"


def render_markdown_table(columns: list[str], rows: list[list[Any]]) -> str:
    rendered_rows = [[stringify_value(value) for value in row] for row in rows]
    widths = [len(column) for column in columns]
    for row in rendered_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def render_row(values: list[str]) -> str:
        padded = [value.ljust(widths[index]) for index, value in enumerate(values)]
        return f"| {' | '.join(padded)} |"

    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    lines = [render_row(columns), separator]
    for row in rendered_rows:
        lines.append(render_row(row))
    return "\n".join(lines)


def rows_to_json(columns: list[str], rows: list[list[Any]]) -> list[dict[str, Any]]:
    return [dict(zip(columns, row)) for row in rows]


def execute_sqlite(query: str, database_path: str, params: Any, limit: int, allow_write: bool) -> dict[str, Any]:
    connection = sqlite3.connect(database_path)
    try:
        if not allow_write:
            try:
                connection.execute("PRAGMA query_only = ON")
            except sqlite3.DatabaseError:
                pass
        cursor = connection.execute(query, params)
        if cursor.description is None:
            connection.commit()
            return {"columns": [], "rows": [], "rowcount": cursor.rowcount, "truncated": False}
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchmany(limit + 1)
        truncated = len(rows) > limit
        return {
            "columns": columns,
            "rows": [list(row) for row in rows[:limit]],
            "rowcount": len(rows[:limit]),
            "truncated": truncated,
        }
    finally:
        connection.close()


def execute_sqlalchemy(query: str, dsn: str, params: Any, limit: int) -> dict[str, Any]:
    if create_engine is None or text is None:
        raise RuntimeError("Missing dependency 'SQLAlchemy'. Install it from requirements.txt before using DSN mode.")
    engine = create_engine(dsn, future=True)
    try:
        with engine.connect() as connection:
            result = connection.execute(text(query), params)
            if result.keys() is None:
                return {"columns": [], "rows": [], "rowcount": result.rowcount, "truncated": False}
            columns = list(result.keys())
            rows = result.fetchmany(limit + 1)
            truncated = len(rows) > limit
            return {
                "columns": columns,
                "rows": [list(row) for row in rows[:limit]],
                "rowcount": len(rows[:limit]),
                "truncated": truncated,
            }
    finally:
        engine.dispose()


def execute_query(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    query = validate_query(args.query, args.allow_write)
    if args.sqlite_path:
        return "sqlite", execute_sqlite(query, args.sqlite_path, args.params, args.limit, args.allow_write)

    dsn = resolve_dsn(args)
    return "sqlalchemy", execute_sqlalchemy(query, dsn, args.params, args.limit)


def emit_json_result(engine_name: str, result: dict[str, Any]) -> None:
    payload = {
        "engine": engine_name,
        "columns": result["columns"],
        "rows": rows_to_json(result["columns"], result["rows"]),
        "rowcount": result["rowcount"],
        "truncated": result["truncated"],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def emit_table_result(limit: int, result: dict[str, Any]) -> None:
    if not result["columns"]:
        print(f"No tabular result. Rows affected: {result['rowcount']}")
        return

    print(render_markdown_table(result["columns"], result["rows"]))
    if result["truncated"]:
        print(f"\nRows shown: {limit} (truncated)")
        return
    print(f"\nRows shown: {result['rowcount']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a compact SQL query against SQLite or a DSN-backed database.")
    parser.add_argument("query", help="SQL query to execute.")
    parser.add_argument("--sqlite-path", help="Path to a SQLite database file.")
    parser.add_argument("--dsn", help="Explicit SQLAlchemy DSN, for example postgresql+psycopg://user:pass@host/db.")
    parser.add_argument("--dsn-env", help="Environment variable containing a SQLAlchemy DSN.")
    parser.add_argument("--params", type=parse_json_argument, default={}, help="JSON object or array of SQL parameters. Default: {}.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Maximum rows to return. Default: {DEFAULT_LIMIT}.")
    parser.add_argument("--output", choices=("table", "json"), default="table", help="Output format. Default: table.")
    parser.add_argument("--allow-write", action="store_true", help="Allow non-read-only statements. Use sparingly.")
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    provided_connections = [bool(args.sqlite_path), bool(args.dsn), bool(args.dsn_env)]
    if sum(provided_connections) != 1:
        parser.error("Provide exactly one of --sqlite-path, --dsn, or --dsn-env.")
    if args.limit < 1:
        parser.error("--limit must be at least 1.")
    if not isinstance(args.params, (dict, list, tuple)):
        parser.error("--params must decode to a JSON object or array.")


def main() -> int:
    load_local_env()
    parser = build_parser()
    args = parser.parse_args()
    validate_args(args, parser)

    try:
        engine_name, result = execute_query(args)
    except (RuntimeError, sqlite3.DatabaseError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.output == "json":
        emit_json_result(engine_name, result)
        return 0

    emit_table_result(args.limit, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

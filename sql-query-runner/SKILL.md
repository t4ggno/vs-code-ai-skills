---
name: sql-query-runner
description: Executes compact SQL queries against SQLite or DSN-backed databases with read-only safety by default. Use for live schema or data inspection and verification. Do not use it for migrations or destructive writes unless the task explicitly requires that.
argument-hint: <query> [sqlite path or DSN env, params, limit]
---

# SQL Query Runner

1. Use this skill when the task requires real database state instead of assumptions from code.
2. Execute the local script [query.py](./query.py) with a single SQL statement.
3. Prefer the default read-only mode. Only use `--allow-write` when the task explicitly requires a write and the risk is understood.
4. Prefer `--sqlite-path` for local SQLite files and `--dsn-env` for server databases so credentials stay outside chat history.
5. Use `--params` for named parameters instead of string-building SQL values manually.
6. Keep result sets small with `--limit` and choose `--output json` only when another tool needs structured output.

## Common invocations

- SQLite read-only query:
	`python ./query.py "select id, email from users order by id limit 5" --sqlite-path ./dev.db`
- DSN from environment:
	`python ./query.py "select id, email from users where email = :email" --dsn-env DATABASE_URL --params '{"email":"seeded-admin@example.com"}'`
- JSON output:
	`python ./query.py "select * from roles" --sqlite-path ./dev.db --output json`

## Guardrails

- The script blocks multi-statement SQL in safe mode.
- Keep writes explicit, minimal, and well justified.
- Prefer inspection queries over ad-hoc schema mutations.

---
name: sql-query-runner
description: Executes SQL queries against SQLite or SQLAlchemy-backed databases, defaults to safe read-only access, and returns compact tables or JSON for schema and data inspection.
---

# SQL Query Runner Skill

Use this skill when the agent needs to inspect live database state instead of guessing what rows or schema exist.

It is especially useful for:

- Validating seed data and authentication tables.
- Inspecting schemas, views, and query results.
- Running compact read-only queries against SQLite, Postgres, or MySQL.
- Confirming whether an API-side mutation actually persisted to the database.

## Authentication guidance

Keep database authentication lean:

- For SQLite, use `--sqlite-path` and no credentials are needed.
- For server databases, prefer `--dsn-env DATABASE_URL` so the connection string stays outside the chat history.
- The script defaults to read-only mode and blocks dangerous statements unless `--allow-write` is explicitly used.

## Setup

Install the dependencies from `requirements.txt`.

- SQLite works immediately with Python's standard library.
- For Postgres or MySQL, install the driver required by your DSN in the active environment if it is not already present.

## Usage

Run a read-only query against SQLite:

```bash
python c:/Users/ehrha/.copilot/skills/sql-query-runner/query.py "select id, email from users order by id limit 5" --sqlite-path ./dev.db
```

Run a query using a DSN from the environment:

```bash
python c:/Users/ehrha/.copilot/skills/sql-query-runner/query.py "select id, email from users where email = :email" --dsn-env DATABASE_URL --params '{"email":"seeded-admin@example.com"}'
```

Return JSON instead of a markdown table:

```bash
python c:/Users/ehrha/.copilot/skills/sql-query-runner/query.py "select * from roles" --sqlite-path ./dev.db --output json
```

## Notes

- The script rejects multi-statement SQL in safe mode.
- Query results are capped with `--limit` to avoid context blowups.
- Use `--params` for named parameters instead of string-concatenating values into SQL.

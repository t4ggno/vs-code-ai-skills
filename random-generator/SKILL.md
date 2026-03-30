---
name: random-generator
description: Generates random or seeded test data including strings, numbers, ranges, choices, and Faker-backed values. Use for fixtures, demos, mock payloads, or quick experiments. Do not use it for cryptographic secrets, passwords, or production identifiers.
argument-hint: <kind> [count, constraints, format, seed]
---

# Random Generator

1. Use this skill when the task needs sample or deterministic test data, not security-sensitive values.
2. Execute the local script [generate.py](./generate.py) instead of manually inventing batches of mock values.
3. Decide whether the result should be reproducible. If yes, set `--seed`.
4. Pick the narrowest generator mode that fits the task: `string`, `integer`, `float`, `boolean`, `choice`, `range`, or `faker`.
5. Use `--unique` only when uniqueness is truly required and the generator can satisfy it.
6. Prefer `faker` for human-like names, emails, addresses, and text; prefer `string --regex` for validator-shaped IDs.

## Common invocations

- Default random strings:
	`python ./generate.py`
- Deterministic integers:
	`python ./generate.py integer --min-value 10 --max-value 99 --count 5 --seed demo-seed`
- Regex-based IDs:
	`python ./generate.py string --regex "[A-Z]{3}-[0-9]{4}" --count 5`
- Fake names with Faker:
	`python ./generate.py faker --provider name --locale en_US --count 10`
- JSON output for downstream tooling:
	`python ./generate.py faker --provider text --provider-args '[40]' --count 3 --output json`

## Guardrails

- Do not use this skill for passwords, API keys, salts, or security tokens.
- Use `--output json` when another tool or script needs structured results.
- Keep JSON arguments wrapped correctly in PowerShell when using `--provider-args` or `--provider-kwargs`.

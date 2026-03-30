---
name: uuid-generator
description: Generates UUID or GUID values across supported versions with batch and JSON output support. Use for IDs, fixtures, seeds, and deterministic namespace-based UUIDs. Do not use it for secrets, API tokens, or non-UUID identifier formats.
argument-hint: <version/count> [namespace, name template, output format]
---

# UUID Generator

1. Use this skill when the task needs standard UUID or GUID values.
2. Execute the local script [generate.py](./generate.py) instead of hand-writing example UUIDs.
3. Use `UUIDv4` for normal random identifiers unless the user specifically needs deterministic or time-ordered variants.
4. Use `UUIDv3` or `UUIDv5` with `--namespace` and `--name` when the user needs deterministic values.
5. Use `--output json` when another tool needs structured metadata along with the generated UUIDs.

## Common invocations

- Default batch of UUIDv4 values:
	`python ./generate.py`
- Single UUIDv4:
	`python ./generate.py --count 1`
- UUIDv7 batch when supported by the runtime:
	`python ./generate.py --version 7 --count 50`
- Deterministic UUIDv5 values:
	`python ./generate.py --version 5 --namespace dns --name example.com --count 3 --output json`
- Indexed deterministic batch:
	`python ./generate.py --version 5 --namespace dns --name user-{index} --count 3`

## Guardrails

- `--namespace` and `--name` are only for `UUIDv3` and `UUIDv5`.
- `--namespace` accepts `dns`, `url`, `oid`, `x500`, or a literal UUID.
- Use `--uppercase` only when the caller explicitly wants uppercase output.
- Do not use UUIDs as a substitute for API tokens or secrets.

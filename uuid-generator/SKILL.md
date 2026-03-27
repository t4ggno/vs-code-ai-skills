---
name: uuid-generator
description: Generates UUIDs with UUIDv4 as the default, supports other standard versions, and can create single values or batches when unique identifiers are needed.
---

# UUID Generator Skill

Use this skill when the user asks for UUIDs or GUIDs for IDs, fixtures, test data, seeds, or migration values.

## Defaults

- Default UUID version: `UUIDv4`
- Default batch size: `20`
- Default output: one UUID per line

## Supported versions

- `UUIDv1`
- `UUIDv3` (deterministic; requires namespace and name)
- `UUIDv4`
- `UUIDv5` (deterministic; requires namespace and name)
- `UUIDv6` and `UUIDv7` when the local Python runtime supports them

## Usage

Run the generator script:

```bash
python c:/Users/ehrha/.copilot/skills/uuid-generator/generate.py
```

That default command prints 20 `UUIDv4` values.

### Common examples

Generate a single random UUIDv4:

```bash
python c:/Users/ehrha/.copilot/skills/uuid-generator/generate.py --count 1
```

Generate 50 UUIDv7 values when supported by the local Python runtime:

```bash
python c:/Users/ehrha/.copilot/skills/uuid-generator/generate.py --version 7 --count 50
```

Generate deterministic UUIDv5 values:

```bash
python c:/Users/ehrha/.copilot/skills/uuid-generator/generate.py --version 5 --namespace dns --name example.com --count 3 --output json
```

Generate a deterministic batch with indexed names:

```bash
python c:/Users/ehrha/.copilot/skills/uuid-generator/generate.py --version 5 --namespace dns --name user-{index} --count 3
```

## Notes

- Use `--namespace` and `--name` only with `UUIDv3` or `UUIDv5`.
- `--namespace` accepts `dns`, `url`, `oid`, `x500`, or a literal UUID.
- For `UUIDv3` and `UUIDv5`, include `{index}` in `--name` if you want unique deterministic values in a batch.
- Use `--output json` when the user needs metadata along with the generated values.
- Use `--uppercase` if the user explicitly wants uppercase UUID strings.

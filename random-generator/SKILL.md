---
name: random-generator
description: Generates random test data such as strings, numbers, ranges, choices, and Faker-backed values for fixtures, seeds, mocks, and quick experiments.
---

# Random Generator Skill

Use this skill when you need batches of random data for fixtures, demos, tests, seeds, or quick throwaway datasets.

It combines Python's standard library with:

- `Faker` for realistic fake data like names, emails, addresses, profiles, and text
- `rstr` for regex-driven string generation

## Defaults

- Default kind: `string`
- Default batch size: `20`
- Default output: one value per line

## Supported kinds

- `string`
- `integer`
- `float`
- `boolean`
- `choice`
- `range`
- `faker`

## Usage

Run the generator script:

```bash
python c:/Users/ehrha/.copilot/skills/random-generator/generate.py
```

That default command prints 20 random strings.

### Common examples

Generate 20 integers between 10 and 99:

```bash
python c:/Users/ehrha/.copilot/skills/random-generator/generate.py integer --min-value 10 --max-value 99
```

Generate 5 regex-based strings:

```bash
python c:/Users/ehrha/.copilot/skills/random-generator/generate.py string --regex "[A-Z]{3}-[0-9]{4}" --count 5
```

Generate a shuffled range:

```bash
python c:/Users/ehrha/.copilot/skills/random-generator/generate.py range --start 1 --stop 101 --shuffle --count 10
```

Generate fake names with Faker:

```bash
python c:/Users/ehrha/.copilot/skills/random-generator/generate.py faker --provider name --locale en_US --count 10
```

Generate fake text as JSON:

```bash
python c:/Users/ehrha/.copilot/skills/random-generator/generate.py faker --provider text --provider-args '[40]' --count 3 --output json
```

Generate deterministic values using a seed:

```bash
python c:/Users/ehrha/.copilot/skills/random-generator/generate.py string --seed demo-seed --count 5
```

## Notes

- Use `--unique` when you want distinct values and the underlying generator can satisfy it.
- `choice` generation requires `--items`.
- `range` generation returns values from Python's `range(start, stop, step)` and truncates to `--count`.
- `faker` generation uses the provider named by `--provider`; optional provider args/kwargs can be passed as JSON.
- On PowerShell, wrap JSON passed to `--provider-args` or `--provider-kwargs` in single quotes.
- `string --regex` requires `rstr` and is ideal for IDs, slugs, and validator-friendly samples.
- `Faker` is excellent for realistic data; `Mimesis` is also a strong future option if you want even more schema-heavy or high-volume fake data generation.

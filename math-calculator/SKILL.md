---
name: math-calculator
description: Safely evaluates precise mathematical expressions with Python instead of guessing. Use for arithmetic, trigonometry, logs, roots, and numeric verification. Do not use it for symbolic algebra, theorem proving, or handwritten equation OCR.
argument-hint: <expression> [required precision or expected units]
---

# Math Calculator

1. Use this skill whenever the answer must be numerically correct and should not be estimated from model intuition.
2. Execute the local script [calculate.py](./calculate.py) with the exact expression.
3. Prefer explicit functions and constants such as `sqrt(81)`, `sin(pi / 2)`, or `math.factorial(6)`.
4. Use `**` for exponentiation instead of `^`.
5. Treat the result as authoritative only for supported numeric expressions; if the task is symbolic, switch to a different approach.

## Common examples

- `python ./calculate.py "2 + 3 * 4"`
- `python ./calculate.py "sqrt(81) + log10(1000)"`
- `python ./calculate.py "math.factorial(6) / 3"`

## Guardrails

- This is for numeric evaluation, not symbolic manipulation.
- Keep units and rounding expectations in the prompt if they matter.
- Re-run with a simplified expression if the first one fails validation.

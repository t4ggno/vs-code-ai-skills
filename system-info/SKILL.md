---
name: system-info
description: Reports local OS, CPU, memory, and Python environment details from the current machine. Use when troubleshooting environment-specific behavior or capability questions. Do not use it for network scans, remote host inspection, or assumptions about infrastructure you cannot access.
argument-hint: <what to inspect> [os, cpu, memory, python environment]
---

# System Information Fetcher

1. Use this skill when the task depends on the local machine characteristics rather than repository code.
2. Execute the local script [info.py](./info.py) to capture the current OS, CPU, memory, and Python environment details.
3. Use the result to ground environment-specific advice such as dependency compatibility, resource limits, or interpreter context.
4. If the task requires remote infrastructure, container internals, or live network inspection, use a different tool instead.

## Common invocation

`python ./info.py`

## Guardrails

- This skill reports the current local environment only.
- It is useful for grounding build, runtime, and interpreter advice.
- It is not a substitute for port scanners, profiler traces, or remote host access.

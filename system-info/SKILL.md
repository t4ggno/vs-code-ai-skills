---
name: system-info
description: Fetches detailed system and hardware capabilities (OS version, CPU cores, Python version) directly from the user's local operating system.
---

# System Information Fetcher

A skill that fetches detailed system and hardware capabilities directly from the user's local operating system using a Python script. This is vital when the LLM agent needs context on the system's performance metrics, open ports, memory limits, or CPU cores.

Use it when asked about:

- OS version and release.
- Hardware capacities (CPU count, RAM).

## Usage

Run the `info.py` script to get a JSON overview:

```bash
python c:/Users/ehrha/.copilot/skills/system-info/info.py
```

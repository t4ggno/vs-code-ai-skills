---
name: continuous-task
description: Keeps an autonomous task running until a clear stop condition is met. Use when the user explicitly asks for exhaustive, continuous, looping, or background-style progress. Do not use it for ordinary multi-step tasks that a normal agent session can finish directly.
argument-hint: <goal> [scope, stop condition, exhaustive criteria]
---

# Continuous Task Execution

1. Use this skill only when the user clearly wants an exhaustive or continuously progressing task, such as “keep going until nothing else is left” or “run this in the background until done.”
2. Extract three things before acting:
   - the core task
   - the stop condition
   - any scope boundaries the agent must not cross
3. In VS Code, prefer a native Copilot CLI session for true continuous/background execution.
4. Never start a nested `copilot` process from inside chat when the goal is a managed VS Code or Copilot CLI background session.
5. If the user wants the task to keep running after the current local session ends, instruct them to hand off to a Copilot CLI session instead of pretending a plain terminal process is equivalent.
6. Use the Python wrapper [continuous_agent.py](./continuous_agent.py) only as an explicit fallback when a native Copilot CLI background session is unavailable.
7. If the wrapper fallback is used, state plainly that it is an unmanaged terminal loop and will not appear as a managed background task in VS Code Chat or `/tasks`.
8. On wrapper restarts, continue from the saved transcript tail instead of restarting the investigation from zero.

## Wrapper fallback command

Run the local wrapper from the target repository directory:

`python -u ./continuous_agent.py "<core_task_description>"`

## Diagnostics to try when the wrapper exits immediately

- Re-run `copilot login`.
- Inspect or remove `~/.copilot/config.json` if it is corrupted.
- Ensure `pwsh.exe` is available, or install PowerShell 7.
- Inspect `~/.copilot/logs/continuous-task-wrapper.log` and the saved transcript tail in `~/.copilot/logs/continuous-task-last-output.txt`.

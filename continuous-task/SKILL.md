---
name: continuous-task
description: Use this skill when the user requests an exhaustive, continuous, or looping task that should run until completely finished without stopping.
---

# Continuous Task Execution

When the user asks you to run a task "until nothing else found", "exhaustively", or "continuously":

1. Extract the core task the user wants to accomplish.
2. In VS Code, prefer a native Copilot CLI session for continuous/background execution.
   - If you are already in a Copilot CLI session, stay in that session and keep working until the task is actually complete.
   - If you need a long-running shell process inside a Copilot CLI session, use the session's native background-process support so it appears in `/tasks`.
3. Never start a nested `copilot` process from inside chat when the goal is a managed VS Code/Copilot CLI background session.
   - A Python wrapper or ordinary terminal background process is **not** the same thing as a managed Copilot CLI background session.
   - Those unmanaged processes will not show up in the Chat view session list or in `/tasks`.
4. If the current session is a local agent session and the user specifically wants the task to continue in the background, tell them to hand off to a Copilot CLI session instead of pretending a terminal process is a managed background task.
   - In VS Code, this means using the Session Target dropdown to select Copilot CLI, choosing Continue in Copilot CLI, or creating a new Copilot CLI session.
5. Only use the Python wrapper as an explicit fallback for environments where native Copilot CLI background sessions are unavailable.
   - If you use the wrapper fallback, be explicit that it is an unmanaged terminal process.
   - Do not claim it will appear in `/tasks` or in the VS Code background-session UI.
   - Launch it from the target repository/workspace directory so the worker inherits the correct working directory.
   - Use unbuffered Python so progress appears live:
     `python -u ~/.copilot/skills/continuous-task/continuous_agent.py "<core_task_description>"`
6. If the wrapper fallback reports that `copilot` exits immediately, follow its diagnostics before retrying. On Windows, the most common fixes reported upstream are:
   - run `copilot login` again
   - inspect or remove `~/.copilot/config.json` if it is corrupted
   - ensure `pwsh.exe` is available, or install PowerShell 7
7. The wrapper fallback stores the most recent transcript tail in `~/.copilot/logs/continuous-task-last-output.txt` and uses it to continue from the last partial run instead of restarting from scratch.
8. Use this skill only for genuinely long-running autonomous tasks.

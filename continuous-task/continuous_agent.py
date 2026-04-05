import sys
import subprocess
import time
import os
import shutil
import tempfile
import json
from pathlib import Path


RAPID_FAILURE_SECONDS = 15
RESTART_DELAY_SECONDS = 3
MAX_RESTART_DELAY_SECONDS = 60
CONTINUATION_TAIL_CHARS = 12000
MAX_AUTOPILOT_CONTINUES = "200"


def get_log_dir():
    log_dir = Path.home() / ".copilot" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def build_task_prompt(user_task, previous_output, attempt_number):
    prompt = (
        f"{user_task}\n\n"
        "INSTRUCTIONS: Work continuously until the task is fully complete. "
        "Do not stop after planning, progress updates, or partial findings. "
        "After every summary sentence, immediately continue with the next concrete action. "
        "Do not say you are doing something in the background unless you are actually using a background-capable tool. "
        "If you are 100% sure the task is exhaustively complete and there is nothing left to do, "
        "you MUST output the exact phrase 'TASK COMPLETED' and exit."
    )

    if attempt_number == 1 or not previous_output.strip():
        return prompt

    transcript_tail = previous_output[-CONTINUATION_TAIL_CHARS:]
    return (
        f"{prompt}\n\n"
        f"IMPORTANT: The previous run exited before finishing. This is restart attempt {attempt_number}. "
        "Continue from the exact next action instead of starting over from scratch. "
        "Re-validate anything important, but prefer building on the prior investigation.\n\n"
        "Previous run transcript tail:\n"
        f"{transcript_tail}"
    )


def build_copilot_command(prompt):
    copilot_path = shutil.which("copilot")

    base_args = [
        "--autopilot",
        "--yolo",
        "--max-autopilot-continues",
        MAX_AUTOPILOT_CONTINUES,
        "-p",
        prompt,
    ]

    if copilot_path:
        _, extension = os.path.splitext(copilot_path)
        if extension.lower() == ".ps1":
            return [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                copilot_path,
                *base_args,
            ]
        return [copilot_path, *base_args]

    return ["copilot", *base_args]


def build_subprocess_env():
    env = os.environ.copy()
    env.setdefault("COPILOT_AGENT_DEBUG", "1")

    if shutil.which("pwsh.exe"):
        return env

    windows_powershell = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )
    if not os.path.exists(windows_powershell):
        return env

    shim_dir = os.path.join(tempfile.gettempdir(), "copilot-pwsh-shim")
    os.makedirs(shim_dir, exist_ok=True)
    shim_path = os.path.join(shim_dir, "pwsh.exe")

    if not os.path.exists(shim_path):
        shutil.copy2(windows_powershell, shim_path)

    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
    return env


def get_wrapper_log_path():
    return get_log_dir() / "continuous-task-wrapper.log"


def get_restart_state_path():
    return get_log_dir() / "continuous-task-last-output.txt"


def print_diagnostics(log_path):
    print("\n[PYTHON] Copilot is exiting too quickly for continuous mode to work reliably.")
    print("[PYTHON] Likely causes reported upstream on Windows:")
    print("[PYTHON]   1. `copilot -p` is silently failing in non-interactive mode")
    print("[PYTHON]   2. authentication is stale; run `copilot login` again")
    print("[PYTHON]   3. `~/.copilot/config.json` is corrupted")
    print("[PYTHON]   4. `pwsh.exe` is missing; install PowerShell 7 or provide a shim")
    print("[PYTHON]   5. the local Copilot CLI build is broken on this machine")
    print(f"[PYTHON] Wrapper log: {log_path}")
    print("[PYTHON] If `COPILOT_AGENT_DEBUG=1` is enabled, also inspect `~/.copilot/logs/process-*.log`.")


def compute_restart_delay(rapid_failures):
    if rapid_failures <= 0:
        return RESTART_DELAY_SECONDS

    delay = RESTART_DELAY_SECONDS * (2 ** (rapid_failures - 1))
    return min(delay, MAX_RESTART_DELAY_SECONDS)


def load_restart_state(state_path, user_task):
    if not state_path.exists():
        return "", 0

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "", 0

    if state.get("user_task") != user_task:
        return "", 0

    previous_output = state.get("output_tail", "")
    attempt_number = state.get("attempt_number", 0)
    if not isinstance(previous_output, str) or not isinstance(attempt_number, int):
        return "", 0

    return previous_output, attempt_number


def persist_last_output(state_path, user_task, attempt_number, output_text):
    state = {
        "user_task": user_task,
        "attempt_number": attempt_number,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "output_tail": output_text[-CONTINUATION_TAIL_CHARS:],
    }
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def run_copilot_once(cmd, env, log_path):
    start_time = time.monotonic()
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        if os.name == "nt"
        else 0,
    )

    if process.stdout is None:
        raise RuntimeError("Failed to capture copilot output")

    full_output = ""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"\n===== Continuous task run started {timestamp} =====\n")

        for line in process.stdout:
            print(line, end="")
            log_file.write(line)
            full_output += line

        return_code = process.wait()
        duration = time.monotonic() - start_time
        log_file.write(
            f"\n===== Continuous task run ended rc={return_code} duration={duration:.1f}s =====\n"
        )

    return return_code, duration, full_output


def is_rapid_failure(return_code, duration, full_output):
    if "TASK COMPLETED" in full_output:
        return False

    if duration >= RAPID_FAILURE_SECONDS:
        return False

    return return_code != 0 or not full_output.strip()


def continuous_copilot_agent(user_task):
    env = build_subprocess_env()
    log_path = get_wrapper_log_path()
    state_path = get_restart_state_path()
    previous_output, attempt_number = load_restart_state(state_path, user_task)
    rapid_failures = 0

    print(
        "[PYTHON] Legacy fallback mode: this wrapper is an unmanaged terminal process. "
        "It will not appear as a managed Copilot CLI background session in VS Code Chat or `/tasks`."
    )

    while True:
        attempt_number += 1
        prompt = build_task_prompt(user_task, previous_output, attempt_number)
        cmd = build_copilot_command(prompt)
        print(f"\n[PYTHON] Starting autonomous loop for task: {user_task[:50]}...")
        return_code, duration, full_output = run_copilot_once(cmd, env, log_path)
        previous_output = full_output
        persist_last_output(state_path, user_task, attempt_number, full_output)

        if "TASK COMPLETED" in full_output:
            print("\n[PYTHON] Success: Agent concluded the task. Exiting loop.")
            break

        if is_rapid_failure(return_code, duration, full_output):
            rapid_failures += 1
            print(
                f"\n[PYTHON] Copilot exited after {duration:.1f}s with rc={return_code}."
            )
            if rapid_failures == 3:
                print_diagnostics(log_path)
        else:
            rapid_failures = 0

        restart_delay = compute_restart_delay(rapid_failures)
        print(
            f"\n[PYTHON] Agent stopped before TASK COMPLETED. Relaunching attempt {attempt_number + 1} in {restart_delay} seconds..."
        )
        time.sleep(restart_delay)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide a task description.")
        sys.exit(1)

    task_description = sys.argv[1]
    continuous_copilot_agent(task_description)

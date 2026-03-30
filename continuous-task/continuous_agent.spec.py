from __future__ import annotations

import io
import json
import runpy
import sys
from pathlib import Path

import pytest

from conftest import load_module

MODULE = load_module("continuous-task/continuous_agent.py", "continuous_task")
SCRIPT_PATH = Path(__file__).with_name("continuous_agent.py")


def test_build_task_prompt_handles_first_and_restart_attempts() -> None:
    first_prompt = MODULE.build_task_prompt("Fix everything", "", 1)
    assert "TASK COMPLETED" in first_prompt
    assert "Previous run transcript tail" not in first_prompt

    second_prompt = MODULE.build_task_prompt("Fix everything", "prior output", 2)
    assert "restart attempt 2" in second_prompt
    assert "Previous run transcript tail:" in second_prompt
    assert second_prompt.endswith("prior output")


def test_build_copilot_command_prefers_powershell_for_ps1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: r"C:\tools\copilot.ps1")

    command = MODULE.build_copilot_command("demo")

    assert command[:5] == [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
    ]
    assert command[5] == r"C:\tools\copilot.ps1"


def test_build_copilot_command_falls_back_to_plain_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: None)
    command = MODULE.build_copilot_command("demo")
    assert command[0] == "copilot"


def test_build_copilot_command_uses_existing_binary_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: r"C:\tools\copilot.cmd")

    command = MODULE.build_copilot_command("demo")

    assert command[0] == r"C:\tools\copilot.cmd"


def test_build_subprocess_env_creates_pwsh_shim_when_needed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: None)
    monkeypatch.setattr(MODULE.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))
    windows_powershell = tmp_path / "Windows" / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    windows_powershell.parent.mkdir(parents=True)
    windows_powershell.write_text("powershell")

    copied: list[tuple[str, str]] = []
    real_exists = MODULE.os.path.exists

    def fake_copy2(source: str, destination: str) -> None:
        copied.append((source, destination))
        Path(destination).write_text("shim")

    monkeypatch.setattr(MODULE.shutil, "copy2", fake_copy2)
    monkeypatch.setattr(MODULE.os.path, "exists", lambda path: real_exists(path))

    env = MODULE.build_subprocess_env()

    assert env["COPILOT_AGENT_DEBUG"] == "1"
    assert copied and copied[0][0] == str(windows_powershell)
    assert env["PATH"].startswith(str(tmp_path / "copilot-pwsh-shim"))


def test_build_subprocess_env_returns_existing_environment_when_pwsh_or_powershell_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "base-path")
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: r"C:\Program Files\PowerShell\7\pwsh.exe" if name == "pwsh.exe" else None)

    env = MODULE.build_subprocess_env()

    assert env["COPILOT_AGENT_DEBUG"] == "1"
    assert env["PATH"] == "base-path"

    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: None)
    monkeypatch.setattr(MODULE.os.path, "exists", lambda _path: False)

    env_without_powershell = MODULE.build_subprocess_env()

    assert env_without_powershell["COPILOT_AGENT_DEBUG"] == "1"
    assert env_without_powershell["PATH"] == "base-path"


def test_compute_restart_delay_caps_at_maximum() -> None:
    assert MODULE.compute_restart_delay(0) == MODULE.RESTART_DELAY_SECONDS
    assert MODULE.compute_restart_delay(1) == MODULE.RESTART_DELAY_SECONDS
    assert MODULE.compute_restart_delay(10) == MODULE.MAX_RESTART_DELAY_SECONDS


def test_log_path_helpers_and_print_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(MODULE.Path, "home", lambda: tmp_path)

    wrapper_log = MODULE.get_wrapper_log_path()
    restart_state = MODULE.get_restart_state_path()

    assert wrapper_log == tmp_path / ".copilot" / "logs" / "continuous-task-wrapper.log"
    assert restart_state == tmp_path / ".copilot" / "logs" / "continuous-task-last-output.txt"

    MODULE.print_diagnostics(wrapper_log)

    diagnostics = capsys.readouterr().out
    assert "Copilot is exiting too quickly" in diagnostics
    assert str(wrapper_log) in diagnostics


def test_load_and_persist_restart_state_round_trip(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"

    MODULE.persist_last_output(state_path, "demo task", 3, "output text")
    previous_output, attempt_number = MODULE.load_restart_state(state_path, "demo task")

    assert previous_output == "output text"
    assert attempt_number == 3
    assert MODULE.load_restart_state(state_path, "other task") == ("", 0)

    state_path.write_text("not-json", encoding="utf-8")
    assert MODULE.load_restart_state(state_path, "demo task") == ("", 0)


def test_load_restart_state_rejects_invalid_types(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps({"user_task": "demo task", "attempt_number": "three", "output_tail": ["bad"]}),
        encoding="utf-8",
    )

    assert MODULE.load_restart_state(state_path, "demo task") == ("", 0)


def test_is_rapid_failure_checks_duration_return_code_and_completion_marker() -> None:
    assert MODULE.is_rapid_failure(1, 1.0, "partial") is True
    assert MODULE.is_rapid_failure(0, 1.0, "") is True
    assert MODULE.is_rapid_failure(0, 20.0, "partial") is False
    assert MODULE.is_rapid_failure(1, 1.0, "TASK COMPLETED") is False


def test_run_copilot_once_streams_output_and_logs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_path = tmp_path / "wrapper.log"

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = io.StringIO("line one\nline two\n")

        def wait(self) -> int:
            return 0

    monkeypatch.setattr(MODULE.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    monotonic_values = iter([10.0, 14.5])
    monkeypatch.setattr(MODULE.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(MODULE.time, "strftime", lambda _fmt: "2026-03-30 12:00:00")

    return_code, duration, output = MODULE.run_copilot_once(["copilot"], {}, log_path)

    assert return_code == 0
    assert duration == pytest.approx(4.5)
    assert output == "line one\nline two\n"
    assert "line one" in capsys.readouterr().out
    assert "Continuous task run started" in log_path.read_text(encoding="utf-8")


def test_run_copilot_once_raises_when_stdout_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeProcess:
        stdout = None

    monkeypatch.setattr(MODULE.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    with pytest.raises(RuntimeError):
        MODULE.run_copilot_once(["copilot"], {}, tmp_path / "wrapper.log")


def test_run_copilot_once_uses_zero_creationflags_outside_windows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_creationflags: list[int] = []

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = io.StringIO("TASK COMPLETED\n")

        def wait(self) -> int:
            return 0

    def fake_popen(*args: object, **kwargs: object) -> FakeProcess:
        captured_creationflags.append(kwargs["creationflags"])
        return FakeProcess()

    monotonic_values = iter([1.0, 2.0])
    monkeypatch.setattr(MODULE.os, "name", "posix")
    monkeypatch.setattr(MODULE.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(MODULE.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(MODULE.time, "strftime", lambda _fmt: "2026-03-30 12:00:00")

    MODULE.run_copilot_once(["copilot"], {}, tmp_path / "wrapper.log")

    assert captured_creationflags == [0]


def test_continuous_copilot_agent_restarts_until_task_completed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_results = iter(
        [
            (1, 1.0, "partial output"),
            (0, 20.0, "TASK COMPLETED"),
        ]
    )
    persisted_attempts: list[int] = []

    monkeypatch.setattr(MODULE, "build_subprocess_env", lambda: {"PATH": "ok"})
    monkeypatch.setattr(MODULE, "get_wrapper_log_path", lambda: tmp_path / "wrapper.log")
    monkeypatch.setattr(MODULE, "get_restart_state_path", lambda: tmp_path / "state.json")
    monkeypatch.setattr(MODULE, "load_restart_state", lambda _path, _task: ("", 0))
    monkeypatch.setattr(MODULE, "build_task_prompt", lambda task, output, attempt: f"{task}:{attempt}:{output}")
    monkeypatch.setattr(MODULE, "build_copilot_command", lambda prompt: ["copilot", prompt])
    monkeypatch.setattr(MODULE, "run_copilot_once", lambda cmd, env, log: next(run_results))
    monkeypatch.setattr(MODULE, "persist_last_output", lambda path, task, attempt, output: persisted_attempts.append(attempt))
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)

    MODULE.continuous_copilot_agent("Investigate")

    output = capsys.readouterr().out
    assert persisted_attempts == [1, 2]
    assert "Relaunching attempt 2" in output
    assert "Success: Agent concluded the task" in output


def test_continuous_copilot_agent_prints_diagnostics_after_three_rapid_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_results = iter(
        [
            (1, 1.0, "partial output 1"),
            (1, 1.0, "partial output 2"),
            (1, 1.0, "partial output 3"),
            (0, 20.0, "still working"),
            (0, 20.0, "TASK COMPLETED"),
        ]
    )
    restart_inputs: list[int] = []
    diagnostics_calls: list[Path] = []

    monkeypatch.setattr(MODULE, "build_subprocess_env", lambda: {"PATH": "ok"})
    monkeypatch.setattr(MODULE, "get_wrapper_log_path", lambda: tmp_path / "wrapper.log")
    monkeypatch.setattr(MODULE, "get_restart_state_path", lambda: tmp_path / "state.json")
    monkeypatch.setattr(MODULE, "load_restart_state", lambda _path, _task: ("", 0))
    monkeypatch.setattr(MODULE, "build_task_prompt", lambda task, output, attempt: f"{task}:{attempt}:{output}")
    monkeypatch.setattr(MODULE, "build_copilot_command", lambda prompt: ["copilot", prompt])
    monkeypatch.setattr(MODULE, "run_copilot_once", lambda cmd, env, log: next(run_results))
    monkeypatch.setattr(MODULE, "persist_last_output", lambda *args: None)
    monkeypatch.setattr(MODULE, "compute_restart_delay", lambda rapid_failures: restart_inputs.append(rapid_failures) or 0)
    monkeypatch.setattr(MODULE, "print_diagnostics", lambda log_path: diagnostics_calls.append(log_path))
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)

    MODULE.continuous_copilot_agent("Investigate")

    assert restart_inputs == [1, 2, 3, 0]
    assert diagnostics_calls == [tmp_path / "wrapper.log"]


def test_script_entrypoint_requires_a_task_description(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH)])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 1
    assert "Please provide a task description." in capsys.readouterr().out


def test_script_entrypoint_runs_until_task_completed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = io.StringIO("TASK COMPLETED\n")

        def wait(self) -> int:
            return 0

    monotonic_values = iter([10.0, 30.0])
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), "Investigate"])
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: None)
    monkeypatch.setattr(MODULE.os.path, "exists", lambda _path: False)
    monkeypatch.setattr(MODULE.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(MODULE.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(MODULE.time, "strftime", lambda _fmt: "2026-03-30 12:00:00")
    monkeypatch.setattr(MODULE.Path, "home", lambda: tmp_path)

    runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert "Success: Agent concluded the task" in capsys.readouterr().out

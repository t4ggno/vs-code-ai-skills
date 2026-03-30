from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from conftest import load_module

MODULE = load_module("system-info/info.py", "system_info")
SCRIPT_PATH = Path(__file__).with_name("info.py")


@pytest.mark.parametrize("system_name", ["Windows", "Linux", "Darwin"])
def test_get_system_info_includes_cpu_cores_for_supported_platforms(
    monkeypatch: pytest.MonkeyPatch,
    system_name: str,
) -> None:
    monkeypatch.setattr(MODULE.platform, "system", lambda: system_name)
    monkeypatch.setattr(MODULE.platform, "release", lambda: "release")
    monkeypatch.setattr(MODULE.platform, "version", lambda: "version")
    monkeypatch.setattr(MODULE.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(MODULE.platform, "processor", lambda: "cpu")
    monkeypatch.setattr(MODULE.platform, "python_version", lambda: "3.12.1")
    monkeypatch.setattr(MODULE.os, "cpu_count", lambda: 16)

    result = MODULE.get_system_info()

    assert result["os"] == system_name
    assert result["architecture"] == "x86_64"
    assert result["cpu_cores"] == 16


def test_get_system_info_omits_cpu_cores_for_unknown_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE.platform, "system", lambda: "Plan9")
    monkeypatch.setattr(MODULE.platform, "release", lambda: "release")
    monkeypatch.setattr(MODULE.platform, "version", lambda: "version")
    monkeypatch.setattr(MODULE.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(MODULE.platform, "processor", lambda: "cpu")
    monkeypatch.setattr(MODULE.platform, "python_version", lambda: "3.12.1")

    result = MODULE.get_system_info()

    assert result["os"] == "Plan9"
    assert "cpu_cores" not in result


def test_get_system_info_includes_memory_and_python_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE.platform, "system", lambda: "Linux")
    monkeypatch.setattr(MODULE.platform, "release", lambda: "release")
    monkeypatch.setattr(MODULE.platform, "version", lambda: "version")
    monkeypatch.setattr(MODULE.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(MODULE.platform, "processor", lambda: "cpu")
    monkeypatch.setattr(MODULE.platform, "platform", lambda: "Linux-test")
    monkeypatch.setattr(MODULE.platform, "python_version", lambda: "3.13.3")
    monkeypatch.setattr(MODULE.platform, "python_implementation", lambda: "CPython")
    monkeypatch.setattr(MODULE.socket, "gethostname", lambda: "devbox")
    monkeypatch.setattr(MODULE.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(MODULE, "detect_total_memory_bytes", lambda: 8 * 1024 ** 3)
    monkeypatch.setattr(MODULE, "detect_python_environment", lambda: {"type": "venv", "path": "/tmp/.venv"})

    result = MODULE.get_system_info()

    assert result["memory_total_bytes"] == 8 * 1024 ** 3
    assert result["memory_total_gb"] == 8.0
    assert result["hostname"] == "devbox"
    assert result["python_environment"] == {"type": "venv", "path": "/tmp/.venv"}


def test_cli_prints_json_payload(capsys: pytest.CaptureFixture[str]) -> None:
    runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    payload = json.loads(capsys.readouterr().out)
    assert "os" in payload
    assert "python_version" in payload

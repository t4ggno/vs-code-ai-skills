from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

from conftest import load_module

MODULE = load_module("math-calculator/calculate.py", "math_calculator")
SCRIPT_PATH = Path(__file__).with_name("calculate.py")


def test_calculate_supports_common_math_operations() -> None:
    assert MODULE.calculate("2 + 3 * 4") == 14
    assert MODULE.calculate("sqrt(81)") == 9.0
    assert MODULE.calculate("abs(-7)") == 7


def test_calculate_supports_trigonometric_functions_and_constants() -> None:
    assert MODULE.calculate("sin(pi / 2)") == pytest.approx(1.0)
    assert MODULE.calculate("cos(0)") == pytest.approx(1.0)


def test_calculate_returns_error_string_for_invalid_expression() -> None:
    result = MODULE.calculate("1 / 0")
    assert result.startswith("Error evaluating expression:")


def test_calculate_disallows_unsafe_builtins_access() -> None:
    result = MODULE.calculate("__import__('os').system('echo nope')")
    assert result.startswith("Error evaluating expression:")


def test_cli_prints_usage_when_expression_is_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH)])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 1
    assert "Usage: python calculate.py" in capsys.readouterr().out


def test_cli_prints_result_for_valid_expression(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), "2 + 2"])

    runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert capsys.readouterr().out.strip() == "Result: 4"

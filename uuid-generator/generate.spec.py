from __future__ import annotations

import argparse
import json
import runpy
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import load_module

MODULE = load_module("uuid-generator/generate.py", "uuid_generator")
SCRIPT_PATH = Path(__file__).with_name("generate.py")


def test_normalize_version_accepts_prefixed_values() -> None:
    assert MODULE.normalize_version("UUID4") == "4"


def test_normalize_version_rejects_unsupported_values() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.normalize_version("uuid999")


def test_module_import_populates_runtime_supported_versions() -> None:
    original_uuid6 = getattr(uuid, "uuid6", None)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(uuid, "uuid6", lambda: uuid.UUID(int=0), raising=False)
    try:
        reloaded = load_module("uuid-generator/generate.py", "uuid_generator_reloaded")
    finally:
        monkeypatch.undo()

    assert "6" in reloaded.SUPPORTED_VERSIONS
    if hasattr(uuid, "uuid7"):
        assert "7" in reloaded.SUPPORTED_VERSIONS


def test_parse_positive_int_and_namespace_validation() -> None:
    assert MODULE.parse_positive_int("3") == 3
    assert MODULE.parse_namespace("dns") == uuid.NAMESPACE_DNS

    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_positive_int("not-a-number")

    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_positive_int("0")

    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_namespace("not-a-uuid")


def test_require_namespace_inputs_rejects_invalid_combinations() -> None:
    parser = MODULE.build_parser()

    with pytest.raises(SystemExit):
        MODULE.require_namespace_inputs(SimpleNamespace(version="3", namespace=None, name=None), parser)

    with pytest.raises(SystemExit):
        MODULE.require_namespace_inputs(
            SimpleNamespace(version="4", namespace=uuid.NAMESPACE_DNS, name="name"),
            parser,
        )


def test_generate_values_uppercases_output(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr(MODULE, "build_generator", lambda _version: lambda: fixed_uuid)
    args = SimpleNamespace(version="4", count=2, namespace=None, name=None, uppercase=True)

    assert MODULE.generate_values(args) == [str(fixed_uuid).upper(), str(fixed_uuid).upper()]


def test_generate_values_for_uuid5_use_indexed_name_templates() -> None:
    args = SimpleNamespace(
        version="5",
        count=2,
        namespace=uuid.NAMESPACE_DNS,
        name="item-{index}",
        uppercase=False,
    )

    values = MODULE.generate_values(args)

    assert values == [
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "item-1")),
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "item-2")),
    ]


def test_emit_json_includes_namespace_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    args = SimpleNamespace(version="5", namespace=uuid.NAMESPACE_URL, name="entry-{index}")
    MODULE.emit_json(args, ["first", "second"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "UUIDv5"
    assert payload["count"] == 2
    assert payload["namespace"] == str(uuid.NAMESPACE_URL)
    assert payload["name_template"] == "entry-{index}"


def test_build_generator_and_require_namespace_inputs_cover_runtime_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = MODULE.build_parser()

    MODULE.require_namespace_inputs(
        SimpleNamespace(version="5", namespace=uuid.NAMESPACE_DNS, name="item-{index}"),
        parser,
    )
    MODULE.require_namespace_inputs(SimpleNamespace(version="4", namespace=None, name=None), parser)

    assert callable(MODULE.build_generator("4"))
    assert MODULE.build_name_value("item-{index}", 3) == "item-3"

    monkeypatch.delattr(MODULE.uuid, "uuid7", raising=False)
    with pytest.raises(ValueError):
        MODULE.build_generator("7")


def test_emit_plain_and_main_support_json_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    MODULE.emit_plain(["first", "second"])
    assert capsys.readouterr().out.splitlines() == ["first", "second"]

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate.py",
            "--version",
            "5",
            "--namespace",
            "dns",
            "--name",
            "item-{index}",
            "--count",
            "1",
            "--output",
            "json",
        ],
    )

    assert MODULE.main() == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "UUIDv5"
    assert payload["uuids"] == [str(uuid.uuid5(uuid.NAMESPACE_DNS, "item-1"))]


def test_main_returns_error_when_generation_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_generation_error(_args: SimpleNamespace) -> list[str]:
        raise ValueError("runtime unsupported")

    monkeypatch.setattr(MODULE, "generate_values", raise_generation_error)
    monkeypatch.setattr(sys, "argv", ["generate.py"])

    assert MODULE.main() == 1
    assert "Error: runtime unsupported" in capsys.readouterr().err


def test_script_entrypoint_exits_with_main_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), "--count", "1"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 0
    uuid.UUID(capsys.readouterr().out.strip())

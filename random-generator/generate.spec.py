from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import load_module

MODULE = load_module("random-generator/generate.py", "random_generator")
SCRIPT_PATH = Path(__file__).with_name("generate.py")


def test_parse_helpers_reject_invalid_values() -> None:
    assert MODULE.parse_positive_int("4") == 4
    assert MODULE.parse_ratio("0.5") == 0.5
    assert MODULE.parse_json_argument('{"value": 1}') == {"value": 1}

    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_positive_int("0")

    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_positive_int("zero")

    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_float("not-a-float")

    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_ratio("1.5")

    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_json_argument("{")


def test_validate_args_rejects_invalid_combinations() -> None:
    parser = MODULE.build_parser()

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(
                min_length=10,
                max_length=5,
                length=None,
                include="",
                kind="string",
                min_value=0,
                max_value=1,
                items=None,
                step=1,
                provider_args=[],
                provider_kwargs={},
            ),
            parser,
        )

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(
                min_length=1,
                max_length=5,
                length=1,
                include="AB",
                kind="string",
                min_value=0,
                max_value=1,
                items=None,
                step=1,
                provider_args=[],
                provider_kwargs={},
            ),
            parser,
        )

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(
                min_length=1,
                max_length=5,
                length=None,
                include="",
                kind="choice",
                min_value=0,
                max_value=1,
                items=None,
                step=1,
                provider_args=[],
                provider_kwargs={},
            ),
            parser,
        )

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(
                min_length=1,
                max_length=5,
                length=None,
                include="",
                kind="range",
                min_value=0,
                max_value=1,
                items=None,
                step=0,
                provider_args=[],
                provider_kwargs={},
            ),
            parser,
        )

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(
                min_length=1,
                max_length=5,
                length=None,
                include="",
                kind="faker",
                min_value=0,
                max_value=1,
                items=None,
                step=1,
                provider_args={},
                provider_kwargs=[],
            ),
            parser,
        )

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(
                min_length=1,
                max_length=5,
                length=None,
                include="",
                kind="integer",
                min_value=10,
                max_value=1,
                items=None,
                step=1,
                provider_args=[],
                provider_kwargs={},
            ),
            parser,
        )

    with pytest.raises(SystemExit):
        MODULE.validate_args(
            SimpleNamespace(
                min_length=1,
                max_length=5,
                length=None,
                include="",
                kind="faker",
                min_value=0,
                max_value=1,
                items=None,
                step=1,
                provider_args=[],
                provider_kwargs=[],
            ),
            parser,
        )


def test_generate_string_respects_include_exclude_and_length() -> None:
    args = SimpleNamespace(
        regex=None,
        length=6,
        min_length=1,
        max_length=6,
        include="AZ",
        alphabet="ABCXYZ123",
        exclude="1C",
    )

    value = MODULE.generate_string(args, MODULE.build_rng("seed"))

    assert len(value) == 6
    assert "A" in value and "Z" in value
    assert "1" not in value and "C" not in value


def test_generate_string_uses_regex_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    args = SimpleNamespace(
        regex="[A-Z]{2}\\d{2}",
        length=None,
        min_length=1,
        max_length=8,
        include="",
        alphabet="ABC123",
        exclude="",
    )

    class FakeRstr:
        def xeger(self, pattern: str) -> str:
            assert pattern == args.regex
            return "AB12"

    monkeypatch.setattr(MODULE, "build_rstr", lambda _rng: FakeRstr())

    assert MODULE.generate_string(args, MODULE.build_rng("seed")) == "AB12"


def test_build_string_pool_and_generate_unique_values_error_paths() -> None:
    with pytest.raises(RuntimeError):
        MODULE.build_string_pool(SimpleNamespace(alphabet="abc", exclude="abc"))

    with pytest.raises(RuntimeError):
        MODULE.generate_unique_values(lambda: "repeat", 2)


def test_dependency_helpers_and_emit_plain_cover_optional_dependency_paths(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    MODULE.ensure_dependency("Faker", object())

    with pytest.raises(RuntimeError):
        MODULE.ensure_dependency("Faker", None)

    monkeypatch.setattr(MODULE, "Faker", None)
    with pytest.raises(RuntimeError):
        MODULE.build_faker(SimpleNamespace(locale="en_US", seed=None, unique=False))

    def raise_missing_module(_name: str) -> object:
        raise ModuleNotFoundError("missing")

    monkeypatch.setattr(MODULE.importlib, "import_module", raise_missing_module)
    with pytest.raises(RuntimeError):
        MODULE.build_rstr(MODULE.build_rng("seed"))

    monkeypatch.setattr(MODULE.importlib, "import_module", lambda _name: SimpleNamespace())
    with pytest.raises(RuntimeError):
        MODULE.build_rstr(MODULE.build_rng("seed"))

    class FakeRstr:
        def __init__(self, rng: object) -> None:
            self.rng = rng

    rng = MODULE.build_rng("seed")
    monkeypatch.setattr(MODULE.importlib, "import_module", lambda _name: SimpleNamespace(Rstr=FakeRstr))
    generated_rstr = MODULE.build_rstr(rng)
    assert isinstance(generated_rstr, FakeRstr)
    assert generated_rstr.rng is rng

    class FakeUnique:
        def __init__(self) -> None:
            self.kind = "unique"

    class FakeFaker:
        instances: list["FakeFaker"] = []

        def __init__(self, locale: str) -> None:
            self.locale = locale
            self.seed_value: str | None = None
            self.unique = FakeUnique()
            FakeFaker.instances.append(self)

        def seed_instance(self, seed: str) -> None:
            self.seed_value = seed

    monkeypatch.setattr(MODULE, "Faker", FakeFaker)
    unique_fake = MODULE.build_faker(SimpleNamespace(locale="en_US", seed="seed", unique=True))
    plain_fake = MODULE.build_faker(SimpleNamespace(locale="de_DE", seed=None, unique=False))

    assert unique_fake.kind == "unique"
    assert FakeFaker.instances[0].locale == "en_US"
    assert FakeFaker.instances[0].seed_value == "seed"
    assert isinstance(plain_fake, FakeFaker)
    assert plain_fake.locale == "de_DE"

    MODULE.emit_plain([{"alpha": 1}, ["beta"]])
    assert capsys.readouterr().out.splitlines() == ['{"alpha": 1}', '["beta"]']


def test_generate_string_integer_and_faker_provider_errors() -> None:
    with pytest.raises(RuntimeError):
        MODULE.generate_string(
            SimpleNamespace(
                regex=None,
                length=1,
                min_length=1,
                max_length=1,
                include="AB",
                alphabet="ABC",
                exclude="",
            ),
            MODULE.build_rng("seed"),
        )

    assert MODULE.resolve_string_length(
        SimpleNamespace(length=None, min_length=4, max_length=4),
        MODULE.build_rng("seed"),
    ) == 4

    with pytest.raises(RuntimeError):
        MODULE.generate_integer(SimpleNamespace(min_value=5, max_value=1), MODULE.build_rng("seed"))

    assert MODULE.generate_float(
        SimpleNamespace(min_value=1.234, max_value=1.234, precision=2),
        MODULE.build_rng("seed"),
    ) == 1.23

    with pytest.raises(RuntimeError):
        MODULE.generate_faker_value(
            SimpleNamespace(provider="missing", locale="en_US", provider_args=[], provider_kwargs={}),
            object(),
        )

    class RaisingSource:
        def broken(self, *args: object, **kwargs: object) -> str:
            raise TypeError("bad args")

    with pytest.raises(RuntimeError):
        MODULE.generate_faker_value(
            SimpleNamespace(provider="broken", locale="en_US", provider_args=[1], provider_kwargs={}),
            RaisingSource(),
        )


@pytest.mark.parametrize(
    ("kind", "attribute", "values"),
    [
        ("integer", "generate_integer", [1, 2]),
        ("float", "generate_float", [1.25, 2.5]),
        ("boolean", "generate_boolean", [True, False]),
    ],
)
def test_generate_values_supports_unique_scalar_modes(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    attribute: str,
    values: list[object],
) -> None:
    iterator = iter(values)
    monkeypatch.setattr(MODULE, attribute, lambda _args, _rng: next(iterator))

    args = SimpleNamespace(kind=kind, count=2, unique=True, seed="seed")

    assert MODULE.generate_values(args) == values


def test_generate_values_for_choice_mode_supports_unique_sampling_and_overflow() -> None:
    unique_args = SimpleNamespace(kind="choice", items=["red", "green", "blue"], count=2, unique=True, seed="seed")
    assert len(set(MODULE.generate_values(unique_args))) == 2

    overflow_args = SimpleNamespace(kind="choice", items=["red", "green"], count=3, unique=True, seed="seed")
    with pytest.raises(RuntimeError):
        MODULE.generate_values(overflow_args)


def test_generate_values_for_choice_mode_supports_non_unique_sampling() -> None:
    args = SimpleNamespace(kind="choice", items=["red", "green"], count=4, unique=False, seed="seed")

    values = MODULE.generate_values(args)

    assert len(values) == 4
    assert set(values).issubset({"red", "green"})


def test_generate_values_for_string_mode_supports_non_unique_output() -> None:
    args = SimpleNamespace(
        kind="string",
        count=2,
        unique=False,
        seed="seed",
        regex=None,
        length=4,
        min_length=4,
        max_length=4,
        include="",
        alphabet="AB",
        exclude="",
    )

    values = MODULE.generate_values(args)

    assert len(values) == 2
    assert all(len(value) == 4 for value in values)


def test_generate_values_for_range_mode_shuffle_and_truncate() -> None:
    args = SimpleNamespace(kind="range", start=0, stop=10, step=2, shuffle=True, count=3, seed="seed")

    values = MODULE.generate_values(args)

    assert len(values) == 3
    assert set(values).issubset({0, 2, 4, 6, 8})


def test_generate_values_for_faker_mode_clears_unique_source(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSource:
        def __init__(self) -> None:
            self.call_count = 0
            self.cleared = False

        def company(self) -> str:
            self.call_count += 1
            return f"Company {self.call_count}"

        def clear(self) -> None:
            self.cleared = True

    fake_source = FakeSource()
    monkeypatch.setattr(MODULE, "build_faker", lambda _args: fake_source)
    args = SimpleNamespace(
        kind="faker",
        count=2,
        unique=True,
        provider="company",
        locale="en_US",
        provider_args=[],
        provider_kwargs={},
        seed=None,
    )

    values = MODULE.generate_values(args)

    assert values == ["Company 1", "Company 2"]
    assert fake_source.cleared is True


def test_main_emits_json_for_deterministic_integer_generation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate.py",
            "integer",
            "--count",
            "2",
            "--seed",
            "seed",
            "--output",
            "json",
            "--min-value",
            "1",
            "--max-value",
            "1",
        ],
    )

    assert MODULE.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "integer"
    assert payload["values"] == [1, 1]


def test_main_returns_error_for_runtime_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate.py", "choice", "--unique", "--count", "3", "--items", "red", "blue"],
    )

    assert MODULE.main() == 1
    assert "Unique choice generation cannot return more values" in capsys.readouterr().err


def test_main_emits_plain_boolean_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate.py",
            "boolean",
            "--count",
            "2",
            "--seed",
            "seed",
            "--true-ratio",
            "1",
        ],
    )

    assert MODULE.main() == 0
    assert capsys.readouterr().out.splitlines() == ["True", "True"]


def test_script_entrypoint_exits_with_main_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), "integer", "--count", "1", "--min-value", "1", "--max-value", "1"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == "1"

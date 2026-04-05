from __future__ import annotations

import argparse
import importlib
import json
import random
import string
import sys
from typing import Any, Callable

try:
    from faker import Faker
except ImportError:  # pragma: no cover - dependency validation happens at runtime
    Faker = None  # type: ignore[assignment]

DEFAULT_COUNT = 20
DEFAULT_ALPHABET = string.ascii_letters + string.digits
KIND_CHOICES = ("string", "integer", "float", "boolean", "choice", "range", "faker")


def parse_positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Value must be an integer.") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("Value must be at least 1.")
    return parsed


def parse_float(value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Value must be numeric.") from exc


def parse_ratio(value: str) -> float:
    parsed = parse_float(value)
    if parsed < 0 or parsed > 1:
        raise argparse.ArgumentTypeError("Ratio must be between 0 and 1.")
    return parsed


def parse_json_argument(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"Invalid JSON: {exc.msg}.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate random data such as strings, numbers, ranges, choices, and Faker-backed values."
    )
    parser.add_argument(
        "kind",
        nargs="?",
        default="string",
        choices=KIND_CHOICES,
        help="Type of data to generate. Default: string.",
    )
    parser.add_argument(
        "--count",
        default=DEFAULT_COUNT,
        type=parse_positive_int,
        help=f"Number of values to generate. Default: {DEFAULT_COUNT}.",
    )
    parser.add_argument(
        "--output",
        choices=("plain", "json"),
        default="plain",
        help="Output format. Default: plain.",
    )
    parser.add_argument(
        "--seed",
        help="Optional seed for deterministic output.",
    )
    parser.add_argument(
        "--unique",
        action="store_true",
        help="Require generated values to be unique when possible.",
    )
    parser.add_argument(
        "--length",
        type=parse_positive_int,
        help="Exact string length.",
    )
    parser.add_argument(
        "--min-length",
        default=8,
        type=parse_positive_int,
        help="Minimum string length when --length is not set. Default: 8.",
    )
    parser.add_argument(
        "--max-length",
        default=16,
        type=parse_positive_int,
        help="Maximum string length when --length is not set. Default: 16.",
    )
    parser.add_argument(
        "--alphabet",
        default=DEFAULT_ALPHABET,
        help="Alphabet to use for string generation.",
    )
    parser.add_argument(
        "--include",
        default="",
        help="Characters that must appear in generated strings.",
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="Characters that must not appear in generated strings.",
    )
    parser.add_argument(
        "--regex",
        help="Generate strings from a regex pattern using rstr.",
    )
    parser.add_argument(
        "--min-value",
        default=0,
        type=parse_float,
        help="Minimum numeric value. Default: 0.",
    )
    parser.add_argument(
        "--max-value",
        default=100,
        type=parse_float,
        help="Maximum numeric value. Default: 100.",
    )
    parser.add_argument(
        "--precision",
        default=2,
        type=int,
        help="Decimal places for float output. Default: 2.",
    )
    parser.add_argument(
        "--true-ratio",
        default=0.5,
        type=parse_ratio,
        help="Probability of True for boolean output. Default: 0.5.",
    )
    parser.add_argument(
        "--items",
        nargs="+",
        help="Items for choice generation.",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start value for range generation. Default: 0.",
    )
    parser.add_argument(
        "--stop",
        type=int,
        default=100,
        help="Stop value for range generation (exclusive). Default: 100.",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=1,
        help="Step value for range generation. Default: 1.",
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle range output before truncating to --count.",
    )
    parser.add_argument(
        "--provider",
        default="name",
        help="Faker provider method name. Default: name.",
    )
    parser.add_argument(
        "--locale",
        default="en_US",
        help="Faker locale. Default: en_US.",
    )
    parser.add_argument(
        "--provider-args",
        type=parse_json_argument,
        default=[],
        help="JSON array of positional args for Faker providers.",
    )
    parser.add_argument(
        "--provider-kwargs",
        type=parse_json_argument,
        default={},
        help="JSON object of keyword args for Faker providers.",
    )
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.min_length > args.max_length:
        parser.error("--min-length cannot be greater than --max-length.")
    if args.length is not None and args.length < len(args.include):
        parser.error("--length must be at least the number of required included characters.")
    if args.kind in {"integer", "float"} and args.min_value > args.max_value:
        parser.error("--min-value cannot be greater than --max-value.")
    if args.kind == "choice" and not args.items:
        parser.error("choice generation requires --items.")
    if args.kind == "range" and args.step == 0:
        parser.error("--step cannot be zero.")
    if args.kind == "faker":
        if not isinstance(args.provider_args, list):
            parser.error("--provider-args must be a JSON array.")
        if not isinstance(args.provider_kwargs, dict):
            parser.error("--provider-kwargs must be a JSON object.")


def build_rng(seed: str | None) -> random.Random:
    rng = random.Random()
    if seed is not None:
        rng.seed(seed)
    return rng


def ensure_dependency(name: str, dependency: Any) -> None:
    if dependency is not None:
        return
    raise RuntimeError(f"Missing optional dependency '{name}'. Install it from requirements.txt before using this mode.")


def build_rstr(rng: random.Random) -> Any:
    try:
        module = importlib.import_module("rstr")
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing optional dependency 'rstr'. Install it from requirements.txt before using regex mode.") from exc

    generator_class = getattr(module, "Rstr", None)
    if generator_class is None:
        raise RuntimeError("Installed 'rstr' package does not expose the expected Rstr class.")
    return generator_class(rng)


def resolve_string_length(args: argparse.Namespace, rng: random.Random) -> int:
    if args.length is not None:
        return args.length
    return rng.randint(args.min_length, args.max_length)


def build_string_pool(args: argparse.Namespace) -> str:
    pool = "".join(character for character in args.alphabet if character not in set(args.exclude))
    if not pool:
        raise RuntimeError("String alphabet is empty after applying exclusions.")
    return pool


def generate_string(args: argparse.Namespace, rng: random.Random) -> str:
    if args.regex:
        return build_rstr(rng).xeger(args.regex)

    length = resolve_string_length(args, rng)
    if length < len(args.include):
        raise RuntimeError("String length is too short for the required included characters.")

    pool = build_string_pool(args)
    base_characters = list(args.include)
    missing = length - len(base_characters)
    base_characters.extend(rng.choice(pool) for _ in range(missing))
    rng.shuffle(base_characters)
    return "".join(base_characters)


def generate_integer(args: argparse.Namespace, rng: random.Random) -> int:
    minimum = int(args.min_value)
    maximum = int(args.max_value)
    if minimum > maximum:
        raise RuntimeError("Integer minimum cannot be greater than maximum.")
    return rng.randint(minimum, maximum)


def generate_float(args: argparse.Namespace, rng: random.Random) -> float:
    value = rng.uniform(args.min_value, args.max_value)
    return round(value, args.precision)


def generate_boolean(args: argparse.Namespace, rng: random.Random) -> bool:
    return rng.random() < args.true_ratio


def generate_choice(args: argparse.Namespace, rng: random.Random) -> str:
    items = list(args.items)
    return rng.choice(items)


def generate_range_values(args: argparse.Namespace, rng: random.Random) -> list[int]:
    values = list(range(args.start, args.stop, args.step))
    if args.shuffle:
        rng.shuffle(values)
    return values[: args.count]


def build_faker(args: argparse.Namespace) -> Any:
    ensure_dependency("Faker", Faker)
    fake = Faker(args.locale)
    if args.seed is not None:
        fake.seed_instance(args.seed)
    return fake.unique if args.unique else fake


def generate_faker_value(args: argparse.Namespace, fake_source: Any) -> Any:
    provider = getattr(fake_source, args.provider, None)
    if provider is None or not callable(provider):
        raise RuntimeError(f"Unknown Faker provider '{args.provider}' for locale '{args.locale}'.")
    try:
        return provider(*args.provider_args, **args.provider_kwargs)
    except TypeError as exc:
        raise RuntimeError(f"Faker provider '{args.provider}' rejected the supplied args/kwargs: {exc}") from exc


def generate_unique_values(generator: Callable[[], Any], count: int) -> list[Any]:
    values: list[Any] = []
    seen: set[str] = set()
    max_attempts = count * 50

    for _ in range(max_attempts):
        if len(values) == count:
            return values
        candidate = generator()
        key = json.dumps(candidate, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        values.append(candidate)

    raise RuntimeError("Could not generate enough unique values with the provided constraints.")


def generate_counted_values(generator: Callable[[], Any], count: int, unique: bool) -> list[Any]:
    if unique:
        return generate_unique_values(generator, count)
    return [generator() for _ in range(count)]


def generate_faker_values(args: argparse.Namespace, fake_source: Any) -> list[Any]:
    values = [generate_faker_value(args, fake_source) for _ in range(args.count)]
    if args.unique and hasattr(fake_source, "clear"):
        fake_source.clear()
    return values


def generate_values(args: argparse.Namespace) -> list[Any]:
    rng = build_rng(args.seed)

    scalar_generators: dict[str, Callable[[], Any]] = {
        "string": lambda: generate_string(args, rng),
        "integer": lambda: generate_integer(args, rng),
        "float": lambda: generate_float(args, rng),
        "boolean": lambda: generate_boolean(args, rng),
    }
    scalar_generator = scalar_generators.get(args.kind)
    if scalar_generator is not None:
        return generate_counted_values(scalar_generator, args.count, args.unique)

    if args.kind == "choice":
        items = list(args.items)
        if args.unique:
            if args.count > len(items):
                raise RuntimeError("Unique choice generation cannot return more values than provided items.")
            return rng.sample(items, args.count)
        return generate_counted_values(lambda: generate_choice(args, rng), args.count, unique=False)

    if args.kind == "range":
        return generate_range_values(args, rng)

    fake_source = build_faker(args)
    return generate_faker_values(args, fake_source)


def format_plain_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def emit_plain(values: list[Any]) -> None:
    print("\n".join(format_plain_value(value) for value in values))


def emit_json(args: argparse.Namespace, values: list[Any]) -> None:
    payload = {
        "kind": args.kind,
        "count": len(values),
        "seed": args.seed,
        "values": values,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    validate_args(args, parser)

    try:
        values = generate_values(args)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.output == "json":
        emit_json(args, values)
        return 0

    emit_plain(values)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Callable

NAMESPACE_ALIASES = {
    "dns": uuid.NAMESPACE_DNS,
    "url": uuid.NAMESPACE_URL,
    "oid": uuid.NAMESPACE_OID,
    "x500": uuid.NAMESPACE_X500,
}

SUPPORTED_VERSIONS = ["1", "3", "4", "5"]
for candidate in ("6", "7"):
    if hasattr(uuid, f"uuid{candidate}"):
        SUPPORTED_VERSIONS.append(candidate)


def normalize_version(value: str) -> str:
    normalized = value.strip().lower()
    if normalized.startswith("uuid"):
        normalized = normalized[4:]
    if normalized not in SUPPORTED_VERSIONS:
        supported = ", ".join(f"UUIDv{item}" for item in SUPPORTED_VERSIONS)
        raise argparse.ArgumentTypeError(f"Unsupported UUID version '{value}'. Choose from: {supported}.")
    return normalized


def parse_positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Count must be an integer.") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("Count must be at least 1.")
    return parsed


def parse_namespace(value: str) -> uuid.UUID:
    normalized = value.strip().lower()
    if normalized in NAMESPACE_ALIASES:
        return NAMESPACE_ALIASES[normalized]
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Namespace must be dns, url, oid, x500, or a valid UUID string."
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate UUID values with UUIDv4 as the default and batch output enabled by default."
    )
    parser.add_argument(
        "--version",
        default="4",
        type=normalize_version,
        help="UUID version to generate. Accepts 4 or UUID4 style values. Default: 4.",
    )
    parser.add_argument(
        "--count",
        default=20,
        type=parse_positive_int,
        help="Number of UUIDs to generate. Default: 20.",
    )
    parser.add_argument(
        "--namespace",
        type=parse_namespace,
        help="Namespace for UUIDv3/UUIDv5. Use dns, url, oid, x500, or a UUID string.",
    )
    parser.add_argument(
        "--name",
        help="Name value for UUIDv3/UUIDv5 deterministic generation. Use {index} for batches.",
    )
    parser.add_argument(
        "--output",
        choices=("plain", "json"),
        default="plain",
        help="Output format. Default: plain.",
    )
    parser.add_argument(
        "--uppercase",
        action="store_true",
        help="Output uppercase UUID strings.",
    )
    return parser


def require_namespace_inputs(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.version in {"3", "5"}:
        if args.namespace is None or args.name is None:
            parser.error("UUIDv3 and UUIDv5 require both --namespace and --name.")
        return
    if args.namespace is not None or args.name is not None:
        parser.error("--namespace and --name can only be used with UUIDv3 or UUIDv5.")


def build_generator(version: str) -> Callable[..., uuid.UUID]:
    generator = getattr(uuid, f"uuid{version}", None)
    if generator is None:
        raise ValueError(f"UUIDv{version} is not supported by this Python runtime.")
    return generator


def build_name_value(template: str, index: int) -> str:
    return template.replace("{index}", str(index))


def generate_values(args: argparse.Namespace) -> list[str]:
    generator = build_generator(args.version)
    values: list[str] = []

    for index in range(1, args.count + 1):
        if args.version in {"3", "5"}:
            generated = generator(args.namespace, build_name_value(args.name, index))
        else:
            generated = generator()
        value = str(generated)
        values.append(value.upper() if args.uppercase else value)

    return values


def emit_plain(values: list[str]) -> None:
    print("\n".join(values))


def emit_json(args: argparse.Namespace, values: list[str]) -> None:
    payload = {
        "version": f"UUIDv{args.version}",
        "count": len(values),
        "uuids": values,
    }
    if args.version in {"3", "5"}:
        payload["namespace"] = str(args.namespace)
        payload["name_template"] = args.name
    print(json.dumps(payload, indent=2))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    require_namespace_inputs(args, parser)

    try:
        values = generate_values(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.output == "json":
        emit_json(args, values)
        return 0

    emit_plain(values)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

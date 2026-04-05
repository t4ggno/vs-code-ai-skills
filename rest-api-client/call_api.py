from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_BODY_CHARS = 8000
DEFAULT_TOKEN_PATHS = (
    "access_token",
    "accessToken",
    "token",
    "data.access_token",
    "data.accessToken",
    "data.token",
)
PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-api-key",
    "x-auth-token",
}


def load_local_env() -> None:
    env_paths = [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]
    seen: set[Path] = set()
    for env_path in env_paths:
        if not env_path.exists() or env_path in seen:
            continue
        seen.add(env_path)
        load_dotenv(env_path, override=False)


def parse_header_items(items: list[str] | None, label: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in items or []:
        if ":" not in item:
            raise ValueError(f"Invalid {label} '{item}'. Use 'Name: Value'.")
        name, value = item.split(":", 1)
        headers[name.strip()] = value.strip()
    return headers


def parse_query_items(items: list[str] | None) -> dict[str, str]:
    query: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"Invalid query item '{item}'. Use 'name=value'.")
        name, value = item.split("=", 1)
        query[name.strip()] = value.strip()
    return query


def render_template(template: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key.lower().startswith("env:"):
            env_name = key[4:].strip()
            env_value = os.environ.get(env_name)
            if env_value is None:
                raise RuntimeError(f"Missing environment variable '{env_name}' for template rendering.")
            return env_value
        value = context.get(key)
        if value is None:
            raise RuntimeError(f"Missing template value '{key}'.")
        return str(value)

    return PLACEHOLDER_PATTERN.sub(replace, template)


def parse_json_argument(raw_value: str, context: dict[str, Any]) -> Any:
    rendered = render_template(raw_value, context)
    try:
        return json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON payload: {exc.msg}.") from exc


def resolve_seed_credentials(args: argparse.Namespace) -> tuple[str, str]:
    username = args.seed_username
    password = args.seed_password

    if username is None and args.seed_username_env:
        username = os.environ.get(args.seed_username_env)
    if password is None and args.seed_password_env:
        password = os.environ.get(args.seed_password_env)

    if not username or not password:
        raise RuntimeError(
            "Seed login requires both a username and password. Provide them directly or via --seed-username-env/--seed-password-env."
        )
    return username, password


def build_template_context(args: argparse.Namespace, token: str | None = None) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if args.seed_username is not None:
        context["seed_username"] = args.seed_username
    if args.seed_password is not None:
        context["seed_password"] = args.seed_password
    if token is not None:
        context["token"] = token
    return context


def maybe_promote_seed_context(args: argparse.Namespace) -> None:
    if args.auth_mode != "seed-login":
        return
    username, password = resolve_seed_credentials(args)
    args.seed_username = username
    args.seed_password = password


def extract_token(payload: Any, explicit_path: str | None) -> str | None:
    candidate_paths = (explicit_path,) if explicit_path else DEFAULT_TOKEN_PATHS
    for path in candidate_paths:
        if path is None:
            continue
        current = payload
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if isinstance(current, str) and current.strip():
            return current.strip()
    return None


def build_login_payload(args: argparse.Namespace, context: dict[str, Any]) -> dict[str, Any]:
    headers = parse_header_items(args.login_header, "login header")
    if args.login_content_type == "json":
        headers.setdefault("Content-Type", "application/json")
        payload = parse_json_argument(args.login_body, context) if args.login_body else {
            args.username_field: context["seed_username"],
            args.password_field: context["seed_password"],
        }
        return {"headers": headers, "json": payload}

    if args.login_content_type == "form":
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        payload = parse_json_argument(args.login_body, context) if args.login_body else {
            args.username_field: context["seed_username"],
            args.password_field: context["seed_password"],
        }
        if not isinstance(payload, dict):
            raise RuntimeError("Form login bodies must render to a JSON object.")
        return {"headers": headers, "data": payload}

    if not args.login_body:
        raise RuntimeError("Raw login requests require --login-body.")
    return {"headers": headers, "data": render_template(args.login_body, context)}


def authenticate_session(session: requests.Session, args: argparse.Namespace) -> dict[str, Any]:
    if args.auth_mode == "none":
        return {"used": False, "token": None, "cookie_count": 0}

    if args.auth_mode == "bearer-env":
        if not args.auth_env_var:
            raise RuntimeError("--auth-env-var is required when --auth-mode bearer-env is used.")
        token = os.environ.get(args.auth_env_var)
        if not token:
            raise RuntimeError(f"Environment variable '{args.auth_env_var}' is missing or empty.")
        return {"used": True, "token": token, "cookie_count": 0}

    if not args.login_url:
        raise RuntimeError("--login-url is required when --auth-mode seed-login is used.")

    context = build_template_context(args)
    login_request = build_login_payload(args, context)
    response = session.request(
        method=args.login_method,
        url=args.login_url,
        timeout=args.timeout,
        verify=not args.insecure,
        **login_request,
    )
    response.raise_for_status()

    token: str | None = None
    try:
        token = extract_token(response.json(), args.token_json_path)
    except ValueError:
        token = None

    if args.token_json_path and not token:
        raise RuntimeError(f"Could not find token at JSON path '{args.token_json_path}'.")

    return {
        "used": True,
        "token": token,
        "cookie_count": len(session.cookies),
    }


def build_request_payload(args: argparse.Namespace, token: str | None) -> dict[str, Any]:
    context = build_template_context(args, token)
    headers = {
        key: render_template(value, context)
        for key, value in parse_header_items(args.header, "header").items()
    }
    query = {
        key: render_template(value, context)
        for key, value in parse_query_items(args.query).items()
    }

    if token:
        headers.setdefault(args.token_header, f"{args.token_prefix} {token}".strip())

    payload: dict[str, Any] = {
        "headers": headers,
        "params": query,
        "timeout": args.timeout,
        "verify": not args.insecure,
    }

    if args.json_body:
        payload["json"] = parse_json_argument(args.json_body, context)
    elif args.body:
        payload["data"] = render_template(args.body, context)

    return payload


def redact_headers(headers: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in headers.items():
        redacted[key] = "<redacted>" if key.lower() in SENSITIVE_HEADERS else value
    return redacted


def truncate_text(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    return f"{value[:max_chars]}\n… [truncated {len(value) - max_chars} chars]", True


def serialize_response_body(response: requests.Response, max_chars: int) -> dict[str, Any]:
    try:
        parsed = response.json()
    except ValueError:
        preview, truncated = truncate_text(response.text, max_chars)
        return {
            "body_format": "text",
            "body": preview,
            "body_truncated": truncated,
        }

    rendered = json.dumps(parsed, indent=2, ensure_ascii=False)
    preview, truncated = truncate_text(rendered, max_chars)
    if truncated:
        return {
            "body_format": "json",
            "body": preview,
            "body_truncated": True,
        }
    return {
        "body_format": "json",
        "body": parsed,
        "body_truncated": False,
    }


def execute_request(session: requests.Session, args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], requests.Response]:
    auth_result = authenticate_session(session, args)
    request_payload = build_request_payload(args, auth_result["token"])
    response = session.request(args.method.upper(), args.url, **request_payload)
    return auth_result, request_payload, response


def build_output_payload(
    args: argparse.Namespace,
    response: requests.Response,
    request_payload: dict[str, Any],
    auth_result: dict[str, Any],
    body_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "request": {
            "method": args.method.upper(),
            "url": response.url,
            "auth_mode": args.auth_mode,
            "headers": redact_headers(request_payload["headers"]),
            "query": request_payload["params"],
            "json_body_supplied": "json" in request_payload,
            "raw_body_supplied": "data" in request_payload,
        },
        "login": {
            "used": auth_result["used"],
            "token_found": bool(auth_result["token"]),
            "cookie_count": auth_result["cookie_count"],
        },
        "response": {
            "status": response.status_code,
            "ok": response.ok,
            "headers": redact_headers(dict(response.headers)),
            "content_type": response.headers.get("Content-Type", ""),
            **body_payload,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call an HTTP API with optional seed-user authentication.")
    parser.add_argument("method", help="HTTP method, for example GET or POST.")
    parser.add_argument("url", help="Target API URL.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Request timeout in seconds. Default: {DEFAULT_TIMEOUT}.")
    parser.add_argument("--header", action="append", help="Request header in 'Name: Value' format.")
    parser.add_argument("--query", action="append", help="Query parameter in 'name=value' format.")
    parser.add_argument("--body", help="Raw request body.")
    parser.add_argument("--json-body", help="JSON request body string.")
    parser.add_argument("--output", choices=("json", "text"), default="json", help="Output format. Default: json.")
    parser.add_argument("--max-body-chars", type=int, default=DEFAULT_MAX_BODY_CHARS, help=f"Maximum response body characters to print. Default: {DEFAULT_MAX_BODY_CHARS}.")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification for local/self-signed development endpoints.")
    parser.add_argument("--auth-mode", choices=("none", "bearer-env", "seed-login"), default="none", help="Authentication strategy. Default: none.")
    parser.add_argument("--auth-env-var", help="Environment variable containing a bearer token for bearer-env mode.")
    parser.add_argument("--token-header", default="Authorization", help="Header name used when injecting a token. Default: Authorization.")
    parser.add_argument("--token-prefix", default="Bearer", help="Token prefix used when injecting a token. Default: Bearer.")
    parser.add_argument("--login-url", help="Authentication or token-exchange endpoint for seed-login mode.")
    parser.add_argument("--login-method", default="POST", help="HTTP method for the login request. Default: POST.")
    parser.add_argument("--login-content-type", choices=("json", "form", "raw"), default="json", help="Body format for the login request. Default: json.")
    parser.add_argument("--login-body", help="Template body for the login request. Supports placeholders such as {{seed_username}} and {{env:VAR}}.")
    parser.add_argument("--login-header", action="append", help="Login request header in 'Name: Value' format.")
    parser.add_argument("--seed-username", help="Seed/test username used during login or token exchange.")
    parser.add_argument("--seed-password", help="Seed/test password used during login or token exchange.")
    parser.add_argument("--seed-username-env", help="Environment variable containing the seed username.")
    parser.add_argument("--seed-password-env", help="Environment variable containing the seed password.")
    parser.add_argument("--username-field", default="username", help="Default username field name for generated login bodies. Default: username.")
    parser.add_argument("--password-field", default="password", help="Default password field name for generated login bodies. Default: password.")
    parser.add_argument("--token-json-path", help="Dot-path used to extract the token from the login response JSON.")
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.body and args.json_body:
        parser.error("Use either --body or --json-body, not both.")
    if args.max_body_chars < 1:
        parser.error("--max-body-chars must be at least 1.")


def main() -> int:
    load_local_env()
    parser = build_parser()
    args = parser.parse_args()
    validate_args(args, parser)
    maybe_promote_seed_context(args)

    session = requests.Session()

    try:
        auth_result, request_payload, response = execute_request(session, args)
    except (RuntimeError, ValueError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    body_payload = serialize_response_body(response, args.max_body_chars)
    if args.output == "text":
        print(body_payload["body"])
        return 0 if response.ok else 1

    output = build_output_payload(args, response, request_payload, auth_result, body_payload)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if response.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from conftest import load_module

MODULE = load_module("rest-api-client/call_api.py", "rest_api_client")
SCRIPT_PATH = Path(__file__).with_name("call_api.py")


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        ok: bool = True,
        url: str = "https://api.example.com/items",
        headers: dict[str, str] | None = None,
        json_payload: object | None = None,
        text_payload: str = "",
    ) -> None:
        self.status_code = status_code
        self.ok = ok
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self._json_payload = json_payload
        self.text = text_payload

    def json(self) -> object:
        if self._json_payload is None:
            raise ValueError("not json")
        return self._json_payload

    def raise_for_status(self) -> None:
        if self.ok:
            return
        raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, login_response: FakeResponse | None = None, api_response: FakeResponse | None = None) -> None:
        self.login_response = login_response
        self.api_response = api_response
        self.calls: list[tuple[str, str, dict[str, object]]] = []
        self.cookies = ["session-cookie"]

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        if self.login_response is not None and url == "https://login.example.com":
            return self.login_response
        if self.api_response is None:
            raise AssertionError("API response was not configured")
        return self.api_response


def test_parse_helpers_and_template_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    assert MODULE.parse_header_items(["Accept: application/json"], "header") == {"Accept": "application/json"}
    assert MODULE.parse_query_items(["page=2"]) == {"page": "2"}

    with pytest.raises(ValueError):
        MODULE.parse_header_items(["broken"], "header")

    with pytest.raises(ValueError):
        MODULE.parse_query_items(["broken"])

    monkeypatch.setenv("API_TOKEN", "secret-token")
    rendered = MODULE.render_template("Bearer {{env:API_TOKEN}}/{{name}}", {"name": "demo"})
    assert rendered == "Bearer secret-token/demo"

    with pytest.raises(RuntimeError):
        MODULE.render_template("{{missing}}", {})


def test_parse_json_argument_and_seed_context_promotion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_USER", "alice")
    monkeypatch.setenv("LOGIN_PASS", "wonderland")

    parsed = MODULE.parse_json_argument('{"user": "{{seed_username}}"}', {"seed_username": "alice"})
    assert parsed == {"user": "alice"}

    with pytest.raises(RuntimeError):
        MODULE.parse_json_argument("{", {})

    args = SimpleNamespace(
        auth_mode="seed-login",
        seed_username=None,
        seed_password=None,
        seed_username_env="LOGIN_USER",
        seed_password_env="LOGIN_PASS",
    )
    MODULE.maybe_promote_seed_context(args)
    assert args.seed_username == "alice"
    assert args.seed_password == "wonderland"


def test_resolve_seed_credentials_and_template_context_error_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(RuntimeError):
        MODULE.resolve_seed_credentials(
            SimpleNamespace(
                seed_username=None,
                seed_password=None,
                seed_username_env=None,
                seed_password_env=None,
            )
        )

    monkeypatch.delenv("MISSING_TEMPLATE_ENV", raising=False)
    with pytest.raises(RuntimeError):
        MODULE.render_template("Bearer {{env:MISSING_TEMPLATE_ENV}}", {})

    context = MODULE.build_template_context(
        SimpleNamespace(seed_username="alice", seed_password="wonderland"),
        "token-123",
    )
    assert context == {
        "seed_username": "alice",
        "seed_password": "wonderland",
        "token": "token-123",
    }


def test_extract_token_and_build_login_payloads() -> None:
    payload = {"data": {"access_token": "abc"}, "token": "fallback"}
    assert MODULE.extract_token(payload, "data.access_token") == "abc"
    assert MODULE.extract_token(payload, None) == "fallback"

    original_paths = MODULE.DEFAULT_TOKEN_PATHS
    MODULE.DEFAULT_TOKEN_PATHS = (None, "token")
    try:
        assert MODULE.extract_token(payload, None) == "fallback"
    finally:
        MODULE.DEFAULT_TOKEN_PATHS = original_paths

    json_args = SimpleNamespace(
        login_header=["Accept: application/json"],
        login_content_type="json",
        login_body=None,
        username_field="email",
        password_field="password",
    )
    assert MODULE.build_login_payload(json_args, {"seed_username": "user", "seed_password": "pass"}) == {
        "headers": {"Accept": "application/json", "Content-Type": "application/json"},
        "json": {"email": "user", "password": "pass"},
    }

    form_args = SimpleNamespace(
        login_header=None,
        login_content_type="form",
        login_body='{"username": "{{seed_username}}"}',
        username_field="username",
        password_field="password",
    )
    assert MODULE.build_login_payload(form_args, {"seed_username": "user", "seed_password": "pass"}) == {
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        "data": {"username": "user"},
    }

    form_default_args = SimpleNamespace(
        login_header=None,
        login_content_type="form",
        login_body=None,
        username_field="username",
        password_field="password",
    )
    assert MODULE.build_login_payload(form_default_args, {"seed_username": "user", "seed_password": "pass"}) == {
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        "data": {"username": "user", "password": "pass"},
    }

    raw_args = SimpleNamespace(
        login_header=["X-Test: 1"],
        login_content_type="raw",
        login_body="username={{seed_username}}",
        username_field="username",
        password_field="password",
    )
    assert MODULE.build_login_payload(raw_args, {"seed_username": "user", "seed_password": "pass"}) == {
        "headers": {"X-Test": "1"},
        "data": "username=user",
    }


def test_build_login_payload_rejects_invalid_form_and_raw_inputs() -> None:
    with pytest.raises(RuntimeError):
        MODULE.build_login_payload(
            SimpleNamespace(
                login_header=None,
                login_content_type="form",
                login_body='["not-a-dict"]',
                username_field="username",
                password_field="password",
            ),
            {"seed_username": "user", "seed_password": "pass"},
        )

    with pytest.raises(RuntimeError):
        MODULE.build_login_payload(
            SimpleNamespace(
                login_header=None,
                login_content_type="raw",
                login_body=None,
                username_field="username",
                password_field="password",
            ),
            {"seed_username": "user", "seed_password": "pass"},
        )


def test_authenticate_session_supports_none_bearer_and_seed_login(monkeypatch: pytest.MonkeyPatch) -> None:
    none_args = SimpleNamespace(auth_mode="none")
    assert MODULE.authenticate_session(FakeSession(), none_args) == {"used": False, "token": None, "cookie_count": 0}

    bearer_args = SimpleNamespace(auth_mode="bearer-env", auth_env_var="API_TOKEN")
    monkeypatch.setenv("API_TOKEN", "token-123")
    assert MODULE.authenticate_session(FakeSession(), bearer_args) == {"used": True, "token": "token-123", "cookie_count": 0}

    missing_bearer_args = SimpleNamespace(auth_mode="bearer-env", auth_env_var="MISSING_TOKEN")
    with pytest.raises(RuntimeError):
        MODULE.authenticate_session(FakeSession(), missing_bearer_args)

    login_response = FakeResponse(json_payload={"token": "login-token"})
    session = FakeSession(login_response=login_response, api_response=FakeResponse(json_payload={"ok": True}))
    login_args = SimpleNamespace(
        auth_mode="seed-login",
        login_url="https://login.example.com",
        login_method="POST",
        timeout=10,
        insecure=False,
        token_json_path="token",
        login_header=None,
        login_content_type="json",
        login_body=None,
        username_field="username",
        password_field="password",
        seed_username="alice",
        seed_password="wonderland",
        seed_username_env=None,
        seed_password_env=None,
    )

    auth_result = MODULE.authenticate_session(session, login_args)
    assert auth_result == {"used": True, "token": "login-token", "cookie_count": 1}
    assert session.calls[0][0] == "POST"


def test_authenticate_session_reports_missing_configuration_and_token_errors() -> None:
    with pytest.raises(RuntimeError):
        MODULE.authenticate_session(FakeSession(), SimpleNamespace(auth_mode="bearer-env", auth_env_var=None))

    with pytest.raises(RuntimeError):
        MODULE.authenticate_session(FakeSession(), SimpleNamespace(auth_mode="seed-login", login_url=None))

    raw_args = SimpleNamespace(
        auth_mode="seed-login",
        login_url="https://login.example.com",
        login_method="POST",
        timeout=10,
        insecure=False,
        token_json_path=None,
        login_header=None,
        login_content_type="raw",
        login_body="seed={{seed_username}}",
        username_field="username",
        password_field="password",
        seed_username="alice",
        seed_password="wonderland",
        seed_username_env=None,
        seed_password_env=None,
    )
    session = FakeSession(login_response=FakeResponse(json_payload=None, text_payload="plain"), api_response=FakeResponse(json_payload={"ok": True}))
    assert MODULE.authenticate_session(session, raw_args) == {"used": True, "token": None, "cookie_count": 1}

    missing_token_args = SimpleNamespace(**{**raw_args.__dict__, "token_json_path": "token"})
    with pytest.raises(RuntimeError):
        MODULE.authenticate_session(
            FakeSession(login_response=FakeResponse(json_payload={}, text_payload="{}"), api_response=FakeResponse(json_payload={"ok": True})),
            missing_token_args,
        )


def test_build_request_payload_and_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUSTOM_VALUE", "from-env")
    args = SimpleNamespace(
        seed_username="alice",
        seed_password="wonderland",
        header=["Authorization: {{token}}", "X-Extra: {{env:CUSTOM_VALUE}}"],
        query=["page=1", "owner={{seed_username}}"],
        timeout=12,
        insecure=True,
        json_body='{"token": "{{token}}", "owner": "{{seed_username}}"}',
        body=None,
        token_header="Authorization",
        token_prefix="Bearer",
    )

    payload = MODULE.build_request_payload(args, "abc123")

    assert payload["headers"] == {"Authorization": "abc123", "X-Extra": "from-env"}
    assert payload["params"] == {"page": "1", "owner": "alice"}
    assert payload["verify"] is False
    assert payload["json"] == {"token": "abc123", "owner": "alice"}
    assert MODULE.redact_headers({"Authorization": "secret", "Accept": "json"}) == {
        "Authorization": "<redacted>",
        "Accept": "json",
    }


def test_build_request_payload_supports_raw_body_and_default_token_header() -> None:
    args = SimpleNamespace(
        seed_username="alice",
        seed_password="wonderland",
        header=None,
        query=None,
        timeout=5,
        insecure=False,
        json_body=None,
        body="owner={{seed_username}}",
        token_header="Authorization",
        token_prefix="Token",
    )

    payload = MODULE.build_request_payload(args, "abc123")

    assert payload == {
        "headers": {"Authorization": "Token abc123"},
        "params": {},
        "timeout": 5,
        "verify": True,
        "data": "owner=alice",
    }


def test_serialize_response_body_handles_json_text_and_truncation() -> None:
    json_response = FakeResponse(json_payload={"alpha": 1}, text_payload="ignored")
    assert MODULE.serialize_response_body(json_response, 100) == {
        "body_format": "json",
        "body": {"alpha": 1},
        "body_truncated": False,
    }

    text_response = FakeResponse(headers={"Content-Type": "text/plain"}, json_payload=None, text_payload="x" * 20)
    serialized = MODULE.serialize_response_body(text_response, 5)
    assert serialized["body_format"] == "text"
    assert serialized["body_truncated"] is True
    assert "truncated" in serialized["body"]


def test_serialize_response_body_truncates_json_payloads() -> None:
    response = FakeResponse(json_payload={"value": "x" * 50}, text_payload="ignored")

    serialized = MODULE.serialize_response_body(response, 10)

    assert serialized["body_format"] == "json"
    assert serialized["body_truncated"] is True
    assert "truncated" in serialized["body"]


def test_main_outputs_redacted_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api_response = FakeResponse(
        json_payload={"items": [1, 2]},
        headers={"Content-Type": "application/json", "Set-Cookie": "secret-cookie"},
    )
    fake_session = FakeSession(api_response=api_response)
    monkeypatch.setattr(MODULE.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "call_api.py",
            "GET",
            "https://api.example.com/items",
            "--header",
            "Authorization: secret-token",
            "--output",
            "json",
        ],
    )

    assert MODULE.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["request"]["headers"]["Authorization"] == "<redacted>"
    assert payload["response"]["headers"]["Set-Cookie"] == "<redacted>"
    assert payload["response"]["body"] == {"items": [1, 2]}


def test_main_returns_error_for_request_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FailingSession:
        def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
            raise requests.RequestException("boom")

    monkeypatch.setattr(MODULE.requests, "Session", lambda: FailingSession())
    monkeypatch.setattr(sys, "argv", ["call_api.py", "GET", "https://api.example.com/items"])

    assert MODULE.main() == 1
    assert "Error: boom" in capsys.readouterr().err


def test_main_outputs_text_and_returns_response_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api_response = FakeResponse(
        status_code=404,
        ok=False,
        headers={"Content-Type": "text/plain"},
        json_payload=None,
        text_payload="not found",
    )
    monkeypatch.setattr(MODULE.requests, "Session", lambda: FakeSession(api_response=api_response))
    monkeypatch.setattr(
        sys,
        "argv",
        ["call_api.py", "GET", "https://api.example.com/items", "--output", "text"],
    )

    assert MODULE.main() == 1
    assert capsys.readouterr().out.strip() == "not found"


def test_main_returns_error_for_missing_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(MODULE.requests, "Session", lambda: FakeSession(api_response=FakeResponse(json_payload={"ok": True})))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "call_api.py",
            "GET",
            "https://api.example.com/items",
            "--auth-mode",
            "bearer-env",
            "--auth-env-var",
            "MISSING_API_TOKEN",
        ],
    )

    assert MODULE.main() == 1
    assert "Environment variable 'MISSING_API_TOKEN' is missing or empty." in capsys.readouterr().err


def test_validate_args_and_script_entrypoint_cover_cli_guards(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = MODULE.build_parser()

    with pytest.raises(SystemExit):
        MODULE.validate_args(SimpleNamespace(body="raw", json_body='{"x":1}', max_body_chars=10), parser)

    with pytest.raises(SystemExit):
        MODULE.validate_args(SimpleNamespace(body=None, json_body=None, max_body_chars=0), parser)

    monkeypatch.setattr(MODULE.requests, "Session", lambda: FakeSession(api_response=FakeResponse(json_payload={"ok": True})))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), "GET", "https://api.example.com/items"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 0
    assert json.loads(capsys.readouterr().out)["response"]["body"] == {"ok": True}

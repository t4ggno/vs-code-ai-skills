from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import load_module

MODULE = load_module("browser-scraper/scrape.py", "browser_scraper")
SCRIPT_PATH = Path(__file__).with_name("scrape.py")


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page = page
        self.selector = selector
        self.first = self

    def fill(self, value: str) -> None:
        self.page.fills.append((self.selector, value))

    def click(self) -> None:
        self.page.clicks.append(self.selector)

    def inner_text(self, timeout: int | None = None) -> str:
        return self.page.inner_text_value

    def screenshot(self, **kwargs: object) -> None:
        self.page.element_screenshots.append((self.selector, kwargs))


class FakePage:
    def __init__(self) -> None:
        self.url = "about:blank"
        self.title_value = "Example Title"
        self.inner_text_value = "Visible text"
        self.links = []
        self.style_data = {"themeColorMeta": "#fff"}
        self.fills: list[tuple[str, str]] = []
        self.clicks: list[str] = []
        self.wait_calls: list[tuple[str, int]] = []
        self.waited_selectors: list[tuple[str, str | None, int]] = []
        self.element_screenshots: list[tuple[str, object]] = []
        self.page_screenshots: list[dict[str, object]] = []
        self.raise_on_networkidle = False
        self.fail_visible_selector = False
        self.closed = False

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.url = url

    def wait_for_load_state(self, state: str, timeout: int) -> None:
        self.wait_calls.append((state, timeout))
        if state == "networkidle" and self.raise_on_networkidle:
            raise RuntimeError("network still busy")

    def wait_for_selector(self, selector: str, state: str | None = None, timeout: int = 0) -> None:
        self.waited_selectors.append((selector, state, timeout))
        if self.fail_visible_selector and state == "visible":
            raise RuntimeError("missing selector")

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def eval_on_selector_all(self, selector: str, script: str) -> list[dict[str, str]]:
        return self.links

    def evaluate(self, script: str) -> dict[str, object]:
        return self.style_data

    def screenshot(self, **kwargs: object) -> None:
        self.page_screenshots.append(kwargs)

    def title(self) -> str:
        return self.title_value

    def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages
        self.saved_storage_paths: list[str] = []
        self.closed = False

    def new_page(self) -> FakePage:
        return self.pages.pop(0)

    def storage_state(self, path: str) -> None:
        self.saved_storage_paths.append(path)

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def make_args(**overrides: object) -> SimpleNamespace:
    base = {
        "viewport_width": 1440,
        "viewport_height": 900,
        "device_scale_factor": 1.0,
        "color_scheme": "default",
        "reduced_motion": "default",
        "screenshot_style": None,
        "hide_selector": None,
        "max_chars": 100,
        "max_links": 5,
        "user_data_dir": None,
        "storage_state": None,
        "screenshot_mode": "viewport",
        "output": "json",
        "screenshot_path": None,
        "screenshot_quality": None,
        "screenshot_type": "png",
        "screenshot_selector": None,
        "browser": "chromium",
        "headed": False,
        "wait_for": None,
        "settle_ms": 0,
        "selector": "body",
        "timeout": 1000,
        "login_url": None,
        "seed_username": None,
        "seed_password": None,
        "seed_username_env": None,
        "seed_password_env": None,
        "login_username_selector": "#user",
        "login_password_selector": "#pass",
        "login_submit_selector": "#submit",
        "post_login_wait_for": None,
        "save_storage_state": None,
        "url": "https://example.com",
        "capture_style": False,
        "style_snapshot_path": None,
        "screenshot_scale": "device",
        "disable_animations": False,
        "screenshot_omit_background": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_helper_functions_cover_secrets_truncation_and_styles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_ENV", "from-env")
    assert MODULE.resolve_secret("direct", "SECRET_ENV") == "direct"
    assert MODULE.resolve_secret(None, "SECRET_ENV") == "from-env"
    assert MODULE.resolve_secret(None, None) is None

    assert MODULE.truncate_text("short", 10) == ("short", False)
    truncated, was_truncated = MODULE.truncate_text("abcdef", 3)
    assert was_truncated is True
    assert "truncated" in truncated
    assert MODULE.normalize_optional_mode("default") is None

    args = make_args(color_scheme="dark", reduced_motion="reduce", screenshot_style="body { color: red; }", hide_selector=[".ad", ".cookie"])
    assert MODULE.build_context_options(args) == {
        "viewport": {"width": 1440, "height": 900},
        "device_scale_factor": 1.0,
        "color_scheme": "dark",
        "reduced_motion": "reduce",
    }
    style = MODULE.build_screenshot_style(args)
    assert ".ad, .cookie" in style
    assert "color: red" in style


def test_load_local_env_and_playwright_runtime_helpers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_cwd = tmp_path / "cwd"
    fake_cwd.mkdir()
    (fake_cwd / ".env").write_text("LOCAL=1", encoding="utf-8")
    (tmp_path / ".env").write_text("ROOT=1", encoding="utf-8")
    script_dir = tmp_path / "browser-scraper"
    script_dir.mkdir()
    dotenv_calls: list[tuple[Path, bool]] = []

    monkeypatch.setattr(MODULE.Path, "cwd", lambda: fake_cwd)
    monkeypatch.setattr(MODULE, "__file__", str(script_dir / "scrape.py"))
    monkeypatch.setattr(MODULE, "load_dotenv", lambda path, override=False: dotenv_calls.append((Path(path), override)))

    MODULE.load_local_env()

    assert {path for path, _override in dotenv_calls} == {fake_cwd / ".env", tmp_path / ".env"}

    def raise_import_error(_name: str) -> object:
        raise ImportError("missing playwright")

    monkeypatch.setattr(MODULE.importlib, "import_module", raise_import_error)
    with pytest.raises(RuntimeError):
        MODULE.ensure_playwright_available()

    playwright_module = SimpleNamespace(Error=RuntimeError, sync_playwright=lambda: "sync-runtime")
    monkeypatch.setattr(MODULE.importlib, "import_module", lambda _name: playwright_module)

    error_type, sync_playwright = MODULE.load_playwright_runtime()

    assert error_type is RuntimeError
    assert sync_playwright() == "sync-runtime"


def test_validate_args_rejects_invalid_combinations() -> None:
    parser = MODULE.build_parser()

    with pytest.raises(SystemExit):
        MODULE.validate_args(make_args(max_chars=0), parser)

    with pytest.raises(SystemExit):
        MODULE.validate_args(make_args(max_links=-1), parser)

    with pytest.raises(SystemExit):
        MODULE.validate_args(make_args(user_data_dir="profile", storage_state="state.json"), parser)

    with pytest.raises(SystemExit):
        MODULE.validate_args(make_args(viewport_width=0), parser)

    with pytest.raises(SystemExit):
        MODULE.validate_args(make_args(device_scale_factor=0), parser)

    with pytest.raises(SystemExit):
        MODULE.validate_args(make_args(screenshot_mode="element", output="text"), parser)

    with pytest.raises(SystemExit):
        MODULE.validate_args(make_args(screenshot_quality=101, screenshot_type="jpeg"), parser)

    with pytest.raises(SystemExit):
        MODULE.validate_args(make_args(screenshot_quality=50, screenshot_type="png"), parser)

    with pytest.raises(SystemExit):
        MODULE.validate_args(make_args(screenshot_mode="viewport", screenshot_selector="#main"), parser)


def test_launch_browser_and_login_cover_remaining_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeBrowserInstance(FakeBrowser):
        def __init__(self) -> None:
            super().__init__()
            self.new_context_kwargs: dict[str, object] | None = None

        def new_context(self, **kwargs: object) -> str:
            self.new_context_kwargs = kwargs
            return "standard-context"

    class FakeBrowserType:
        def __init__(self) -> None:
            self.persistent_call: tuple[str, bool, dict[str, object]] | None = None
            self.browser = FakeBrowserInstance()

        def launch_persistent_context(self, user_data_dir: str, *, headless: bool, **kwargs: object) -> str:
            self.persistent_call = (user_data_dir, headless, kwargs)
            return "persistent-context"

        def launch(self, *, headless: bool) -> FakeBrowserInstance:
            assert headless is True
            return self.browser

    browser_type = FakeBrowserType()
    playwright = SimpleNamespace(chromium=browser_type)

    browser, context = MODULE.launch_browser(playwright, make_args(user_data_dir="profile", headed=True))
    assert browser is None
    assert context == "persistent-context"
    assert browser_type.persistent_call is not None
    assert browser_type.persistent_call[0] == "profile"
    assert browser_type.persistent_call[1] is False

    browser, context = MODULE.launch_browser(playwright, make_args(storage_state="state.json"))
    assert browser is browser_type.browser
    assert context == "standard-context"
    assert browser_type.browser.new_context_kwargs is not None
    assert browser_type.browser.new_context_kwargs["storage_state"] == "state.json"

    page = FakePage()
    page.fail_visible_selector = True
    with pytest.raises(RuntimeError):
        MODULE.fill_visible_field(page, "#missing", "alice", "username", 100)

    assert MODULE.perform_login(FakeContext([FakePage()]), make_args(login_url=None)) is False

    waited: list[bool] = []
    login_page = FakePage()
    login_context = FakeContext([login_page])
    monkeypatch.setattr(MODULE, "wait_for_page_ready", lambda _page, _args: waited.append(True))

    assert MODULE.perform_login(
        login_context,
        make_args(
            login_url="https://example.com/login",
            seed_username="alice",
            seed_password="wonderland",
            post_login_wait_for=None,
        ),
    ) is True
    assert waited == [True]


def test_wait_for_page_ready_handles_networkidle_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage()
    page.raise_on_networkidle = True
    slept: list[float] = []
    monkeypatch.setattr(MODULE.time, "sleep", lambda value: slept.append(value))

    MODULE.wait_for_page_ready(page, make_args(wait_for="#main", settle_ms=250, timeout=500))

    assert page.wait_calls == [("domcontentloaded", 500), ("networkidle", 500)]
    assert page.waited_selectors[-1] == ("#main", None, 500)
    assert slept == [0.25]


def test_collect_links_deduplicates_and_limits_results() -> None:
    page = FakePage()
    page.links = [
        {"text": "One", "href": "https://example.com/a"},
        {"text": "Dup", "href": "https://example.com/a"},
        {"text": "", "href": " "},
        {"text": "Two", "href": "https://example.com/b"},
    ]

    assert MODULE.collect_links(page, 1) == [{"text": "One", "href": "https://example.com/a"}]


def test_collect_links_skips_blank_and_duplicate_hrefs() -> None:
    page = FakePage()
    page.links = [
        {"text": "One", "href": "https://example.com/a"},
        {"text": "Dup", "href": "https://example.com/a"},
        {"text": "Blank", "href": "   "},
        {"text": "Two", "href": "https://example.com/b"},
    ]

    assert MODULE.collect_links(page, 5) == [
        {"text": "One", "href": "https://example.com/a"},
        {"text": "Two", "href": "https://example.com/b"},
    ]


def test_fill_visible_field_and_perform_login(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    page = FakePage()
    context = FakeContext([page])
    saved_paths: list[str] = []
    monkeypatch.setattr(MODULE, "save_storage_state", lambda _context, path: saved_paths.append(path))

    args = make_args(
        login_url="https://example.com/login",
        seed_username="alice",
        seed_password="wonderland",
        post_login_wait_for="#dashboard",
        save_storage_state=str(tmp_path / "state.json"),
    )

    assert MODULE.perform_login(context, args) is True
    assert page.fills == [("#user", "alice"), ("#pass", "wonderland")]
    assert page.clicks == ["#submit"]
    assert saved_paths == [str(tmp_path / "state.json")]
    assert page.closed is True

    with pytest.raises(RuntimeError):
        MODULE.perform_login(FakeContext([FakePage()]), make_args(login_url="https://example.com/login"))


def test_save_storage_state_collect_style_snapshot_and_save_json_file(tmp_path: Path) -> None:
    context = FakeContext([])
    state_path = tmp_path / "state" / "storage.json"

    MODULE.save_storage_state(context, str(state_path))

    assert context.saved_storage_paths == [str(state_path)]
    assert state_path.parent.exists()

    page = FakePage()
    assert MODULE.collect_style_snapshot(page) == page.style_data

    json_path = MODULE.save_json_file(str(tmp_path / "style" / "snapshot.json"), {"theme": "dark"})
    assert Path(json_path).read_text(encoding="utf-8") == '{\n  "theme": "dark"\n}'


def test_capture_screenshot_handles_element_and_full_page(tmp_path: Path) -> None:
    page = FakePage()
    element_args = make_args(
        screenshot_path=str(tmp_path / "element.png"),
        screenshot_mode="element",
        screenshot_selector="#card",
        screenshot_style="body { color: red; }",
        hide_selector=[".ad"],
    )

    element_result = MODULE.capture_screenshot(page, element_args)
    assert element_result == {
        "path": str(tmp_path / "element.png"),
        "mode": "element",
        "selector": "#card",
        "type": "png",
    }
    assert page.element_screenshots[0][0] == "#card"

    full_page_result = MODULE.capture_screenshot(
        page,
        make_args(screenshot_path=str(tmp_path / "page.png"), screenshot_mode="full-page"),
    )
    assert full_page_result == {
        "path": str(tmp_path / "page.png"),
        "mode": "full-page",
        "selector": None,
        "type": "png",
    }
    assert page.page_screenshots[-1]["fullPage"] is True


def test_capture_screenshot_supports_none_and_additional_options(tmp_path: Path) -> None:
    page = FakePage()

    assert MODULE.capture_screenshot(page, make_args()) is None

    viewport_result = MODULE.capture_screenshot(
        page,
        make_args(
            screenshot_path=str(tmp_path / "viewport.jpg"),
            screenshot_type="jpeg",
            screenshot_quality=80,
            screenshot_omit_background=True,
        ),
    )

    assert viewport_result == {
        "path": str(tmp_path / "viewport.jpg"),
        "mode": "viewport",
        "selector": None,
        "type": "jpeg",
    }
    assert page.page_screenshots[-1]["quality"] == 80
    assert page.page_screenshots[-1]["omitBackground"] is True


def test_scrape_page_collects_text_links_screenshot_and_style_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    page = FakePage()
    page.inner_text_value = "Visible text from page"
    page.links = [{"text": "Home", "href": "https://example.com/home"}]
    context = FakeContext([page])
    style_snapshot = {"themeColorMeta": "#111"}
    screenshot_payload = {"path": "capture.png", "mode": "viewport", "selector": None, "type": "png"}
    saved_payloads: list[tuple[str, object]] = []

    monkeypatch.setattr(MODULE, "capture_screenshot", lambda _page, _args: screenshot_payload)
    monkeypatch.setattr(MODULE, "collect_style_snapshot", lambda _page: style_snapshot)
    monkeypatch.setattr(MODULE, "save_json_file", lambda path, payload: saved_payloads.append((path, payload)) or path)

    result = MODULE.scrape_page(
        context,
        make_args(capture_style=True, style_snapshot_path=str(tmp_path / "style.json")),
    )

    assert result["url"] == "https://example.com"
    assert result["title"] == "Example Title"
    assert result["text"] == "Visible text from page"
    assert result["links"] == [{"text": "Home", "href": "https://example.com/home"}]
    assert result["screenshot"] == screenshot_payload
    assert result["style_snapshot"] == style_snapshot
    assert saved_payloads == [(str(tmp_path / "style.json"), style_snapshot)]
    assert page.closed is True


def test_main_outputs_json_and_closes_resources(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    browser = FakeBrowser()
    context = FakeContext([])

    class FakePlaywrightContextManager:
        def __enter__(self) -> object:
            return object()

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

    monkeypatch.setattr(MODULE, "load_local_env", lambda: None)
    monkeypatch.setattr(MODULE, "ensure_playwright_available", lambda: None)
    monkeypatch.setattr(MODULE, "load_playwright_runtime", lambda: (RuntimeError, lambda: FakePlaywrightContextManager()))
    monkeypatch.setattr(MODULE, "launch_browser", lambda playwright, args: (browser, context))
    monkeypatch.setattr(MODULE, "perform_login", lambda ctx, args: True)
    monkeypatch.setattr(
        MODULE,
        "scrape_page",
        lambda ctx, args: {
            "url": "https://example.com",
            "title": "Example Title",
            "selector": "body",
            "text": "Visible text",
            "text_truncated": False,
            "links": [],
            "screenshot": None,
            "style_snapshot": None,
            "style_snapshot_path": None,
        },
    )
    monkeypatch.setattr(sys, "argv", ["scrape.py", "https://example.com"])

    assert MODULE.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["authenticated"] is True
    assert browser.closed is True
    assert context.closed is True


def test_main_returns_error_for_runtime_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    browser = FakeBrowser()
    context = FakeContext([])

    class FakePlaywrightContextManager:
        def __enter__(self) -> object:
            return object()

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

    monkeypatch.setattr(MODULE, "load_local_env", lambda: None)
    monkeypatch.setattr(MODULE, "ensure_playwright_available", lambda: None)
    monkeypatch.setattr(MODULE, "load_playwright_runtime", lambda: (RuntimeError, lambda: FakePlaywrightContextManager()))
    monkeypatch.setattr(MODULE, "launch_browser", lambda playwright, args: (browser, context))
    monkeypatch.setattr(MODULE, "perform_login", lambda ctx, args: False)
    monkeypatch.setattr(MODULE, "scrape_page", lambda ctx, args: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(sys, "argv", ["scrape.py", "https://example.com"])

    assert MODULE.main() == 1
    assert "Error: boom" in capsys.readouterr().err
    assert browser.closed is True
    assert context.closed is True


def test_main_outputs_text_saves_storage_state_and_script_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    browser = FakeBrowser()
    context = FakeContext([])
    saved_storage_paths: list[str] = []

    class FakePlaywrightContextManager:
        def __enter__(self) -> object:
            return object()

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

    monkeypatch.setattr(MODULE, "load_local_env", lambda: None)
    monkeypatch.setattr(MODULE, "ensure_playwright_available", lambda: None)
    monkeypatch.setattr(MODULE, "load_playwright_runtime", lambda: (RuntimeError, lambda: FakePlaywrightContextManager()))
    monkeypatch.setattr(MODULE, "launch_browser", lambda playwright, args: (browser, context))
    monkeypatch.setattr(MODULE, "perform_login", lambda ctx, args: False)
    monkeypatch.setattr(
        MODULE,
        "scrape_page",
        lambda ctx, args: {
            "url": "https://example.com",
            "title": "Example Title",
            "selector": "body",
            "text": "Visible text",
            "text_truncated": False,
            "links": [],
            "screenshot": None,
            "style_snapshot": None,
            "style_snapshot_path": None,
        },
    )
    monkeypatch.setattr(MODULE, "save_storage_state", lambda ctx, path: saved_storage_paths.append(path))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scrape.py",
            "https://example.com",
            "--output",
            "text",
            "--save-storage-state",
            str(tmp_path / "state.json"),
        ],
    )

    assert MODULE.main() == 0
    assert saved_storage_paths == [str(tmp_path / "state.json")]
    assert capsys.readouterr().out.strip() == "Visible text"

    class RuntimeBrowser(FakeBrowser):
        def __init__(self) -> None:
            super().__init__()
            self.context = FakeContext([FakePage()])

        def new_context(self, **kwargs: object) -> FakeContext:
            return self.context

    class RuntimeBrowserType:
        def launch(self, *, headless: bool) -> RuntimeBrowser:
            return RuntimeBrowser()

    class RuntimePlaywrightManager:
        def __enter__(self) -> SimpleNamespace:
            return SimpleNamespace(chromium=RuntimeBrowserType())

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

    playwright_module = SimpleNamespace(Error=RuntimeError, sync_playwright=lambda: RuntimePlaywrightManager())
    monkeypatch.setattr(MODULE.importlib, "import_module", lambda _name: playwright_module)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), "https://example.com", "--output", "text", "--settle-ms", "0"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 0
    assert "Visible text" in capsys.readouterr().out

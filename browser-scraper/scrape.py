from __future__ import annotations

import argparse
from collections import Counter
import importlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

DEFAULT_TIMEOUT_MS = 30000
DEFAULT_MAX_CHARS = 12000
DEFAULT_MAX_LINKS = 30
DEFAULT_SELECTOR = "body"
DEFAULT_VIEWPORT_WIDTH = 1440
DEFAULT_VIEWPORT_HEIGHT = 900
DEFAULT_USERNAME_SELECTOR = 'input[name="email"], input[name="username"], input[type="email"], #email, #username'
DEFAULT_PASSWORD_SELECTOR = 'input[type="password"], input[name="password"], #password'
DEFAULT_SUBMIT_SELECTOR = 'button[type="submit"], input[type="submit"], button:has-text("Sign in"), button:has-text("Log in")'


def load_local_env() -> None:
    env_paths = [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]
    seen: set[Path] = set()
    for env_path in env_paths:
        if not env_path.exists() or env_path in seen:
            continue
        seen.add(env_path)
        load_dotenv(env_path, override=False)


def resolve_secret(value: str | None, env_name: str | None) -> str | None:
    if value:
        return value
    if env_name:
        return os.environ.get(env_name)
    return None


def truncate_text(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    return f"{value[:max_chars]}\n… [truncated {len(value) - max_chars} chars]", True


def ensure_playwright_available() -> None:
    try:
        importlib.import_module("playwright.sync_api")
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'playwright'. Install it from requirements.txt and run 'python -m playwright install chromium'."
        ) from exc


def load_playwright_runtime() -> tuple[type[Exception], Any]:
    module = importlib.import_module("playwright.sync_api")
    return module.Error, module.sync_playwright


def normalize_optional_mode(value: str) -> str | None:
    if value == "default":
        return None
    return value


def build_context_options(args: argparse.Namespace) -> dict[str, Any]:
    options: dict[str, Any] = {
        "viewport": {
            "width": args.viewport_width,
            "height": args.viewport_height,
        },
        "device_scale_factor": args.device_scale_factor,
    }
    color_scheme = normalize_optional_mode(args.color_scheme)
    if color_scheme is not None:
        options["color_scheme"] = color_scheme
    reduced_motion = normalize_optional_mode(args.reduced_motion)
    if reduced_motion is not None:
        options["reduced_motion"] = reduced_motion
    return options


def build_screenshot_style(args: argparse.Namespace) -> str | None:
    style_chunks: list[str] = []
    if args.screenshot_style:
        style_chunks.append(args.screenshot_style)
    if args.hide_selector:
        selector_list = ", ".join(args.hide_selector)
        style_chunks.append(f"{selector_list} {{ visibility: hidden !important; opacity: 0 !important; }}")
    if not style_chunks:
        return None
    return "\n".join(style_chunks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a page in a browser and extract visible text plus links.")
    parser.add_argument("url", help="Page URL to open and scrape.")
    parser.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium", help="Browser engine. Default: chromium.")
    parser.add_argument("--selector", default=DEFAULT_SELECTOR, help=f"CSS selector to extract text from. Default: {DEFAULT_SELECTOR}.")
    parser.add_argument("--wait-for", help="Optional CSS selector to wait for before extracting.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_MS, help=f"Timeout in milliseconds. Default: {DEFAULT_TIMEOUT_MS}.")
    parser.add_argument("--settle-ms", type=int, default=500, help="Extra wait time after navigation completes. Default: 500.")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS, help=f"Maximum text characters to print. Default: {DEFAULT_MAX_CHARS}.")
    parser.add_argument("--max-links", type=int, default=DEFAULT_MAX_LINKS, help=f"Maximum number of links to include. Default: {DEFAULT_MAX_LINKS}.")
    parser.add_argument("--viewport-width", type=int, default=DEFAULT_VIEWPORT_WIDTH, help=f"Viewport width in pixels. Default: {DEFAULT_VIEWPORT_WIDTH}.")
    parser.add_argument("--viewport-height", type=int, default=DEFAULT_VIEWPORT_HEIGHT, help=f"Viewport height in pixels. Default: {DEFAULT_VIEWPORT_HEIGHT}.")
    parser.add_argument("--device-scale-factor", type=float, default=1.0, help="Device scale factor for sharper captures. Default: 1.0.")
    parser.add_argument("--color-scheme", choices=("default", "light", "dark", "no-preference"), default="default", help="Optional color scheme emulation.")
    parser.add_argument("--reduced-motion", choices=("default", "reduce", "no-preference"), default="default", help="Optional reduced-motion emulation.")
    parser.add_argument("--output", choices=("json", "text"), default="json", help="Output format. Default: json.")
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window instead of headless mode.")
    parser.add_argument("--user-data-dir", help="Browser profile directory for persistent authenticated sessions.")
    parser.add_argument("--storage-state", help="Path to a Playwright storage state JSON file to preload.")
    parser.add_argument("--save-storage-state", help="Path where the resulting storage state JSON should be written.")
    parser.add_argument("--screenshot-path", help="Path where a screenshot should be written.")
    parser.add_argument("--screenshot-mode", choices=("viewport", "full-page", "element"), default="viewport", help="Screenshot capture mode. Default: viewport.")
    parser.add_argument("--screenshot-selector", help="Selector for element screenshots. Defaults to --selector when screenshot mode is element.")
    parser.add_argument("--screenshot-type", choices=("png", "jpeg"), default="png", help="Screenshot file type. Default: png.")
    parser.add_argument("--screenshot-quality", type=int, help="JPEG quality between 0 and 100.")
    parser.add_argument("--screenshot-scale", choices=("css", "device"), default="device", help="Screenshot scale mode. Default: device.")
    parser.add_argument("--screenshot-omit-background", action="store_true", help="Allow transparent background when supported by the screenshot type.")
    parser.add_argument("--disable-animations", action="store_true", help="Disable CSS and Web animations during screenshot capture.")
    parser.add_argument("--hide-selector", action="append", help="CSS selector to hide before taking the screenshot. Can be provided multiple times.")
    parser.add_argument("--screenshot-style", help="Extra CSS to inject only during screenshot capture.")
    parser.add_argument("--capture-style", action="store_true", help="Capture a style snapshot of colors, fonts, and CSS variables.")
    parser.add_argument("--style-snapshot-path", help="Optional path to save the extracted style snapshot JSON.")
    parser.add_argument("--login-url", help="Optional login page URL.")
    parser.add_argument("--seed-username", help="Seed/test username for browser login.")
    parser.add_argument("--seed-password", help="Seed/test password for browser login.")
    parser.add_argument("--seed-username-env", help="Environment variable that contains the seed username.")
    parser.add_argument("--seed-password-env", help="Environment variable that contains the seed password.")
    parser.add_argument("--login-username-selector", default=DEFAULT_USERNAME_SELECTOR, help="Selector for the login username field.")
    parser.add_argument("--login-password-selector", default=DEFAULT_PASSWORD_SELECTOR, help="Selector for the login password field.")
    parser.add_argument("--login-submit-selector", default=DEFAULT_SUBMIT_SELECTOR, help="Selector for the login submit button.")
    parser.add_argument("--post-login-wait-for", help="Selector that confirms login succeeded.")
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.max_chars < 1:
        parser.error("--max-chars must be at least 1.")
    if args.max_links < 0:
        parser.error("--max-links cannot be negative.")
    if args.viewport_width < 1 or args.viewport_height < 1:
        parser.error("Viewport dimensions must be at least 1 pixel.")
    if args.device_scale_factor <= 0:
        parser.error("--device-scale-factor must be greater than 0.")
    if args.user_data_dir and args.storage_state:
        parser.error("Use either --user-data-dir or --storage-state, not both.")
    if args.screenshot_mode == "element" and args.output == "text" and not args.screenshot_path:
        parser.error("Element screenshot mode is only useful when --screenshot-path or --output json is used.")
    if args.screenshot_quality is not None and (args.screenshot_quality < 0 or args.screenshot_quality > 100):
        parser.error("--screenshot-quality must be between 0 and 100.")
    if args.screenshot_quality is not None and args.screenshot_type != "jpeg":
        parser.error("--screenshot-quality can only be used with --screenshot-type jpeg.")
    if args.screenshot_mode != "element" and args.screenshot_selector:
        parser.error("--screenshot-selector can only be used when --screenshot-mode element.")


def launch_browser(playwright: Any, args: argparse.Namespace) -> tuple[Any | None, Any]:
    browser_type = getattr(playwright, args.browser)
    context_options = build_context_options(args)
    if args.user_data_dir:
        context = browser_type.launch_persistent_context(args.user_data_dir, headless=not args.headed, **context_options)
        return None, context

    browser = browser_type.launch(headless=not args.headed)
    context_kwargs = context_options
    if args.storage_state:
        context_kwargs["storage_state"] = args.storage_state
    context = browser.new_context(**context_kwargs)
    return browser, context


def wait_for_page_ready(page: Any, args: argparse.Namespace) -> None:
    page.wait_for_load_state("domcontentloaded", timeout=args.timeout)
    try:
        page.wait_for_load_state("networkidle", timeout=args.timeout)
    except Exception:
        pass
    if args.wait_for:
        page.wait_for_selector(args.wait_for, timeout=args.timeout)
    if args.settle_ms > 0:
        time.sleep(args.settle_ms / 1000)


def fill_visible_field(page: Any, selector: str, value: str, label: str, timeout: int) -> None:
    try:
        page.wait_for_selector(selector, state="visible", timeout=timeout)
    except Exception as exc:
        raise RuntimeError(f"Could not find a visible {label} field using selector: {selector}") from exc
    page.locator(selector).first.fill(value)


def perform_login(context: Any, args: argparse.Namespace) -> bool:
    if not args.login_url:
        return False

    username = resolve_secret(args.seed_username, args.seed_username_env)
    password = resolve_secret(args.seed_password, args.seed_password_env)
    if not username or not password:
        raise RuntimeError(
            "Browser login requires both a username and password. Provide them directly or via --seed-username-env/--seed-password-env."
        )

    page = context.new_page()
    page.goto(args.login_url, wait_until="domcontentloaded", timeout=args.timeout)
    fill_visible_field(page, args.login_username_selector, username, "username", args.timeout)
    fill_visible_field(page, args.login_password_selector, password, "password", args.timeout)
    page.locator(args.login_submit_selector).first.click()

    if args.post_login_wait_for:
        page.wait_for_selector(args.post_login_wait_for, timeout=args.timeout)
    else:
        wait_for_page_ready(page, args)

    if args.save_storage_state:
        save_storage_state(context, args.save_storage_state)

    page.close()
    return True


def save_storage_state(context: Any, target_path: str) -> None:
    destination = Path(target_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(destination))


def collect_links(page: Any, max_links: int) -> list[dict[str, str]]:
    link_items = page.eval_on_selector_all(
        "a[href]",
        """
        elements => elements.map(element => ({
            text: (element.innerText || '').trim(),
            href: element.href || ''
        }))
        """,
    )
    seen: set[str] = set()
    links: list[dict[str, str]] = []
    for item in link_items:
        href = item.get("href", "").strip()
        if not href or href in seen:
            continue
        seen.add(href)
        links.append({"text": item.get("text", "").strip(), "href": href})
        if len(links) == max_links:
            break
    return links


def collect_style_snapshot(page: Any) -> dict[str, Any]:
    style_data = page.evaluate(
        """
        () => {
            const normalize = value => (value || '').trim();
            const isVisible = element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
            };
            const collectTop = values => Object.entries(values)
                .sort((left, right) => right[1] - left[1])
                .slice(0, 10)
                .map(([value, count]) => ({ value, count }));
            const visibleElements = Array.from(document.querySelectorAll('body *')).filter(isVisible).slice(0, 200);
            const textColors = {};
            const backgroundColors = {};
            const fonts = {};
            const pushCount = (bucket, value) => {
                const normalized = normalize(value);
                if (!normalized || normalized === 'rgba(0, 0, 0, 0)' || normalized === 'transparent') {
                    return;
                }
                bucket[normalized] = (bucket[normalized] || 0) + 1;
            };

            for (const element of [document.body, ...visibleElements]) {
                const style = window.getComputedStyle(element);
                pushCount(textColors, style.color);
                pushCount(backgroundColors, style.backgroundColor);
                pushCount(fonts, style.fontFamily);
            }

            const rootStyle = window.getComputedStyle(document.documentElement);
            const rootVariables = [];
            for (const propertyName of Array.from(rootStyle)) {
                if (!propertyName.startsWith('--')) {
                    continue;
                }
                const propertyValue = normalize(rootStyle.getPropertyValue(propertyName));
                if (!propertyValue) {
                    continue;
                }
                rootVariables.push({ name: propertyName, value: propertyValue });
            }

            const sampleElements = selector => Array.from(document.querySelectorAll(selector))
                .filter(isVisible)
                .slice(0, 5)
                .map(element => {
                    const style = window.getComputedStyle(element);
                    return {
                        text: normalize(element.innerText || element.textContent || '').slice(0, 120),
                        fontFamily: normalize(style.fontFamily),
                        fontSize: normalize(style.fontSize),
                        fontWeight: normalize(style.fontWeight),
                        color: normalize(style.color),
                        backgroundColor: normalize(style.backgroundColor),
                    };
                });

            return {
                themeColorMeta: document.querySelector('meta[name="theme-color"]')?.getAttribute('content') || null,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight,
                    devicePixelRatio: window.devicePixelRatio,
                },
                body: {
                    fontFamily: normalize(window.getComputedStyle(document.body).fontFamily),
                    fontSize: normalize(window.getComputedStyle(document.body).fontSize),
                    color: normalize(window.getComputedStyle(document.body).color),
                    backgroundColor: normalize(window.getComputedStyle(document.body).backgroundColor),
                },
                topTextColors: collectTop(textColors),
                topBackgroundColors: collectTop(backgroundColors),
                topFonts: collectTop(fonts),
                rootCssVariables: rootVariables.slice(0, 50),
                headingSamples: sampleElements('h1, h2, h3'),
                buttonSamples: sampleElements('button, [role="button"], input[type="submit"], input[type="button"]'),
                linkSamples: sampleElements('a[href]'),
            };
        }
        """
    )
    return style_data


def save_json_file(target_path: str, payload: Any) -> str:
    destination = Path(target_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(destination)


def capture_screenshot(page: Any, args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.screenshot_path:
        return None

    destination = Path(args.screenshot_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    screenshot_options: dict[str, Any] = {
        "path": str(destination),
        "type": args.screenshot_type,
        "timeout": args.timeout,
        "scale": args.screenshot_scale,
        "animations": "disabled" if args.disable_animations else "allow",
        "caret": "hide",
    }
    if args.screenshot_quality is not None:
        screenshot_options["quality"] = args.screenshot_quality
    if args.screenshot_omit_background:
        screenshot_options["omitBackground"] = True

    screenshot_style = build_screenshot_style(args)
    if screenshot_style:
        screenshot_options["style"] = screenshot_style

    if args.screenshot_mode == "element":
        selector = args.screenshot_selector or args.selector
        page.locator(selector).first.screenshot(**screenshot_options)
        return {
            "path": str(destination),
            "mode": args.screenshot_mode,
            "selector": selector,
            "type": args.screenshot_type,
        }

    screenshot_options["fullPage"] = args.screenshot_mode == "full-page"
    page.screenshot(**screenshot_options)
    return {
        "path": str(destination),
        "mode": args.screenshot_mode,
        "selector": None,
        "type": args.screenshot_type,
    }


def scrape_page(context: Any, args: argparse.Namespace) -> dict[str, Any]:
    page = context.new_page()
    page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)
    wait_for_page_ready(page, args)
    page.wait_for_selector(args.selector, state="visible", timeout=args.timeout)
    text_content = page.locator(args.selector).first.inner_text(timeout=args.timeout)
    preview, truncated = truncate_text(text_content, args.max_chars)
    screenshot = capture_screenshot(page, args)
    style_snapshot = collect_style_snapshot(page) if args.capture_style or args.style_snapshot_path else None
    saved_style_snapshot_path = save_json_file(args.style_snapshot_path, style_snapshot) if args.style_snapshot_path and style_snapshot else None
    result = {
        "url": page.url,
        "title": page.title(),
        "selector": args.selector,
        "text": preview,
        "text_truncated": truncated,
        "links": collect_links(page, args.max_links),
        "screenshot": screenshot,
        "style_snapshot": style_snapshot,
        "style_snapshot_path": saved_style_snapshot_path,
    }
    page.close()
    return result


def main() -> int:
    load_local_env()
    ensure_playwright_available()
    parser = build_parser()
    args = parser.parse_args()
    validate_args(args, parser)

    browser: Any = None
    context: Any = None
    playwright_error: type[Exception] = Exception

    try:
        playwright_error, sync_playwright = load_playwright_runtime()
        with sync_playwright() as playwright:
            browser, context = launch_browser(playwright, args)
            authenticated = perform_login(context, args)
            result = scrape_page(context, args)
            if args.save_storage_state and not args.login_url:
                save_storage_state(context, args.save_storage_state)
    except (RuntimeError, playwright_error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if context is not None:
            context.close()
        if browser is not None:
            browser.close()

    if args.output == "text":
        print(result["text"])
        return 0

    payload = {
        "authenticated": authenticated,
        "user_data_dir_used": bool(args.user_data_dir),
        "storage_state_used": bool(args.storage_state),
        **result,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

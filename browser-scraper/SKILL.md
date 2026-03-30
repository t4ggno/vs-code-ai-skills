---
name: browser-scraper
description: Renders JavaScript-heavy pages in a real browser, reuses authenticated sessions, and captures screenshots or style snapshots. Use when static fetch tools are insufficient for SPAs, login-protected flows, or visual UI inspection. Do not use it for static pages that can be fetched directly.
argument-hint: <url> [what to extract, auth mode, selectors, screenshot needs]
---

# Browser Scraper

1. Use this skill only when the page needs a real browser runtime, existing session state, an interactive login flow, or a screenshot/style capture.
2. Execute the local script [scrape.py](./scrape.py) instead of improvising ad-hoc browser automation.
3. Pick the lightest authentication option that works:
	 - `--user-data-dir` to reuse an existing logged-in browser profile.
	 - `--storage-state` to reuse a saved Playwright auth state.
	 - `--login-url` with seeded credentials to perform a safe test login.
4. Scope extraction tightly:
	 - Use `--selector` to focus on the relevant container.
	 - Use `--wait-for` or `--post-login-wait-for` to wait for a reliable ready signal.
	 - Use `--max-chars` and `--max-links` to keep output compact.
5. If the task is visual or UX-oriented, capture the page deliberately:
	 - Use `--screenshot-path` with `--screenshot-mode viewport|full-page|element`.
	 - Use `--capture-style` or `--style-snapshot-path` when the goal is design analysis.
	 - Use `--hide-selector` or `--screenshot-style` to suppress banners or overlays.
6. Save durable login state with `--save-storage-state` only when the same flow will be reused.
7. Never store or repeat secrets in chat. Store only reusable non-secret details such as selectors, login success conditions, or storage-state file paths.

## Common invocations

- Render a dashboard after hydration:
	`python ./scrape.py https://example.com/dashboard --wait-for "[data-ready='true']"`
- Capture a visual style snapshot plus screenshot:
	`python ./scrape.py https://example.com --capture-style --style-snapshot-path .artifacts/style.json --screenshot-path .artifacts/homepage.png --screenshot-mode full-page`
- Reuse a logged-in browser profile:
	`python ./scrape.py https://example.com/account --user-data-dir "<browser-profile-dir>"`
- Login with a seeded user and persist auth state:
	`python ./scrape.py https://example.com/admin --login-url https://example.com/login --seed-username seeded-admin@example.com --seed-password <seed-password> --post-login-wait-for "nav" --save-storage-state .auth/seed-admin.json`

## Guardrails

- Prefer this skill over raw HTTP fetching only when browser execution is truly needed.
- Prefer seeded/test users over real credentials.
- Treat screenshots, storage-state files, and extracted text as potentially sensitive artifacts.
- Install Playwright once in the active environment before first use: `python -m playwright install chromium`.

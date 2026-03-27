---
name: browser-scraper
description: Loads JavaScript-heavy pages in a real browser, supports profile or seeded-login authentication, captures screenshots, and extracts visual-style signals for design and UX work.
---

# Browser Scraper Skill

Use this skill when a normal HTTP fetch is not enough because the page needs JavaScript, a browser session, an interactive login, or a visual capture of the current UI.

It is especially useful for:

- Scraping SPAs and dashboards that render client-side.
- Reusing an existing logged-in browser profile.
- Logging in with a seeded user and then extracting authenticated page content.
- Saving a browser storage state for later authenticated runs.
- Capturing full-page, viewport, or element screenshots.
- Extracting style fingerprints such as colors, fonts, CSS variables, and sample UI elements.
- Understanding the current visual language of a website before redesigning it.

## Authentication guidance

Prefer one of these lean options:

- `--user-data-dir`: Reuse an existing browser profile when you are already logged in.
- `--storage-state`: Reuse a previously saved Playwright auth state.
- `--login-url` with seeded credentials: Perform a login flow using a seed/test account, then save the resulting state with `--save-storage-state` if needed.

When the authentication flow is discovered and likely to be reused, store only the durable non-secret details in memory, such as selectors, the success condition, and the storage-state file path. Never store passwords, tokens, cookies, or storage-state contents.

## Setup

Install the dependencies from `requirements.txt`, then install the browser runtime once:

```bash
python -m playwright install chromium
```

## Usage

Scrape a page after JavaScript finishes rendering:

```bash
python c:/Users/ehrha/.copilot/skills/browser-scraper/scrape.py https://example.com/dashboard --wait-for "[data-ready='true']"
```

### Capture the current visual style and save a screenshot

```bash
python c:/Users/ehrha/.copilot/skills/browser-scraper/scrape.py https://example.com --capture-style --screenshot-path .artifacts/example-homepage.png --screenshot-mode full-page --viewport-width 1440 --viewport-height 900 --hide-selector ".cookie-banner"
```

### Capture a specific element for design analysis

```bash
python c:/Users/ehrha/.copilot/skills/browser-scraper/scrape.py https://example.com/pricing --selector "main" --screenshot-path .artifacts/pricing-card.png --screenshot-mode element --screenshot-selector ".pricing-card.featured" --capture-style
```

### Reuse an existing browser profile

```bash
python c:/Users/ehrha/.copilot/skills/browser-scraper/scrape.py https://example.com/account --user-data-dir "C:/Users/ehrha/AppData/Local/Microsoft/Edge/User Data"
```

### Login with a seeded user and save state

```bash
python c:/Users/ehrha/.copilot/skills/browser-scraper/scrape.py https://example.com/admin --login-url https://example.com/login --seed-username seeded-admin@example.com --seed-password Passw0rd! --post-login-wait-for "nav" --save-storage-state .auth/seed-admin.json
```

### Login, capture the dashboard style, and save the style snapshot JSON

```bash
python c:/Users/ehrha/.copilot/skills/browser-scraper/scrape.py https://example.com/admin --login-url https://example.com/login --seed-username seeded-admin@example.com --seed-password Passw0rd! --post-login-wait-for "nav" --capture-style --style-snapshot-path .artifacts/admin-style.json --screenshot-path .artifacts/admin-dashboard.png --screenshot-mode viewport
```

## Notes

- The scraper extracts visible text, not raw HTML by default.
- Use `--selector` to focus extraction on a specific panel or container.
- The output can include page title, final URL, visible text, a capped link list, a screenshot path, and a style snapshot.
- Screenshot capture is based on Playwright's screenshot support and can capture full pages, viewports, or single elements.
- Use `--color-scheme dark` or `--reduced-motion reduce` when you need to simulate a specific presentation mode.
- Use `--hide-selector` or `--screenshot-style` to hide cookie banners, chat widgets, or noisy overlays during design capture.
- For sensitive apps, prefer seeded users or local browser profiles over hard-coded real credentials.

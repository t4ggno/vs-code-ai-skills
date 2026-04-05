# VS Code AI Skills

A curated collection of Python-backed AI skills and helper scripts for GitHub Copilot in VS Code. This repository is intentionally structured like a real personal skills directory, so it works both as:

- a ready-to-use `~/.copilot/skills` folder,
- a reference implementation for authoring new skills, and
- a small, testable Python codebase for validating skill helper scripts.

## What this repository contains

The repo currently includes:

- **14 self-contained skill folders** covering browser automation, image generation, image conversion, image effects, video conversion, math, maps, PDF extraction, API calls, SQL inspection, system diagnostics, UUID generation, and more
- **One `SKILL.md` file per skill** with routing metadata and task-specific instructions
- **One Python helper script per skill** that performs the actual work locally
- **One pytest spec per helper script** so each skill can be validated independently
- **Shared root configuration** for dependency installation and test discovery
- **Optional local `.env` support** for skills that need API keys, tokens, or other environment-specific settings

In short: this is not just a list of markdown prompts. It is a practical, runnable skills workspace.

## What are VS Code Agent Skills?

Agent Skills are localized folders containing instructions, scripts, and resources that GitHub Copilot can dynamically load to perform specialized tasks. They follow an open skill format and can be used across skills-compatible agents such as GitHub Copilot in VS Code, the GitHub Copilot CLI, and the Copilot coding agent.

Unlike general custom instructions—which define broad coding preferences or repository rules—skills are designed for **specific, repeatable workflows**. When a user request matches a skill, the agent can load only that skill's instructions and use its helper script without dragging unrelated context into the session.

### Why this repo is useful

- **Concrete examples:** each folder shows a complete skill, not just theory
- **Reusable patterns:** frontmatter, step-based instructions, examples, and guardrails are consistent across skills
- **Runnable helpers:** the Python scripts turn a skill into something operational instead of purely descriptive
- **Test coverage:** every skill has a matching `*.spec.py` file for local verification
- **Portable layout:** the structure mirrors how personal skills are actually organized on disk

## Skill locations

Depending on scope, skills can live in one of two common locations:

1. **Personal skills (global)**  
   Available across all repositories for the current user.  
   **Windows default:** `C:\Users\<USERNAME>\.copilot\skills`  
   **macOS/Linux default:** `~/.copilot/skills`
2. **Project skills (local)**  
   Tracked inside a specific repository and only available in that project.  
   **Typical location:** `.github/skills`

This repository models the **personal skills** layout.

## Repository layout

Every skill in this repo follows the same shape:

- `SKILL.md` — frontmatter plus usage instructions, examples, and guardrails
- `<script>.py` — the local helper used to carry out the skill's concrete work
- `<script>.spec.py` — pytest coverage for the helper script

At the root, the repo includes:

- `README.md` — repository documentation
- `requirements.txt` — shared Python dependencies for the skill helpers
- `pytest.ini` — pytest discovery configuration (`*.spec.py`) and `importlib` import mode
- `conftest.py` — shared test helper for loading modules from skill folders
- `.env` — optional local environment variables for live runs

### Current structure

```text
.copilot/skills/
├── README.md
├── requirements.txt
├── pytest.ini
├── conftest.py
├── .env
├── browser-scraper/
│   ├── SKILL.md
│   ├── scrape.py
│   └── scrape.spec.py
├── continuous-task/
│   ├── SKILL.md
│   ├── continuous_agent.py
│   └── continuous_agent.spec.py
├── image-effects/
│   ├── SKILL.md
│   ├── effects.py
│   └── effects.spec.py
├── image-generator/
│   ├── SKILL.md
│   ├── generate.py
│   └── generate.spec.py
├── math-calculator/
│   ├── SKILL.md
│   ├── calculate.py
│   └── calculate.spec.py
├── media-converter-image/
│   ├── SKILL.md
│   ├── convert.py
│   └── convert.spec.py
├── media-converter-video/
│   ├── SKILL.md
│   ├── convert.py
│   └── convert.spec.py
├── openstreetmap/
│   ├── SKILL.md
│   ├── query.py
│   └── query.spec.py
├── pdf-text-extractor/
│   ├── SKILL.md
│   ├── extract.py
│   └── extract.spec.py
├── random-generator/
│   ├── SKILL.md
│   ├── generate.py
│   └── generate.spec.py
├── rest-api-client/
│   ├── SKILL.md
│   ├── call_api.py
│   └── call_api.spec.py
├── sql-query-runner/
│   ├── SKILL.md
│   ├── query.py
│   └── query.spec.py
├── system-info/
│   ├── SKILL.md
│   ├── info.py
│   └── info.spec.py
└── uuid-generator/
    ├── SKILL.md
    ├── generate.py
    └── generate.spec.py
```

## Included skills

| Skill                   | Main script           | What it covers                                                       | Notable capabilities in this repo                                                                         |
| ----------------------- | --------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `browser-scraper`       | `scrape.py`           | Browser-powered scraping for JavaScript-heavy or authenticated pages | Playwright runtime, auth reuse, screenshots, style snapshots                                              |
| `continuous-task`       | `continuous_agent.py` | Fallback wrapper for exhaustive or continuous agent workflows        | Long-running loop support, transcript tail recovery, CLI fallback guidance                                |
| `image-effects`         | `effects.py`          | Local image cleanup and effect pipelines                             | Background removal, transparent-edge trimming, blur, sharpen, color adjustments                           |
| `image-generator`       | `generate.py`         | New image and seamless texture generation                            | OpenAI image generation, tileable mode, built-in vision evaluation                                        |
| `math-calculator`       | `calculate.py`        | Precise numeric evaluation                                           | Python `math`-based expressions for reliable arithmetic and trig                                          |
| `media-converter-image` | `convert.py`          | Common raster/icon image conversions                                 | PNG/JPEG/WEBP/AVIF/TIFF/BMP/ICO/ICNS conversions, animation-preserving output, optional SVG rasterization |
| `media-converter-video` | `convert.py`          | Local video and animated preview conversion                          | MP4/WEBM/MOV/MKV/AVI conversion plus GIF/APNG export using bundled FFmpeg                                 |
| `openstreetmap`         | `query.py`            | Structured map and location queries                                  | Nominatim search/reverse/verify plus Overpass nearby and raw queries                                      |
| `pdf-text-extractor`    | `extract.py`          | Text extraction from text-based PDFs                                 | Page-range extraction and optional JSON output                                                            |
| `random-generator`      | `generate.py`         | Sample and deterministic mock data                                   | Strings, numbers, booleans, regex generation, Faker providers, seeding                                    |
| `rest-api-client`       | `call_api.py`         | Real HTTP API verification                                           | Structured headers/body support, seeded login flow, bearer token env auth                                 |
| `sql-query-runner`      | `query.py`            | Compact SQL inspection against live databases                        | SQLite and DSN support, named params, read-only-by-default safety                                         |
| `system-info`           | `info.py`             | Local machine and interpreter inspection                             | OS, CPU, memory, and Python environment details                                                           |
| `uuid-generator`        | `generate.py`         | Standard UUID/GUID generation                                        | Batch output, JSON output, deterministic namespace-based variants                                         |

## Shared authoring patterns across the repo

If you are browsing this repository to build your own skills, a few conventions are used consistently:

- **Frontmatter-driven routing:** each `SKILL.md` starts with metadata such as `name`, `description`, and `argument-hint`
- **Clear positive and negative triggers:** the descriptions explain both when to use a skill and when not to use it
- **Relative script paths:** examples reference helpers with paths like `./generate.py` instead of machine-specific absolute paths
- **Step-based instructions:** skill bodies are intentionally structured as procedure, examples, and guardrails
- **Secrets stay out of chat:** environment variables and `.env` usage are preferred over inline tokens or credentials
- **One skill, one responsibility:** each folder is focused on a narrow capability rather than becoming a kitchen-sink tool

## Python, dependencies, and testing

All helper scripts in this repository are Python-based.

### Shared dependencies

The current `requirements.txt` includes:

- `openai`
- `requests`
- `Pillow`
- `PyPDF2`
- `python-dotenv`
- `Faker`
- `rstr`
- `imageio-ffmpeg`
- `playwright`
- `rembg[cpu]` (for Python `< 3.14`)
- `SQLAlchemy`
- `pytest`

### Test setup

Pytest is configured at the root with:

- `python_files = *.spec.py` so skill-specific spec files are discovered correctly
- `addopts = --import-mode=importlib` so dotted filenames and folder-based loading work cleanly

The shared `conftest.py` exposes a module loader that imports skill scripts directly from their folders, which keeps tests simple and avoids awkward path hacks.

### Notes for specific skills

- `browser-scraper` depends on Playwright and typically needs a one-time browser install such as Chromium
- `image-effects` uses `rembg` for local background removal and is most reliable on Python 3.12/3.11 today because of `onnxruntime` wheel availability
- `image-generator` expects `OPENAI_API_KEY` to be available for live image generation
- `media-converter-image` supports common raster/icon conversions out of the box and can optionally rasterize SVG input if CairoSVG is installed separately
- `media-converter-video` uses `imageio-ffmpeg` to locate a local FFmpeg binary without requiring a separate system-wide install on most platforms
- `openstreetmap` supports optional environment variables such as custom Nominatim or Overpass endpoints and a custom `User-Agent`
- `rest-api-client` is designed to keep auth tokens and credentials in environment variables instead of chat history

## How to install and use

### Use the whole repo as your personal skills directory

1. Clone or download this repository.
2. Place the contents directly into your global skills directory:
   `C:\Users\<USERNAME>\.copilot\skills`
3. Install the Python dependencies from `requirements.txt`.
4. If needed, add local environment variables in `.env` for skills that require secrets.
5. Reload or restart GitHub Copilot in VS Code.
6. Ask for a task that matches one of the skill domains and Copilot can route to the relevant skill automatically.

### Use only selected skills

You do not need to adopt the entire repository. You can copy a single folder such as `openstreetmap/` or `random-generator/` into your personal skills directory or adapt it into a project-local `.github/skills` folder.

## Example user prompts that map well to this repo

- _"Capture a full-page screenshot of this authenticated dashboard and summarize the visible data."_
- _"Generate a seamless basalt floor texture for a game prototype."_
- _"Convert this PNG logo to a multi-size ICO for a Windows app."_
- _"Convert this MP4 clip to a short GIF preview for chat."_
- _"Remove the background from this product image and trim the empty edges."_
- _"Evaluate this trig expression exactly instead of estimating it."_
- _"Reverse geocode these coordinates and list nearby cafes."_
- _"Extract pages 5 through 12 from this PDF and summarize them."_
- _"Generate 20 deterministic fake customer emails for test fixtures."_
- _"Call this API with a bearer token from the environment and show me the response."_
- _"Run a read-only SQL query against a SQLite file and return JSON."_
- _"Show me my local OS, CPU, memory, and Python environment details."_
- _"Generate a batch of UUIDv5 values for seeded records."_

## Extending the repository

If you add a new skill, the existing folders provide a good template:

1. Create a new skill directory.
2. Add a `SKILL.md` file with routing metadata and clear usage guidance.
3. Add a Python helper script for the concrete task.
4. Add a matching `*.spec.py` test.
5. Add any new dependencies only if the capability truly needs them.

That pattern keeps the repo tidy, testable, and easy for both humans and agents to navigate.

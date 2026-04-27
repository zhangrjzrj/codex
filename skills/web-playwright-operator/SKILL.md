---
name: web-playwright-operator
description: Use this when the user wants Codex to automatically operate Chrome/Chromium on a website (open URL, read text and images via screenshots/downloads, and click/type) using Python Playwright, including a login-first flow for sites with captcha.
---

# Web Playwright Operator

## What this skill is for

When the user gives a URL and asks you to **read page content (including images)** and **click buttons / fill forms** to complete a task automatically.

This skill uses **Python + Playwright (Chromium)** via bundled scripts.

## Guardrails

- If the site shows a **captcha / SMS / human verification**, do **not** attempt to bypass it.
- Use the **login-once** flow: run headful once, user completes verification, save `storage_state`, then run headless for automation.
- Prefer stable selectors:
  - `get_by_role(...)` with accessible name first
  - then `text=...`
  - CSS as last resort

## Quick start (environment)

Run these once on the machine:

```powershell
python -m pip install -r skills/web-playwright-operator/requirements.txt
python -m playwright install chromium
```

## Workflow

1) Convert the user’s natural language request into a small step list (URL + actions).
2) If login/captcha is involved:
   - Ask for login URL, run `login_once.py` headful, have user finish verification, save `auth_state.json`.
3) Run `run_steps.py` headless with:
   - the steps JSON
   - optional `--state auth_state.json`
4) Read artifacts:
   - screenshots in `out/`
   - downloaded images in `out/`
   - extracted text in `out/result.json`
5) If something fails, iterate:
   - tighten selectors
   - add waits (`wait_for_load_state`, `wait_for_selector`)
   - add a screenshot right before the failing step

## Step format (JSON)

Create a JSON file like:

```json
{
  "url": "https://www.wikipedia.org/",
  "steps": [
    {"type": "screenshot", "path": "home.png", "full_page": true},
    {"type": "click_role", "role": "link", "name": "English"},
    {"type": "wait_network_idle"},
    {"type": "extract_text", "name": "h1", "selector": "h1"},
    {"type": "download_img", "name": "logo", "selector": "img.mw-wiki-logo"}
  ]
}
```

Supported step `type` values are implemented in `scripts/run_steps.py`.

## Commands

### Login once (headful, manual verification)

```powershell
python skills/web-playwright-operator/scripts/login_once.py --url "https://example.com/login" --state auth_state.json
```

### Login once (headful, no-stdin environments)

If the terminal can't accept `input()` (common in automation), use a signal file:

```powershell
python skills/web-playwright-operator/scripts/login_once.py --url "https://example.com/login" --state auth_state.json --save-signal save.signal
# After you finish login in the browser window, create save.signal (empty file is fine).
```

### Run automation (headless)

```powershell
python skills/web-playwright-operator/scripts/run_steps.py --spec steps.json --out skills/web-playwright-operator/out --state auth_state.json --headless
```

If no login is needed, omit `--state`.

### Run automation (headful / normal browser)

```powershell
python skills/web-playwright-operator/scripts/run_steps.py --spec steps.json --out skills/web-playwright-operator/out --headful
```

### Open and hold (headful)

Keeps the browser open until you create `close.signal`:

```powershell
python skills/web-playwright-operator/scripts/open_hold.py --url "https://example.com" --state auth_state.json --close-signal close.signal
```

## Examples

- `skills/web-playwright-operator/examples/wikipedia_en_logo.json`
- `skills/web-playwright-operator/examples/baidu_search_github.json`

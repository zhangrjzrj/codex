---
name: "web-browser-session"
description: "Operate a live Chromium browser session through CDP/Playwright when Codex needs to understand JavaScript-rendered pages, preserve login state, inspect tabs, extract runtime DOM semantics, read page text/HTML, and perform browser actions such as navigate, click, fill, press, or switch tabs. Use for internal docs, web apps, multi-tab browsing, login-first flows, and DOM-first page understanding where screenshots should be a fallback rather than the primary input."
---

# Web Browser Session

## Purpose

Use this skill to keep a browser open, attach to it repeatedly, understand the current JavaScript-rendered DOM, and operate the page from structured semantic snapshots.

Prefer this skill over one-shot browser automation when the task requires login persistence, multi-step browsing, multi-tab inspection, or iterative page understanding.

## Core Workflow

1. Open or attach to a session.
   - Start with `scripts/open_session.py` unless a compatible CDP browser is already running.
   - Use a persistent profile for login-heavy sites.
2. Inspect the page.
   - Use `scripts/list_tabs.py` to see open tabs.
   - Use `scripts/snapshot_page.py` to get `url`, `title`, visible text, dialogs/loading hints, clickables, and inputs.
3. Decide from the JSON snapshot.
   - Choose actions by `id` where possible.
   - Use text-based action only when the target is unambiguous.
4. Act and re-snapshot.
   - Use `scripts/act.py` for `goto`, `activate_tab`, `click`, `fill`, and `press`.
   - Re-run `snapshot_page.py` after every meaningful action.
5. Read content.
   - Use `scripts/read_page.py` for page text and optional HTML.
   - Use screenshots only when DOM text is empty, canvas/PDF/image content is involved, or visual layout must be verified.

## Login-Heavy Sites

For sites with Google OAuth, captcha, SSO, or strict browser checks, prefer launching normal Chrome with a dedicated profile and a CDP port instead of Chrome for Testing:

```powershell
Start-Process -FilePath "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList @("--remote-debugging-port=9222", "--user-data-dir=D:\hanhan\chrome-figma-profile", "https://www.figma.com/files/") -WindowStyle Normal
```

Then ask the user to complete login in that visible Chrome window. After login, attach with the regular `--port 9222` scripts. This preserves login state and avoids OAuth popup failures that can happen in automation-first browsers.

## Commands

Open a persistent browser session:

```powershell
python C:\Users\zhangruojun\.codex\skills\web-browser-session\scripts\open_session.py --url "https://example.com" --port 9222
```

List tabs:

```powershell
python C:\Users\zhangruojun\.codex\skills\web-browser-session\scripts\list_tabs.py --port 9222
```

Snapshot the active tab:

```powershell
python C:\Users\zhangruojun\.codex\skills\web-browser-session\scripts\snapshot_page.py --port 9222 --out snapshot.json
```

Click by snapshot id:

```powershell
python C:\Users\zhangruojun\.codex\skills\web-browser-session\scripts\act.py --port 9222 --action click --id 12
```

Fill an input by snapshot id:

```powershell
python C:\Users\zhangruojun\.codex\skills\web-browser-session\scripts\act.py --port 9222 --action fill --id 3 --text "nearfar"
```

Read page text:

```powershell
python C:\Users\zhangruojun\.codex\skills\web-browser-session\scripts\read_page.py --port 9222 --out page.json
```

## Output Contract

Scripts print the output JSON path or JSON object. Treat JSON as the source of truth for decisions.

Important snapshot fields:

- `page`: `url`, `title`, `body_text_head`, login/loading hints.
- `tabs`: known open tabs when available.
- `clickables`: visible buttons, links, menu items, clickable cards, and pointer-style elements.
- `inputs`: visible input, textarea, select, and contenteditable elements.
- `dialogs`: visible dialog/modal-like containers.

Each actionable element has a stable per-snapshot `id`. Re-snapshot after navigation or major DOM changes because ids are regenerated.

## Guardrails

- Do not bypass captcha, SMS, SSO, or hardware-token verification. Keep the browser open and ask the user to complete verification.
- Prefer DOM/HTML extraction first. Use screenshots only as a fallback.
- Do not assume initial HTML represents the page; inspect the runtime DOM after JavaScript has executed.
- For repeated text targets, click/fill by snapshot `id`, not text.
- If an action fails because the page changed, re-run `snapshot_page.py` and choose again.

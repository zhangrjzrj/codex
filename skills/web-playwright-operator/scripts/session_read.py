from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / 'session_state.json'
OUT_DIR = BASE_DIR / 'out' / 'session'


def main() -> int:
    if not STATE_PATH.exists():
        raise SystemExit(f'session state not found: {STATE_PATH}')

    state = json.loads(STATE_PATH.read_text(encoding='utf-8'))
    port = int(state.get('port', 9223))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shot = OUT_DIR / 'current.png'
    text_out = OUT_DIR / 'current.txt'
    json_out = OUT_DIR / 'current.json'

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
        pages = [pg for c in browser.contexts for pg in c.pages]
        if not pages:
            raise SystemExit('no pages in current session')

        page = pages[-1]
        page.wait_for_timeout(500)

        info = {
            'title': page.title(),
            'url': page.url,
            'screenshot': str(shot),
            'text_file': str(text_out),
        }

        body_text = page.locator('body').inner_text(timeout=5000)
        page.screenshot(path=str(shot), full_page=True)
        text_out.write_text(body_text, encoding='utf-8')
        json_out.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(info, ensure_ascii=False))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
